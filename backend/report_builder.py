
"""Build and validate versioned reports from parser facts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .gemma import GemmaError
from .scoring import calculate_score
from .validation.validate_report_schema import validate_report


def build_report(
    facts: dict[str, Any],
    gemma: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scored = calculate_score(facts)

    # Deterministic claims are derived from the static findings.
    # They remain available even if the optional AI explanation fails.
    claims = [
        {
            "id": f"claim:{finding['ruleId']}",
            "text": finding["summary"],
            "classification": "Can",
            "evidenceIds": [
                item["id"] for item in finding["evidence"]
            ],
            "status": "verified",
        }
        for finding in scored["findings"]
    ]

    report: dict[str, Any] = {
        "schemaVersion": "1.0",
        "reportId": f"report:{uuid.uuid4()}",
        "generatedAt": (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        ),
        "app": facts["app"],
        "score": {
            key: scored[key]
            for key in ("value", "label", "severity", "breakdown")
        },
        "findings": scored["findings"],
        "capabilityChains": [],
        "claims": claims,
        "ai": {
            "status": "unavailable",
            "provider": "Gemma 4",
            "message": (
                "AI explanation unavailable; no endpoint is configured."
            ),
        },
    }

    if gemma is not None:
        try:
            result = gemma(facts)

            # Validate the returned contract before incorporating it.
            if not isinstance(result, dict):
                raise GemmaError(
                    "Gemma returned an invalid result object."
                )

            ai_claims = result.get("claims")
            explanations = result.get("explanations")

            if not isinstance(ai_claims, list):
                raise GemmaError(
                    "Gemma result must contain a claims list."
                )

            if not isinstance(explanations, dict) or not all(
                isinstance(explanations.get(language), str)
                and explanations[language].strip()
                for language in ("en", "hi")
            ):
                raise GemmaError(
                    "Gemma result must contain English and Hindi explanations."
                )

            report["claims"] = ai_claims

            for finding in report["findings"]:
                finding["explanations"] = {
                    "en": explanations["en"].strip(),
                    "hi": explanations["hi"].strip(),
                }

            report["ai"] = {
                "status": "available",
                "provider": "Gemma 4",
                "message": (
                    "AI explanations generated and structurally validated. "
                    "Claims have not been independently verified for "
                    "semantic entailment by the AI validation layer."
                ),
            }

        except GemmaError as error:
            # AI failure must not discard deterministic static findings.
            report["ai"] = {
                "status": "error",
                "provider": "Gemma 4",
                "message": f"{error.code}: {error}",
            }

    errors = validate_report(report)
    if errors:
        raise ValueError(
            "Generated report failed schema validation: "
            + "; ".join(errors)
        )

    return report
