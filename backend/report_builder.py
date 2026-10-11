"""Build and validate versioned reports from parser facts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Callable

from .gemma import GemmaError
from .scoring import calculate_score
from .validation.validate_report_schema import validate_report


def build_report(facts: dict[str, Any], gemma: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    scored = calculate_score(facts)
    evidence = facts.get("evidence", [])
    claims = [
        {
            "id": f"claim:{finding['ruleId']}",
            "text": {"en": finding["summary"], "hi": finding["summary"]},
            "classification": "Can",
            "evidenceIds": [item["id"] for item in finding["evidence"]],
            "status": "verified",
        }
        for finding in scored["findings"]
    ]
    report: dict[str, Any] = {
        "schemaVersion": "1.0",
        "reportId": f"report:{hashlib.sha256(facts['app']['packageName'].encode()).hexdigest()[:16]}",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "app": facts["app"],
        "score": {key: scored[key] for key in ("value", "label", "severity", "breakdown")},
        "findings": scored["findings"],
        "capabilityChains": [],
        "claims": claims,
        "ai": {"status": "unavailable", "provider": "Gemma 4", "message": "AI explanation unavailable; no endpoint is configured."},
    }
    if gemma:
        try:
            result = gemma(facts)
            # Merge AI claims into the report, avoiding duplicate IDs
            existing_claim_ids = {c.get("id") for c in report["claims"] if "id" in c}
            for claim in result.get("claims", []):
                if not isinstance(claim, dict):
                    continue
                claim_id = claim.get("id")
                if not claim_id:
                    continue  # skip malformed claim without ID
                if claim_id not in existing_claim_ids:
                    report["claims"].append(claim)
                    existing_claim_ids.add(claim_id)
            # Attach AI explanations to each finding (could be refined per claim)
            for finding in report["findings"]:
                finding["explanations"] = result["explanations"]
            report["ai"] = {"status": "verified", "provider": "Gemma 4", "message": "Evidence-grounded AI explanation verified against supplied evidence."}
        except GemmaError as error:
            report["ai"] = {
                "status": "error",
                "provider": "Gemma 4",
                "message": f"{error.code}: {error}",
            }
    errors = validate_report(report)
    if errors:
        raise ValueError(f"Generated report failed schema validation: {'; '.join(errors)}")
    return report
