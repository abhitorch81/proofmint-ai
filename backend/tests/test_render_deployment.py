"""Release-focused checks that do not require live PayPal or Render."""
from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal
from fastapi import HTTPException
from app.db import url
from app.main import validate_capture
from app import moments_api


def test_database_url_is_test_sqlite():
    # Existing local regression suite must stay offline / isolated.
    assert url.startswith('sqlite')


def test_production_upload_requires_private_token(client, monkeypatch):
    monkeypatch.setattr(moments_api, 'get_settings', lambda: SimpleNamespace(
        app_env='production', demo_upload_token='a-private-test-value',
        max_video_mb=20, upload_dir='/not-used', momentweave_export_dir='/not-used',
        max_video_seconds=180))
    res = client.post('/api/videos', data={'title':'Test Video','creator':'Test Creator',
        'rights_asserted':'true'}, files={'file':('test.mp4',b'placeholder','video/mp4')})
    assert res.status_code == 403
    assert 'token' in res.text.lower()


def test_production_upload_with_wrong_token_still_blocked(client, monkeypatch):
    monkeypatch.setattr(moments_api, 'get_settings', lambda: SimpleNamespace(
        app_env='production', demo_upload_token='correct-private-token',
        max_video_mb=20, upload_dir='/not-used', momentweave_export_dir='/not-used',
        max_video_seconds=180))
    res = client.post('/api/videos', data={'title':'Test Video','creator':'Test Creator',
        'rights_asserted':'true'}, files={'file':('test.mp4',b'placeholder','video/mp4')},
        headers={'X-Demo-Upload-Token':'incorrect'})
    assert res.status_code == 403


def test_capture_does_not_round_fractional_cents():
    asset = SimpleNamespace(id='asset-1',price_cents=499)
    result = {'id':'ord-1', 'status':'COMPLETED','purchase_units':[{'custom_id':'asset-1',
        'reference_id':'asset-1','payments':{'captures':[{'id':'capture-1','status':'COMPLETED',
        'amount':{'currency_code':'USD','value':'4.991'}}]}}]}
    try:
        validate_capture(result,asset,'ord-1')
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('Fractional cent must be rejected')
