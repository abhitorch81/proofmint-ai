"""Speech recognition and approval-gated voice commerce endpoints."""
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
import os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from .db import get_db
from .commerce_agent import run_commerce_agent, provenance_evidence
from .models import Moment, VideoAsset
from .paypal import PayPalClient
from .models import Purchase
from uuid import uuid4
from .config import get_settings

router=APIRouter(prefix='/api/agent',tags=['Voice Commerce'])
class ChatRequest(BaseModel):
    message:str=Field(min_length=2,max_length=600)
class CheckoutRequest(BaseModel):
    moment_id:str
    acknowledged_price_cents:int=Field(ge=100,le=1000000)
    confirmed:bool=False

@lru_cache(maxsize=1)
def whisper_model():
    from faster_whisper import WhisperModel
    settings=get_settings()
    return WhisperModel(settings.whisper_model,device='cpu',compute_type='int8')

@router.get('/capabilities')
def capabilities():
    from importlib.util import find_spec
    return {'speech_recognition_installed':find_spec('faster_whisper') is not None,
            'langgraph_installed':find_spec('langgraph') is not None,
            'tts':'BROWSER_SPEECH_SYNTHESIS','checkout':'PAYPAL_SANDBOX_EXPLICIT_APPROVAL'}

@router.post('/chat')
def chat(body:ChatRequest,db:Session=Depends(get_db)):
    return run_commerce_agent(db,body.message)

@router.post('/transcribe')
async def transcribe(audio:UploadFile=File(...)):
    # Enforce size, speech-only intention, and avoid storing the user's recording.
    allowed={'.webm','.wav','.mp3','.mp4','.ogg','.m4a'}
    suffix=Path(audio.filename or '').suffix.lower()
    if suffix not in allowed:raise HTTPException(415,'Unsupported audio format')
    try:
        whisper_model()
    except (ImportError,OSError,RuntimeError) as ex:
        raise HTTPException(503,'Install requirements-voice.txt and download a Whisper model for transcription') from ex
    data=await audio.read(8*1024*1024+1)
    if not data:raise HTTPException(422,'Empty audio')
    if len(data)>8*1024*1024:raise HTTPException(413,'Audio must be <= 8 MB')
    file_path=None
    try:
        with NamedTemporaryFile(suffix=suffix,delete=False) as f:
            file_path=f.name;f.write(data)
        segments,info=whisper_model().transcribe(file_path,beam_size=3,vad_filter=True)
        transcript=' '.join(s.text.strip() for s in segments).strip()
        if not transcript:raise HTTPException(422,'No speech detected; try again')
        return {'transcript':transcript[:600],'language':info.language,'model':get_settings().whisper_model}
    finally:
        if file_path:Path(file_path).unlink(missing_ok=True)
        await audio.close()

@router.get('/moments/{moment_id}/provenance')
def explain_provenance(moment_id:str,db:Session=Depends(get_db)):
    m=db.get(Moment,moment_id)
    if not m:raise HTTPException(404,'Moment not found')
    video=db.get(VideoAsset,m.video_id)
    return {'moment_id':m.id,'evidence':provenance_evidence(m,video),
            'explanation':'Source SHA-256 and keyframe fingerprints are recorded. The uploader asserts rights; there is no independent rights verification or tamper-proof public provenance chain.'}

@router.post('/checkout/prepare')
async def prepare_checkout(body:CheckoutRequest,db:Session=Depends(get_db)):
    # Called ONLY from an explicit PayPal approval button; the chat/voice agent cannot call it.
    if not body.confirmed:raise HTTPException(403,'Explicit buyer approval is required')
    m=db.get(Moment,body.moment_id)
    if not m:raise HTTPException(404,'Moment not found')
    v=db.get(VideoAsset,m.video_id)
    if not v or not v.rights_asserted:raise HTTPException(409,'Rights assertion missing')
    if m.price_cents != body.acknowledged_price_cents:raise HTTPException(409,'Price changed; review current price')
    result=await PayPalClient().create_order(m,str(uuid4()))
    order_id=result.get('id')
    url=next((x.get('href') for x in result.get('links',[]) if x.get('rel') in ('approve','payer-action')),None)
    if not order_id or not url or not url.startswith('https://www.sandbox.paypal.com/'):
        raise HTTPException(502,'Invalid PayPal sandbox approval response')
    record=Purchase(moment_id=m.id,paypal_order_id=order_id)
    db.add(record);db.commit()
    return {'order_id':order_id,'approval_url':url,'status':'AWAITING_PAYPAL_APPROVAL',
            'amount_cents':m.price_cents,'currency':'USD','moment_id':m.id}
