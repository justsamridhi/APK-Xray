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
- `GET /api/report`

Accepted uploads must have an `.apk` extension and an accepted APK or binary
content type. The default maximum upload size is 50 MiB.

## Configuration

Configuration is read from the process environment by `backend/config.py`.

In **local development**, the `.env` file in the **project root** (not `backend/.env`)
is automatically loaded via `python-dotenv` when `load_settings()` is first called.
Production deployments should inject environment variables directly via container
orchestration or hosting platform environment configuration.

`.env` is listed in `.gitignore` — never commit it.

| Variable | Default | Behavior |
| --- | --- | --- |
| `APK_XRAY_MAX_UPLOAD_BYTES` | `52428800` | Positive integer upload limit. |
| `GEMMA4_ENDPOINT` | unset | Enables the optional Gemma call when non-empty. |
| `GEMMA4_API_KEY` | unset | Required by the Gemma adapter; never log or commit it. |
| `APK_XRAY_GEMMA_TIMEOUT` | `90` | Positive timeout in seconds. The adapter retries once on timeout only. |
| `APK_XRAY_GEMMA_DIAGNOSTICS` | unset | Set to `1` only for redacted live-verifier part diagnostics. |
| `SENTRY_DSN` | unset | Sentry project DSN. When set, enables error tracking and performance tracing. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Fraction of requests to trace (0.0 to 1.0). Use `1.0` for local testing. |

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
| `APKX-NET-001` | `INTERNET` permission | 12 | low |
| `APKX-SMS-001` | `READ_SMS` or `SEND_SMS` | 25 | high |
| `APKX-MIC-001` | `RECORD_AUDIO` | 18 | medium |
| `APKX-LOC-001` | fine/coarse location | 12 | medium |
| `APKX-EXP-001` | exported component without permission | 20 | high |

The score is the capped sum of matched rule points. No capability-chain
scoring rule is currently implemented.

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

## Sentry tracing

Optional stage-level performance and error tracing via the Sentry SDK.

### Environment variables

| Variable | Default | Behaviour |
| --- | --- | --- |
| `SENTRY_DSN` | unset | Enables Sentry when set to a non-empty DSN string. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Fraction of transactions to sample (`0.0`–`1.0`). `0.0` disables performance traces; errors are still captured when a DSN is set. |

When `SENTRY_DSN` is absent or empty the SDK is not initialised and the
application behaves identically to a build without Sentry.

### Local setup (without real credentials)

Leave both variables unset or set `SENTRY_DSN=` in your environment.
All tests run completely offline and never contact a Sentry endpoint.

### Real analysis trace structure

Each `POST /api/upload` request creates a Sentry transaction with the
following child spans:

```
POST /api/upload                             ← FastAPI transaction
  apk.parse       Parse APK manifest         ← Androguard extraction
  apk.report      Build and validate report  ← scoring + AI agent lifecycle + schema
    ai.lifecycle  AI explanation workflow    ← agent lifecycle & orchestration
      gen_ai.generate  Gemma 4 generate      ← actual HTTP call to Gemini API
      gen_ai.validate  Validate response     ← JSON parsing + token metrics
      ai.validate_claims Validate claims     ← claim structure & citation validation
    ai.fallback   AI explanation fallback    ← fallback path when AI is unconfigured
  apk.persist     Persist report to SQLite   ← SQLite write
```

The `gen_ai.*` spans are created inside `backend/gemma.py` at the exact
network/model call boundary, while `ai.lifecycle` and `ai.validate_claims` trace
the agent decision flow and claim verification in `backend/report_builder.py`.

### GenAI & Agent attributes recorded

| Attribute | Source | Notes |
| --- | --- | --- |
| `gen_ai.system` | constant | `"google_gemini"` |
| `gen_ai.agent.name` | constant | `"apk_xray_explainer"` (Sentry Agent module key) |
| `gen_ai.operation.name` | constant | `"generate"` |
| `gen_ai.request.model` | constant | `"gemma-4"` |
| `gen_ai.usage.input_tokens` | `usageMetadata.promptTokenCount` | `None` when absent |
| `gen_ai.usage.output_tokens` | `usageMetadata.candidatesTokenCount` | `None` when absent |
| `gen_ai.usage.total_tokens` | `usageMetadata.totalTokenCount` | `None` when absent |
| `apk_xray.retry_count` | runtime | `0` = no retry, `1` = one retry occurred |
| `apk_xray.token_source` | runtime | `"response_metadata"` or `"unavailable"` |
| `apk_xray.claim_count` | runtime | Total claims emitted by AI |
| `apk_xray.kept_claim_count` | runtime | Validated claims citing known evidence |
| `apk_xray.rejected_claim_count` | runtime | Claims rejected due to invalid structure/citations |
| `apk_xray.validation_outcome` | runtime | `"ok"`, `"partial_rejection"`, `"full_rejection"` |
| `apk_xray.findings_count` | runtime | Total deterministic findings evaluated |
| `apk_xray.risk_score` | runtime | Deterministic risk score passed to agent |
| `outcome` | runtime | `ok`, `timeout`, `rate_limit`, `provider_error`, `network_error`, `invalid_json`, `contract_violation`, `unconfigured` |

Token counts are measured from the Gemini API `usageMetadata` field only.
They are never estimated. Cost is not calculated.

### Timeout and failure behaviour

When Gemma times out, the `gen_ai.generate` span records `outcome=timeout`
and `apk_xray.retry_count=1`. The report is returned with all deterministic
findings intact; only `ai.status` changes to `"error"`. The API returns
HTTP 200, not a 500.

### Privacy controls

The `scrub_event` function in `backend/sentry_setup.py` is registered as both
`before_send` and `before_send_transaction`.  Before any event leaves the
process it removes:

- Request body, URL, query string, cookies, and environment block
- Sensitive headers: `Authorization`, `x-goog-api-key`, `x-api-key`, `Cookie`,
  and others (matched case-insensitively)
- Exception `value` strings and all local variable snapshots (`frame.vars`)
- All breadcrumbs
- `extra` and `user` blocks
- All SDK contexts except `trace`
- Transaction names normalised (`/api/report/<id>` → `/api/report/{report_id}`)
- Span `data` filtered to an explicit allowlist — only operational and GenAI
  attributes survive; prompts, model responses, package names, evidence,
  and paths are stripped unconditionally

`send_default_pii=False` and `max_request_body_size="never"` are set at
initialisation as a first-layer defence; `scrub_event` is a second,
independent layer applied to every event.

### Manual dashboard verification

After configuring a real DSN and uploading a test APK:

1. Confirm the transaction appears under the configured project.
2. Verify the span tree: `apk.parse` → `apk.report` → `gen_ai.generate` →
   `gen_ai.validate` → `apk.persist`.
3. Check that `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
   `apk_xray.retry_count`, and `apk_xray.token_source` appear on
   `gen_ai.generate`.
4. Verify that no request body, filename, path, API key, package name,
   evidence array, or raw model response appears anywhere in the event.
5. Confirm the transaction name is `POST /api/upload`.
6. Reproduce a timeout with a short `APK_XRAY_GEMMA_TIMEOUT` and confirm
   `outcome=timeout`, `apk_xray.retry_count=1` on `gen_ai.generate`.

No automated test covers live Sentry dashboard output; all claims above
require manual verification with real credentials.

## Limitations

This is static declaration analysis. It cannot establish runtime behavior,
malware presence, exploitability, or a complete security assessment. The
exposure score is deterministic and explainable, but it is not an effectiveness
or accuracy metric. Gemma availability, response quality, latency, endpoint
support, and credential configuration remain external dependencies.
