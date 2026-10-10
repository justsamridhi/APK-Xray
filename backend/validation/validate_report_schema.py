"""Validate APK-Xray report JSON against the versioned report schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parents[1] / "schema" / "report.schema.json"
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "reports"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_report(value: Any, schema_path: Path = SCHEMA_PATH) -> list[str]:
    """Return schema errors, or an empty list when the report is valid."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:
        raise RuntimeError(
            "jsonschema is not installed; install validation dependencies with "
            "`python -m pip install -r backend\\requirements-validation.txt`."
        ) from error

    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to a report JSON file.")
    args = parser.parse_args()

    if not args.report.is_file():
        print(json.dumps({"valid": False, "errors": [f"Report not found: {args.report}"]}))
        return 2

    try:
        errors = validate_report(load_json(args.report))
    except (OSError, json.JSONDecodeError, RuntimeError) as error:
        print(json.dumps({"valid": False, "errors": [str(error)]}))
        return 1

    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
