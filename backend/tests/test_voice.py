import hashlib
from unittest.mock import AsyncMock,patch
from app.models import Moment,VideoAsset
from app.db import get_db

# Fixture overrides are provided by conftest. Seed through the dependency override.
def seed_moments(client):
    from app.main import app
    session=next(app.dependency_overrides[get_db]())
    v=VideoAsset(id='video-voice',title='Soccer Finals',creator='Creator',source_sha256='a'*64,source_filename='soccer.mp4',duration_seconds=60,rights_asserted=True)
    m=Moment(id='goal-voice',video_id=v.id,start_ms=12000,end_ms=27000,title='Exciting winning goal',description='The final dramatic score',emotion='Excitement',narrative_role='climax',motion_score=1,keyframe_dhash='0'*16,keyframe_sha256='b'*64,analysis_version='momentweave-export-v1',price_cents=699)
    session.add_all([v,m]);session.commit();session.close()

def test_text_agent_filters_budget_and_returns_evidence(client):
    seed_moments(client)
    r=client.post('/api/agent/chat',json={'message':'Find exciting goal under $10 for 20 seconds'})
    assert r.status_code==200,r.text
    d=r.json();assert len(d['recommendations'])==1
    assert d['recommendations'][0]['provenance']['legal_ownership_verified'] is False
    assert d['constraints']['max_price_cents']==1000
    assert d['payment_action'].startswith('NONE')
    assert d['audit']==['search_moment_tool','verify_provenance_tool','compose_response_tool']

def test_agent_cannot_buy_when_price_exceeds_budget(client):
    seed_moments(client)
    d=client.post('/api/agent/chat',json={'message':'Find exciting goal under $5'}).json()
    assert d['recommendations']==[]

def test_checkout_requires_explicit_approval(client):
    seed_moments(client)
    req={'moment_id':'goal-voice','acknowledged_price_cents':699,'confirmed':False}
    assert client.post('/api/agent/checkout/prepare',json=req).status_code==403
    req.update(confirmed=True,acknowledged_price_cents=500)
    assert client.post('/api/agent/checkout/prepare',json=req).status_code==409

def test_checkout_prepare_calls_paypal_only_after_approval(client):
    seed_moments(client)
    payload={'id':'ORDER-VOICE','links':[{'rel':'approve','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER-VOICE'}]}
    with patch('app.voice_api.PayPalClient') as paypal:
        paypal.return_value.create_order=AsyncMock(return_value=payload)
        r=client.post('/api/agent/checkout/prepare',json={'moment_id':'goal-voice','acknowledged_price_cents':699,'confirmed':True})
        assert r.status_code==200,r.text
        assert r.json()['status']=='AWAITING_PAYPAL_APPROVAL'
        paypal.return_value.create_order.assert_awaited_once()

def test_transcribe_rejects_bad_type(client):
    r=client.post('/api/agent/transcribe',files={'audio':('command.exe',b'x','application/octet-stream')})
    assert r.status_code==415

def test_provenance_explanation(client):
    seed_moments(client)
    d=client.get('/api/agent/moments/goal-voice/provenance').json()
    assert d['evidence']['source_sha256']=='a'*64
    assert not d['evidence']['legal_ownership_verified']

def test_spoken_word_budget(client):
    seed_moments(client)
    d=client.post('/api/agent/chat',json={'message':'Find exciting goal under ten dollars for 20 seconds'}).json()
    assert d['constraints']['max_price_cents']==1000
    assert len(d['recommendations'])==1
