"""Documented, deterministic APK-Xray scoring rules."""

from __future__ import annotations

from typing import Any

RULES = (
    ("APKX-NET-001", {"android.permission.INTERNET"}, 12, "low", "Network access declared"),
    (
        "APKX-SMS-001",
        {"android.permission.SEND_SMS", "android.permission.READ_SMS"},
        25,
        "high",
        "SMS access declared",
    ),
    (
        "APKX-MIC-001",
        {"android.permission.RECORD_AUDIO"},
        18,
        "medium",
        "Microphone access declared",
    ),
    (
        "APKX-LOC-001",
        {"android.permission.ACCESS_FINE_LOCATION", "android.permission.ACCESS_COARSE_LOCATION"},
        12,
        "medium",
        "Location access declared",
    ),
)


def _evidence(evidence: list[dict[str, Any]], permission: str) -> dict[str, Any]:
    return next(
        (
            item
            for item in evidence
            if item.get("id") == f"manifest:permission:{permission}"
        ),
        {
            "id": f"manifest:permission:{permission}",
            "label": permission,
            "snippet": permission,
            "availability": "available",
        },
    )


def calculate_score(facts: dict[str, Any]) -> dict[str, Any]:
    permissions = set(facts["app"].get("permissions", []))
    evidence = facts.get("evidence", [])
    findings: list[dict[str, Any]] = []
    breakdown: list[dict[str, Any]] = []
    for rule_id, required, points, severity, title in RULES:
        matched = sorted(permissions & required)
        if not matched:
            continue
        rule_evidence = [_evidence(evidence, permission) for permission in matched]
        finding = {
            "ruleId": rule_id,
            "severity": severity,
            "title": title,
            "summary": f"The manifest declares {', '.join(matched)}.",
            "evidence": rule_evidence,
            "claimStatus": "verified",
            "points": points,
            "explanations": {
                "en": f"Static evidence confirms {', '.join(matched)} is declared.",
                "hi": f"स्थिर साक्ष्य पुष्टि करता है कि {', '.join(matched)} घोषित है।",
            },
        }
        findings.append(finding)
        breakdown.append({"ruleId": rule_id, "points": points})

    for component in facts["app"].get("components", []):
        if component.get("exported") is True and not component.get("permission"):
            rule_id = "APKX-EXP-001"
            evidence_item = next(
                (item for item in evidence if item.get("id") == component.get("id")),
                {"id": component["id"], "label": component["name"], "snippet": "exported=true", "availability": "available"},
            )
            findings.append(
                {
                    "ruleId": rule_id,
                    "severity": "high",
                    "title": "Unprotected exported component",
                    "summary": f"{component['name']} is exported without a component permission.",
                    "evidence": [evidence_item],
                    "claimStatus": "verified",
                    "points": 20,
                    "explanations": {
                        "en": "The manifest exposes a component without a declared permission.",
                        "hi": "मैनिफेस्ट एक ऐसे घटक को उजागर करता है जिस पर अनुमति घोषित नहीं है।",
                    },
                }
            )
            breakdown.append({"ruleId": rule_id, "points": 20})

    value = min(100, sum(item["points"] for item in breakdown))
    severity = "low" if value < 20 else "moderate" if value < 45 else "high" if value < 70 else "very-high"
    label = {"low": "Low exposure", "moderate": "Moderate exposure", "high": "High exposure", "very-high": "Very high exposure"}[severity]
    return {"value": value, "label": label, "severity": severity, "breakdown": breakdown, "findings": findings}
