
import unittest

from backend.scoring import calculate_score


class ScoringTests(unittest.TestCase):
    def test_score_is_deterministic_and_evidence_linked(self):
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
        self.assertEqual(
            first["findings"][0]["evidence"][0]["id"],
            "manifest:permission:android.permission.INTERNET",
        )

    def test_permission_without_evidence_is_not_scored(self):
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": ["android.permission.INTERNET"],
                "components": [],
            },
            "evidence": [],
        }

        result = calculate_score(facts)
        self.assertEqual(result["value"], 0)
        self.assertEqual(result["findings"], [])

    def test_exported_component_requires_real_evidence(self):
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": [],
                "components": [
                    {
                        "id": "manifest:activity:Main",
                        "type": "activity",
                        "name": "Main",
                        "exported": True,
                        "permission": None,
                    }
                ],
            },
            "evidence": [],
        }

        result = calculate_score(facts)
        self.assertEqual(result["value"], 0)
        self.assertEqual(result["findings"], [])

    def test_exported_component_with_evidence_is_scored(self):
        component_id = "manifest:activity:Main"
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": [],
                "components": [
                    {
                        "id": component_id,
                        "type": "activity",
                        "name": "Main",
                        "exported": True,
                        "permission": None,
                    }
                ],
            },
            "evidence": [
                {
                    "id": component_id,
                    "label": "activity: Main",
                    "snippet": "exported=True",
                    "availability": "available",
                }
            ],
        }

        result = calculate_score(facts)
        self.assertEqual(result["value"], 20)
        self.assertEqual(len(result["findings"]), 1)

    def test_unknown_export_status_is_not_flagged(self):
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": [],
                "components": [
                    {
                        "id": "manifest:activity:Main",
                        "type": "activity",
                        "name": "Main",
                        "exported": None,
                        "permission": None,
                    }
                ],
            },
            "evidence": [
                {
                    "id": "manifest:activity:Main",
                    "label": "activity: Main",
                    "snippet": "exported=None",
                    "availability": "available",
                }
            ],
        }

        result = calculate_score(facts)
        self.assertEqual(result["value"], 0)
        self.assertEqual(result["findings"], [])

    def test_duplicate_components_do_not_double_score(self):
        component = {
            "id": "manifest:activity:Main",
            "type": "activity",
            "name": "Main",
            "exported": True,
            "permission": None,
        }
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": [],
                "components": [component, component.copy()],
            },
            "evidence": [
                {
                    "id": "manifest:activity:Main",
                    "label": "activity: Main",
                    "snippet": "exported=True",
                    "availability": "available",
                }
            ],
        }

        result = calculate_score(facts)
        self.assertEqual(result["value"], 20)
        self.assertEqual(len(result["findings"]), 1)

    def test_every_finding_references_supplied_evidence(self):
        evidence = [
            {
                "id": "manifest:permission:android.permission.INTERNET",
                "label": "android.permission.INTERNET",
                "availability": "available",
            },
            {
                "id": "manifest:activity:Main",
                "label": "activity: Main",
                "snippet": "exported=True",
                "availability": "available",
            },
        ]
        facts = {
            "app": {
                "packageName": "org.example.app",
                "permissions": ["android.permission.INTERNET"],
                "components": [
                    {
                        "id": "manifest:activity:Main",
                        "type": "activity",
                        "name": "Main",
                        "exported": True,
                        "permission": None,
                    }
                ],
            },
            "evidence": evidence,
        }

        result = calculate_score(facts)
        supplied_ids = {item["id"] for item in evidence}

        for finding in result["findings"]:
            self.assertTrue(finding["evidence"])
            for item in finding["evidence"]:
                self.assertIn(item["id"], supplied_ids)


if __name__ == "__main__":
    unittest.main()
