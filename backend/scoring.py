"""Documented, deterministic APK-Xray scoring rules."""

from __future__ import annotations

from typing import Any

# Scoring rules: (rule_id, required_permissions_set, points, severity, title)
RULES = (
    ("APKX-NET-001", {"android.permission.INTERNET"}, 2, "low", "Network access declared (informational)"),
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



# RULES = (
#     ("APKX-NET-001", {"android.permission.INTERNET"}, 2, "low", "Network access declared (informational)"),
#     (
#         "APKX-SMS-001",
#         {"android.permission.SEND_SMS", "android.permission.READ_SMS"},
#         25,
#         "high",
#         "SMS access declared",
#     ),
#     (
#         "APKX-MIC-001",
#         {"android.permission.RECORD_AUDIO"},
#         18,
#         "medium",
#         "Microphone access declared",
#     ),
#     (
#         "APKX-LOC-001",
#         {"android.permission.ACCESS_FINE_LOCATION", "android.permission.ACCESS_COARSE_LOCATION"},
#         12,
#         "medium",
#         "Location access declared",
#     ),
# )





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
        # Launcher activities must be exported so users can start the app.
        if component.get("exported") is True and not component.get("permission") and not component.get("isLauncher") and component.get("type") != "activity-alias":
            rule_id = "APKX-EXP-001"
            evidence_item = next(
                (item for item in evidence if item.get("id") == component.get("id")),
                {"id": component["id"], "label": component["name"], "snippet": "exported=true", "availability": "available"},
            )
            findings.append(
                {
                    "ruleId": rule_id,
                    "severity": "medium",
                    "title": "Potentially exposed exported component",
                    "summary": f"The manifest declares {component['name']} as exported without a declared component or application permission. This does not prove runtime exploitability.",
                    "evidence": [evidence_item],
                    "claimStatus": "verified",
                    "points": 20,
                    "explanations": {
                        "en": "Static manifest evidence shows an exported component without a declared permission. This is a review signal, not proof of exploitability or malicious behavior.",
                        "hi": "मैनिफेस्ट एक ऐसे घटक को उजागर करता है जिस पर अनुमति घोषित नहीं है।",
                    },
                }
            )
            breakdown.append({"ruleId": rule_id, "points": 20})

    # Cap total points for exported components (APKX-EXP-001) at 20
    exp_rule_id = "APKX-EXP-001"
    exp_points = sum(b["points"] for b in breakdown if b["ruleId"] == exp_rule_id)

    if exp_points > 20:
        excess = exp_points - 20

        # Reduce breakdown points, preserving earlier entries first
        for b in breakdown:
            if b["ruleId"] == exp_rule_id and excess > 0:
                reduction = min(b["points"], excess)
                b["points"] -= reduction
                excess -= reduction

        # Keep finding points consistent with the 20-point cap
        remaining = 20
        for f in findings:
            if f["ruleId"] == exp_rule_id:
                kept = min(f.get("points", 0), remaining)
                f["points"] = kept
                remaining -= kept

    # Always calculate and return the final score
    value = min(100, sum(item["points"] for item in breakdown))
    severity = (
        "low" if value < 20
        else "moderate" if value < 45
        else "high" if value < 70
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
