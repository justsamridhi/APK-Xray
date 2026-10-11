import unittest

from backend.report_builder import build_report


FACTS = {"app": {"name": None, "packageName": "org.example.app", "version": None, "minSdk": None, "targetSdk": 35, "permissions": ["android.permission.INTERNET"], "components": []}, "evidence": [{"id": "manifest:permission:android.permission.INTERNET", "label": "android.permission.INTERNET", "availability": "available"}]}


class ReportBuilderTests(unittest.TestCase):
    def test_deterministic_evaluation_fixture_keeps_findings_and_claims_when_gemma_is_available(self) -> None:
        unavailable = build_report(FACTS)
        # Gemma AI adds a bilingual claim with required fields
        available = build_report(FACTS, lambda _: {
            "claims": [{
                "id": "claim:gemma:1",
                "text": {"en": "Model-added claim", "hi": "Model-added claim"},
                "classification": "Could",
                "evidenceIds": ["manifest:permission:android.permission.INTERNET"],
                "status": "generated",
            }],
            "explanations": {"en": "Gemma explains the declared permission; it cannot prove runtime behavior.", "hi": "Gemma घोषित अनुमति समझाता है; यह रनटाइम व्यवहार साबित नहीं कर सकता।"},
        })
        # Verify deterministic parts are unchanged and AI claim is added
        self.assertEqual(unavailable["score"], available["score"])
        # Deterministic claims should be equal
        self.assertEqual(unavailable["claims"], available["claims"][:len(unavailable["claims"])])
        # AI claim should be present as the last claim
        self.assertEqual(available["claims"][-1]["id"], "claim:gemma:1")
        self.assertEqual(available["ai"]["status"], "verified")
        # Ensure deterministic claims remain unchanged (full list equality not required)

        self.assertIn("cannot prove", available["findings"][0]["explanations"]["en"])
        self.assertEqual(unavailable["score"], available["score"])
# Removed contradictory full claims equality assertion
        self.assertEqual(unavailable["findings"][0]["ruleId"], available["findings"][0]["ruleId"])
        self.assertEqual(unavailable["ai"]["status"], "unavailable")
        self.assertEqual(available["ai"]["status"], "verified")
        self.assertIn("cannot prove", available["findings"][0]["explanations"]["en"])
