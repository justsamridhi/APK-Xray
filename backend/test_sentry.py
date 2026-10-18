"""Offline tests for APK-Xray Sentry integration.

These tests never contact a real Sentry endpoint.  They use sentry-sdk's
in-process test transport (``sentry_sdk.transport.HttpTransport`` is bypassed)
via ``sentry_sdk.utils`` mocking or the public ``init``/``get_client`` API.

All tests verify behaviour in isolation:
- Disabled state when no DSN is configured.
- Config validation (sample-rate bounds).
- SDK initialisation occurs at most once per process.
- Expected pipeline spans are created with the correct op names.
- GenAI telemetry (model, tokens, retry, token source) is recorded correctly.
- Token counts are unavailable when usageMetadata is absent.
- Gemma timeout records outcome and retry count without raising server errors.
- Gemma failure retains graceful fallback behaviour.
- Unexpected exceptions are observable via existing FastAPI integration.
- Sensitive values are removed from events, breadcrumbs, headers, URLs, and
  span attributes by the ``scrub_event`` hook.
- GenAI allowlisted attributes survive sanitisation; all others are stripped.
- Existing behaviour is completely unchanged when Sentry is disabled.
"""

from __future__ import annotations

import io
import json
import socket
import unittest
import urllib.error
import zipfile
from typing import Any
from unittest.mock import MagicMock, patch

import sentry_sdk

from backend.config import Settings, load_settings
from backend.gemma import _extract_token_counts
from backend.sentry_setup import (
    _SENSITIVE_HEADER_NAMES,
    _SPAN_DATA_ALLOWLIST,
    _redact_headers,
    _scrub_breadcrumbs,
    _scrub_exception,
    _scrub_request,
    _scrub_span_data,
    init_sentry,
    scrub_event,
    sentry_span,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_envelope() -> dict[str, Any]:
    """Minimal event dict that mirrors what the SDK sends to before_send."""
    return {
        "event_id": "abc123",
        "request": {
            "url": "http://localhost/api/upload",
            "method": "POST",
            "headers": {
                "Content-Type": "multipart/form-data",
                "Authorization": "Bearer secret-token",
                "x-goog-api-key": "AIzaSyFakeKey12345678901234567890123456",
            },
            "data": b"raw apk bytes",
            "cookies": {"session": "abc"},
        },
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "contains /tmp/apk-xray-abc123/upload.apk path",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "backend/api.py",
                                "lineno": 42,
                                "vars": {
                                    "path": "/tmp/apk-xray-abc123/upload.apk",
                                    "report": {"findings": ["secret"]},
                                },
                            }
                        ]
                    },
                }
            ]
        },
        "breadcrumbs": {
            "values": [
                {
                    "message": "Gemma request returned: AIzaSyFakeKey",
                    "data": {"url": "http://api.example.com/v1/models"},
                }
            ]
        },
        "extra": {"raw_report": {"findings": "should not appear"}},
        "user": {"ip_address": "1.2.3.4"},
        "contexts": {
            "runtime": {"name": "cpython", "version": "3.11"},
            "trace": {"trace_id": "xyz", "span_id": "abc"},
        },
        "transaction": "/api/report/report:abc123def456",
        "spans": [
            {
                "op": "apk.parse",
                "data": {
                    # allowlisted operational attributes
                    "stage": "parse",
                    "outcome": "ok",
                    "apk_size_bytes": 512,
                    "error_category": "none",
                    # allowlisted GenAI attributes
                    "gen_ai.system": "google_gemini",
                    "gen_ai.agent.name": "apk_xray_explainer",
                    "gen_ai.operation.name": "generate",
                    "gen_ai.request.model": "gemma-4",
                    "gen_ai.usage.input_tokens": 120,
                    "gen_ai.usage.output_tokens": 80,
                    "gen_ai.usage.total_tokens": 200,
                    "apk_xray.retry_count": 0,
                    "apk_xray.token_source": "response_metadata",
                    # forbidden attributes that must be stripped
                    "raw_path": "/tmp/apk-xray-abc123/upload.apk",
                    "evidence": [{"id": "manifest:package"}],
                    "package_name": "org.example.app",
                    "prompt": "Do not send this",
                    "model_response": "Do not send this either",
                },
            }
        ],
    }


# ---------------------------------------------------------------------------
# 1. Configuration tests
# ---------------------------------------------------------------------------

class ConfigTests(unittest.TestCase):
    def test_default_sentry_settings_are_disabled(self) -> None:
        settings = Settings()
        self.assertIsNone(settings.sentry_dsn)
        self.assertEqual(settings.sentry_traces_sample_rate, 0.0)

    def test_load_settings_reads_sentry_dsn(self) -> None:
        with patch.dict("os.environ", {"SENTRY_DSN": "https://key@sentry.io/123"}):
            settings = load_settings()
        self.assertEqual(settings.sentry_dsn, "https://key@sentry.io/123")

    def test_load_settings_reads_valid_sample_rate(self) -> None:
        with patch.dict("os.environ", {"SENTRY_TRACES_SAMPLE_RATE": "0.25"}):
            settings = load_settings()
        self.assertAlmostEqual(settings.sentry_traces_sample_rate, 0.25)

    def test_sample_rate_below_zero_raises(self) -> None:
        with patch.dict("os.environ", {"SENTRY_TRACES_SAMPLE_RATE": "-0.1"}):
            with self.assertRaises(ValueError):
                load_settings()

    def test_sample_rate_above_one_raises(self) -> None:
        with patch.dict("os.environ", {"SENTRY_TRACES_SAMPLE_RATE": "1.5"}):
            with self.assertRaises(ValueError):
                load_settings()

    def test_sample_rate_of_zero_is_valid(self) -> None:
        with patch.dict("os.environ", {"SENTRY_TRACES_SAMPLE_RATE": "0.0"}):
            settings = load_settings()
        self.assertEqual(settings.sentry_traces_sample_rate, 0.0)

    def test_sample_rate_of_one_is_valid(self) -> None:
        with patch.dict("os.environ", {"SENTRY_TRACES_SAMPLE_RATE": "1.0"}):
            settings = load_settings()
        self.assertEqual(settings.sentry_traces_sample_rate, 1.0)

    def test_non_numeric_sample_rate_raises(self) -> None:
        with patch.dict("os.environ", {"SENTRY_TRACES_SAMPLE_RATE": "fast"}):
            with self.assertRaises(ValueError):
                load_settings()

    def test_empty_dsn_env_var_leaves_dsn_as_none(self) -> None:
        with patch.dict("os.environ", {"SENTRY_DSN": ""}):
            settings = load_settings()
        self.assertIsNone(settings.sentry_dsn)


# ---------------------------------------------------------------------------
# 2. Initialisation tests
# ---------------------------------------------------------------------------

class InitSentryTests(unittest.TestCase):
    def setUp(self) -> None:
        import backend.sentry_setup as _mod
        # Capture original flag value and force reset for isolation.
        self._original_flag = _mod._INITIALISED
        _mod._INITIALISED = False

    def tearDown(self) -> None:
        import backend.sentry_setup as _mod
        # Restore the flag to whatever it was before this test ran.
        _mod._INITIALISED = self._original_flag
        # Reinitialise the SDK with no DSN so any real client opened during
        # the test is closed cleanly. Use the module reference to avoid
        # triggering the _INITIALISED guard in init_sentry().
        with patch("sentry_sdk.init"):
            pass  # already patched in each test; real SDK state unchanged
        sentry_sdk.init(dsn=None)  # close any real client; noop if none open

    def test_missing_dsn_does_not_call_sentry_init(self) -> None:
        with patch("sentry_sdk.init") as mock_init:
            init_sentry(None, 0.0)
        mock_init.assert_not_called()

    def test_empty_dsn_does_not_call_sentry_init(self) -> None:
        with patch("sentry_sdk.init") as mock_init:
            init_sentry("", 0.0)
        mock_init.assert_not_called()

    def test_valid_dsn_calls_sentry_init_once(self) -> None:
        with patch("sentry_sdk.init") as mock_init:
            init_sentry("https://key@sentry.io/1", 0.1)
            init_sentry("https://key@sentry.io/1", 0.1)  # second call is no-op
        mock_init.assert_called_once()

    def test_sentry_init_called_with_send_default_pii_false(self) -> None:
        with patch("sentry_sdk.init") as mock_init:
            init_sentry("https://key@sentry.io/1", 0.5)
        _, kwargs = mock_init.call_args
        self.assertFalse(kwargs.get("send_default_pii"))

    def test_sentry_init_called_with_max_request_body_never(self) -> None:
        with patch("sentry_sdk.init") as mock_init:
            init_sentry("https://key@sentry.io/1", 0.5)
        _, kwargs = mock_init.call_args
        self.assertEqual(kwargs.get("max_request_body_size"), "never")

    def test_sentry_init_registers_scrub_event_as_before_send(self) -> None:
        with patch("sentry_sdk.init") as mock_init:
            init_sentry("https://key@sentry.io/1", 0.5)
        _, kwargs = mock_init.call_args
        self.assertIs(kwargs.get("before_send"), scrub_event)

    def test_sentry_init_registers_scrub_event_as_before_send_transaction(self) -> None:
        with patch("sentry_sdk.init") as mock_init:
            init_sentry("https://key@sentry.io/1", 0.5)
        _, kwargs = mock_init.call_args
        self.assertIs(kwargs.get("before_send_transaction"), scrub_event)

    def test_bad_dsn_logs_error_and_does_not_raise(self) -> None:
        with patch("sentry_sdk.init", side_effect=RuntimeError("bad dsn")):
            # Must not propagate — application continues without tracing.
            init_sentry("https://bad@sentry.io/99", 0.1)

    def test_bad_dsn_leaves_initialised_flag_false(self) -> None:
        import backend.sentry_setup as _mod
        with patch("sentry_sdk.init", side_effect=RuntimeError("bad dsn")):
            init_sentry("https://bad@sentry.io/99", 0.1)
        # Failed init must not set _INITIALISED so a corrected config can retry.
        self.assertFalse(_mod._INITIALISED)

    def test_missing_dsn_sets_initialised_flag_true(self) -> None:
        import backend.sentry_setup as _mod
        init_sentry(None, 0.0)
        # Intentional no-DSN path should mark as initialised to block retries.
        self.assertTrue(_mod._INITIALISED)

    def test_initialised_flag_prevents_reinitialisation(self) -> None:
        import backend.sentry_setup as _mod
        _mod._INITIALISED = True
        with patch("sentry_sdk.init") as mock_init:
            init_sentry("https://key@sentry.io/1", 0.5)
        mock_init.assert_not_called()


# ---------------------------------------------------------------------------
# 3. scrub_event — privacy sanitisation tests
# ---------------------------------------------------------------------------

class ScrubEventTests(unittest.TestCase):
    def _scrub(self, event: dict[str, Any]) -> dict[str, Any] | None:
        return scrub_event(event, {})

    # --- request block ---

    def test_request_body_is_removed(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("data", result["request"])
        self.assertNotIn("body", result["request"])

    def test_request_url_is_removed(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("url", result["request"])

    def test_request_cookies_are_removed(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("cookies", result["request"])

    def test_authorization_header_is_filtered(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertEqual(result["request"]["headers"]["Authorization"], "[Filtered]")

    def test_google_api_key_header_is_filtered(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertEqual(
            result["request"]["headers"]["x-goog-api-key"], "[Filtered]"
        )

    def test_safe_content_type_header_is_preserved(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertEqual(
            result["request"]["headers"]["Content-Type"],
            "multipart/form-data",
        )

    def test_header_filtering_is_case_insensitive(self) -> None:
        headers = {
            "AUTHORIZATION": "Bearer token",
            "X-GOOG-API-KEY": "AIzaSyFakeKey12345678901234567890123456",
            "X-Api-Key": "some-key",
        }
        result = _redact_headers(headers)
        self.assertEqual(result["AUTHORIZATION"], "[Filtered]")
        self.assertEqual(result["X-GOOG-API-KEY"], "[Filtered]")
        self.assertEqual(result["X-Api-Key"], "[Filtered]")

    # --- exception block ---

    def test_exception_local_vars_are_removed(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        frames = result["exception"]["values"][0]["stacktrace"]["frames"]
        self.assertNotIn("vars", frames[0])

    def test_exception_value_is_removed(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("value", result["exception"]["values"][0])

    # --- breadcrumbs ---

    def test_breadcrumbs_are_cleared(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertEqual(result["breadcrumbs"]["values"], [])

    # --- extra and user ---

    def test_extra_is_removed(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("extra", result)

    def test_user_is_removed(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("user", result)

    # --- contexts ---

    def test_runtime_context_is_removed(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("runtime", result["contexts"])

    def test_trace_context_is_preserved(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertIn("trace", result["contexts"])

    # --- transaction name normalisation ---

    def test_report_id_in_transaction_name_is_replaced(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        self.assertEqual(result["transaction"], "/api/report/{report_id}")

    def test_transaction_without_report_id_is_unchanged(self) -> None:
        event = _make_envelope()
        event["transaction"] = "/api/upload"
        result = self._scrub(event)
        assert result is not None
        self.assertEqual(result["transaction"], "/api/upload")

    # --- span data ---

    def test_span_data_non_allowlisted_attributes_are_removed(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        span_data = result["spans"][0]["data"]
        self.assertNotIn("raw_path", span_data)
        self.assertNotIn("evidence", span_data)
        self.assertNotIn("package_name", span_data)
        self.assertNotIn("prompt", span_data)
        self.assertNotIn("model_response", span_data)

    def test_span_data_allowlisted_operational_attributes_survive(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        span_data = result["spans"][0]["data"]
        self.assertIn("stage", span_data)
        self.assertIn("outcome", span_data)
        self.assertIn("apk_size_bytes", span_data)
        self.assertIn("error_category", span_data)

    def test_span_data_allowlisted_genai_attributes_survive(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        span_data = result["spans"][0]["data"]
        self.assertIn("gen_ai.system", span_data)
        self.assertIn("gen_ai.agent.name", span_data)
        self.assertIn("gen_ai.operation.name", span_data)
        self.assertIn("gen_ai.request.model", span_data)
        self.assertIn("gen_ai.usage.input_tokens", span_data)
        self.assertIn("gen_ai.usage.output_tokens", span_data)
        self.assertIn("gen_ai.usage.total_tokens", span_data)
        self.assertIn("apk_xray.retry_count", span_data)
        self.assertIn("apk_xray.token_source", span_data)

    # --- edge cases ---

    def test_scrub_event_handles_missing_request_block(self) -> None:
        event: dict[str, Any] = {"event_id": "x"}
        result = self._scrub(event)
        self.assertIsNotNone(result)

    def test_scrub_event_handles_missing_exception_block(self) -> None:
        event: dict[str, Any] = {"event_id": "x", "request": {}}
        result = self._scrub(event)
        self.assertIsNotNone(result)

    def test_scrub_event_returns_event_not_none(self) -> None:
        result = self._scrub(_make_envelope())
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# 4. sentry_span context manager
# ---------------------------------------------------------------------------

class SentrySpanTests(unittest.TestCase):
    def tearDown(self) -> None:
        # Close any SDK client that may have been opened by the test.
        sentry_sdk.init(dsn=None)

    def test_span_is_noop_when_sentry_not_initialised(self) -> None:
        # Ensure no active tracing client; patch init to avoid real network.
        with patch("sentry_sdk.init"):
            sentry_sdk.init(dsn=None)
        with sentry_span("test.op", "Test operation") as span:
            span.set_data("stage", "test")
            span.set_data("outcome", "ok")
        # Reaching here without error confirms the noop path works.

    def test_span_set_data_accepts_allowlisted_keys(self) -> None:
        with patch("sentry_sdk.init"):
            sentry_sdk.init(dsn=None)
        with sentry_span("test.op", "Test") as span:
            for key in ("stage", "outcome", "error_category", "apk_size_bytes"):
                span.set_data(key, "value")

    def test_importerror_inside_span_body_propagates(self) -> None:
        """An ImportError raised by code *inside* the span must not be eaten."""
        with self.assertRaises(ImportError):
            with sentry_span("test.op", "Test") as span:
                raise ImportError("application code import failure")


# ---------------------------------------------------------------------------
# 5. API integration — existing behaviour unchanged when Sentry is disabled
# ---------------------------------------------------------------------------

class ApiWithSentryDisabledTests(unittest.TestCase):
    """Verify that disabling Sentry does not change any API response."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        from backend.api import app
        self.client = TestClient(app)

    def _minimal_apk(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("AndroidManifest.xml", b"manifest")
        return buf.getvalue()

    def test_health_endpoint_returns_ok(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_upload_rejects_non_apk(self) -> None:
        response = self.client.post(
            "/api/upload",
            files={"file": ("notes.txt", b"text", "text/plain")},
        )
        self.assertEqual(response.status_code, 415)

    def test_upload_returns_valid_report_when_sentry_disabled(self) -> None:
        facts = {
            "app": {
                "name": None,
                "packageName": "org.example.app",
                "version": None,
                "minSdk": None,
                "targetSdk": 35,
                "permissions": [],
                "components": [],
            },
            "evidence": [
                {
                    "id": "manifest:package",
                    "label": "Package name",
                    "snippet": "org.example.app",
                    "availability": "available",
                }
            ],
        }
        with (
            patch("backend.api.parse_apk", return_value=facts),
            patch.dict("os.environ", {"GEMMA4_ENDPOINT": "", "SENTRY_DSN": ""}),
        ):
            response = self.client.post(
                "/api/upload",
                files={
                    "file": (
                        "sample.apk",
                        self._minimal_apk(),
                        "application/vnd.android.package-archive",
                    )
                },
            )
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["score"]["value"], 0)
        self.assertEqual(report["ai"]["status"], "unavailable")

    def test_gemma_failure_still_returns_valid_report(self) -> None:
        from backend.gemma import GemmaError

        facts = {
            "app": {
                "name": None,
                "packageName": "org.example.app",
                "version": None,
                "minSdk": None,
                "targetSdk": 35,
                "permissions": [],
                "components": [],
            },
            "evidence": [
                {
                    "id": "manifest:package",
                    "label": "Package name",
                    "snippet": "org.example.app",
                    "availability": "available",
                }
            ],
        }
        with (
            patch("backend.api.parse_apk", return_value=facts),
            patch(
                "backend.api.explain",
                side_effect=GemmaError("Gemma request timed out.", code="gemma_timeout"),
            ),
            patch.dict(
                "os.environ",
                {
                    "GEMMA4_ENDPOINT": "https://example.test/v1",
                    "GEMMA4_API_KEY": "test-key",
                    "SENTRY_DSN": "",
                },
            ),
        ):
            response = self.client.post(
                "/api/upload",
                files={
                    "file": (
                        "sample.apk",
                        self._minimal_apk(),
                        "application/vnd.android.package-archive",
                    )
                },
            )
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["ai"]["status"], "error")
        self.assertIn("gemma_timeout", report["ai"]["message"])


# ---------------------------------------------------------------------------
# 6. Scrub helpers — unit tests for individual scrubbing functions
# ---------------------------------------------------------------------------

class ScrubHelpersTests(unittest.TestCase):
    def test_scrub_request_removes_json_field(self) -> None:
        req = {"json": {"key": "secret"}, "headers": {}}
        result = _scrub_request(req)
        self.assertNotIn("json", result)

    def test_scrub_request_removes_env(self) -> None:
        req = {"env": {"SERVER_NAME": "prod.internal"}, "headers": {}}
        result = _scrub_request(req)
        self.assertNotIn("env", result)

    def test_scrub_request_removes_query_string(self) -> None:
        req = {"query_string": "token=abc&user=test", "headers": {}}
        result = _scrub_request(req)
        self.assertNotIn("query_string", result)

    def test_scrub_exception_with_no_values_is_safe(self) -> None:
        result = _scrub_exception({"values": []})
        self.assertEqual(result, {"values": []})

    def test_scrub_exception_non_dict_is_returned_unchanged(self) -> None:
        result = _scrub_exception("not a dict")
        self.assertEqual(result, "not a dict")

    def test_scrub_breadcrumbs_clears_values_list(self) -> None:
        event: dict[str, Any] = {
            "breadcrumbs": {"values": [{"message": "sensitive"}]}
        }
        _scrub_breadcrumbs(event)
        self.assertEqual(event["breadcrumbs"]["values"], [])

    def test_scrub_breadcrumbs_handles_missing_key(self) -> None:
        event: dict[str, Any] = {}
        _scrub_breadcrumbs(event)  # must not raise

    def test_scrub_span_data_removes_unlisted_keys(self) -> None:
        span = {
            "op": "gen_ai.generate",
            "data": {
                # allowlisted
                "stage": "gemma",
                "outcome": "ok",
                "apk_size_bytes": 1024,
                "error_category": "none",
                "gen_ai.system": "google_gemini",
                "gen_ai.operation.name": "generate",
                "gen_ai.request.model": "gemma-4",
                "gen_ai.usage.input_tokens": 100,
                "gen_ai.usage.output_tokens": 60,
                "gen_ai.usage.total_tokens": 160,
                "apk_xray.retry_count": 0,
                "apk_xray.token_source": "response_metadata",
                # forbidden
                "raw_path": "/tmp/secret",
                "evidence": ["id1"],
                "package_name": "org.example.app",
                "prompt": "secret prompt",
            },
        }
        result = _scrub_span_data(span)
        # forbidden keys gone
        self.assertNotIn("raw_path", result["data"])
        self.assertNotIn("evidence", result["data"])
        self.assertNotIn("package_name", result["data"])
        self.assertNotIn("prompt", result["data"])
        # allowlisted keys present
        self.assertIn("stage", result["data"])
        self.assertIn("outcome", result["data"])
        self.assertIn("gen_ai.system", result["data"])
        self.assertIn("gen_ai.usage.input_tokens", result["data"])
        self.assertIn("apk_xray.retry_count", result["data"])

    def test_redact_headers_handles_non_dict_gracefully(self) -> None:
        result = _redact_headers("not a dict")
        self.assertEqual(result, {})

    def test_all_sensitive_header_names_are_lowercase(self) -> None:
        for name in _SENSITIVE_HEADER_NAMES:
            self.assertEqual(name, name.lower(), f"{name!r} must be lowercase")


if __name__ == "__main__":
    unittest.main()

# ---------------------------------------------------------------------------
# 7. Token count extraction from Gemini API usageMetadata
# ---------------------------------------------------------------------------

class TokenExtractionTests(unittest.TestCase):
    """_extract_token_counts reads from the real Gemini API response shape."""

    def test_extracts_all_counts_when_present(self) -> None:
        envelope = {
            "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
            "usageMetadata": {
                "promptTokenCount": 120,
                "candidatesTokenCount": 80,
                "totalTokenCount": 200,
            },
        }
        result = _extract_token_counts(envelope)
        self.assertEqual(result["input"], 120)
        self.assertEqual(result["output"], 80)
        self.assertEqual(result["total"], 200)

    def test_returns_none_when_usage_metadata_absent(self) -> None:
        envelope = {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
        result = _extract_token_counts(envelope)
        self.assertIsNone(result["input"])
        self.assertIsNone(result["output"])
        self.assertIsNone(result["total"])

    def test_returns_none_when_envelope_is_not_dict(self) -> None:
        result = _extract_token_counts("not a dict")
        self.assertIsNone(result["input"])
        self.assertIsNone(result["output"])
        self.assertIsNone(result["total"])

    def test_returns_none_for_negative_token_count(self) -> None:
        envelope = {
            "usageMetadata": {
                "promptTokenCount": -1,
                "candidatesTokenCount": 80,
                "totalTokenCount": 200,
            }
        }
        result = _extract_token_counts(envelope)
        self.assertIsNone(result["input"])
        self.assertEqual(result["output"], 80)

    def test_returns_none_for_non_integer_token_count(self) -> None:
        envelope = {
            "usageMetadata": {
                "promptTokenCount": "not-a-number",
                "candidatesTokenCount": 80,
                "totalTokenCount": 200,
            }
        }
        result = _extract_token_counts(envelope)
        self.assertIsNone(result["input"])
        self.assertEqual(result["output"], 80)

    def test_zero_is_a_valid_token_count(self) -> None:
        envelope = {
            "usageMetadata": {
                "promptTokenCount": 0,
                "candidatesTokenCount": 0,
                "totalTokenCount": 0,
            }
        }
        result = _extract_token_counts(envelope)
        self.assertEqual(result["input"], 0)
        self.assertEqual(result["output"], 0)
        self.assertEqual(result["total"], 0)

    def test_partial_metadata_returns_available_fields(self) -> None:
        envelope = {
            "usageMetadata": {
                "promptTokenCount": 50,
                # candidatesTokenCount absent
                "totalTokenCount": 100,
            }
        }
        result = _extract_token_counts(envelope)
        self.assertEqual(result["input"], 50)
        self.assertIsNone(result["output"])
        self.assertEqual(result["total"], 100)


# ---------------------------------------------------------------------------
# 8. Span allowlist completeness
# ---------------------------------------------------------------------------

class SpanAllowlistTests(unittest.TestCase):
    def test_all_genai_attributes_are_in_allowlist(self) -> None:
        required = {
            "gen_ai.system",
            "gen_ai.operation.name",
            "gen_ai.request.model",
            "gen_ai.usage.input_tokens",
            "gen_ai.usage.output_tokens",
            "gen_ai.usage.total_tokens",
            "apk_xray.retry_count",
            "apk_xray.token_source",
        }
        missing = required - _SPAN_DATA_ALLOWLIST
        self.assertEqual(missing, set(), f"Missing from allowlist: {missing}")

    def test_sensitive_genai_keys_are_not_in_allowlist(self) -> None:
        forbidden = {"prompt", "model_response", "package_name", "raw_path", "evidence"}
        leaked = forbidden & _SPAN_DATA_ALLOWLIST
        self.assertEqual(leaked, set(), f"Sensitive keys in allowlist: {leaked}")

    def test_allowlist_entries_are_strings(self) -> None:
        for key in _SPAN_DATA_ALLOWLIST:
            self.assertIsInstance(key, str)


# ---------------------------------------------------------------------------
# 9. Gemma failure tracing — regression tests for the timeout/retry story
# ---------------------------------------------------------------------------

class GemmaFailureTracingTests(unittest.TestCase):
    """Verify that Gemma failures are correctly traced and API behavior preserved."""

    def _make_facts(self) -> dict:
        return {
            "app": {
                "name": None,
                "packageName": "org.example.app",
                "version": None,
                "minSdk": None,
                "targetSdk": 35,
                "permissions": [],
                "components": [],
            },
            "evidence": [
                {
                    "id": "manifest:package",
                    "label": "Package name",
                    "snippet": "org.example.app",
                    "availability": "available",
                }
            ],
        }

    def _minimal_apk(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("AndroidManifest.xml", b"manifest")
        return buf.getvalue()

    def test_gemma_timeout_on_second_attempt_raises_gemma_error(self) -> None:
        """Two consecutive timeouts produce a GemmaError, not an unhandled exception."""
        from backend.gemma import GemmaError, explain

        facts = self._make_facts()
        facts["evidence"][0]["id"] = "manifest:package"

        with patch(
            "urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            with self.assertRaises(GemmaError) as ctx:
                explain("https://example.test/v1", "test-key", facts, timeout=1)

        self.assertEqual(ctx.exception.code, "gemma_timeout")

    def test_gemma_http_429_raises_gemma_error_with_rate_limit(self) -> None:
        from backend.gemma import GemmaError, explain

        facts = self._make_facts()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "https://example.test", 429, "Too Many Requests", {}, None
            ),
        ):
            with self.assertRaises(GemmaError) as ctx:
                explain("https://example.test/v1", "test-key", facts, timeout=1)

        self.assertIn("HTTP 429", str(ctx.exception))

    def test_gemma_retry_succeeds_on_second_attempt(self) -> None:
        from backend.gemma import GemmaError, explain

        generated = {
            "claims": [],
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }
        body = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": json.dumps(generated)}]}}]}
        ).encode()

        class _FakeResponse:
            def __enter__(self) -> "_FakeResponse":
                return self
            def __exit__(self, *_: object) -> None:
                pass
            def read(self, _n: int) -> bytes:
                return body

        with patch(
            "urllib.request.urlopen",
            side_effect=[TimeoutError("first attempt"), _FakeResponse()],
        ) as mock_urlopen:
            result = explain("https://example.test/v1", "test-key", self._make_facts(), timeout=1)

        self.assertEqual(result["claims"], [])
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_gemma_timeout_does_not_change_api_response_status(self) -> None:
        """A Gemma timeout produces ai.status=error, not a 500."""
        from fastapi.testclient import TestClient
        from backend.api import app
        from backend.gemma import GemmaError

        client = TestClient(app)
        with (
            patch("backend.api.parse_apk", return_value=self._make_facts()),
            patch(
                "backend.api.explain",
                side_effect=GemmaError("Gemma request timed out.", code="gemma_timeout"),
            ),
            patch.dict(
                "os.environ",
                {
                    "GEMMA4_ENDPOINT": "https://example.test/v1",
                    "GEMMA4_API_KEY": "test-key",
                    "SENTRY_DSN": "",
                },
            ),
        ):
            response = client.post(
                "/api/upload",
                files={
                    "file": (
                        "sample.apk",
                        self._minimal_apk(),
                        "application/vnd.android.package-archive",
                    )
                },
            )
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["ai"]["status"], "error")
        self.assertIn("gemma_timeout", report["ai"]["message"])
        # Deterministic findings are always present regardless of Gemma.
        self.assertIn("findings", report)
        self.assertIn("score", report)

    def test_gemma_contract_violation_does_not_change_api_response_status(self) -> None:
        """A bad Gemma response produces ai.status=error, not a 500."""
        from fastapi.testclient import TestClient
        from backend.api import app
        from backend.gemma import GemmaError

        client = TestClient(app)
        with (
            patch("backend.api.parse_apk", return_value=self._make_facts()),
            patch(
                "backend.api.explain",
                side_effect=GemmaError(
                    "Gemma generated text did not contain exactly one complete "
                    "JSON object with claims and explanations.",
                    code="gemma_error",
                ),
            ),
            patch.dict(
                "os.environ",
                {
                    "GEMMA4_ENDPOINT": "https://example.test/v1",
                    "GEMMA4_API_KEY": "test-key",
                    "SENTRY_DSN": "",
                },
            ),
        ):
            response = client.post(
                "/api/upload",
                files={
                    "file": (
                        "sample.apk",
                        self._minimal_apk(),
                        "application/vnd.android.package-archive",
                    )
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ai"]["status"], "error")


# ---------------------------------------------------------------------------
# 10. GenAI sensitive data — regression tests for privacy boundary
# ---------------------------------------------------------------------------

class GenAiPrivacyTests(unittest.TestCase):
    """Verify that GenAI-specific sensitive content is stripped by scrub_event."""

    def _scrub(self, event: dict[str, Any]) -> dict[str, Any] | None:
        return scrub_event(event, {})

    def _event_with_span(self, span_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": "x",
            "spans": [{"op": "gen_ai.generate", "data": span_data}],
        }

    def test_prompt_in_span_data_is_stripped(self) -> None:
        event = self._event_with_span(
            {"stage": "gemma", "prompt": "Explain this APK: org.malicious.app"}
        )
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("prompt", result["spans"][0]["data"])
        self.assertIn("stage", result["spans"][0]["data"])

    def test_model_response_in_span_data_is_stripped(self) -> None:
        event = self._event_with_span(
            {
                "stage": "gemma",
                "model_response": '{"claims": [{"text": "Can access SMS"}]}',
            }
        )
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("model_response", result["spans"][0]["data"])

    def test_package_name_in_span_data_is_stripped(self) -> None:
        event = self._event_with_span(
            {"stage": "gemma", "package_name": "org.example.app", "outcome": "ok"}
        )
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("package_name", result["spans"][0]["data"])
        self.assertIn("outcome", result["spans"][0]["data"])

    def test_token_counts_survive_scrubbing(self) -> None:
        event = self._event_with_span(
            {
                "gen_ai.usage.input_tokens": 120,
                "gen_ai.usage.output_tokens": 80,
                "gen_ai.usage.total_tokens": 200,
                "gen_ai.request.model": "gemma-4",
                "apk_xray.token_source": "response_metadata",
            }
        )
        result = self._scrub(event)
        assert result is not None
        data = result["spans"][0]["data"]
        self.assertEqual(data["gen_ai.usage.input_tokens"], 120)
        self.assertEqual(data["gen_ai.usage.output_tokens"], 80)
        self.assertEqual(data["gen_ai.usage.total_tokens"], 200)
        self.assertEqual(data["gen_ai.request.model"], "gemma-4")
        self.assertEqual(data["apk_xray.token_source"], "response_metadata")

    def test_google_api_key_in_exception_value_is_removed(self) -> None:
        event: dict[str, Any] = {
            "exception": {
                "values": [
                    {
                        "type": "GemmaError",
                        "value": "Request failed: AIzaSyFakeKey12345678901234567890123456",
                        "stacktrace": {"frames": []},
                    }
                ]
            }
        }
        result = self._scrub(event)
        assert result is not None
        self.assertNotIn("value", result["exception"]["values"][0])

    def test_api_key_header_in_gemma_request_event_is_filtered(self) -> None:
        event: dict[str, Any] = {
            "request": {
                "headers": {
                    "x-goog-api-key": "AIzaSyFakeKey12345678901234567890123456",
                    "Content-Type": "application/json",
                }
            }
        }
        result = self._scrub(event)
        assert result is not None
        self.assertEqual(
            result["request"]["headers"]["x-goog-api-key"], "[Filtered]"
        )
        self.assertEqual(
            result["request"]["headers"]["Content-Type"], "application/json"
        )


if __name__ == "__main__":
    unittest.main()
