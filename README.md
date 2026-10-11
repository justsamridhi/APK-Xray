# APK-Xray

APK-Xray is an evidence-first Android static-analysis application. It accepts
an APK, reads its manifest with Androguard, and returns a reviewable report
without installing, launching, or executing the package.

## What is implemented

The current workflow includes:

- a React/Vite frontend for APK selection, upload progress, report rendering,
  evidence drawers, and English/Hindi explanation display;
- a FastAPI backend at `POST /api/upload`;
- archive and upload-size validation before parsing;
- normalized package metadata, permissions, components, and stable evidence IDs;
- deterministic exposure rules and a capped score owned by the backend;
- schema-validated version `1.0` reports;
- evidence-linked claims with `Can`, `Could`, and `Cannot Prove` classifications;
- an optional Google Gemma 4 explanation adapter that receives normalized
  evidence only; and
- explicit AI states for verified, unavailable, and error responses.

Gemma can provide explanations and claims, but it cannot create evidence,
change deterministic findings, alter severity, or modify the score. If Gemma is
not configured or fails, the deterministic report remains available.

## Architecture

```text
APK upload
    -> FastAPI validation
    -> Androguard static manifest parser
    -> deterministic rules and exposure score
    -> optional evidence-only Gemma explanation
    -> JSON Schema validation
    -> frontend report and evidence views
```

The frontend renders the report returned directly from `/api/upload`. Reports
are not retained in a process-wide backend slot, so one analysis cannot be
retrieved by a later, unrelated request.

## Setup

### Backend

Use the repository virtual environment or another supported Python environment:

```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.api:app --reload
```

The backend listens on `http://127.0.0.1:8000` by default. Detailed backend
configuration, testing, and safe live-verification instructions are in
[backend/README.md](backend/README.md).

### Frontend

```powershell
Set-Location frontend
npm ci
npm run dev
```

The Vite development server serves the frontend locally. Set
`VITE_API_UPLOAD_URL` or `VITE_API_REPORT_URL` only when the API is not available
at the default same-origin paths.

## Verification

Backend tests require the backend and parser import paths:

```powershell
$env:PYTHONPATH = "E:\APK-Xray\backend;E:\APK-Xray\backend\parser"
& E:\APK-Xray\.venv\Scripts\python.exe -m pytest backend -v
```

Frontend checks run from `frontend\`:

```powershell
npm test
npm run typecheck
npm run lint
npm run build
```

The automated suites use mocked Gemma transport and isolate the API key from
tests. A live Gemma request is an optional manual check and is not part of the
offline test suite. A previous live run has been reported, but repeatability
has not been established by that single observation.

## Limitations and safety

APK-Xray reports declarations and deterministic static indicators. It does not
prove runtime behavior, malware presence, exploitability, or overall security.
The score is a documented exposure heuristic, not a security guarantee.

Uploaded APKs are treated as untrusted archives and are never installed or
executed. Gemma receives normalized metadata and evidence, not the APK itself.
Model output is rejected when it is malformed, incomplete, or cites unknown
evidence. Credentials must remain in the local environment and must never be
committed or logged.

The current deterministic implementation covers network, SMS, microphone,
location, and unprotected exported-component indicators. Capability-chain
support is represented in the report contract, but no C1/C2 detection rules
are currently implemented in `backend/scoring.py`.
