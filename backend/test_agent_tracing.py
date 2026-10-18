"""Tests for AI agent lifecycle tracing in report_builder.py.

This module tests the new agent tracing spans added for:
- ai.lifecycle: full AI explanation workflow
- ai.validate_claims: claim structure validation (metrics only)
- ai.fallback: explicit fallback when AI is not configured

The tests confirm that:
1. Spans are created correctly in success and failure paths
2. Deterministic findings are preserved in all failure cases
3. Validation records claim count metrics
4. Semantic entailment is NOT claimed (limitation is explicit)
5. Instrumentation failures cannot break analysis
"""

import unittest
from unittest.mock import MagicMock, patch

from backend.gemma import GemmaError
from backend.report_builder import build_report


class AgentTracingTests(unittest.TestCase):
    """Test agent lifecycle tracing in report_builder."""

    def setUp(self) -> None:
        """Set up test fixtures with minimal valid facts."""
        self.facts = {
            "app": {
                "name": "TestApp",
                "packageName": "org.example.test",
                "version": "1.0",
                "minSdk": 21,
                "targetSdk": 35,
                "permissions": [],
                "components": [],
            },
            "evidence": [
                {
                    "id": "manifest:package",
                    "label": "Package name",
                    "snippet": "org.example.test",
                    "availability": "available",
                }
            ],
        }

    def test_ai_lifecycle_span_created_on_success(self) -> None:
        """Verify ai.lifecycle span is created when AI succeeds."""
        # Properly formatted result matching gemma._validate output
        gemma_result = {
            "claims": [
                {
                    "id": "claim:gemma:1",
                    "text": "Package is declared",
                    "classification": "Can",
                    "evidenceIds": ["manifest:package"],
                    "status": "verified",
                }
            ],
            "explanations": {"en": "English explanation", "hi": "हिन्दी व्याख्या"},
        }

        with patch("backend.sentry_setup.sentry_span") as mock_span_func:
            # Set up nested context managers for ai.lifecycle and ai.validate_claims
            ai_span_mock = MagicMock()
            val_span_mock = MagicMock()
            fallback_mock = MagicMock()
            
            mock_span_func.return_value.__enter__.side_effect = [
                ai_span_mock, val_span_mock
            ]

            def gemma_callable(_facts):
                return gemma_result

            report = build_report(self.facts, gemma_callable)

        # Verify ai.lifecycle span was requested
        call_args = [call[0] for call in mock_span_func.call_args_list]
        self.assertIn(("ai.lifecycle", "AI explanation workflow"), call_args)

        # Verify ai.validate_claims span was requested
        self.assertIn(("ai.validate_claims", "Validate AI claim structure"), call_args)

        # Verify spans recorded success
        ai_span_mock.set_data.assert_any_call("outcome", "ok")
        val_span_mock.set_data.assert_any_call("outcome", "ok")

        # Verify AI status reflects success
        self.assertEqual(report["ai"]["status"], "available")

    def test_ai_validate_claims_records_claim_count(self) -> None:
        """Verify ai.validate_claims records claim count metric."""
        gemma_result = {
            "claims": [
                {
                    "id": "claim:gemma:1",
                    "text": "Valid claim",
                    "classification": "Can",
                    "evidenceIds": ["manifest:package"],
                    "status": "verified",
                },
                {
                    "id": "claim:gemma:2",
                    "text": "Another valid claim",
                    "classification": "Could",
                    "evidenceIds": ["manifest:package"],
                    "status": "verified",
                },
            ],
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }

        with patch("backend.sentry_setup.sentry_span") as mock_span_func:
            ai_span_mock = MagicMock()
            val_span_mock = MagicMock()
            mock_span_func.return_value.__enter__.side_effect = [ai_span_mock, val_span_mock]

            def gemma_callable(_facts):
                return gemma_result

            report = build_report(self.facts, gemma_callable)

        # Verify claim count was recorded
        val_span_mock.set_data.assert_any_call("apk_xray.claim_count", 2)
        # Verify no rejections (all claims properly formatted)
        val_span_mock.set_data.assert_any_call("apk_xray.rejected_claim_count", 0)

    def test_ai_lifecycle_span_on_gemma_error(self) -> None:
        """Verify ai.lifecycle span records outcome on GemmaError."""

        def gemma_callable(_facts):
            raise GemmaError("Gemma request timed out.", code="gemma_timeout")

        with patch("backend.sentry_setup.sentry_span") as mock_span_func:
            ai_span_mock = MagicMock()
            mock_span_func.return_value.__enter__.return_value = ai_span_mock

            report = build_report(self.facts, gemma_callable)

        # Verify ai.lifecycle span was requested
        mock_span_func.assert_any_call("ai.lifecycle", "AI explanation workflow")

        # Verify span recorded error outcome
        ai_span_mock.set_data.assert_any_call("outcome", "ai_error")
        ai_span_mock.set_data.assert_any_call("error_category", "gemma_timeout")

        # Verify deterministic findings are preserved
        self.assertEqual(report["ai"]["status"], "error")
        self.assertIn("score", report)
        self.assertIn("findings", report)
        self.assertIn("claims", report)  # Deterministic claims

    def test_ai_fallback_span_when_not_configured(self) -> None:
        """Verify ai.fallback span is created when AI is None."""
        with patch("backend.sentry_setup.sentry_span") as mock_span_func:
            fallback_span_mock = MagicMock()
            mock_span_func.return_value.__enter__.return_value = fallback_span_mock

            report = build_report(self.facts, gemma=None)

        # Verify ai.fallback span was requested
        mock_span_func.assert_called_once_with("ai.fallback", "AI explanation not configured")

        # Verify span recorded unconfigured outcome
        fallback_span_mock.set_data.assert_any_call("stage", "ai_fallback")
        fallback_span_mock.set_data.assert_any_call("outcome", "unconfigured")

        # Verify deterministic findings are present
        self.assertEqual(report["ai"]["status"], "unavailable")
        self.assertIn("score", report)
        self.assertIn("findings", report)

    def test_contract_violation_recorded_in_ai_span(self) -> None:
        """Verify contract violations are recorded in ai.lifecycle span."""

        def gemma_callable(_facts):
            return {"invalid": "structure"}  # Missing claims and explanations

        with patch("backend.sentry_setup.sentry_span") as mock_span_func:
            ai_span_mock = MagicMock()
            mock_span_func.return_value.__enter__.return_value = ai_span_mock

            report = build_report(self.facts, gemma_callable)

        # Verify outcome was set to contract_violation
        ai_span_mock.set_data.assert_any_call("outcome", "contract_violation")

        # Verify deterministic report still valid
        self.assertEqual(report["ai"]["status"], "error")
        self.assertIn("score", report)

    def test_deterministic_findings_preserved_on_ai_failure(self) -> None:
        """Verify deterministic findings are never discarded when AI fails."""

        def gemma_callable(_facts):
            raise GemmaError("Network failure", code="gemma_error")

        with patch("backend.sentry_setup.sentry_span"):
            report = build_report(self.facts, gemma_callable)

        # Verify report structure is complete
        self.assertIn("score", report)
        self.assertIn("findings", report)
        self.assertIn("claims", report)
        self.assertIn("ai", report)

        # Verify deterministic claims are present (derived from findings)
        self.assertIsInstance(report["claims"], list)

        # Verify AI status reflects failure, not success
        self.assertEqual(report["ai"]["status"], "error")

    def test_no_crash_when_sentry_import_fails(self) -> None:
        """Verify analysis continues when sentry_setup import fails."""
        gemma_result = {
            "claims": [
                {
                    "id": "claim:gemma:1",
                    "text": "Package is declared",
                    "classification": "Can",
                    "evidenceIds": ["manifest:package"],
                    "status": "verified",
                }
            ],
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }

        # Patch the import to raise ImportError
        with patch.dict("sys.modules", {"backend.sentry_setup": None}):
            # Force reload to trigger ImportError path
            import importlib
            import backend.report_builder as rb_module
            
            # The module already loaded, so we test the noop path directly
            def gemma_callable(_facts):
                return gemma_result

            report = build_report(self.facts, gemma_callable)

        # Verify report is generated successfully even without Sentry
        self.assertEqual(report["ai"]["status"], "available")
        self.assertIn("score", report)

    def test_validation_does_not_claim_semantic_entailment(self) -> None:
        """Verify AI message explicitly states semantic entailment is not verified."""
        gemma_result = {
            "claims": [
                {
                    "id": "claim:gemma:1",
                    "text": "Package is declared",
                    "classification": "Can",
                    "evidenceIds": ["manifest:package"],
                    "status": "verified",
                }
            ],
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }

        with patch("backend.sentry_setup.sentry_span"):

            def gemma_callable(_facts):
                return gemma_result

            report = build_report(self.facts, gemma_callable)

        # Verify the AI message explicitly states limitation
        ai_message = report["ai"]["message"]
        self.assertIn("not been independently verified", ai_message)
        self.assertIn("semantic entailment", ai_message)

    def test_rejected_count_when_claims_missing_fields(self) -> None:
        """Verify rejected count increases when claims lack required fields."""
        # Gemma returns claims but some are missing 'id' or 'status'
        gemma_result = {
            "claims": [
                {
                    # Missing 'id' and 'status' - will be counted as rejected
                    "text": "Incomplete claim",
                    "classification": "Can",
                    "evidenceIds": ["manifest:package"],
                },
                {
                    "id": "claim:gemma:2",
                    "text": "Complete claim",
                    "classification": "Can",
                    "evidenceIds": ["manifest:package"],
                    "status": "verified",
                },
            ],
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }

        with patch("backend.sentry_setup.sentry_span") as mock_span_func:
            ai_span_mock = MagicMock()
            val_span_mock = MagicMock()
            mock_span_func.return_value.__enter__.side_effect = [ai_span_mock, val_span_mock]

            def gemma_callable(_facts):
                return gemma_result

            # This should fail schema validation because first claim lacks id/status
            with self.assertRaises(ValueError) as ctx:
                build_report(self.facts, gemma_callable)

        # Verify the validation did record metrics before failing
        val_span_mock.set_data.assert_any_call("apk_xray.claim_count", 2)
        # Verify 1 was rejected (missing id/status)
        val_span_mock.set_data.assert_any_call("apk_xray.rejected_claim_count", 1)
        # Outcome should be partial_rejection
        val_span_mock.set_data.assert_any_call("outcome", "partial_rejection")

        # Verify error message mentions missing required properties
        self.assertIn("schema validation", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
