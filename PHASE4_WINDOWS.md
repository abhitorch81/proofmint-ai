# ProofMint AI — Phase 4: AKAZE + keyed frame-watermark provenance

**This ZIP contains the full Phase 3 application PLUS Phase 4 changes.** The successful PayPal Orders v2 and signed-receipt code is preserved. No new database columns or migrations are introduced. Keep your existing `backend/.env`, `backend/proofmint.db`, `backend/uploads`, and `backend/momentweave_exports` when upgrading.

## 1. Safe upgrade on Windows

The safest method is to **back up your working Phase 3 directory**, then extract this ZIP to a **new** folder and copy your existing runtime state across. Avoid placing one `proofmint-ai` folder inside another.

In **Anaconda Prompt** (CMD):

```cmd
conda activate proofmint
cd /d D:\hackathons
xcopy proofmint-ai proofmint-ai-backup\ /E /I /H /Y
```

Extract the Phase 4 ZIP using Windows Extract All into `D:\hackathons\proofmint-phase4\` so the resulting source root is `D:\hackathons\proofmint-phase4\proofmint-ai\`. If your working folder is somewhere else, adjust paths. Copy the following from your Phase 3 installation to the Phase 4 `backend`:

```cmd
copy D:\hackathons\proofmint-ai\backend\.env D:\hackathons\proofmint-phase4\proofmint-ai\backend\.env
copy D:\hackathons\proofmint-ai\backend\proofmint.db D:\hackathons\proofmint-phase4\proofmint-ai\backend\proofmint.db
xcopy D:\hackathons\proofmint-ai\backend\uploads D:\hackathons\proofmint-phase4\proofmint-ai\backend\uploads\ /E /I /Y
REM Import existing export JSON files only if you have permission to use them.
REM For a previous export folder, use scripts\migrate-moment-exports.ps1 after extraction.
```

**If those files or folders don't exist**, skip their copy commands. Update `backend\.env`: replace any previous export-directory configuration with `MOMENTWEAVE_EXPORT_DIR=./momentweave_exports`. If your `DATABASE_URL`, `UPLOAD_DIR`, or `MOMENTWEAVE_EXPORT_DIR` refers to an absolute path, check that path rather than duplicating the database. Do not overwrite the existing database without a backup. Stop Phase 3 before starting Phase 4 on the same ports.

## 2. Launch backend

```cmd
conda activate proofmint
cd /d D:\hackathons\proofmint-phase4\proofmint-ai\backend
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8000
```

Expected: **21 passing Python tests** in the test environment used for packaging. Deprecation warnings related to FastAPI `on_event` are nonblocking. No need to reinstall `requirements-voice.txt` if it already works in your Conda environment. For first-time installations only, see the main README.

**Critical:** retain the same `RECEIPT_SIGNING_SECRET` from Phase 3. Changing it will invalidate verification of older HMAC receipts and previously embedded watermark tags. Keep `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` set to your functioning *sandbox merchant* app. Never paste these values into messages or screenshots.

## 3. Launch frontend

In a second terminal:

```cmd
cd /d D:\hackathons\proofmint-phase4\proofmint-ai\frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000/moments`, and `http://localhost:3000/voice`. Optional check: `npm run build` and `npx tsc --noEmit`. **The frontend build was not executed in the packaging environment** because npm packages were not installed there; verify locally.

## 4. Test the Phase 4 provenance panel

1. Open your previously uploaded 30-second demo video (if you copied the database and `uploads` folder). Otherwise upload `ProofMint_MomentGraph_Test_30s.mp4` again and assert that you own the demo content.
2. Under **03 · Moments & provenance**, choose any moment card. Existing Phase 3 hash comparison and PayPal checkout are unchanged.
3. **AKAZE:** Select an image from that moment or a slightly resized/re-encoded screenshot under **AKAZE: compare**. The response provides keypoint counts, Lowe-ratio matches, RANSAC inliers, and a conservative candidate-match decision. Simple smooth graphics can have very few AKAZE keypoints, so a false-negative on the synthetic test video is possible. For a stronger demonstration, upload an original **textured** photo/video of a city, street, or landscape.
4. **Watermark:** Click **Download keyed watermarked PNG** on a moment card; save the generated PNG. Upload that PNG using **Verify watermark** on the SAME card. Expect `DETECTED` and typically `32/32 bits` for unmodified PNG. Compress the PNG as a 90%-quality JPEG and try again; the model is designed for this but is not guaranteed robust against all transforms. Upload an unmarked original to confirm a negative. Repeat against a DIFFERENT moment to confirm the per-moment key does not match.
5. **Narrative Graph:** Click **Show narrative relationships**. Without a MomentWeave export, the graph is labeled `OPENCV_TEMPORAL_FALLBACK` and shows chronological edges only. With an import containing `edges`, source is labeled `MOMENTWEAVE_JSON`; these are imported annotations, not freshly inferred edges.
6. **Commerce regression:** Use your verified $4.99 sandbox checkout, sign in with a *separate sandbox personal account*, and verify the receipt. You do NOT need to make another payment merely to test watermarking.

## 5. MomentWeave JSON integration (without proprietary code)

Upload a MomentWeave JSON alongside a **new** video, with 3–5 sorted, non-overlapping moments. Example for a 30-second source:

```json
{
  "moments": [
    {"start_ms":0,"end_ms":7500,"title":"Opening","description":"Introduction","emotion":"Curiosity","narrative_role":"setup"},
    {"start_ms":7500,"end_ms":15000,"title":"Momentum","description":"Scene builds","emotion":"Anticipation","narrative_role":"rising_action"},
    {"start_ms":15000,"end_ms":22500,"title":"Climax","description":"Decisive highlight","emotion":"Excitement","narrative_role":"climax"},
    {"start_ms":22500,"end_ms":30000,"title":"Resolution","description":"Ending scene","emotion":"Calm","narrative_role":"resolution"}
  ],
  "edges": [
    {"source_index":0,"target_index":1,"relation":"builds_to"},
    {"source_index":1,"target_index":2,"relation":"culminates_in"},
    {"source_index":2,"target_index":3,"relation":"resolves_to"}
  ]
}
```

**Important:** This JSON is an illustrative contract, **not actual MomentWeave inference**; the emotions shown are placeholders. The existing adapter only reads `moments` and binds each supplied segment to an *approximate* nearest locally sampled keyframe. The graph endpoint separately reads the same export `edges` and binds indices to persisted moment IDs. The JSON schema is source-agnostic. Only use original or appropriately licensed annotations; do not claim this application executes any third-party proprietary analysis.

## 6. New REST API endpoints

All also appear in `http://localhost:8000/docs`.

| Method | Endpoint | Function |
| --- | --- | --- |
| POST | `/api/moments/{id}/verify-akaze` | Multipart `file`: AKAZE ratio + RANSAC geometric evidence |
| GET | `/api/moments/{id}/marked-frame` | Download per-moment **marked still PNG** |
| POST | `/api/moments/{id}/verify-watermark` | Multipart `file`: verify secret-keyed DCT QIM still-frame watermark |
| GET | `/api/videos/{id}/narrative-graph` | Indexed MomentWeave graph or plainly labeled temporal fallback |

**Security / limitations:** Local demo only. Endpoints are currently unauthenticated, including marked-frame download. Never deploy publicly with user-owned videos without authenticated access, authorization to mint marks, secure artifact delivery, key rotation, rate limiting, audit logs, webhook verification and legal rights review. HMAC watermark tags link to locally supplied moment identifiers; these are neither publicly verifiable C2PA provenance nor proof of copyright ownership. The algorithm watermarks a **single image frame**, not the entire MP4. AKAZE does **not** embed a watermark. The watermark may fail on crops, large resizes, low quality JPEG and adversarial edits. Source keyframes are downsampled JPEGs; matching those against arbitrary frames is not guaranteed.

## 7. CI-style checks

```cmd
conda activate proofmint
cd /d D:\hackathons\proofmint-phase4\proofmint-ai\backend
python -m pytest -q
python -m pip check
```

Use the `test_phase4.py` tests as a reproducible starting benchmark; also collect metrics on real sample clips (true positives, false positives, transformed-image recall and latency) before quoting robustness in a hackathon presentation.
