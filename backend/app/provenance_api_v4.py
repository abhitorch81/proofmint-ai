"""Isolated Phase-4 endpoints; existing payment and license routes unchanged."""
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session
import cv2
from .db import get_db
from .models import Moment, VideoAsset
from .config import get_settings
from .provenance_v4 import safe_decode, akaze_evidence, embed_frame, verify_frame_watermark

router = APIRouter(prefix='/api/moments', tags=['Phase 4 provenance'])


def _source(moment_id: str, db: Session):
    moment = db.get(Moment, moment_id)
    if moment is None: raise HTTPException(404, 'Moment not found')
    # Use saved source-video keyframe for comparison; provenance still needs rights review.
    path = Path(get_settings().upload_dir) / f'{moment_id}.jpg'
    if not path.is_file(): raise HTTPException(404, 'Source keyframe unavailable')
    frame = cv2.imread(str(path))
    if frame is None: raise HTTPException(500, 'Source keyframe corrupted')
    return moment, frame


async def _read_image(file: UploadFile):
    if file.content_type and not file.content_type.startswith('image/'):
        raise HTTPException(415, 'Please upload an image file')
    data = await file.read(8*1024*1024+1)
    await file.close()
    try: return safe_decode(data)
    except ValueError as ex: raise HTTPException(422, str(ex)) from ex


@router.post('/{moment_id}/verify-akaze')
async def verify_akaze(moment_id: str, file: UploadFile=File(...), db: Session=Depends(get_db)):
    moment, original = _source(moment_id, db)
    candidate = await _read_image(file)
    report = akaze_evidence(original, candidate)
    return {'moment_id':moment.id, 'analysis_version':moment.analysis_version, **report}


@router.get('/{moment_id}/marked-frame')
def marked_frame(moment_id: str, db:Session=Depends(get_db)):
    moment, original = _source(moment_id, db)
    if not db.get(VideoAsset,moment.video_id).rights_asserted:
        raise HTTPException(403,'Creator rights assertion required')
    try:
        raw, _ = embed_frame(original, get_settings().receipt_signing_secret,moment.id)
    except ValueError as ex: raise HTTPException(503,str(ex)) from ex
    return Response(content=raw,media_type='image/png',headers={'Content-Disposition':f'attachment; filename="marked-{moment.id}.png"', 'Cache-Control':'no-store'})


@router.post('/{moment_id}/verify-watermark')
async def verify_watermark(moment_id: str, file: UploadFile=File(...), db:Session=Depends(get_db)):
    moment, _ = _source(moment_id, db)
    candidate=await _read_image(file)
    try: return verify_frame_watermark(candidate,get_settings().receipt_signing_secret,moment.id)
    except ValueError as ex: raise HTTPException(503,str(ex)) from ex
