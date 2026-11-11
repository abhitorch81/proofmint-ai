# ProofMint AI — Phase 4 (Windows)

**Start here: [`MOMENTWEAVE_RENAME.md`](MOMENTWEAVE_RENAME.md) for renamed APIs and safe migration; [`PHASE4_WINDOWS.md`](PHASE4_WINDOWS.md) for safe upgrade, new provenance APIs, Windows commands, and honest implementation scope.**

# ProofMint AI — MomentGraph Competition MVP (Windows-first, Phase 2)

An executable **local hackathon prototype**: upload a rights-cleared video; produce 3–5 reproducible, CPU-detected *candidate* moments; optionally ingest your own MomentWeave annotations; search and compare frames; approve a PayPal sandbox transaction for a specific moment; receive a tamper-evident **demo** license receipt.

**Important distinction:** the included `moment_engine.py` is OpenCV *scene/motion proxy logic*, **NOT** a pretrained nine-lens classifier or true emotion recognition. To use a separate moment classification model, export its moment JSON or replace the adapter. In full semantic mode an optional MiniLM embedding model is used. Offline base installation falls back to lexical matching and labels the method. The demo uses one-image dHash evidence, **not** robust audio/video watermarking, complete AKAZE video tracking, signed C2PA records, or legal copyright validation.

## 1. Requirements

Windows 10/11; Python 3.11–3.13 (3.13 used for local verification); Node.js 22; PowerShell; internet for pip/npm and initial MiniLM weights; PayPal developer sandbox credentials for real sandbox checkout. No GPU, Docker, Gemini key or paid LLM required. A short **MP4/H.264** clip (5–60 seconds recommended; 100 MB cap) is the simplest test video. OpenCV codec support depends on your OS/build.

**Extract ZIP** to `D:\hackathons\proofmint-ai` (change path if desired). If you already ran Phase 1 and are using SQLite, back up and rename `backend\proofmint.db` before launching Phase 2 because `create_all` does not migrate existing tables (Phase 2 adds `purchases.moment_id` and changes nullable columns). If using Phase 1 PostgreSQL, use a proper migration or a fresh development database, not production data.

## 2. Backend — PowerShell terminal 1

```powershell
cd D:\hackathons\proofmint-ai\backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the generated secret into `RECEIPT_SIGNING_SECRET=` in `backend\.env`. Never commit `.env` or live credentials. PowerShell activation blocked? Instead use `\.venv\Scripts\python.exe -m pip ...` and `\.venv\Scripts\python.exe -m uvicorn ...`.

```powershell
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` and `http://localhost:8000/api/health`. Default local database: `backend\proofmint.db`; local uploaded videos and thumbnails: `backend\uploads`.

**Optional real semantic vectors**: stop API, run `pip install -r requirements-semantic.txt` (install PyTorch CPU / sentence-transformers dependencies; may be large), restart. First semantic search downloads `sentence-transformers/all-MiniLM-L6-v2` weights from Hugging Face. Query `GET /api/moments/search?q=exciting+highlight`; confirm `method` equals `MINILM_COSINE_EMBEDDINGS`. Without optional dependencies it reports `LOCAL_LEXICAL_FALLBACK_NO_EMBEDDINGS`. Do not claim the fallback is semantic AI.

## 3. Frontend — PowerShell terminal 2

```powershell
cd D:\hackathons\proofmint-ai\frontend
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000/moments` (or click **Open MomentGraph** on the homepage). To validate the production bundle: `npm run build`. The backend was tested here, but the frontend build has **not** been verified in this environment because npm dependency installation timed out; run the build locally and report any messages.

### User walkthrough

1. Select MP4 and enter title, creator, and per-moment price in cents (default 499 = $4.99).
2. Check the *rights asserted* checkbox **only for footage you own/have rights to license**. Click **Analyze video**. The CPU analysis returns 3–5 candidate time windows and representative still images.
3. Search `highlight`, `calm`, `closing`, etc. The API reports the actual search mechanism.
4. Use **Compare candidate image** with a downloaded moment thumbnail to see dHash distance 0. This is **visual similarity only**; a near match does not prove video identity, provenance authenticity or copyrights.
5. Click **License with PayPal sandbox** on a moment. Approve with a **sandbox personal buyer**. After returning, the server captures and verifies amount + currency + moment ID against the stored order, then issues a signed demo license receipt identifying the moment and exact time window.

The preview endpoint serves the full uploaded original video **without authentication**. Use only fictional or rights-cleared demo material and **never publicly deploy this version**.

## 4. PayPal Sandbox setup

1. Visit <https://developer.paypal.com/dashboard/> → **Apps & Credentials** → **Sandbox**. Create or select a REST **merchant business** application, then copy **Client ID** and **Secret**.
2. Edit `backend\.env`:

```dotenv
PAYPAL_CLIENT_ID=YOUR_SANDBOX_APP_CLIENT_ID
PAYPAL_CLIENT_SECRET=YOUR_SANDBOX_APP_SECRET
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000
```

3. Create/use a **Personal sandbox buyer** under **Testing Tools → Sandbox Accounts**. Those login credentials are **not** the API credentials.
4. Restart FastAPI. Create a moment order, approve it in PayPal sandbox, and return to `/checkout/return?token=...`. The shared Phase 1 return page captures the order and renders the receipt. This code talks to the sandbox only, never PayPal live.
5. No PayPal credentials needed for `pytest` because requests are mocked. Actual checkout has **not** been live-tested here without your sandbox credentials.

Official REST Orders v2: <https://developer.paypal.com/api/rest/integration/orders-api/>; idempotency: <https://developer.paypal.com/api/make-api-requests>.

## 5. MomentWeave export integration

On upload, optionally attach a JSON export file. Example: `sample_momentweave_moments.json`:

```json
{
  "moments": [
    {"start_ms": 0, "end_ms": 2000, "title": "Opening", "description": "Introducing the scene", "emotion": "Curiosity", "narrative_role": "setup"},
    {"start_ms": 2000, "end_ms": 4000, "title": "Momentum", "description": "Action builds", "emotion": "Excitement", "narrative_role": "rising_action"},
    {"start_ms": 4000, "end_ms": 6000, "title": "Climax", "description": "The decisive moment", "emotion": "Excitement", "narrative_role": "climax"}
  ]
}
```

The export must contain **3–5 nonoverlapping, sorted, valid** segments within the actual video duration. For a 6-second example clip, the three windows above are suitable. The app preserves the supplied labels/times and associates each with the *nearest local candidate keyframe as approximate evidence*; it is not a frame-perfect temporal hash. This JSON exchange is a standalone annotation contract, not a trained emotion, event, or narrative inference model. Only integrate original or properly licensed model outputs.

## 6. API contract

| Method | Endpoint | What it does |
|---|---|---|
| GET | `/api/health` | Health check |
| GET / POST | `/api/assets` | Original Phase 1 asset registry |
| POST | `/api/provenance/lookup` | Exact SHA-256 lookup |
| POST | `/api/videos` | Multipart fields `file`, `title`, `creator`, `rights_asserted`, `price_cents`, optional `momentweave_json` |
| GET | `/api/videos` | List video metadata |
| GET | `/api/videos/{id}/moments` | Identified candidate windows |
| GET | `/api/videos/{id}/file` | Local demo video preview (unprotected) |
| GET | `/api/moments/{id}/thumbnail` | Representative JPEG |
| GET | `/api/moments/search?q=...` | Optional MiniLM or fallback token search |
| POST | `/api/moments/{id}/verify-frame` | Multipart candidate image; keyframe dHash Hamming distance |
| POST | `/api/orders` | Body `{ "asset_id": "<moment_id>" }` to start PayPal sandbox moment checkout |
| POST | `/api/orders/{id}/capture` | Verified capture + idempotent demo receipt creation |
| GET | `/api/receipts/{id}` | Fetch demo receipt |
| POST | `/api/receipts/verify` | Verify local HMAC payload integrity |

Important: `/api/orders` intentionally retains Phase 1's `asset_id` field to avoid breaking its existing UI, and accepts either an asset ID or moment ID.

## 7. PostgreSQL alternative (optional)

```powershell
cd D:\hackathons\proofmint-ai
docker compose up -d postgres
```

In `backend\.env` set:

```dotenv
DATABASE_URL=postgresql+psycopg://proofmint:proofmint_local_only@localhost:5433/proofmint
```

Start API after changing DB URL. ORM initializes new tables. `database/schema.sql` provides reference statements but is **not** a migration script. Do not manually run it over existing tables. For SQLite reset: stop API, then rename `backend\proofmint.db` before restart; that deletes none of your prior data, but it is not imported into the new DB.

## 8. Tests / expected results

```powershell
cd D:\hackathons\proofmint-ai\backend
python -m pytest -q
```

Locally verified **10 passed** (as of package build): six original tests, video ingest/search/dHash/keyframe verification, rights assertion rejection, mocked moment PayPal create/capture/receipt/idempotency, and dHash hamming calculation. The synthetic video test requires working OpenCV `VideoWriter`; if its codec is missing, that test will skip rather than test the full video path.

Manual quick check:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod 'http://localhost:8000/api/moments/search?q=highlight'
```

For a file upload, use frontend or Swagger UI (the latter supports file multipart inputs).

## 9. Architectural and safety limitations

- **MVP heuristic segmentation:** equal time windows; select keyframe using local motion score. Not semantic shot detection and not true automatically detected emotions. Segment boundaries are provisional and need human verification.
- **Moment provenance:** source video SHA-256 plus representative frame dHash. Resizing/compression tolerance is limited; collisions/false positives are possible; no C2PA signed assertions, rights proof or robust watermarking yet.
- **Receipt:** HMAC server-secret signs a payment-verified payload, useful for local tamper checks; not an externally verifiable identity certificate. PayPal capture validation is server-side and idempotent for sequential repeat requests, but there is no webhook verification, durable queue, atomic concurrent-order locking, or fraud controls.
- **Auth and rights:** only self-attested ownership; no login, content authorization, malware scanning, virus scanning, payout split or data retention policy. **Local-only demonstration.**
- **AI:** MiniLM used only when installed. No external proprietary model code, pretrained emotion recognition, agentic purchasing/decisioning, Elasticsearch, AG Grid or Render sponsor integration is claimed.

## 10. Proposed next milestone

Integrate original or properly licensed moment-classification outputs via an asynchronous job API and a real temporal keyframe mapping; add an AI licensing recommendation agent with explicit buyer approval; secure uploads/downloads, signed provenance and verified webhooks. For the hackathon demo, prioritize a fully reproducible sandbox purchase and a concise three-minute story.

---

# Phase 3 — Voice Commerce MVP (NEW)

This release **extends** Phase 2 without replacing the asset and moment APIs.
The new route is **http://localhost:3000/voice**. It uses your original-video
moments, MomentWeave JSON adapter, MiniLM embeddings when installed, and PayPal
sandbox Orders v2.

### Windows prerequisites

- Python **3.11 or 3.12**, Node.js **20+**, and npm; PowerShell; modern Chrome/Edge.
- Video test: a rights-cleared short MP4 uploaded through `/moments`.
- Microphone access requires `localhost` or HTTPS and browser permission.
- CPU-only Faster-Whisper uses the `tiny.en` model by default; it downloads on
  first transcription. First transcription can be slow. For English-only demo.
- An external LLM, Piper and API key are **not** necessary. Browser SpeechSynthesis
  is the included TTS implementation; installed voices depend on Windows/browser.

### Step-by-step Windows PowerShell — clean installation

```powershell
# 1: Unzip to D:\hackathons\proofmint-ai, then open a PowerShell terminal.
cd D:\hackathons\proofmint-ai\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-voice.txt
# Optional real semantic embeddings (larger packages and one-time model download):
# pip install -r requirements-semantic.txt
Copy-Item .env.example .env  # If it does not already exist
# Edit .env for PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET and RECEIPT_SIGNING_SECRET
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8000
```

In **second** PowerShell terminal:

```powershell
cd D:\hackathons\proofmint-ai\frontend
Copy-Item .env.local.example .env.local  # If it does not already exist
npm install
npm run dev
# Later verify production build with: npm run build
```

1. Open `http://localhost:3000/moments` and upload a rights-cleared MP4;
   optionally attach a real MomentWeave JSON export with 3–5 annotated moments.
2. Open `http://localhost:3000/voice` and search via text first.
3. Check `http://localhost:8000/api/agent/capabilities` and test microphone
   push-to-talk (click **Push to talk**, speak, click **Stop**).
4. Enable **Speak responses** for the browser speech synthesis fallback.
5. Inspect provenance and licensing terms for a recommended moment.
6. Click **Review checkout**, tick the *explicit buyer approval* checkbox,
   then **Continue to PayPal sandbox**. Log into a sandbox buyer account and
   approve payment; the original `/checkout/return` page captures payment and
   returns a signed HMAC demonstration receipt.

### Windows one-off model / environment notes

Set in `backend/.env`:

```dotenv
WHISPER_MODEL=tiny.en
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CLIENT_ID=your_sandbox_app_id
PAYPAL_CLIENT_SECRET=your_sandbox_secret
RECEIPT_SIGNING_SECRET=replace_this_with_a_long_random_cryptographic_secret
```

Generate a secret in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

If an existing SQLite database from Phase 1 is present, back it up and use
fresh development tables if its schema lacks Phase 2 tables; SQLAlchemy's
`create_all` does not upgrade tables. Phase 3 itself introduces no new tables.

### Phase 3 API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/agent/capabilities` | Report voice/graph availability |
| `POST /api/agent/chat` | Agent search / verification / explain; no payment |
| `POST /api/agent/transcribe` | Whisper local CPU transcription (8 MB max) |
| `GET /api/agent/moments/{id}/provenance` | Source and keyframe evidence |
| `POST /api/agent/checkout/prepare` | **Separate approval-gated** sandbox order creation |

Sample text query:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/agent/chat' -Method Post -ContentType 'application/json' -Body '{"message":"Find an exciting clip under $10 for 20 seconds"}'
```

### Validation

```powershell
cd D:\hackathons\proofmint-ai\backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod http://localhost:8000/api/agent/capabilities
```

**Local result for this package: 17 passed, 2 FastAPI deprecation warnings.**
The Whisper model, actual audio transcription, real LangGraph execution (when
optional dependency installed), browser UI build, and live PayPal sandbox
checkout were **not** exercised in the build environment. Windows users should
run these and report issues. Tests cover agent filtering, evidence disclosure,
rejected unconfirmed/changed-price checkout, mocked PayPal order creation,
format rejection, spoken-word budget recognition, plus Phase 1/2 functions.

### Commerce security boundary

- Speech/text agents only **recommend**, never place orders, charge funds,
  or issue licenses. `POST /api/agent/checkout/prepare` must be called after
  review through a separate buyer action and a server-side price check.
- PayPal itself must be approved by the buyer on the PayPal sandbox page.
  Receipt issuance still uses the existing server-verified order capture path.
- `confirmed: true` is only a local-demo client assertion; it is **not secure
  user authentication**. The original `/api/orders` endpoint remains available
  for Phase 1/2. Protect all order APIs with authenticated buyer sessions,
  CSRF defense and authorization before any internet deployment.
- Uploaded audio is immediately removed from temporary disk after transcription;
  recording is not persisted as a user account history. Avoid logging utterances
  in publicly accessible systems.
- Provenance is *evidence* of stored files and an unverified publisher rights
  assertion, not legal copyright proof. UI explicitly states this limitation.
- This is a demo *not* production readiness, C2PA certification, payment escrow,
  or validated emotion recognition.

### Code map

```text
backend/app/commerce_agent.py      constrained discovery, rights evidence, LangGraph workflow/fallback
backend/app/voice_api.py           text/chat, transcription, provenance, confirmed sandbox checkout
backend/requirements-voice.txt     optional Faster-Whisper and LangGraph dependencies
backend/tests/test_voice.py        six new backend test cases
frontend/app/voice/page.tsx        push-to-talk, speech synthesis, recommendations, checkout gate
```

### Suggested voice demo script

1. Show moments prepared on `/moments` from **your own** clip.
2. Say: “Find an exciting 20 second clip under ten dollars.”
3. Show agent trace and original SHA-256 / keyframe fingerprints.
4. Show an **unverified rights assertion** and review licensing conditions.
5. Confirm selected moment and price; approve payment on PayPal sandbox.
6. Return to the signed demo receipt and explain how capture is verified.
