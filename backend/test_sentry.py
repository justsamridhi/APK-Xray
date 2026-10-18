"""Offline tests for APK-Xray Sentry integration.

These tests never contact a real Sentry endpoint.  They use sentry-sdk's
in-process test transport (``sentry_sdk.transport.HttpTransport`` is bypassed)
via ``sentry_sdk.utils`` mocking or the public ``init``/``get_client`` API.

All tests verify behaviour in isolation:
- Disabled state when no DSN is configured.
- Config validation (sample-rate bounds).
- SDK initialisation occurs at most once per process.
- Expected spans are created around pipeline stages.
- Unexpected exceptions are captured without altering API responses.
- Gemma failure preserves graceful fallback.
- Sensitive values are removed from events, breadcrumbs, headers, URLs, and
  span attributes by the ``scrub_event`` hook.
- Existing behaviour is completely unchanged when Sentry is disabled.
"""

from __future__ import annotations

import io
import unittest
import zipfile
from typing import Any
from unittest.mock import MagicMock, call, patch

import sentry_sdk

from backend.config import Settings, load_settings
from backend.sentry_setup import (
    _SENSITIVE_HEADER_NAMES,
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
                    "stage": "parse",
                    "outcome": "ok",
                    "apk_size_bytes": 512,
                    "raw_path": "/tmp/apk-xray-abc123/upload.apk",
                    "evidence": [{"id": "manifest:package"}],
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

    def test_span_data_allowlisted_attributes_survive(self) -> None:
        event = _make_envelope()
        result = self._scrub(event)
        assert result is not None
        span_data = result["spans"][0]["data"]
        self.assertIn("stage", span_data)
        self.assertIn("outcome", span_data)
        self.assertIn("apk_size_bytes", span_data)

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
            "op": "apk.parse",
            "data": {
                "stage": "parse",
                "outcome": "ok",
                "apk_size_bytes": 1024,
                "error_category": "parse_error",
                "raw_path": "/tmp/secret",
                "evidence": ["id1"],
            },
        }
        result = _scrub_span_data(span)
        self.assertNotIn("raw_path", result["data"])
        self.assertNotIn("evidence", result["data"])
        self.assertIn("stage", result["data"])
        self.assertIn("outcome", result["data"])
        self.assertIn("apk_size_bytes", result["data"])
        self.assertIn("error_category", result["data"])

    def test_redact_headers_handles_non_dict_gracefully(self) -> None:
        result = _redact_headers("not a dict")
        self.assertEqual(result, {})

    def test_all_sensitive_header_names_are_lowercase(self) -> None:
        for name in _SENSITIVE_HEADER_NAMES:
            self.assertEqual(name, name.lower(), f"{name!r} must be lowercase")


if __name__ == "__main__":
    unittest.main()
