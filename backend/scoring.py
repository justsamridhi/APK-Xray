
"""Documented, deterministic APK-Xray scoring rules."""

from __future__ import annotations

from typing import Any

RULES = (
    ("APKX-NET-001", {"android.permission.INTERNET"}, 12, "low", "Network access declared"),
    ("APKX-SMS-001", {"android.permission.SEND_SMS", "android.permission.READ_SMS"}, 25, "high", "SMS permission declared"),
    ("APKX-MIC-001", {"android.permission.RECORD_AUDIO"}, 18, "medium", "Microphone permission declared"),
    (
        "APKX-LOC-001",
        {
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.ACCESS_COARSE_LOCATION",
        },
        12,
        "medium",
        "Location permission declared",
    ),
)


def calculate_score(facts: dict[str, Any]) -> dict[str, Any]:
    """Score declared capabilities only when supported by parser evidence."""
    app = facts["app"]
    permissions = set(app.get("permissions", []))
    evidence_items = facts.get("evidence", [])

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for item in evidence_items:
        evidence_id = item.get("id")
        if isinstance(evidence_id, str) and evidence_id:
            evidence_by_id.setdefault(evidence_id, item)

    findings: list[dict[str, Any]] = []
    breakdown: list[dict[str, Any]] = []

    for rule_id, required, points, severity, title in RULES:
        matched = sorted(permissions & required)
        supported = [
            permission
            for permission in matched
            if f"manifest:permission:{permission}" in evidence_by_id
        ]

        if not supported:
            continue

        rule_evidence = [
            evidence_by_id[f"manifest:permission:{permission}"]
            for permission in supported
        ]

        if rule_id == "APKX-SMS-001":
            descriptions = {
                "android.permission.READ_SMS": "read SMS messages",
                "android.permission.SEND_SMS": "send SMS messages",
            }
            capability = " and ".join(
                descriptions[permission] for permission in supported
            )
            summary = (
                f"The manifest declares permission(s) associated with the "
                f"ability to {capability}. This does not establish runtime use."
            )
        elif rule_id == "APKX-NET-001":
            summary = (
                "The manifest declares internet access. This does not establish "
                "that the app sends data or communicates maliciously."
            )
        elif rule_id == "APKX-MIC-001":
            summary = (
                "The manifest declares microphone access. This does not establish "
                "that the app records audio at runtime."
            )
        else:
            summary = (
                "The manifest declares location permission(s): "
                + ", ".join(supported)
                + ". This does not establish that location is accessed at runtime."
            )

        findings.append(
            {
                "ruleId": rule_id,
                "severity": severity,
                "title": title,
                "summary": summary,
                "evidence": rule_evidence,
                "claimStatus": "verified",
                "points": points,
                "explanations": {
                    "en": summary,
                    "hi": (
                        "मैनिफेस्ट में संबंधित अनुमति घोषित है। इससे अपने-आप "
                        "रनटाइम व्यवहार या दुर्भावनापूर्ण इरादा सिद्ध नहीं होता।"
                    ),
                },
            }
        )
        breakdown.append({"ruleId": rule_id, "points": points})

    # Aggregate exported components into one rule contribution.
    seen_component_ids: set[str] = set()
    exported_evidence: list[dict[str, Any]] = []
    exported_names: list[str] = []

    for component in app.get("components", []):
        component_id = component.get("id")
        component_name = component.get("name")

        if (
            component.get("exported") is not True
            or component.get("permission")
            or not isinstance(component_id, str)
            or not isinstance(component_name, str)
            or component_id in seen_component_ids
        ):
            continue

        seen_component_ids.add(component_id)
        evidence_item = evidence_by_id.get(component_id)

        # Never fabricate missing evidence.
        if evidence_item is None:
            continue

        exported_evidence.append(evidence_item)
        exported_names.append(component_name)

    if exported_evidence:
        summary = (
            "The manifest declares these components exported without a "
            "component-level permission: "
            + ", ".join(exported_names)
            + ". Review whether external access is intended; this finding "
            "alone does not prove exploitability."
        )
        findings.append(
            {
                "ruleId": "APKX-EXP-001",
                "severity": "high",
                "title": "Exported component without a declared permission",
                "summary": summary,
                "evidence": exported_evidence,
                "claimStatus": "verified",
                "points": 20,
                "explanations": {
                    "en": summary,
                    "hi": (
                        "मैनिफेस्ट में एक या अधिक घटक exported घोषित हैं और "
                        "उन पर घटक-स्तर की अनुमति नहीं दिखती। इससे अपने-आप "
                        "शोषण योग्य होना सिद्ध नहीं होता।"
                    ),
                },
            }
        )
        breakdown.append({"ruleId": "APKX-EXP-001", "points": 20})

    value = min(100, sum(item["points"] for item in breakdown))
    severity = (
        "low"
        if value < 20
        else "moderate"
        if value < 45
        else "high"
        if value < 70
        else "very-high"
    )
    label = {
        "low": "Low exposure",
        "moderate": "Moderate exposure",
        "high": "High exposure",
        "very-high": "Very high exposure",
    }[severity]

    return {
        "value": value,
        "label": label,
        "severity": severity,
        "breakdown": breakdown,
        "findings": findings,
    }
