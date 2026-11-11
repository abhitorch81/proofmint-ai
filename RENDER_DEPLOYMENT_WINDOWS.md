# ProofMint AI (MomentWeave) — Render deployment from Windows

## Read this first

This package is a **demo**, not a production-ready payment marketplace or a verified rights registry. It retains OpenCV segmentation, MomentWeave JSON input, AKAZE/RANSAC, keyed still-frame DCT watermark, local text-agent workflow, PayPal **sandbox** Orders v2 and HMAC-signed demo receipts. It does **not** include a proprietary moment classifier, full-MP4 watermarking, an independently verified copyright registry, production user authentication, or production-ready payment reconciliation.

### Prerequisites

- A GitHub repository containing this folder **without** `.env` files, DB files, or media.
- Render account with a paid web instance for the backend (for an attached disk), a Node frontend service, and a PostgreSQL database. Check Render pricing before provisioning.
- PayPal **US Business sandbox** REST application client ID and secret. Use a **separate Personal sandbox** login for checkout. Never use live PayPal credentials in this app.
- Windows local setup already uses `conda activate proofmint` and localhost 8000/3000. This continues to work.

## 1. Preserve your working local system

Do not overwrite the working Phase 3 or Phase 4 folders. Back up `.env`, `proofmint.db`, `uploads/`, `momentweave_exports/` privately. Do **not** commit or upload these to a public repository. Keep `RECEIPT_SIGNING_SECRET` unchanged if moving your old receipts, otherwise receipt validation will fail. SQLite data are **not automatically imported** to Render PostgreSQL; Render starts with a new empty database. Re-upload an original rights-cleared demo clip using the protected upload form.

## 2. Windows preflight

```powershell
cd D:\hackathons\proofmint-momentweave\proofmint-ai\backend
conda activate proofmint
python -m pip install -r requirements.txt
python -m pytest -q

cd ..\frontend
npm install
npm run build
npm audit --omit=dev
```

Use your **actual extraction directory** if it differs. Test again on Windows before deployment.

## 3. GitHub push (PowerShell)

```powershell
cd D:\hackathons\proofmint-momentweave\proofmint-ai
git init
git status --short
git add .
git diff --cached --name-only
# Stop if this lists .env, uploads, secrets, .db, node_modules or .next files.
git commit -m "ProofMint MomentWeave Render sandbox deployment"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git push -u origin main
```

Create the empty GitHub repo first. Use `git remote set-url origin ...` if an origin already exists.

## 4. Deploy the Render Blueprint

1. In Render Dashboard choose **New → Blueprint** and connect the GitHub repo.
2. Render finds `render.yaml` at repo root. Review the resources before clicking Deploy. Confirm your workspace supports the selected database plan and persistent disk; update the plan in `render.yaml` if the dashboard rejects it.
3. The Blueprint creates `proofmint-api` (Docker, paid Starter plan, persistent `/var/data`), `proofmint-web` (Node web service) and `proofmint-db` (managed PostgreSQL). This is **not free**. Storage, database and compute are separately billed.
4. Populate all `sync: false` environment variables before deploying, using your actual Render HTTPS addresses. Names can be suffixed automatically if taken; look up your real service URLs.

**Backend (`proofmint-api`)**:

| Variable | Value |
|---|---|
| `FRONTEND_URL` | `https://YOUR-FRONTEND.onrender.com` (no trailing slash) |
| `CORS_ORIGINS` | `https://YOUR-FRONTEND.onrender.com` |
| `PAYPAL_CLIENT_ID` | US business *sandbox app* Client ID |
| `PAYPAL_CLIENT_SECRET` | US business *sandbox app* Secret |
| `RECEIPT_SIGNING_SECRET` | Strong 32-byte-or-longer random secret; use original key only if migrating existing receipts |
| `DEMO_UPLOAD_TOKEN` | New long random password, entered privately into upload UI (never `NEXT_PUBLIC_*`) |

**Frontend (`proofmint-web`)**:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://YOUR-API.onrender.com` (no trailing slash) |

`NEXT_PUBLIC_API_URL` is embedded into Next.js **at build time**. If changed, trigger **Manual Deploy → Deploy latest commit** for the frontend (with build cache cleared if needed). Do not set secrets as `NEXT_PUBLIC_*`.

Blueprint-managed backend defaults: `APP_ENV=production`, PostgreSQL URL injected via `fromDatabase`, `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`, `UPLOAD_DIR=/var/data/uploads`, `MOMENTWEAVE_EXPORT_DIR=/var/data/momentweave_exports`, `MAX_VIDEO_MB=20`, `MAX_VIDEO_SECONDS=180`. The disk persists only data under `/var/data`.

### Voice / agent on Render

The backend Docker image installs **base dependencies** (FastAPI/OpenCV/AKAZE/watermark). Browser TTS and typed agent queries remain usable. CPU Faster-Whisper and LangGraph are **optional** and are not bundled in the lightweight Render image; to enable Whisper on a larger paid backend, add `RUN pip install -r requirements-voice.txt` and copy that file in the backend Dockerfile, then redeploy. This increases build time and RAM demand. Windows already supports the optional speech dependencies.

### PostgreSQL and migrations

The API uses SQLAlchemy `create_all()` at startup for a **new** empty database. That is not a schema migration system: never assume it upgrades an existing schema. Start with fresh Render DB for hackathon. For future releases, introduce Alembic migrations and perform backups before changes. Old SQLite receipts will not be copied automatically.

## 5. Verify public deployment

```powershell
$api = 'https://YOUR-API.onrender.com'
$web = 'https://YOUR-FRONTEND.onrender.com'
Invoke-RestMethod "$api/api/health"
Invoke-WebRequest "$web/moments"
Invoke-WebRequest "$web/voice"
```

Open `/moments` in a browser. Use the **private demo upload token** field to register a rights-cleared 20–60s MP4 (under 20 MB). Verify 3–5 moment cards, AKAZE match, keyed PNG generation/detection, MomentWeave narrative relationship view, and text-agent search. The original synthetic 30-second test MP4 is useful, but low-texture graphics may have too few AKAZE keypoints; use a textured rights-cleared video for AKAZE.

For PayPal: choose a moment, confirm exact price, approve a **new** order through your separate sandbox Personal account; verify return to the HTTPS frontend `/checkout/return`, PayPal capture `COMPLETED`, and signed receipt. Do not use a real account or real money.

If PayPal returns to localhost, correct `FRONTEND_URL` on the backend and create a **new** sandbox order; existing PayPal order return URLs do not change retroactively.

## 6. Storage and security boundaries

- Uploaded video/keyframes and MomentWeave exports live on the attached Render disk. The database is managed PostgreSQL. Only **one backend instance** should access the disk; do not scale horizontally in this setup.
- In production, video ingestion rejects missing or incorrect `X-Demo-Upload-Token`. The frontend has a password-style field for that token; it is held in page state and sent directly over HTTPS to the API, not added to git or browser local storage. For a fully public multi-user site, replace this with proper authentication and per-user authorization.
- Public `/api/videos/*/file` and `/api/moments/*/thumbnail` are demo previews, not private licensed-content delivery. Upload **only footage cleared for public demonstration**.
- Other public demo endpoints, including checkout creation and AI chat, are not comprehensively rate-limited or user-authenticated. Limit publicity, monitor logs, and disable the services after judging if necessary. Do not market this as ready for real customers.
- PayPal API credentials stay backend-only and sandbox-only. Signature secret is server-side. **Never commit secrets**. CORS allows only the configured frontend, but CORS is *not* authentication.
- Keep only supported upload formats and small demo clips; guard against malicious/untrusted video files. In a production marketplace, move video processing to an isolated queue/worker and store media in controlled object storage.
- There is no verified webhook pipeline or advanced concurrency control. PayPal capture uses a stable idempotency key; retain a single worker for demo use and verify capture amounts and license IDs. Do not use with live PayPal traffic.
- DCT watermarking is experimental, applied to a **still frame only**; matching results are evidence, not legal proof of ownership.

## 7. How to roll back

Keep Phase 3 working locally. If Render fails, do not modify the local DB or signing key. Use the previous tested local version and the recorded demo. On Render, roll back web services to a known-good Git commit; never delete database or persistent disk without backup. Contact Render support for hosting platform problems. Do not expose tokens, secrets, signed receipts containing personal data or live transaction details in the public Devpost submission.

## Local Windows still works

```cmd
conda activate proofmint
cd /d D:\hackathons\proofmint-momentweave\proofmint-ai\backend
python -m uvicorn app.main:app --reload --port 8000
```

Second terminal:

```cmd
cd /d D:\hackathons\proofmint-momentweave\proofmint-ai\frontend
npm run dev
```

Development defaults keep SQLite, local `uploads/`, `http://localhost:3000` and `http://localhost:8000`. No demo upload token is required locally. Keep your working `.env` file **private**.

## Official reference

- https://render.com/docs/infrastructure-as-code
- https://render.com/docs/blueprint-spec
- https://render.com/docs/disks
- https://render.com/docs/configure-environment-variables
- https://render.com/docs/health-checks
