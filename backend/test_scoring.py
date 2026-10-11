
import unittest
from collections import defaultdict

from backend.scoring import calculate_score


class ScoringTests(unittest.TestCase):
    def assert_score_consistent(self, result: dict) -> None:
        """Verify that the returned score, breakdown, and findings agree."""
        breakdown = result["breakdown"]
        findings = result["findings"]

        breakdown_total = sum(item["points"] for item in breakdown)
        self.assertEqual(result["value"], min(100, breakdown_total))

        breakdown_by_rule = defaultdict(int)
        findings_by_rule = defaultdict(int)

        for item in breakdown:
            self.assertGreaterEqual(item["points"], 0)
            breakdown_by_rule[item["ruleId"]] += item["points"]

        for finding in findings:
            self.assertIn("ruleId", finding)
            self.assertIn("severity", finding)
            self.assertIn("evidence", finding)
            self.assertGreaterEqual(finding.get("points", 0), 0)
            findings_by_rule[finding["ruleId"]] += finding.get("points", 0)

        self.assertEqual(dict(breakdown_by_rule), dict(findings_by_rule))

    def test_score_is_deterministic_and_evidence_linked(self) -> None:
        evidence_id = "manifest:permission:android.permission.INTERNET"
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": ["android.permission.INTERNET"],
                "components": [],
            },
            "evidence": [
                {
                    "id": evidence_id,
                    "label": "android.permission.INTERNET",
                    "availability": "available",
                }
            ],
        }

        first = calculate_score(facts)

        self.assertEqual(first, calculate_score(facts))
        self.assertEqual(first["value"], 2)
        self.assertEqual(len(first["findings"]), 1)
        self.assertEqual(first["findings"][0]["evidence"][0]["id"], evidence_id)
        self.assertIn(
            evidence_id,
            {item["id"] for item in facts["evidence"]},
        )
        self.assert_score_consistent(first)

    def test_empty_app_has_zero_score_and_no_findings(self) -> None:
        facts = {
            "app": {
                "packageName": "org.example.empty",
                "permissions": [],
                "components": [],
            },
            "evidence": [],
        }

        result = calculate_score(facts)

        self.assertEqual(result["value"], 0)
        self.assertEqual(result["breakdown"], [])
        self.assertEqual(result["findings"], [])
        self.assert_score_consistent(result)

    def test_exported_component_without_permission_is_a_manifest_review_signal(self) -> None:
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": [],
                "components": [
                    {
                        "id": "manifest:activity:Main",
                        "name": "Main",
                        "type": "activity",
                        "exported": True,
                        "permission": None,
                    }
                ],
            },
            "evidence": [],
        }

        result = calculate_score(facts)

        self.assertEqual(result["value"], 20)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["ruleId"], "APKX-EXP-001")
        self.assertEqual(result["findings"][0]["severity"], "medium")
        self.assertIn(
            "does not prove runtime exploitability",
            result["findings"][0]["summary"],
        )
        self.assert_score_consistent(result)

    def test_guarded_and_unknown_export_states_do_not_create_exposure_findings(self) -> None:
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": [],
                "components": [
                    {
                        "id": "manifest:activity:Guarded",
                        "name": "Guarded",
                        "type": "activity",
                        "exported": True,
                        "permission": "org.example.GUARD",
                    },
                    {
                        "id": "manifest:provider:Unknown",
                        "name": "Unknown",
                        "type": "provider",
                        "exported": None,
                        "permission": None,
                    },
                ],
            },
            "evidence": [],
        }

        result = calculate_score(facts)

        self.assertEqual(result["findings"], [])
        self.assertEqual(result["value"], 0)
        self.assert_score_consistent(result)

    def test_exported_activity_alias_is_excluded(self) -> None:
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": [],
                "components": [
                    {
                        "id": "manifest:activity-alias:Launcher",
                        "name": "Launcher",
                        "type": "activity-alias",
                        "exported": True,
                        "permission": None,
                    }
                ],
            },
            "evidence": [],
        }

        result = calculate_score(facts)

        self.assertEqual(result["findings"], [])
        self.assertEqual(result["value"], 0)
        self.assert_score_consistent(result)

    def test_exported_component_score_cap_and_breakdown_consistency(self) -> None:
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": [],
                "components": [
                    {
                        "id": f"manifest:activity:A{i}",
                        "name": f"A{i}",
                        "type": "activity",
                        "exported": True,
                        "permission": None,
                    }
                    for i in range(1, 4)
                ],
            },
            "evidence": [],
        }

        result = calculate_score(facts)

        self.assertEqual(result["value"], 20)

        exported_findings = [
            finding
            for finding in result["findings"]
            if finding["ruleId"] == "APKX-EXP-001"
        ]
        exported_breakdown = [
            item
            for item in result["breakdown"]
            if item["ruleId"] == "APKX-EXP-001"
        ]

        self.assertEqual(len(exported_findings), 3)
        self.assertEqual(sum(f.get("points", 0) for f in exported_findings), 20)
        self.assertEqual(sum(item["points"] for item in exported_breakdown), 20)
        self.assertEqual(
            sorted(f["points"] for f in exported_findings),
            [0, 0, 20],
        )
        self.assert_score_consistent(result)


if __name__ == "__main__":
    unittest.main()
