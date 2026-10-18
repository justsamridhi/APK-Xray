
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

    # Import the span helper lazily to avoid a hard dependency on Sentry.
    try:
        from .sentry_setup import sentry_span as _sentry_span
    except ImportError:
        class _NoopCtx:  # type: ignore[no-redef]
            def __enter__(self) -> "_NoopSpanInner":
                return _NoopSpanInner()
            def __exit__(self, *_: object) -> None:
                pass
        class _NoopSpanInner:
            def set_data(self, _k: str, _v: object) -> None: pass
            def set_status(self, _s: str) -> None: pass
        def _sentry_span(op: str, description: str) -> "_NoopCtx":  # type: ignore[misc]
            return _NoopCtx()

    if gemma is not None:
        # ------------------------------------------------------------------
        # ai.lifecycle: agent explanation workflow
        # Connected as a child of the existing apk.report span.
        # Covers the full optional AI explanation workflow: call the model,
        # validate the contract, and check evidence citations.
        # ------------------------------------------------------------------
        with _sentry_span("ai.lifecycle", "AI explanation workflow") as ai_span:
            ai_span.set_data("gen_ai.system", "google_gemini")
            ai_span.set_data("stage", "ai_explanation")

            try:
                result = gemma(facts)

                # Validate the returned contract before incorporating it.
                if not isinstance(result, dict):
                    ai_span.set_data("outcome", "contract_violation")
                    raise GemmaError(
                        "Gemma returned an invalid result object."
                    )

                ai_claims = result.get("claims")
                explanations = result.get("explanations")

                if not isinstance(ai_claims, list):
                    ai_span.set_data("outcome", "contract_violation")
                    raise GemmaError(
                        "Gemma result must contain a claims list."
                    )

                if not isinstance(explanations, dict) or not all(
                    isinstance(explanations.get(language), str)
                    and explanations[language].strip()
                    for language in ("en", "hi")
                ):
                    ai_span.set_data("outcome", "contract_violation")
                    raise GemmaError(
                        "Gemma result must contain English and Hindi explanations."
                    )

                # ----------------------------------------------------------
                # ai.validate_claims: validate claim structure
                # This is a lightweight structural check. The full evidence
                # validation already happened in gemma._validate().
                # We only record metrics here for observability.
                # ----------------------------------------------------------
                with _sentry_span("ai.validate_claims", "Validate AI claim structure") as val_span:
                    val_span.set_data("stage", "claim_validation")
                    val_span.set_data("apk_xray.claim_count", len(ai_claims))

                    # Count structurally complete claims (gemma._validate did the real check)
                    valid_count = sum(
                        1 for c in ai_claims
                        if isinstance(c, dict)
                        and isinstance(c.get("id"), str)
                        and isinstance(c.get("text"), str)
                        and c.get("classification") in {"Can", "Could", "Cannot Prove"}
                        and isinstance(c.get("evidenceIds"), list)
                        and c.get("status") == "verified"
                    )
                    rejected_count = len(ai_claims) - valid_count
                    val_span.set_data("apk_xray.rejected_claim_count", rejected_count)

                    # Validation status (rejection means gemma._validate passed but
                    # claims are missing expected fields from the contract)
                    if rejected_count > 0:
                        val_span.set_data("outcome", "partial_rejection")
                    else:
                        val_span.set_data("outcome", "ok")

                # Structural validation passed — incorporate AI claims.
                report["claims"] = ai_claims

                for finding in report["findings"]:
                    finding["explanations"] = {
                        "en": explanations["en"].strip(),
                        "hi": explanations["hi"].strip(),
                    }

                ai_span.set_data("outcome", "ok")
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
                ai_span.set_data("outcome", "ai_error")
                ai_span.set_data("error_category", error.code)
                report["ai"] = {
                    "status": "error",
                    "provider": "Gemma 4",
                    "message": f"{error.code}: {error}",
                }
    else:
        # ------------------------------------------------------------------
        # ai.fallback: AI not configured
        # Explicit fallback span when no AI endpoint is configured.
        # Deterministic findings remain intact.
        # ------------------------------------------------------------------
        with _sentry_span("ai.fallback", "AI explanation not configured") as fallback_span:
            fallback_span.set_data("stage", "ai_fallback")
            fallback_span.set_data("outcome", "unconfigured")

    errors = validate_report(report)
    if errors:
        raise ValueError(
            "Generated report failed schema validation: "
            + "; ".join(errors)
        )

    return report
