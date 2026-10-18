"""Sentry SDK initialisation and privacy-safe event processing for APK-Xray.

Privacy contract
----------------
APK-Xray handles potentially sensitive application artefacts.  The following
are *never* forwarded to Sentry:

- APK bytes, filenames, or local filesystem paths
- Request or response bodies, including Gemma prompts and model responses
- API keys, credentials, or authorisation headers
- Raw evidence items, permission arrays, component names, or report contents
- Package names, report identifiers, or any APK-derived values
- Any PII collected by the SDK's default instrumentation

Permitted span attributes (explicit allowlist in ``_SPAN_DATA_ALLOWLIST``):
- Operational: ``stage``, ``outcome``, ``error_category``, ``apk_size_bytes``
- GenAI: ``gen_ai.system``, ``gen_ai.operation.name``,
  ``gen_ai.usage.input_tokens``, ``gen_ai.usage.output_tokens``,
  ``gen_ai.usage.total_tokens``, ``gen_ai.request.model``,
  ``apk_xray.retry_count``, ``apk_xray.token_source``

The ``scrub_event`` hook is registered as both ``before_send`` and
``before_send_transaction``.  It is the single chokepoint for privacy
enforcement: every event passes through it unconditionally before leaving
the process.
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger("APK_Xray.Sentry")

# ---------------------------------------------------------------------------
# Headers that must never appear in Sentry events.
# Matched case-insensitively; the set covers common variants.
# ---------------------------------------------------------------------------
_SENSITIVE_HEADER_NAMES: frozenset[str] = frozenset(
    {
        "authorization",
        "x-goog-api-key",
        "x-api-key",
        "cookie",
        "set-cookie",
        "proxy-authorization",
        "x-amz-security-token",
        "x-gemma-api-key",
    }
)

# Patterns that, if found in a string value, suggest the value is sensitive.
# One top-level (?i) flag — inline flags mid-alternation are rejected in 3.13+.
_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)"
    r"(AIza[0-9A-Za-z_\-]{35}"        # Google API key prefix
    r"|bearer\s+\S+"                   # Bearer token
    r"|api[_-]?key\s*[:=]\s*\S+"      # Generic key assignment
    r")",
)

# Explicit allowlist of span data keys permitted to leave the process.
# Everything else is stripped by ``_scrub_span_data``.
_SPAN_DATA_ALLOWLIST: frozenset[str] = frozenset(
    {
        # ---- operational ----
        "stage",
        "outcome",
        "error_category",
        "apk_size_bytes",
        # ---- GenAI (OTel semantic conventions, Sentry GenAI module) ----
        "gen_ai.system",            # provider category: "google_gemini"
        "gen_ai.operation.name",    # "chat" / "generate"
        "gen_ai.request.model",     # model identifier without credentials
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.total_tokens",
        # ---- APK-Xray-specific ----
        "apk_xray.retry_count",     # 0 = no retry, 1 = one retry occurred
        "apk_xray.token_source",    # "response_metadata" | "unavailable"
        "apk_xray.claim_count",     # number of AI claims returned
        "apk_xray.rejected_claim_count",  # claims failing structure validation
        "apk_xray.kept_claim_count",  # claims passing validation
        "apk_xray.validation_outcome",  # "ok" | "partial_rejection" | "full_rejection"
        "apk_xray.findings_count",  # number of deterministic findings
        "apk_xray.risk_score",  # integer risk score
    }
)

_INITIALISED = False


def _redact_headers(headers: Any) -> dict[str, str]:
    """Return a new headers dict with sensitive values replaced."""
    if not isinstance(headers, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str):
            continue
        if key.lower() in _SENSITIVE_HEADER_NAMES:
            result[key] = "[Filtered]"
        elif isinstance(value, str) and _SENSITIVE_VALUE_RE.search(value):
            result[key] = "[Filtered]"
        else:
            result[key] = value if isinstance(value, str) else str(value)
    return result


def _scrub_request(request: dict[str, Any]) -> dict[str, Any]:
    """Remove body, strip sensitive headers, and sanitise the URL."""
    # Drop the full URL — it may contain a package name embedded by the router.
    request.pop("url", None)
    request.pop("query_string", None)
    # Remove the request body unconditionally.
    request.pop("data", None)
    request.pop("body", None)
    request.pop("json", None)
    # Redact headers.
    if "headers" in request:
        request["headers"] = _redact_headers(request["headers"])
    # Remove cookies entirely.
    request.pop("cookies", None)
    request.pop("env", None)
    return request


def _scrub_exception(exc_info: Any) -> Any:
    """Remove values attached to exception context that may be sensitive."""
    if not isinstance(exc_info, dict):
        return exc_info
    values = exc_info.get("values")
    if not isinstance(values, list):
        return exc_info
    for exc in values:
        if not isinstance(exc, dict):
            continue
        # Strip exception message — may contain provider error details or paths.
        exc.pop("value", None)
        mechanism = exc.get("mechanism")
        if isinstance(mechanism, dict):
            mechanism.pop("data", None)
        # Remove local variable snapshots from every frame.
        stacktrace = exc.get("stacktrace")
        if isinstance(stacktrace, dict):
            frames = stacktrace.get("frames")
            if isinstance(frames, list):
                for frame in frames:
                    if isinstance(frame, dict):
                        frame.pop("vars", None)
    return exc_info


def _scrub_breadcrumbs(event: dict[str, Any]) -> None:
    """Clear all breadcrumbs — they may contain filesystem paths or bodies."""
    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        breadcrumbs["values"] = []


def _scrub_contexts(event: dict[str, Any]) -> None:
    """Remove SDK-added contexts that may include environment details."""
    contexts = event.get("contexts", {})
    # Keep only the ``trace`` context (needed for performance traces).
    safe_keys = {"trace"}
    for key in list(contexts.keys()):
        if key not in safe_keys:
            contexts.pop(key)


def _scrub_span_data(span: dict[str, Any]) -> dict[str, Any]:
    """Keep only explicitly allowlisted attributes on a span.

    The allowlist (``_SPAN_DATA_ALLOWLIST``) covers operational attributes
    and a subset of OTel GenAI semantic conventions.  Everything else —
    including any APK-derived value, token string, or provider detail that
    does not appear in the allowlist — is stripped.
    """
    data = span.get("data")
    if not isinstance(data, dict):
        return span
    span["data"] = {k: v for k, v in data.items() if k in _SPAN_DATA_ALLOWLIST}
    return span


def scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Privacy-safe Sentry before_send / before_send_transaction hook.

    Called by the SDK before every event and transaction envelope is sent.
    Returns the sanitised event, or ``None`` to drop it entirely.

    This function is the single chokepoint for privacy enforcement and is
    applied to both error events and transaction/performance envelopes.
    Unit-tested directly in ``test_sentry.py``.
    """
    # --- request block ---
    request = event.get("request")
    if isinstance(request, dict):
        event["request"] = _scrub_request(request)

    # --- exception block ---
    exception = event.get("exception")
    if exception is not None:
        event["exception"] = _scrub_exception(exception)

    # --- breadcrumbs ---
    _scrub_breadcrumbs(event)

    # --- extra / user ---
    event.pop("extra", None)
    event.pop("user", None)

    # --- contexts ---
    _scrub_contexts(event)

    # --- transaction name: normalise dynamic segments ---
    # The SDK may set the transaction name from the URL which could include
    # a report ID or package name.
    if "transaction" in event:
        txn = event["transaction"]
        if isinstance(txn, str):
            txn = re.sub(r"(/report/)[^/\s]+", r"\1{report_id}", txn)
            event["transaction"] = txn

    # --- spans inside transactions ---
    spans = event.get("spans")
    if isinstance(spans, list):
        event["spans"] = [
            _scrub_span_data(s) if isinstance(s, dict) else s
            for s in spans
        ]

    return event


def init_sentry(dsn: str | None, traces_sample_rate: float) -> None:
    """Initialise the Sentry SDK once.

    Calling this function more than once is safe — subsequent calls are
    no-ops so that test isolation and module reimports do not re-initialise.

    If ``dsn`` is empty or ``None`` the SDK is not initialised and Sentry
    remains disabled.  The rest of the application continues normally.
    """
    global _INITIALISED
    if _INITIALISED:
        return

    if not dsn:
        logger.debug("SENTRY_DSN is not configured; Sentry is disabled.")
        _INITIALISED = True
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=traces_sample_rate,
            # Privacy: disable all automatic PII collection.
            send_default_pii=False,
            # Privacy: strip request bodies, raw URLs, and large payloads.
            max_request_body_size="never",
            # Hook that sanitises every event before transmission.
            before_send=scrub_event,
            before_send_transaction=scrub_event,
            integrations=[
                StarletteIntegration(transaction_style="url"),
                FastApiIntegration(transaction_style="url"),
            ],
            # Only record errors and performance — no profiling data.
            profiles_sample_rate=0.0,
        )
        # Mark as initialised only after the SDK call succeeds.
        _INITIALISED = True
        logger.info(
            "Sentry initialised (traces_sample_rate=%.2f).",
            traces_sample_rate,
        )
    except Exception as exc:  # noqa: BLE001
        # A misconfigured DSN must not crash the analysis service, but we
        # surface the problem clearly rather than silently swallowing it.
        # _INITIALISED is intentionally left False so a corrected DSN can
        # be retried (e.g. after a config fix and server restart).
        logger.error(
            "Sentry initialisation failed; continuing without tracing: %s",
            type(exc).__name__,
        )


@contextmanager
def sentry_span(
    op: str,
    description: str,
) -> Generator[Any, None, None]:
    """Wrap a block in a Sentry child span when tracing is active.

    Yields the span object so callers can attach low-cardinality attributes.
    When Sentry is not initialised or the SDK is absent the context manager
    is a transparent no-op — no import error, no performance cost.

    Only the attributes listed in ``_SPAN_DATA_ALLOWLIST`` survive
    sanitisation.  Do not attach APK-derived values, filenames, package
    names, prompts, model responses, or any high-cardinality data.
    """
    try:
        import sentry_sdk as _sentry_sdk
    except ImportError:
        yield _NoopSpan()
        return

    with _sentry_sdk.start_span(op=op, name=description) as span:
        yield span


def capture_gemma_error(exc: Exception, *, is_expected: bool) -> None:
    """Capture a Gemma failure in Sentry without duplicate reporting.

    Expected ``GemmaError`` failures (timeouts, rate limits, contract
    violations) are recorded only as breadcrumb-free error events so that
    they are observable but not treated as unhandled server errors.

    Unexpected exceptions should be left to propagate naturally so that
    FastAPI's Sentry integration captures them through the standard path,
    avoiding duplicate events.

    ``is_expected=True`` means the application handles this failure
    gracefully and the deterministic report is still returned.
    """
    if not is_expected:
        return  # let FastAPI/Starlette integration handle it

    try:
        import sentry_sdk as _sentry_sdk

        with _sentry_sdk.push_scope() as scope:
            # Strip all context that might contain provider details.
            scope.clear_breadcrumbs()
            scope.set_extra("stage", "gemma_explanation")
            # Capture only the exception type, not the message.
            scope.fingerprint = ["gemma_expected_failure", type(exc).__name__]
            _sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001
        pass  # telemetry failure must never mask application behaviour


class _NoopSpan:
    """Drop-in replacement when the SDK is not installed or not initialised."""

    def set_data(self, _key: str, _value: object) -> None:
        pass

    def set_status(self, _status: str) -> None:
        pass
