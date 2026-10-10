import unittest

from backend.scoring import calculate_score


class ScoringTests(unittest.TestCase):
    def test_score_is_deterministic_and_evidence_linked(self) -> None:
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": ["android.permission.INTERNET"],
                "components": [],
            },
            "evidence": [
                {
                    "id": "manifest:permission:android.permission.INTERNET",
                    "label": "android.permission.INTERNET",
                    "availability": "available",
                }
            ],
        }
        first = calculate_score(facts)
        self.assertEqual(first, calculate_score(facts))
        self.assertEqual(first["value"], 12)
        self.assertEqual(first["findings"][0]["evidence"][0]["id"], "manifest:permission:android.permission.INTERNET")

    def test_exported_component_without_permission_is_high_risk(self) -> None:
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": [],
                "components": [{"id": "manifest:activity:Main", "name": "Main", "exported": True, "permission": None}],
            },
            "evidence": [],
        }
        result = calculate_score(facts)
        self.assertEqual(result["value"], 20)
        self.assertEqual(result["findings"][0]["ruleId"], "APKX-EXP-001")
