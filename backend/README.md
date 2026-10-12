# APK-Xray backend

The backend is a FastAPI service for safe, static APK analysis. It validates
the upload, reads the APK archive with Androguard, applies deterministic rules,
optionally requests an evidence-only Gemma explanation, and validates the
resulting report against `schema/report.schema.json`.

Uploaded APKs are temporary files. The parser never installs, launches, or
executes an APK.

## Installation and operation

From the repository root, use the selected Python environment:

```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.api:app --reload
```

The service exposes:

- `GET /api/health`
- `POST /api/upload` with multipart field `file`

Accepted uploads must have an `.apk` extension and an accepted APK or binary
content type. The default maximum upload size is 50 MiB. ZIP metadata is
validated before parsing: unsafe paths, entry count, expanded-size, and
compression-ratio limits are rejected without extracting the archive.

## Configuration

Configuration is read from the process environment by `backend/config.py`.
The application does not automatically load a `.env` file.

| Variable | Default | Behavior |
| --- | --- | --- |
| `APK_XRAY_MAX_UPLOAD_BYTES` | `52428800` | Positive integer upload limit. |
| `APK_XRAY_MAX_ZIP_ENTRIES` | `1000` | Maximum ZIP entries accepted before parsing. |
| `APK_XRAY_MAX_TOTAL_UNCOMPRESSED_BYTES` | `209715200` | Maximum combined expanded ZIP-entry size. |
| `APK_XRAY_MAX_ENTRY_UNCOMPRESSED_BYTES` | `52428800` | Maximum expanded size of one ZIP entry. |
| `APK_XRAY_MAX_COMPRESSION_RATIO` | `100` | Maximum expanded-to-compressed ratio for an entry or archive. |
| `GEMMA4_ENDPOINT` | unset | Enables the optional Gemma call when non-empty. |
| `GEMMA4_API_KEY` | unset | Required by the Gemma adapter; never log or commit it. |
| `APK_XRAY_GEMMA_TIMEOUT` | `90` | Positive timeout in seconds. The adapter retries once on timeout only. |
| `APK_XRAY_GEMMA_DIAGNOSTICS` | unset | Set to `1` only for redacted live-verifier part diagnostics. |

Copy [`.env.example`](.env.example) as a reference only; environment files
containing credentials must remain local. If Gemma is not configured, reports
use `ai.status = "unavailable"`. HTTP, timeout, parsing, contract, and
validation failures leave the deterministic report available and use
`ai.status = "error"`. Timeout failures use the safe `gemma_timeout` error code
in the AI status message.

The deterministic score and rule findings are calculated before Gemma is
called. Gemma cannot add evidence, change findings, alter severity, or modify
the score. Its claims must use supplied evidence IDs, and its explanations
must contain non-empty English (`en`) and Hindi (`hi`) text.

## Tests

Run the full backend suite from the repository root:

```powershell
Set-Location E:\APK-Xray
$env:PYTHONPATH = "E:\APK-Xray\backend;E:\APK-Xray\backend\parser"
& E:\APK-Xray\.venv\Scripts\python.exe -m pytest backend -v
```

The shared `backend/conftest.py` fixture removes `GEMMA4_API_KEY` for every
test. Gemma-dependent tests use mocked HTTP responses and do not contact the
network. The live verifier is intentionally separate from the test suite.

## Live Gemma verification

`backend\verify_gemma_live.py` uses synthetic evidence only. It reads
`GEMMA4_ENDPOINT` and `GEMMA4_API_KEY` from the current process environment,
calls the real adapter, and validates the returned evidence IDs and
English/Hindi explanations. Configure credentials locally in the terminal;
never paste or print the key.

```powershell
Set-Location E:\APK-Xray
$env:PYTHONPATH = "E:\APK-Xray\backend;E:\APK-Xray\backend\parser"
$env:APK_XRAY_GEMMA_DIAGNOSTICS = "1"
& E:\APK-Xray\.venv\Scripts\python.exe backend\verify_gemma_live.py
Remove-Item Env:APK_XRAY_GEMMA_DIAGNOSTICS
```

The optional diagnostics print only candidate count, finish reason, part
metadata, thought-flag state, text lengths, likely JSON presence, and detected
contract keys. They do not print generated text, API keys, request headers, or
the full response. This command makes an external API request and is not run by
the offline tests.

## Deterministic rules

| Rule | Trigger | Points | Severity |
| --- | --- | ---: | --- |
| `APKX-NET-001` | `INTERNET` permission | 2 | low |
| `APKX-SMS-001` | `READ_SMS` or `SEND_SMS` | 25 | high |
| `APKX-MIC-001` | `RECORD_AUDIO` | 18 | medium |
| `APKX-LOC-001` | fine/coarse location | 12 | medium |
| `APKX-EXP-001` | non-launcher exported component without permission | 20 | high |

The score is the capped sum of matched rule points. No capability-chain
scoring rule is currently implemented.
Launcher activities are exported by design so users can open the app and are
not scored as exposure findings.

## Schema and parser

The authoritative report contract is
[`schema/report.schema.json`](schema/report.schema.json). Reports are checked
with JSON Schema validation before the API returns them. The report includes
stable IDs, app metadata, score information, findings, capability-chain slots,
claims, and optional AI status.

The parser in `parser/apk_parser.py` validates the ZIP container, extracts
package metadata, permissions, and manifest components, and emits stable
evidence IDs. Invalid, truncated, or unsupported inputs become explicit API
errors.

## Limitations

This is static declaration analysis. It cannot establish runtime behavior,
malware presence, exploitability, or a complete security assessment. The
exposure score is deterministic and explainable, but it is not an effectiveness
or accuracy metric. Gemma availability, response quality, latency, endpoint
support, and credential configuration remain external dependencies.
