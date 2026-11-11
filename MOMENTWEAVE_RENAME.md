# ProofMint AI — independent MomentWeave namespace

**MomentWeave** is the name of this project's open JSON moment-annotation interface. It is not a claim that any external proprietary model, algorithm, dataset or trade name is included. The default moment detector remains local OpenCV motion-based candidate segmentation.

## Renamed locations

- `backend/app/momentweave_adapter.py` — import adapter
- `MOMENTWEAVE_EXPORT_DIR=./momentweave_exports` — local export directory
- `momentweave_json` — optional multipart upload field to `POST /api/videos`
- `momentweave_export_used` — response flag
- `momentweave-export-v1` — version for **new** user-imported annotations
- `MOMENTWEAVE_JSON` / `MOMENTWEAVE_EXPORT` — narrative graph provenance labels
- Web UI and public documentation refer to MomentWeave, not third-party brands.

## Upgrade existing local installation without losing receipts

1. Stop backend and frontend, back up the entire project and database.
2. Unzip into a **new** folder. Copy your existing `backend/.env`, `backend/proofmint.db`, and `backend/uploads` into the new backend directory.
3. In `.env`, set `MOMENTWEAVE_EXPORT_DIR=./momentweave_exports`. Remove any outdated export-directory environment variable. Keep `RECEIPT_SIGNING_SECRET` and PayPal sandbox settings unchanged.
4. If your prior installation has JSON exports in a differently named folder, copy those files into `backend/momentweave_exports` using the provided script below. Do not change historical signed receipts or database payment IDs. Historical `analysis_version` values may retain their original source labels because altering previously signed data would invalidate signatures or obscure provenance.
5. Restart and test `GET /api/videos`, `/api/videos/{id}/narrative-graph`, `POST /api/videos` with optional `momentweave_json`, and the previous receipt verification flow.

From the new project root, in PowerShell:

```powershell
.\scripts\migrate-moment-exports.ps1 -SourceDir "D:\path\to\existing\export-folder"
```

**Security and ownership:** Renaming code or annotations does not confer ownership of any third-party algorithms. Do not copy proprietary code, private datasets or model weights without authorization.

## Windows terminal commands for your current Phase 4 installation

Extract the new ZIP to `D:\hackathons\proofmint-momentweave\proofmint-ai`. Stop both running servers first. In PowerShell (adjust paths if needed):

```powershell
$old = 'D:\hackathons\proofmint-phase4\proofmint-ai\backend'
$new = 'D:\hackathons\proofmint-momentweave\proofmint-ai\backend'
Copy-Item "$old\.env" "$new\.env" -Force
if (Test-Path "$old\proofmint.db") { Copy-Item "$old\proofmint.db" "$new\proofmint.db" -Force }
if (Test-Path "$old\uploads") { Copy-Item "$old\uploads" "$new\uploads" -Recurse -Force }
# Move only licensed JSON exports from your previous configured directory:
# & 'D:\hackathons\proofmint-momentweave\proofmint-ai\scripts\migrate-moment-exports.ps1' -SourceDir 'D:\path\to\old\exports'
notepad "$new\.env"
```

In Notepad, set `MOMENTWEAVE_EXPORT_DIR=./momentweave_exports`, retain the same signing secret and sandbox credentials, and remove the obsolete export-dir setting. New upload JSON field is `momentweave_json`; older client scripts must be adjusted.

```powershell
conda activate proofmint
cd D:\hackathons\proofmint-momentweave\proofmint-ai\backend
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd D:\hackathons\proofmint-momentweave\proofmint-ai\frontend
Copy-Item .env.local.example .env.local
npm install
npm run build
npm run dev
```

The frontend package includes the three previously corrected Next.js client directive and internal-link fixes, but its production build still needs to be executed on Windows. Existing database rows and receipts are not rewritten.
