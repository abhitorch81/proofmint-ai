import hashlib, hmac, json, re
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import get_settings
from .db import Base, engine, get_db
from .models import Asset, Purchase, LicenseReceipt, Moment, VideoAsset
from .schemas import AssetCreate, OrderCreate, HashCheck
from .paypal import PayPalClient

settings = get_settings()
if settings.app_env.lower() == 'production':
    if len(settings.receipt_signing_secret) < 32 or settings.receipt_signing_secret.startswith('replace-') or settings.receipt_signing_secret == 'development-only-change-me':
        raise RuntimeError('Production requires a strong RECEIPT_SIGNING_SECRET')
    if settings.frontend_url.startswith('http://') or not settings.cors_origins.startswith('https://'):
        raise RuntimeError('Production requires HTTPS FRONTEND_URL and CORS_ORIGINS')
    if not settings.database_url.startswith(('postgresql://','postgresql+psycopg://','postgres://')):
        raise RuntimeError('Production requires PostgreSQL')
    if not settings.demo_upload_token:
        raise RuntimeError('Production requires DEMO_UPLOAD_TOKEN')
app = FastAPI(title='ProofMint AI API', version='0.2.0', docs_url=None if settings.app_env.lower() == 'production' else '/docs', redoc_url=None if settings.app_env.lower() == 'production' else '/redoc')
app.add_middleware(CORSMiddleware,allow_origins=[v.strip() for v in settings.cors_origins.split(',')],allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Content-Type'])

@app.on_event('startup')
def init(): Base.metadata.create_all(bind=engine)

@app.get('/api/health')
def health(): return {'status':'ok','phase':4,'paypal_mode':'sandbox'}

@app.get('/api/assets')
def assets(db:Session=Depends(get_db)):
    rows=db.scalars(select(Asset).order_by(Asset.created_at.desc())).all()
    return [asset_out(x) for x in rows]

def asset_out(a):
    return {'id':a.id,'title':a.title,'creator':a.creator,'sha256':a.sha256,'price_cents':a.price_cents,'currency':a.currency,'license_text':a.license_text}

@app.post('/api/assets',status_code=201)
def create_asset(body:AssetCreate,db:Session=Depends(get_db)):
    obj=Asset(**body.model_dump(),currency='USD');db.add(obj);db.commit();db.refresh(obj)
    return asset_out(obj)

@app.post('/api/provenance/lookup')
def lookup_hash(body:HashCheck,db:Session=Depends(get_db)):
    if not re.fullmatch(r'[0-9a-fA-F]{64}',body.sha256): raise HTTPException(422,'Invalid SHA256')
    matched=db.scalars(select(Asset).where(Asset.sha256==body.sha256.lower())).all()
    return {'match_type':'EXACT_SHA256' if matched else 'NO_EXACT_MATCH','assets':[asset_out(a) for a in matched], 'note':'An exact hash match is not a proof of legal ownership.'}

@app.post('/api/orders')
async def create_order(body:OrderCreate, db:Session=Depends(get_db)):
    asset=db.get(Asset,body.asset_id)
    moment=None
    if not asset:
        moment=db.get(Moment,body.asset_id)
        if not moment: raise HTTPException(404,'Asset or moment not found')
        video=db.get(VideoAsset,moment.video_id)
        if not video or not video.rights_asserted: raise HTTPException(409,'Creator rights not asserted')
        asset=moment
    result=await PayPalClient().create_order(asset,str(uuid4()))
    paypal_id=result.get('id')
    approval=next((x.get('href') for x in result.get('links',[]) if x.get('rel') in ('approve','payer-action')),None)
    if not paypal_id or not approval or not approval.startswith('https://'):
        raise HTTPException(502,'Incomplete PayPal create-order response')
    purchase=Purchase(asset_id=asset.id if moment is None else None,moment_id=moment.id if moment else None,paypal_order_id=paypal_id)
    db.add(purchase);db.commit()
    return {'order_id':paypal_id,'approval_url':approval,'status':'CREATED'}

def sign(payload):
    return hmac.new(settings.receipt_signing_secret.encode(),payload.encode(),hashlib.sha256).hexdigest()

def receipt_out(rec): return {'id':rec.id,'payload':json.loads(rec.payload_json),'signature':rec.signature,'signature_scheme':'HMAC-SHA256-DEMO'}

def validate_capture(result, asset, order_id):
    if result.get('id')!=order_id or result.get('status')!='COMPLETED': raise HTTPException(409,'Order not completed')
    units=result.get('purchase_units') or []
    if len(units)!=1: raise HTTPException(409,'Unexpected purchase units')
    unit=units[0]
    if unit.get('custom_id')!=asset.id or unit.get('reference_id')!=asset.id: raise HTTPException(409,'Asset ID mismatch')
    captures=unit.get('payments',{}).get('captures') or []
    if len(captures)!=1 or captures[0].get('status')!='COMPLETED': raise HTTPException(409,'Payment not completed')
    capture=captures[0]
    amount=capture.get('amount') or {}
    try:
        from decimal import Decimal, InvalidOperation
        cents = Decimal(str(amount['value'])) * 100
        if cents != cents.to_integral_value():
            raise ValueError('Fractional cent')
        amount_cents = int(cents)
    except (KeyError, ValueError, TypeError, InvalidOperation):
        raise HTTPException(409,'Invalid captured amount')
    if amount.get('currency_code')!='USD' or amount_cents!=asset.price_cents: raise HTTPException(409,'Captured amount mismatch')
    if not capture.get('id'): raise HTTPException(409,'Missing capture ID')
    return capture['id']

@app.post('/api/orders/{order_id}/capture')
async def capture_order(order_id:str, db:Session=Depends(get_db)):
    purchase=db.scalar(select(Purchase).where(Purchase.paypal_order_id==order_id))
    if not purchase: raise HTTPException(404,'Unknown PayPal order')
    receipt=db.scalar(select(LicenseReceipt).where(LicenseReceipt.purchase_id==purchase.id))
    if receipt: return {'status':'COMPLETED','receipt':receipt_out(receipt)}
    moment=db.get(Moment,purchase.moment_id) if purchase.moment_id else None
    asset=moment if moment else db.get(Asset,purchase.asset_id)
    client=PayPalClient()
    # Deterministic PayPal idempotency key for safe retries; then read canonical order state.
    await client.capture_order(order_id,purchase.id)
    result=await client.get_order(order_id)
    capture_id=validate_capture(result,asset,order_id)
    purchase.status='COMPLETED';purchase.paypal_capture_id=capture_id
    payload={'asset_id':asset.id,'asset_sha256':db.get(VideoAsset,moment.video_id).source_sha256 if moment else asset.sha256,'license':asset.license_text,'paypal_order_id':order_id,'paypal_capture_id':capture_id,'price_cents':asset.price_cents,'currency':'USD','issued_at':datetime.now(timezone.utc).isoformat()}
    if moment:
        payload.update(moment_id=moment.id,source_video_id=moment.video_id,segment_start_ms=moment.start_ms,segment_end_ms=moment.end_ms,analysis_version=moment.analysis_version)
    canonical=json.dumps(payload,sort_keys=True,separators=(',',':'))
    receipt=LicenseReceipt(purchase_id=purchase.id,payload_json=canonical,signature=sign(canonical))
    db.add(receipt);db.commit();db.refresh(receipt)
    return {'status':'COMPLETED','receipt':receipt_out(receipt)}

@app.get('/api/receipts/{receipt_id}')
def get_receipt(receipt_id:str,db:Session=Depends(get_db)):
    rec=db.get(LicenseReceipt,receipt_id)
    if not rec: raise HTTPException(404,'Receipt not found')
    return receipt_out(rec)

@app.post('/api/receipts/verify')
def verify_receipt(body:dict):
    payload=body.get('payload');signature=body.get('signature')
    if not isinstance(payload,dict) or not isinstance(signature,str): raise HTTPException(422,'Supply payload and signature')
    canonical=json.dumps(payload,sort_keys=True,separators=(',',':'))
    return {'valid':hmac.compare_digest(sign(canonical),signature),'scheme':'HMAC-SHA256-DEMO','note':'Demo server-secret signature, not publicly verifiable provenance.'}


from .moments_api import router as moments_router
app.include_router(moments_router)

from .voice_api import router as voice_router
app.include_router(voice_router)

from .provenance_api_v4 import router as provenance_v4_router
app.include_router(provenance_v4_router)
from .narrative_api_v4 import router as narrative_v4_router
app.include_router(narrative_v4_router)
