"""Sentry SDK initialisation and privacy-safe event processing for APK-Xray.

Privacy contract
----------------
APK-Xray handles potentially sensitive application artefacts.  The following
are *never* forwarded to Sentry:

- APK bytes, filenames, or local filesystem paths
- Request or response bodies
- API keys, credentials, or authorisation headers
- Raw evidence items, Gemma prompts / responses, or complete report objects
- Any PII collected by the SDK's default instrumentation

Only low-cardinality operational attributes are attached to spans:
``stage``, ``outcome``, ``error_category``, and ``apk_size_bytes``.

The ``scrub_event`` hook is registered as both ``before_send`` and
``before_send_transaction`` so every event type passes through the same
sanitisation pipeline regardless of how it was captured.
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
        # Strip exception context that may contain report dicts or paths.
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
    """Keep only low-cardinality operational attributes on a span."""
    data = span.get("data")
    if not isinstance(data, dict):
        return span
    allowed = {"stage", "outcome", "error_category", "apk_size_bytes"}
    span["data"] = {k: v for k, v in data.items() if k in allowed}
    return span


def scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Privacy-safe Sentry before_send / before_send_transaction hook.

    Called by the SDK before every event and transaction envelope is sent.
    Returns the sanitised event, or ``None`` to drop it entirely.

    This function is the single chokepoint for privacy enforcement.
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

    # --- transaction name: replace with a fixed safe placeholder ---
    # The SDK may set the transaction name from the URL which could include
    # a report ID or package name.
    if "transaction" in event:
        # Normalise dynamic segments out of transaction names.
        txn = event["transaction"]
        if isinstance(txn, str):
            # Replace anything after /report/ with a placeholder.
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

    Usage::

        with sentry_span("apk.parse", "Parse APK manifest") as span:
            span.set_data("stage", "parse")
            result = parse_apk(path)

    Only the attributes listed in ``_scrub_span_data`` survive sanitisation:
    ``stage``, ``outcome``, ``error_category``, ``apk_size_bytes``.
    """
    try:
        import sentry_sdk as _sentry_sdk
    except ImportError:
        yield _NoopSpan()
        return

    with _sentry_sdk.start_span(op=op, name=description) as span:
        yield span


class _NoopSpan:
    """Drop-in replacement when the SDK is not installed or not initialised."""

    def set_data(self, _key: str, _value: object) -> None:  # noqa: D401
        pass

    def set_status(self, _status: str) -> None:
        pass
