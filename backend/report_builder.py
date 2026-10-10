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
            "text": finding["summary"],
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
            report["claims"] = result["claims"]
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
