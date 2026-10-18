
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

    # Record deterministic analysis metrics for observability
    findings_count = len(scored["findings"])
    risk_score = scored["value"]

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
            ai_span.set_data("apk_xray.findings_count", findings_count)
            ai_span.set_data("apk_xray.risk_score", risk_score)

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
                # ai.validate_claims: evidence-based claim validation
                # This is a structural + evidence check. Claims must cite
                # known evidence IDs from the deterministic findings.
                # Semantic entailment is NOT verified.
                # ----------------------------------------------------------
                with _sentry_span("ai.validate_claims", "Validate AI claim structure") as val_span:
                    val_span.set_data("stage", "claim_validation")
                    val_span.set_data("apk_xray.claim_count", len(ai_claims))

                    # Build the known evidence set from facts.
                    # These are the ONLY valid evidence IDs AI can reference.
                    # Note: We use facts["evidence"] not findings because
                    # findings might be empty but evidence still exists.
                    known_evidence_ids = set()
                    for evidence_item in facts.get("evidence", []):
                        # Defensive: skip malformed evidence records
                        if not isinstance(evidence_item, dict):
                            continue
                        evidence_id = evidence_item.get("id")
                        # Only add valid string IDs
                        if isinstance(evidence_id, str) and evidence_id:
                            known_evidence_ids.add(evidence_id)

                    # Validate each claim: structure + evidence citations.
                    # Claims are rejected if they cite unknown evidence IDs.
                    kept_claims = []
                    rejected_count = 0

                    for claim in ai_claims:
                        # Structural validation per report.schema.json
                        if not isinstance(claim, dict):
                            rejected_count += 1
                            continue

                        # Required field: id (stableId)
                        claim_id = claim.get("id")
                        if not isinstance(claim_id, str) or not claim_id:
                            rejected_count += 1
                            continue

                        # Required field: text (non-empty string)
                        claim_text = claim.get("text")
                        if not isinstance(claim_text, str) or not claim_text:
                            rejected_count += 1
                            continue

                        # Required field: classification (enum)
                        if claim.get("classification") not in {"Can", "Could", "Cannot Prove"}:
                            rejected_count += 1
                            continue

                        # Required field: status (enum)
                        if claim.get("status") not in {"verified", "removed", "unsupported", "unavailable"}:
                            rejected_count += 1
                            continue

                        # Required field: evidenceIds (non-empty array of stableIds)
                        cited_evidence = claim.get("evidenceIds")
                        if not isinstance(cited_evidence, list):
                            rejected_count += 1
                            continue

                        # Evidence IDs must be non-empty strings
                        valid_evidence_ids = []
                        for eid in cited_evidence:
                            if not isinstance(eid, str) or not eid:
                                # Malformed or empty evidence ID
                                rejected_count += 1
                                break
                            valid_evidence_ids.append(eid)
                        else:
                            # All evidence IDs are valid strings, now check they exist
                            if not valid_evidence_ids:
                                # Empty evidence list (schema requires non-empty for claims)
                                rejected_count += 1
                                continue

                            # Reject claims citing unknown evidence IDs
                            if not all(eid in known_evidence_ids for eid in valid_evidence_ids):
                                rejected_count += 1
                                continue

                            # Claim is structurally valid and cites known evidence
                            kept_claims.append(claim)

                    # Record validation metrics
                    val_span.set_data("apk_xray.kept_claim_count", len(kept_claims))
                    val_span.set_data("apk_xray.rejected_claim_count", rejected_count)

                    # Determine validation outcome
                    if rejected_count == 0:
                        validation_outcome = "ok"
                    elif len(kept_claims) > 0:
                        validation_outcome = "partial_rejection"
                    else:
                        validation_outcome = "full_rejection"

                    val_span.set_data("apk_xray.validation_outcome", validation_outcome)
                    val_span.set_data("outcome", validation_outcome)

                # Use only validated claims
                # (deterministic claims remain available if AI fails validation)
                if kept_claims:
                    report["claims"] = kept_claims

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
