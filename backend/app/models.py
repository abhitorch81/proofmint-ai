from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc)

class Asset(Base):
    __tablename__ = 'assets'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(150))
    creator: Mapped[str] = mapped_column(String(150))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    license_text: Mapped[str] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default='USD')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Purchase(Base):
    __tablename__ = 'purchases'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey('assets.id'), index=True, nullable=True)
    moment_id: Mapped[str | None] = mapped_column(ForeignKey('moments.id'), index=True, nullable=True)
    paypal_order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(20), default='CREATED')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class LicenseReceipt(Base):
    __tablename__ = 'license_receipts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    purchase_id: Mapped[str] = mapped_column(ForeignKey('purchases.id'), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class VideoAsset(Base):
    __tablename__ = 'video_assets'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(150))
    creator: Mapped[str] = mapped_column(String(150))
    source_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source_filename: Mapped[str] = mapped_column(String(255))
    duration_seconds: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='READY')
    rights_asserted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Moment(Base):
    __tablename__ = 'moments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey('video_assets.id'), index=True)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str] = mapped_column(String(40))
    narrative_role: Mapped[str] = mapped_column(String(50))
    motion_score: Mapped[float] = mapped_column(default=0.0)
    keyframe_dhash: Mapped[str] = mapped_column(String(16))
    keyframe_sha256: Mapped[str] = mapped_column(String(64))
    analysis_version: Mapped[str] = mapped_column(String(70), default='opencv-local-v1')
    price_cents: Mapped[int] = mapped_column(Integer, default=499)
    license_text: Mapped[str] = mapped_column(Text, default='Demo nonexclusive promotional clip license; subject to creator rights.')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
