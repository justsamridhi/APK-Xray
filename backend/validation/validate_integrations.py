"""Reproducible Androguard and Gemma 4 boundary validation.

This is intentionally a standalone spike. It does not execute an APK, persist
APK data, or make a model request unless an endpoint is explicitly provided.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def extract_with_androguard(apk_path: Path) -> dict[str, Any]:
    try:
        from androguard.core.apk import APK
    except ImportError as error:
        raise RuntimeError(
            "Androguard is not installed; install the validation dependency with "
            "`python -m pip install androguard`."
        ) from error

    if not zipfile.is_zipfile(apk_path):
        raise ValueError("The fixture is not a ZIP/APK archive.")

    started = time.perf_counter()
    apk = APK(str(apk_path))
    permissions = sorted(apk.get_permissions() or [])
    package_name = apk.get_package()
    if not package_name:
        raise ValueError("Androguard extracted no package name from the manifest.")
    return {
        "package": package_name,
        "permissions": permissions,
        "permission_count": len(permissions),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def gemma_prompt(extracted: dict[str, Any]) -> dict[str, Any]:
    return {
        "system": (
            "Return JSON only. Claims must cite supplied evidence IDs. "
            "Do not infer intent from a permission alone."
        ),
        "user": {
            "task": "Summarize static APK facts as evidence-grounded claims.",
            "facts": extracted,
            "evidence": [
                {"id": "manifest.package", "value": extracted.get("package")},
                {"id": "manifest.permissions", "value": extracted.get("permissions", [])},
            ],
            "output_schema": {
                "claims": [
                    {
                        "text": "string",
                        "classification": "Can | Could | Cannot Prove",
                        "evidence_ids": ["string"],
                    }
                ]
            },
        },
    }


def validate_structured_response(value: Any) -> dict[str, Any]:
    payload = value.get("structured_output", value) if isinstance(value, dict) else value
    claims = payload.get("claims") if isinstance(payload, dict) else None
    if not isinstance(claims, list):
        raise ValueError("Gemma response does not contain a structured claims list.")
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError(f"Claim {index} is not an object.")
        if not isinstance(claim.get("text"), str) or not claim["text"].strip():
            raise ValueError(f"Claim {index} has no text.")
        if claim.get("classification") not in {"Can", "Could", "Cannot Prove"}:
            raise ValueError(f"Claim {index} has an unsupported classification.")
        if not isinstance(claim.get("evidence_ids"), list):
            raise ValueError(f"Claim {index} has no evidence_ids list.")
    return {"claim_count": len(claims), "claims": claims}


def call_gemma(endpoint: str, prompt: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"messages": [{"role": "user", "content": json.dumps(prompt)}]}).encode(),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Gemma endpoint request failed: {error}") from error
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Gemma response exceeded the 2 MiB validation limit.")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as error:
        raise ValueError("Gemma endpoint returned malformed JSON.") from error
    result = validate_structured_response(parsed)
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True, help="Path to a fixture APK.")
    parser.add_argument("--gemma-endpoint", help="Optional compatible structured-output endpoint.")
    args = parser.parse_args()

    if not args.apk.is_file():
        print(json.dumps({"status": "error", "error": f"APK fixture not found: {args.apk}"}))
        return 2

    result: dict[str, Any] = {
        "status": "ok",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "androguard": package_version("androguard"),
            "requests": package_version("requests"),
        },
        "apk": {"path": str(args.apk), "bytes": args.apk.stat().st_size},
    }
    try:
        extracted = extract_with_androguard(args.apk)
        result["androguard"] = {"status": "ok", "facts": extracted}
    except (RuntimeError, ValueError, OSError) as error:
        result["androguard"] = {"status": "error", "error": str(error)}
        result["status"] = "error"
        extracted = {"package": None, "permissions": []}

    prompt = gemma_prompt(extracted)
    if args.gemma_endpoint:
        try:
            result["gemma"] = {"status": "ok", **call_gemma(args.gemma_endpoint, prompt, os.environ.get("GEMMA4_API_KEY"))}
        except (RuntimeError, ValueError) as error:
            result["gemma"] = {"status": "error", "error": str(error)}
            result["status"] = "error"
    else:
        result["gemma"] = {
            "status": "dry-run",
            "message": "No endpoint supplied; request was not sent.",
            "prompt": prompt,
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
