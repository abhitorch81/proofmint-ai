-- Informational PostgreSQL reference schema. FastAPI creates equivalent tables through SQLAlchemy.
CREATE TABLE IF NOT EXISTS assets (
 id VARCHAR(36) PRIMARY KEY, title VARCHAR(150) NOT NULL, creator VARCHAR(150) NOT NULL,
 sha256 VARCHAR(64) NOT NULL, license_text TEXT NOT NULL,
 price_cents INTEGER NOT NULL CHECK(price_cents >= 100), currency VARCHAR(3) NOT NULL DEFAULT 'USD', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_assets_sha256 ON assets(sha256);
CREATE TABLE IF NOT EXISTS purchases (
 id VARCHAR(36) PRIMARY KEY, asset_id VARCHAR(36) NOT NULL REFERENCES assets(id),
 paypal_order_id VARCHAR(128) UNIQUE NOT NULL, paypal_capture_id VARCHAR(128) UNIQUE,
 status VARCHAR(20) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS license_receipts (
 id VARCHAR(36) PRIMARY KEY, purchase_id VARCHAR(36) UNIQUE NOT NULL REFERENCES purchases(id),
 payload_json TEXT NOT NULL, signature VARCHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Phase 2: New-install reference. For an existing Phase 1 PostgreSQL database,
-- use ALTER TABLE purchases ADD COLUMN moment_id VARCHAR(36) AFTER creating moments;
-- additionally make purchases.asset_id nullable. Use a migration tool for production.
CREATE TABLE IF NOT EXISTS video_assets (
 id VARCHAR(36) PRIMARY KEY,
 title VARCHAR(150) NOT NULL, creator VARCHAR(150) NOT NULL,
 source_sha256 VARCHAR(64) NOT NULL, source_filename VARCHAR(255) NOT NULL,
 duration_seconds DOUBLE PRECISION NOT NULL, status VARCHAR(20) NOT NULL,
 rights_asserted BOOLEAN NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS moments (
 id VARCHAR(36) PRIMARY KEY, video_id VARCHAR(36) NOT NULL REFERENCES video_assets(id),
 start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL, title VARCHAR(160) NOT NULL,
 description TEXT NOT NULL, emotion VARCHAR(40) NOT NULL, narrative_role VARCHAR(50) NOT NULL,
 motion_score DOUBLE PRECISION NOT NULL, keyframe_dhash VARCHAR(16) NOT NULL,
 keyframe_sha256 VARCHAR(64) NOT NULL, analysis_version VARCHAR(70) NOT NULL,
 price_cents INTEGER NOT NULL, license_text TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), CHECK (end_ms > start_ms)
);
-- Fresh Phase 2 purchases table includes nullable asset_id AND nullable moment_id;
-- at least one must be present. Do not run this reference SQL over a running Phase 1 DB.
-- ALTER TABLE purchases ADD COLUMN moment_id VARCHAR(36) REFERENCES moments(id);
-- ALTER TABLE purchases ALTER COLUMN asset_id DROP NOT NULL;
