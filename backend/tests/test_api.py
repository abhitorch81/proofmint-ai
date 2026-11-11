from unittest.mock import AsyncMock, patch
from app.main import sign, validate_capture
from fastapi import HTTPException

ASSET={'title':'Sunrise photograph','creator':'Demo Creator','sha256':'a'*64,'license_text':'Commercial use on one website','price_cents':1200}

def test_health(client):
    r=client.get('/api/health'); assert r.status_code==200;assert r.json()['paypal_mode']=='sandbox'

def test_assets_and_hash_lookup(client):
    r=client.post('/api/assets',json=ASSET);assert r.status_code==201
    aid=r.json()['id']
    r=client.get('/api/assets');assert len(r.json())==1
    r=client.post('/api/provenance/lookup',json={'sha256':'a'*64})
    assert r.json()['match_type']=='EXACT_SHA256' and r.json()['assets'][0]['id']==aid
    assert client.post('/api/provenance/lookup',json={'sha256':'b'*64}).json()['match_type']=='NO_EXACT_MATCH'

def test_asset_validation(client):
    assert client.post('/api/assets',json={**ASSET,'sha256':'invalid'}).status_code==422
    assert client.post('/api/assets',json={**ASSET,'price_cents':-1}).status_code==422

def test_receipt_tampering(client):
    payload={'asset_id':'abc','license':'testing'}
    import json
    signature=sign(json.dumps(payload,sort_keys=True,separators=(',',':')))
    assert client.post('/api/receipts/verify',json={'payload':payload,'signature':signature}).json()['valid'] is True
    assert client.post('/api/receipts/verify',json={'payload':{**payload,'license':'fake'},'signature':signature}).json()['valid'] is False

def test_order_and_capture_mocked_paypal(client):
    asset=client.post('/api/assets',json=ASSET).json()
    order={'id':'ORDER-123','links':[{'rel':'approve','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER-123'}]}
    with patch('app.main.PayPalClient') as cls:
        instance=cls.return_value
        instance.create_order=AsyncMock(return_value=order)
        r=client.post('/api/orders',json={'asset_id':asset['id']})
        assert r.status_code==200
        capture={'id':'CAP-123','status':'COMPLETED','amount':{'value':'12.00','currency_code':'USD'}}
        completed={'id':'ORDER-123','status':'COMPLETED','purchase_units':[{'reference_id':asset['id'],'custom_id':asset['id'],'payments':{'captures':[capture]}}]}
        instance.capture_order=AsyncMock(return_value=completed)
        instance.get_order=AsyncMock(return_value=completed)
        r=client.post('/api/orders/ORDER-123/capture')
        assert r.status_code==200,r.text
        receipt=r.json()['receipt']
        assert receipt['payload']['paypal_capture_id']=='CAP-123'
        assert client.post('/api/receipts/verify',json=receipt).json()['valid']
        assert client.post('/api/orders/ORDER-123/capture').json()['receipt']['id']==receipt['id']
        assert instance.capture_order.await_count==1

def test_reject_incorrect_payment(client):
    asset=client.post('/api/assets',json=ASSET).json()
    fake=type('A',(),asset)()
    result={'id':'ORDER-123','status':'COMPLETED','purchase_units':[{'reference_id':asset['id'],'custom_id':asset['id'],'payments':{'captures':[{'id':'C1','status':'COMPLETED','amount':{'value':'1.00','currency_code':'USD'}}]}}]}
    try: validate_capture(result,fake,'ORDER-123')
    except HTTPException as ex: assert ex.status_code==409
    else: raise AssertionError('Invalid payment was accepted')
