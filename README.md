# APK-Xray

### Know what an Android app can access before you install it.

**APK-Xray** is an evidence-first Android static-analysis application that helps users inspect an APK before installing it. It extracts manifest information, evaluates deterministic security rules, and generates a structured report containing findings, an exposure score, and supporting evidence.

An optional Google Gemma 4 integration explains the findings in plain English and Hindi. The model acts as an explanation layer; it does not determine the security score, change rule severity, or replace the deterministic analysis engine.

> **Core principle: Rules decide. Language explains. Evidence supports every claim.**

**Repository:** [github.com/justsamridhi/APK-Xray](https://github.com/justsamridhi/APK-Xray)

---

## Table of Contents

- [The Problem](#the-problem)
- [Our Solution](#our-solution)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [End-to-End Workflow](#end-to-end-workflow)
- [Advantages](#advantages)
- [Limitations](#limitations)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Verification and Testing](#verification-and-testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

## The Problem

Android APKs can be distributed through messaging platforms, SMS, and websites outside trusted app stores. Fraudulent applications may impersonate traffic-challan services, utility providers, or KYC updates.

Users may struggle to understand the implications of requested permissions and may have difficulty verifying security warnings from tools that provide only a verdict.

APK-Xray addresses three related challenges:

- **Limited transparency:** A security verdict without supporting evidence is difficult to verify.
- **Technical complexity:** Permissions and application components can be difficult for non-technical users to interpret.
- **Overstated conclusions:** A requested permission or suspicious indicator does not, by itself, prove malicious intent.

Examples of reporting on APK-related scams in India:

- [BOOM — Fake RTO e-challan message on WhatsApp](https://www.boomlive.in/decode/scamcheck/fake-rto-e-challan-message-on-whatsapp-a-growing-apk-scam-29919)
- [The Hitavada — Do not download that e-Challan](https://www.thehitavada.com/Encyc/2025/6/9/Do-not-download-that-e-Challan!.html)
- [Moneylife — From e-Challan to APK traps](https://www.moneylife.in/article/fraud-alert-from-echallan-gas-bill-updates-to-apk-traps-how-malware-scams-are-draining-bank-accounts/79996.html)

These articles provide context for the problem; they do not establish APK-Xray's detection accuracy.

## Our Solution

APK-Xray provides a structured, reviewable report instead of relying on a black-box verdict.

The application:

1. Accepts an APK through a web interface.
2. Validates the uploaded file before parsing.
3. Extracts supported Android manifest information using Androguard.
4. Applies deterministic rules to identify supported security-relevant indicators.
5. Calculates an exposure score using backend-controlled scoring logic.
6. Optionally generates evidence-linked explanations using Gemma.
7. Validates the report structure and displays the findings and supporting evidence.

The result describes observable capabilities and limitations, rather than claiming to prove that an application is malicious or safe.

## Key Features

- **Static APK analysis:** Inspects APK contents without installing or launching the application.
- **Manifest parsing:** Extracts package metadata, permissions, and application components.
- **Deterministic rule engine:** Evaluates implemented security indicators using identifiable rules.
- **Exposure scoring:** Produces a capped score with a breakdown based on the rules.
- **Evidence-linked findings:** Connects findings and explanation claims to evidence identifiers.
- **Structured reports:** Validates reports against the versioned JSON Schema (`1.0`).
- **AI-assisted explanations:** Optionally uses Google Gemma 4 to explain findings in English and Hindi.
- **AI output validation:** Rejects malformed model responses and claims referencing unknown evidence identifiers.
- **Graceful AI failure handling:** Keeps the deterministic report available when the explanation service is unavailable or returns an error.
- **Interactive frontend:** Supports APK selection, upload progress, report rendering, evidence drawers, and language switching.
- **Sentry Agent Tracing:** Full-stack observability into the AI explainer agent lifecycle, claim structure validation, token consumption, fallback paths, and distributed transactions without leaking secrets or APK binaries (see [Sentry Tracing](backend/README.md#sentry-tracing)).
- **Automated tests:** Provides regression tests for supported backend and frontend functionality.

## Technology Stack

### Frontend

| Technology | Purpose |
|---|---|
| React | Component-based user interface and report rendering |
| TypeScript | Type safety and maintainable frontend code |
| Vite | Frontend development server and build tooling |
| CSS | Interface styling, layout, and themes |
| Browser session storage | Temporary report fallback when navigating between report views |

### Backend

| Technology | Purpose |
|---|---|
| Python | Core backend and analysis implementation |
| FastAPI | HTTP API, request handling, and upload workflow |
| Uvicorn | ASGI server for running the API |
| Androguard | Android APK and manifest analysis |
| Deterministic Python rules | Security indicator evaluation and exposure scoring |
| JSON Schema | Report structure and contract validation |
| Google Gemma 4 API | Optional evidence-based explanation generation |
| Sentry SDK | Privacy-safe OpenTelemetry GenAI agent tracing and observability |
| Pytest | Backend testing and regression checks |

### Engineering and development tools

- Git and GitHub for version control and collaboration.
- npm for frontend dependency management and scripts.
- Automated backend and frontend checks for regression prevention.

**Architecture note:** The current documented workflow uses synchronous API processing and does not require Celery, Redis, or MongoDB. Asynchronous task processing and scalable report storage are planned improvements, not assumed to be implemented features.

## System Architecture

```text
+--------------------------------------------------+
|                  Frontend                        |
|            React + TypeScript + Vite             |
|                                                  |
|       APK Upload | Report | Evidence Drawer      |
+-------------------------+------------------------+
                          |
                          | HTTP request
                          v
+--------------------------------------------------+
|                  FastAPI Backend                 |
|                                                  |
|  1. Upload and archive validation                |
|  2. APK parsing with Androguard                  |
|  3. Metadata normalization and evidence IDs      |
|  4. Deterministic rules and exposure scoring     |
|  5. Optional Gemma explanation adapter           |
|  6. Report schema validation                     |
+-------------------------+------------------------+
                          |
                          v
+--------------------------------------------------+
|                Structured Report                 |
|                                                  |
|  Findings | Score | Evidence | Explanations      |
+-------------------------+------------------------+
                          |
                          v
+--------------------------------------------------+
|               Frontend Presentation              |
|                                                  |
|       Reviewable report in English and Hindi     |
+--------------------------------------------------+
```

### Component responsibilities

**Frontend:** Provides the upload interface, presents analysis results, displays supporting evidence, and renders available English and Hindi explanations.

**Backend API:** Validates uploads, coordinates parsing and scoring, optionally requests AI explanations, validates the report, and returns structured results.

**Static analysis engine:** Extracts supported manifest information and applies deterministic security rules. It is the source of the findings and exposure score.

**Gemma explanation layer:** Receives normalized evidence and generates human-readable explanations. It does not independently determine the risk score or severity.

**Report validation:** Enforces the expected report structure before the report is accepted by the application.

## End-to-End Workflow

### Step 1 — Upload

The user selects an APK in the React frontend. The file is submitted to `POST /api/upload`.

### Step 2 — Validate

FastAPI checks the upload and archive before parsing. Invalid or unreadable files should be rejected with an appropriate error response.

### Step 3 — Parse

Androguard extracts supported Android manifest information, including package metadata, permissions, and application components.

### Step 4 — Normalize evidence

The parser normalizes extracted information and associates it with stable evidence identifiers. These identifiers allow findings and explanations to refer to specific pieces of extracted data.

### Step 5 — Evaluate rules

The deterministic rule engine checks the available evidence against implemented security indicators. Triggered rules generate findings, and the backend calculates the exposure score.

### Step 6 — Generate optional explanations

If Gemma is configured, the application sends normalized evidence to the model for explanation generation. The original APK is not intentionally sent to the explanation adapter.

If AI is unavailable or fails, the deterministic analysis remains available.

### Step 7 — Validate the report

The report is checked against the versioned JSON Schema. Model-generated claims are also checked against the application's evidence and output contract.

### Step 8 — Display results

The frontend displays the exposure score, findings, rule identifiers, evidence details, and available English/Hindi explanations.

The user can inspect the evidence behind a finding instead of relying solely on the overall score.

### API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/upload` | Upload and analyse an APK |
| `GET` | `/api/report` | Retrieve the latest report held by the backend |

The current frontend stores the returned report in session storage and uses the report endpoint when opening the report route, with a stored-report fallback.

The latest-report backend design is intended for local, single-user use. Shared deployments require per-session or per-user report handling and appropriate access controls.

## Advantages

### 1. Evidence-first reporting

Findings are designed to reference extracted evidence. This improves transparency and allows users and developers to review the basis of a security warning.

### 2. Separation of detection and explanation

The deterministic engine controls findings and scoring, while Gemma provides explanations. This reduces the risk of allowing generated text to directly determine a security verdict.

### 3. No application execution

APK-Xray is designed to inspect uploaded packages statically rather than installing or launching them. This avoids the need to run an unknown application as part of the analysis workflow.

### 4. Understandable explanations

English and Hindi explanations make technical findings more accessible to a wider range of users.

### 5. Structured and testable output

A versioned report schema, stable evidence identifiers, and automated tests support consistency and regression testing.

### 6. Graceful handling of AI failure

The optional AI layer does not need to be available for the deterministic findings and exposure score to remain useful.

### 7. Modular design

The frontend, backend API, parser, rule engine, explanation adapter, and report contract have distinct responsibilities. This makes individual components easier to maintain and extend.

## Limitations

APK-Xray is an assistive static-analysis tool, not a complete malware detection or certification system.

### 1. Static analysis cannot prove runtime behavior

The tool examines static declarations and supported indicators. It cannot establish every action an application may take when executed, including behavior triggered dynamically at runtime.

### 2. Detection coverage is limited

The deterministic rules currently cover supported network, SMS, microphone, location, and unprotected exported-component indicators. Detection quality depends on the rules actually implemented in `backend/scoring.py`.

Capability-chain support exists in the report contract, but C1/C2 detection rules are not currently implemented.

### 3. A risk indicator does not prove malicious intent

Legitimate applications may request sensitive permissions or expose components for valid reasons. A finding indicates a capability or pattern that merits review, not definitive proof of malicious behavior.

### 4. Exposure scores are heuristic

The score is based on deterministic rules and is not a probability of malware or a security guarantee. Score calibration against a documented dataset remains future work.

### 5. AI explanations can be inaccurate

Evidence-ID validation confirms that referenced identifiers exist; it does not prove that every generated statement is factually correct. AI explanations should remain subordinate to the extracted evidence and deterministic findings.

### 6. Parser and archive risks remain

Uploaded APKs are untrusted input. Static analysis avoids installing or launching them but does not eliminate every risk associated with parsing malformed archives or exploiting vulnerable dependencies.

### 7. Current report storage is not multi-user isolation

The latest-report API is suitable for local, single-user use. Concurrent or public deployments require isolated report retrieval and appropriate access controls.

## Getting Started

### Prerequisites

- Python installed and compatible with the backend dependencies.
- Node.js and npm installed.
- Git installed if cloning the repository.

### 1. Clone the repository

```powershell
git clone https://github.com/justsamridhi/APK-Xray.git
Set-Location APK-Xray
```

### 2. Set up the backend

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```powershell
python -m pip install -r backend\requirements.txt
```

Configure the Python import paths and start the API:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\backend;$PWD\backend\parser"
python -m uvicorn backend.api:app --reload
```

The backend is available at:

- API base URL: `http://127.0.0.1:8000`
- Interactive API documentation: `http://127.0.0.1:8000/docs`

Keep the backend terminal running.

### 3. Set up the frontend

Open a second terminal from the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open the local URL printed by Vite.

If the frontend and backend use different origins, configure the API URLs and the backend's CORS settings for your development environment.

## Configuration

### Optional Gemma integration

The AI explanation layer can be enabled using environment variables.

| Variable | Purpose |
|---|---|
| `GEMMA4_ENDPOINT` | Configured Gemma inference endpoint |
| `GEMMA4_API_KEY` | API credential for the configured endpoint |
| `APK_XRAY_GEMMA_TIMEOUT` | Optional request timeout in seconds |
| `APK_XRAY_GEMMA_DIAGNOSTICS` | Optional diagnostic setting; set to `1` for live checks when needed |

See [`backend/.env.example`](backend/.env.example) for the configuration template.

Set the variables in the same terminal used to launch the backend:

```powershell
$env:GEMMA4_ENDPOINT = "YOUR_CONFIGURED_GEMMA_ENDPOINT"
$env:GEMMA4_API_KEY = Read-Host "Enter API key"
```

Replace the endpoint placeholder with the endpoint supported by your provider. Restart the backend after changing its environment.

**Never commit API keys or real `.env` files.** Do not place secrets in frontend `VITE_*` variables because those values may be exposed to browser code.

## Verification and Testing

### Backend tests

Run from the repository root:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\backend;$PWD\backend\parser"
& .\.venv\Scripts\python.exe -m pytest backend -v
```

### Frontend checks

Run from `frontend\`:

```powershell
npm test
npm run typecheck
npm run lint
npm run build
```

These frontend commands require the corresponding scripts to be defined in `frontend/package.json`.

### Offline tests and live inference

Automated tests use mocked Gemma transport and do not require a live provider request or real API key. Passing tests verify only the behaviors covered by those tests.

Live Gemma inference should be tested separately using a known APK and a correctly configured endpoint.

An AI status of `verified` indicates that the generated claims passed the configured contract and evidence-ID checks. It does not mean that the APK is safe or that every generated statement is factually correct.

## Roadmap

The following features are planned and should not be treated as implemented:

- Additional rules for boot persistence, accessibility services, drawing over other apps, device administration, package installation, notification access, and contacts/call-log access.
- Implementation and validation of C1/C2 capability-chain detection.
- Exposure-score calibration against a documented set of benign and suspicious APKs.
- A reproducible evaluation suite with published results and documented limitations.
- A message-to-purpose comparison between a scam message's claims and an APK's declared capabilities.
- Improved handling of large uploads and analysis latency.
- Asynchronous task processing and scalable report storage.
- Stronger regression tests for report consistency and evidence-grounded explanations.
- Per-session report handling and access controls for shared deployments.

## Contributing

Contributions are welcome.

1. Check existing GitHub issues or open an issue describing the proposed change.
2. Create a branch from `main`.
3. Make focused changes and add relevant tests.
4. Run the appropriate backend and frontend checks.
5. Open a pull request describing the change and its verification.

Please do not push directly to `main`. Never commit APKs containing sensitive data, API keys, or real environment files.

## Security

If you discover a vulnerability, report it privately through GitHub Security Advisories where available. Avoid publishing exploit details or sensitive data in public issues.

## License

This project is released under the MIT License. See [`LICENSE`](LICENSE) for the full terms.

Gemma is accessed through the configured provider's API and is subject to that provider's applicable terms and data-handling policies.
