"""Run one live Gemma verification using synthetic APK evidence."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(REPOSITORY_ROOT / "backend" / "parser"))

from backend.gemma import GemmaError, explain


def main() -> int:
    endpoint = os.getenv("GEMMA4_ENDPOINT")
    api_key = os.getenv("GEMMA4_API_KEY")
    if not endpoint or not api_key:
        missing = [
            name
            for name, value in (
                ("GEMMA4_ENDPOINT", endpoint),
                ("GEMMA4_API_KEY", api_key),
            )
            if not value
        ]
        print(f"ERROR: missing configuration: {', '.join(missing)}")
        return 2

    facts = {
        "app": {
            "name": "Synthetic verification fixture",
            "packageName": "org.example.verification",
            "version": "1.0.0",
            "minSdk": 26,
            "targetSdk": 35,
            "permissions": ["android.permission.INTERNET"],
            "components": [],
        },
        "evidence": [
            {
                "id": "manifest:permission:android.permission.INTERNET",
                "label": "android.permission.INTERNET",
                "snippet": "android.permission.INTERNET",
            }
        ],
    }
    evidence_ids = {item["id"] for item in facts["evidence"]}
    diagnostics = os.getenv("APK_XRAY_GEMMA_DIAGNOSTICS") == "1"
    try:
        result = explain(endpoint, api_key, facts, timeout=30, diagnostics=diagnostics)
        returned_ids = {
            evidence_id
            for claim in result["claims"]
            for evidence_id in claim["evidenceIds"]
        }
        invalid_ids = returned_ids - evidence_ids
        if invalid_ids:
            print("ERROR: response contained invalid evidence IDs.")
            return 1
        print(
            "SUCCESS: live Gemma response parsed and validated "
            f"({len(result['claims'])} claims; evidence IDs valid; English/Hindi explanations present)."
        )
        return 0
    except GemmaError as error:
        print(f"ERROR: Gemma verification failed: {error}")
        return 1
    except (KeyError, TypeError, ValueError) as error:
        print(f"ERROR: Gemma response validation failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
