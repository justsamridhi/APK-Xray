# Backend integration validation

Issue #7 is a validation spike, not a production integration. The harness in
`validation/validate_integrations.py` checks the two proposed boundaries without
adding either dependency to the application:

```powershell
python backend\validation\validate_integrations.py --apk path\to\fixture.apk
```

Use the repository's selected Python interpreter or a disposable virtual
environment. Androguard is optional for the harness, but is required for the
APK extraction check:

```powershell
python -m pip install androguard
```

The Gemma check is a dry run by default. To exercise a compatible service,
provide an endpoint explicitly:

```powershell
$env:GEMMA4_ENDPOINT = "https://your-provider.example/v1/chat/completions"
$env:GEMMA4_API_KEY = "..."
python backend\validation\validate_integrations.py --apk path\to\fixture.apk --gemma-endpoint $env:GEMMA4_ENDPOINT
```

The endpoint must return JSON containing a structured object under `claims`,
or an explicit `structured_output` object. The harness never sends a request
unless `--gemma-endpoint` is supplied, never logs the API key, and never stores
APK contents.

## Validation decision record

- **Androguard boundary:** keep it behind a small adapter that returns
  normalized metadata and permissions. Pin and test the chosen version before
  production use; parser exceptions must become explicit API errors.
- **Gemma 4 boundary:** keep the model behind a provider-neutral client that
  accepts deterministic facts and requires schema-validated JSON. Do not let
  model output change the score or rule severity.
- **Runtime:** the repository does not yet mandate a Python version or model
  runtime. The command records the interpreter version and dependency versions
  so the decision can be made from observed results.
- **Open risks:** model endpoint availability and structured-output support,
  prompt/output size limits, latency, memory usage, sensitive APK metadata
  handling, and malformed or unsupported model responses.

No production dependency is introduced by this spike.
