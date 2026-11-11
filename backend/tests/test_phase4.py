"""Phase 4 tests use only synthetic imagery and mocked/local infrastructure."""
import io
import os
from pathlib import Path
import cv2
import numpy as np
from app import provenance_v4 as p
from app.config import get_settings
from app.models import Moment,VideoAsset
from conftest import Session

SECRET='test-only-secret-made-long-enough-123456789'

def synthetic():
    rng=np.random.default_rng(82)
    img=rng.integers(0,256,(360,640,3),dtype=np.uint8)
    cv2.putText(img,'PROOFMINT',(65,110),cv2.FONT_HERSHEY_SIMPLEX,1.4,(255,255,255),3)
    cv2.rectangle(img,(70,160),(350,300),(0,180,255),5)
    return img


def jpg(im, quality=90):
    return cv2.imencode('.jpg',im,[cv2.IMWRITE_JPEG_QUALITY,quality])[1].tobytes()


def test_akaze_identical_and_transformed():
    src=synthetic()
    identical=p.akaze_evidence(src,src)
    assert identical['candidate_visual_match'] and identical['inliers']>=8
    small=cv2.resize(src,(520,293))
    score=p.akaze_evidence(src,small)
    assert score['candidate_visual_match']
    other=np.zeros_like(src)
    assert not p.akaze_evidence(src,other)['candidate_visual_match']


def test_watermark_roundtrip_jpeg_and_negative():
    src=synthetic()
    marked, tag=p.embed_frame(src,SECRET,'moment-001')
    assert len(tag)==8
    assert p.verify_frame_watermark(p.safe_decode(marked),SECRET,'moment-001')['watermark_detected']
    compressed=p.safe_decode(jpg(p.safe_decode(marked),90))
    assert p.verify_frame_watermark(compressed,SECRET,'moment-001')['watermark_detected']
    assert not p.verify_frame_watermark(src,SECRET,'moment-001')['watermark_detected']
    assert not p.verify_frame_watermark(p.safe_decode(marked),SECRET,'a-different-moment')['watermark_detected']


def test_image_safety():
    import pytest
    with pytest.raises(ValueError):p.safe_decode(b'nothing')
    with pytest.raises(ValueError):p.embed_frame(synthetic(),'weak','moment')


def test_phase4_routes(client,tmp_path,monkeypatch):
    # Set env through mocked settings, do not touch users' actual uploads or .env.
    settings=get_settings()
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path))
    monkeypatch.setattr(settings,'momentweave_export_dir',str(tmp_path))
    monkeypatch.setattr(settings,'receipt_signing_secret',SECRET)
    v=VideoAsset(id='00000000-0000-0000-0000-000000000001',title='demo',creator='author',
                 source_sha256='f'*64,source_filename='demo.mp4',duration_seconds=30.0,rights_asserted=True)
    m=Moment(id='00000000-0000-0000-0000-000000000002',video_id=v.id,start_ms=1000,end_ms=4000,
             title='Demo',description='scene',emotion='unclassified',narrative_role='opening',
             motion_score=0.0,keyframe_dhash='0'*16,keyframe_sha256='f'*64,analysis_version='opencv-test')
    with Session() as db:
        db.add(v);db.add(m);db.commit()
    (tmp_path/f'{m.id}.jpg').write_bytes(jpg(synthetic()))
    graph=client.get(f'/api/videos/{v.id}/narrative-graph')
    assert graph.status_code==200 and graph.json()['nodes'][0]['title']=='Demo'
    response=client.post(f'/api/moments/{m.id}/verify-akaze',files={'file':('image.jpg',jpg(synthetic()),'image/jpeg')})
    assert response.status_code==200 and response.json()['candidate_visual_match']
    marked=client.get(f'/api/moments/{m.id}/marked-frame')
    assert marked.status_code==200 and marked.headers['content-type']=='image/png'
    verified=client.post(f'/api/moments/{m.id}/verify-watermark', files={'file':('marked.png',marked.content,'image/png')})
    assert verified.status_code==200 and verified.json()['watermark_detected']
    assert client.post(f'/api/moments/{m.id}/verify-watermark',files={'file':('bad.png',b'bad','image/png')}).status_code==422
