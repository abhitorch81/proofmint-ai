from pathlib import Path
from unittest.mock import AsyncMock, patch
import cv2
import numpy as np
import pytest
from app.config import get_settings
from app.moment_engine import hamming


def create_video(path):
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),6,(160,96))
    if not writer.isOpened():
        pytest.skip('OpenCV VideoWriter codec unavailable')
    for i in range(36):
        frame=np.zeros((96,160,3),dtype=np.uint8)
        frame[:]=((i//9)*35, (i//9)*55, (i//9)*72)
        cv2.rectangle(frame,(i*3%120,20),(i*3%120+32,65),(230,220,120),-1)
        writer.write(frame)
    writer.release()

@pytest.fixture
def prepared_video(client,tmp_path,monkeypatch):
    monkeypatch.setenv('UPLOAD_DIR',str(tmp_path/'uploads'))
    get_settings.cache_clear()
    file=tmp_path/'clip.mp4';create_video(file)
    with file.open('rb') as f:
        res=client.post('/api/videos',data={'title':'Demo Basketball','creator':'Demo Creator',
            'rights_asserted':'true','price_cents':'499'},files={'file':('clip.mp4',f,'video/mp4')})
    assert res.status_code==201,res.text
    data=res.json();assert 3<=len(data['moments'])<=5
    yield data,tmp_path
    get_settings.cache_clear()


def test_upload_search_verify(client,prepared_video):
    data,tmp=prepared_video
    vid=data['video']['id'];moments=data['moments']
    assert data['video']['source_sha256']
    assert all(m['start_ms']<m['end_ms'] for m in moments)
    assert client.get(f'/api/videos/{vid}/moments').json()[0]['id']==moments[0]['id']
    assert client.get(f'/api/videos/{vid}/file').status_code==200
    found=client.get('/api/moments/search',params={'q':'highlight'}).json()
    assert found['results']
    moment=moments[0]
    thumb=client.get(moment['thumbnail_url'])
    assert thumb.status_code==200
    matched=client.post(f'/api/moments/{moment["id"]}/verify-frame',files={'file':('frame.jpg',thumb.content,'image/jpeg')})
    assert matched.status_code==200,matched.text
    assert matched.json()['candidate_visual_match'] is True
    assert matched.json()['hamming_distance']==0


def test_upload_requires_rights(client,tmp_path):
    file=tmp_path/'clip.mp4';create_video(file)
    with file.open('rb') as f:
        r=client.post('/api/videos',data={'title':'Demo Video','creator':'Creator','rights_asserted':'false'},files={'file':('clip.mp4',f,'video/mp4')})
    assert r.status_code==422


def test_moment_paypal_mock(client,prepared_video):
    moment=prepared_video[0]['moments'][1]
    oid='ORDER-MOMENT-123'
    response={'id':oid,'links':[{'rel':'approve','href':'https://www.sandbox.paypal.com/checkoutnow?token='+oid}]}
    capture={'id':'CAP-MOMENT','status':'COMPLETED','amount':{'currency_code':'USD','value':'4.99'}}
    complete={'id':oid,'status':'COMPLETED','purchase_units':[{'reference_id':moment['id'],
        'custom_id':moment['id'],'payments':{'captures':[capture]}}]}
    with patch('app.main.PayPalClient') as cls:
        instance=cls.return_value
        instance.create_order=AsyncMock(return_value=response)
        instance.capture_order=AsyncMock(return_value=complete)
        instance.get_order=AsyncMock(return_value=complete)
        order=client.post('/api/orders',json={'asset_id':moment['id']})
        assert order.status_code==200,order.text
        done=client.post(f'/api/orders/{oid}/capture')
        assert done.status_code==200,done.text
        payload=done.json()['receipt']['payload']
        assert payload['moment_id']==moment['id']
        assert payload['segment_start_ms']==moment['start_ms']
        assert payload['segment_end_ms']==moment['end_ms']
        assert client.post('/api/receipts/verify',json=done.json()['receipt']).json()['valid']
        assert client.post(f'/api/orders/{oid}/capture').status_code==200
        assert instance.capture_order.await_count==1


def test_dhash_hamming():
    assert hamming('0000000000000000','ffffffffffffffff')==64
    assert hamming('0000000000000000','0000000000000000')==0
