import json
import unittest
from pathlib import Path

from validate_report_schema import FIXTURE_DIR, load_json, validate_report


class ReportSchemaTests(unittest.TestCase):
    def test_valid_report_fixture(self) -> None:
        self.assertEqual(validate_report(load_json(FIXTURE_DIR / "valid.json")), [])

    def test_empty_report_fixture_is_valid(self) -> None:
        self.assertEqual(validate_report(load_json(FIXTURE_DIR / "empty.json")), [])

    def test_malformed_fixture_is_invalid(self) -> None:
        errors = validate_report(load_json(FIXTURE_DIR / "malformed.json"))
        self.assertTrue(errors)

    def test_partial_fixture_is_invalid(self) -> None:
        errors = validate_report(load_json(FIXTURE_DIR / "partial.json"))
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
