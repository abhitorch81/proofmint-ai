"""Moment ingestion/search/provenance endpoints, and PayPal micro-licensing entrypoint."""
from pathlib import Path
from uuid import uuid4
import hashlib
import re
import shutil
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Header
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .config import get_settings
from .models import VideoAsset, Moment
from .moment_engine import inspect_video, dhash, hamming
from .momentweave_adapter import apply_export
from .semantic_search import score_documents
import cv2
import numpy as np

router=APIRouter(prefix='/api', tags=['MomentGraph'])


def moment_out(m):
    return {'id':m.id,'video_id':m.video_id,'title':m.title,'description':m.description,
            'start_ms':m.start_ms,'end_ms':m.end_ms,'emotion':m.emotion,
            'narrative_role':m.narrative_role,'motion_score':m.motion_score,
            'price_cents':m.price_cents,'license_text':m.license_text,
            'analysis_version':m.analysis_version,
            'thumbnail_url':f'/api/moments/{m.id}/thumbnail'}


def video_out(v):
    return {'id':v.id,'title':v.title,'creator':v.creator,'duration_seconds':v.duration_seconds,
            'source_sha256':v.source_sha256,'rights_asserted':v.rights_asserted,'status':v.status,
            'preview_url':f'/api/videos/{v.id}/file'}

@router.post('/videos', status_code=201)
async def video_upload(file:UploadFile=File(...), momentweave_json:UploadFile|None=File(None), title:str=Form(...), creator:str=Form(...),
                       rights_asserted:bool=Form(False), price_cents:int=Form(499),
                       db:Session=Depends(get_db), x_demo_upload_token:str|None=Header(None)):
    if not 2 <= len(title.strip()) <= 150 or not 2 <= len(creator.strip()) <= 150:
        raise HTTPException(422,'Title and creator must contain 2-150 characters')
    if not rights_asserted:
        raise HTTPException(422,'Creator must assert rights to license this video')
    if not 100 <= price_cents <= 1000000:
        raise HTTPException(422,'Price must be between 100 and 1,000,000 cents')
    if Path(file.filename or '').suffix.lower() not in ('.mp4','.mov','.webm','.mkv'):
        raise HTTPException(415,'Supported video extensions: mp4, mov, webm, mkv')
    settings=get_settings()
    if settings.app_env.lower() == 'production':
        if not settings.demo_upload_token or x_demo_upload_token != settings.demo_upload_token:
            raise HTTPException(403, 'Valid private demo upload token required')
    base=Path(settings.upload_dir); base.mkdir(parents=True,exist_ok=True)
    vid=str(uuid4())
    path=base/f'{vid}.video'
    export_path=Path(settings.momentweave_export_dir)/f'{vid}.json'
    sha=hashlib.sha256();total=0
    try:
        with path.open('wb') as stream:
            while chunk:=await file.read(1024*1024):
                total+=len(chunk)
                if total > settings.max_video_mb*1024*1024:
                    raise HTTPException(413,f'Maximum video size is {settings.max_video_mb} MB')
                sha.update(chunk);stream.write(chunk)
        if total == 0:
            raise HTTPException(422,'Empty video')
        if momentweave_json is not None:
            if not (momentweave_json.filename or '').lower().endswith('.json'):
                raise HTTPException(415,'MomentWeave export must be JSON')
            raw=await momentweave_json.read(64*1024+1)
            if len(raw)>64*1024:raise HTTPException(413,'MomentWeave export must be <=64 KB')
            export_path.parent.mkdir(parents=True,exist_ok=True)
            export_path.write_bytes(raw)
        try:
            duration, candidates = inspect_video(path)
            if duration > settings.max_video_seconds:
                raise HTTPException(413, f'Maximum video duration is {settings.max_video_seconds} seconds')
            candidates, used_export=apply_export(vid,duration,candidates,settings.momentweave_export_dir)
        except (ValueError,cv2.error, OSError, __import__('json').JSONDecodeError) as ex:
            raise HTTPException(422,f'Video analysis failed: {ex}') from ex
        video=VideoAsset(id=vid,title=title.strip(),creator=creator.strip(),source_filename=file.filename[:255],
                         source_sha256=sha.hexdigest(),duration_seconds=duration,rights_asserted=True)
        db.add(video)
        moments=[]
        for candidate in candidates:
            mid=str(uuid4())
            (base/f'{mid}.jpg').write_bytes(candidate.pop('jpg'))
            m=Moment(id=mid,video_id=vid,price_cents=price_cents,**candidate)
            db.add(m); moments.append(m)
        db.commit()
        return {'video':video_out(video),'moments':[moment_out(m) for m in moments],
                'momentweave_export_used':used_export}
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        export_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
        if momentweave_json is not None:await momentweave_json.close()

@router.get('/videos')
def videos(db:Session=Depends(get_db)):
    return [video_out(v) for v in db.scalars(select(VideoAsset).order_by(VideoAsset.created_at.desc())).all()]

@router.get('/videos/{video_id}/moments')
def video_moments(video_id:str,db:Session=Depends(get_db)):
    if not db.get(VideoAsset,video_id): raise HTTPException(404,'Video not found')
    return [moment_out(m) for m in db.scalars(select(Moment).where(Moment.video_id==video_id).order_by(Moment.start_ms)).all()]

@router.get('/videos/{video_id}/file')
def video_file(video_id:str,db:Session=Depends(get_db)):
    if not db.get(VideoAsset,video_id): raise HTTPException(404,'Video not found')
    path=Path(get_settings().upload_dir)/f'{video_id}.video'
    if not path.is_file(): raise HTTPException(404,'Video file missing')
    return FileResponse(path,media_type='video/mp4',filename=f'{video_id}.mp4',content_disposition_type='inline')

@router.get('/moments/{moment_id}/thumbnail')
def thumb(moment_id:str,db:Session=Depends(get_db)):
    if not db.get(Moment,moment_id): raise HTTPException(404,'Moment not found')
    path=Path(get_settings().upload_dir)/f'{moment_id}.jpg'
    if not path.is_file(): raise HTTPException(404,'Preview missing')
    return FileResponse(path,media_type='image/jpeg')


def token_set(value):
    return set(re.findall(r'[a-z0-9]+',value.lower())) - {'the','a','an','is','for','and','of','to','in','on','with'}

@router.get('/moments/search')
def search_moments(q:str='', db:Session=Depends(get_db)):
    """Local lexical/semantic-lite demo search. Does not use an embedding model."""
    records=db.scalars(select(Moment)).all()
    docs=[' '.join((m.title,m.description,m.emotion,m.narrative_role)) for m in records]
    scores, method=score_documents(q,docs)
    found=[(score,m) for score,m in zip(scores,records) if score>0 or not q.strip()]
    found.sort(key=lambda v:(-v[0],v[1].start_ms))
    return {'query':q,'method':method,'results':[{**moment_out(m),'relevance':round(score,3)} for score,m in found[:30]]}

@router.post('/moments/{moment_id}/verify-frame')
async def verify_moment_frame(moment_id:str, file:UploadFile=File(...), db:Session=Depends(get_db)):
    m=db.get(Moment,moment_id)
    if not m:raise HTTPException(404,'Moment not found')
    data=await file.read(5*1024*1024+1)
    if len(data)>5*1024*1024:raise HTTPException(413,'Image must be <=5MB')
    frame=cv2.imdecode(np.frombuffer(data,dtype=np.uint8),cv2.IMREAD_COLOR)
    if frame is None:raise HTTPException(422,'Image is not decodable')
    distance=hamming(dhash(frame),m.keyframe_dhash)
    return {'moment_id':m.id,'method':'KEYFRAME_DHASH_64','hamming_distance':distance,
            'candidate_visual_match':distance<=12,
            'original_video_sha256':db.get(VideoAsset,m.video_id).source_sha256,
            'evidence':'Single-frame perceptual similarity only; false positives possible. Not proof of ownership, clip identity or license.'}
