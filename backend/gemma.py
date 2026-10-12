"""Optional, evidence-only Gemma 4 explanation adapter."""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
import urllib.parse
from typing import Any


class GemmaError(RuntimeError):
    """Raised when a configured Gemma endpoint cannot produce valid output."""

    def __init__(self, message: str, code: str = "gemma_error") -> None:
        self.code = code
        super().__init__(message)


MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _validate(value: Any, evidence_ids: set[str]) -> dict[str, Any]:
    payload = value.get("structured_output", value) if isinstance(value, dict) else value
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise GemmaError("Gemma response must contain a claims list.")
    claims = []
    for index, claim in enumerate(payload["claims"]):
        # Validate text field: allow string (legacy) or dict with en/hi languages
        text_field = claim.get("text")
        if isinstance(text_field, str):
            if not text_field.strip():
                raise GemmaError(f"Gemma claim {index} text is empty.")
            bilingual_text = {"en": text_field.strip(), "hi": text_field.strip()}
        elif isinstance(text_field, dict):
            en = text_field.get("en")
            hi = text_field.get("hi")
            if not (isinstance(en, str) and en.strip()) or not (isinstance(hi, str) and hi.strip()):
                raise GemmaError(f"Gemma claim {index} missing or empty language text.")
            bilingual_text = {"en": en.strip(), "hi": hi.strip()}
        else:
            raise GemmaError(f"Gemma claim {index} text is malformed.")
        if claim.get("classification") not in {"Can", "Could", "Cannot Prove"}:
            raise GemmaError(f"Gemma claim {index} has an invalid classification.")
        ids = claim.get("evidenceIds", claim.get("evidence_ids"))
        if not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item in evidence_ids for item in ids):
            raise GemmaError(f"Gemma claim {index} cites unknown evidence.")
        # Preserve claim status if provided; default to "generated" for AI‑generated claims.
        claim_status = claim.get("status", "generated")
        # Validate that the status is one of the allowed enum values.
        if claim_status not in {"verified", "removed", "unsupported", "unavailable", "generated"}:
            raise GemmaError(f"Gemma claim {index} has an invalid status '{claim_status}'.")
        claims.append(
            {
                "id": f"claim:gemma:{index + 1}",
                "text": bilingual_text,
                "classification": claim["classification"],
                "evidenceIds": ids,
                "status": claim_status,
            }
        )
    explanations = payload.get("explanations", {})
    if not isinstance(explanations, dict) or not all(
        isinstance(explanations.get(language), str)
        and explanations[language].strip()
        for language in ("en", "hi")
    ):
        raise GemmaError("Gemma response must contain English and Hindi explanations.")
    return {
        "claims": claims,
        "explanations": {
            "en": explanations["en"].strip(),
            "hi": explanations["hi"].strip(),
        },
    }


def _candidate_parts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        raise GemmaError("Gemma response was not a JSON object.")
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        suffix = " The prompt may have been blocked." if value.get("promptFeedback") else ""
        raise GemmaError(f"Gemma response contained no candidates.{suffix}")
    candidate = candidates[0]
    content = candidate.get("content") if isinstance(candidate, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise GemmaError("Gemma response contained no content parts.")
    return [part for part in parts if isinstance(part, dict)]


def _extract_generated_text(value: Any) -> str:
    parts = _candidate_parts(value)
    has_thought_parts = any(part.get("thought") is True for part in parts)
    if has_thought_parts:
        selected_parts = [
            part
            for part in parts
            if part.get("thought") is not True and isinstance(part.get("text"), str)
        ]
        if not selected_parts:
            raise GemmaError(
                "Gemma response contained thought content but no usable "
                "non-thought final output."
            )
    else:
        selected_parts = [
            part for part in parts if isinstance(part.get("text"), str)
        ]
    text = "".join(part["text"] for part in selected_parts).strip()
    if not text:
        raise GemmaError("Gemma response contained empty generated text.")
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) < 3:
            raise GemmaError("Gemma returned an empty Markdown code fence.")
        text = "\n".join(lines[1:-1]).strip()
    if not text:
        raise GemmaError("Gemma returned an empty Markdown code fence.")
    return text


def _response_diagnostics(value: Any) -> str:
    if not isinstance(value, dict):
        return "response_shape=non-object"
    candidates = value.get("candidates")
    if not isinstance(candidates, list):
        return "response_shape=missing-candidates"
    first = candidates[0] if candidates else {}
    content = first.get("content") if isinstance(first, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    finish_reason = first.get("finishReason") if isinstance(first, dict) else None
    return (
        f"candidates={len(candidates)}, "
        f"finish_reason={finish_reason or 'unknown'}, "
        f"parts={len(parts) if isinstance(parts, list) else 0}"
    )


def _part_diagnostics(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return []
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return []
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return []

    decoder = json.JSONDecoder()
    diagnostics = []
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            diagnostics.append(
                f"part={index}, thought=absent, text_length=0, "
                "likely_json_object=no, expected_top_level_keys=none"
            )
            continue
        thought = part.get("thought")
        thought_state = "true" if thought is True else "false" if thought is False else "absent"
        text = part.get("text") if isinstance(part.get("text"), str) else ""
        object_keys: set[str] = set()
        for offset, character in enumerate(text):
            if character != "{":
                continue
            try:
                decoded, _ = decoder.raw_decode(text[offset:])
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                object_keys.update(str(key) for key in decoded)
        likely_json = "yes" if "{" in text else "no"
        expected_keys = (
            "claims,explanations"
            if {"claims", "explanations"}.issubset(object_keys)
            else "none"
        )
        diagnostics.append(
            f"part={index}, thought={thought_state}, text_length={len(text)}, "
            f"likely_json_object={likely_json}, "
            f"expected_top_level_keys={expected_keys}"
        )
    return diagnostics


def _parse_generated_json(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    decoded: list[tuple[int, int, dict[str, Any]]] = []
    shapes: list[str] = []
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, consumed = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        shapes.append(",".join(sorted(str(key) for key in value.keys())) or "<empty>")
        decoded.append((index, index + consumed, value))

    outermost = [
        item
        for item in decoded
        if not any(
            other[0] < item[0] and other[1] >= item[1]
            for other in decoded
        )
    ]
    candidates: list[dict[str, Any]] = []
    contract_failures: list[str] = []
    for _, _, value in outermost:
        payload = value.get("structured_output", value)
        explanations = payload.get("explanations") if isinstance(payload, dict) else None
        claims = payload.get("claims") if isinstance(payload, dict) else None
        if (
            isinstance(payload, dict)
            and isinstance(claims, list)
            and isinstance(explanations, dict)
            and all(
                isinstance(explanations.get(language), str)
                and explanations[language].strip()
                for language in ("en", "hi")
            )
        ):
            candidates.append(value)
        elif isinstance(payload, dict):
            claim_type = type(claims).__name__
            explanation_keys = (
                ",".join(sorted(str(key) for key in explanations))
                if isinstance(explanations, dict)
                else "none"
            )
            claim_item_keys = "none"
            if isinstance(claims, list) and claims and isinstance(claims[0], dict):
                claim_item_keys = ",".join(sorted(str(key) for key in claims[0]))
            contract_failures.append(
                f"claims_type={claim_type},claim_item_keys={claim_item_keys},"
                f"explanation_keys={explanation_keys}"
            )
    if len(candidates) != 1:
        raise GemmaError(
            "Gemma generated text did not contain exactly one complete JSON "
            "object with claims and explanations"
            f" (contract_objects={len(candidates)}, "
            f"json_object_shapes={';'.join(shapes[:8]) or 'none'}, "
            f"contract_failures={';'.join(contract_failures[:3]) or 'none'})."
        )
    return candidates[0]


def explain(
    endpoint: str,
    api_key: str | None,
    facts: dict[str, Any],
    timeout: float | None = None,
    diagnostics: bool = False,
) -> dict[str, Any]:
    if not endpoint:
        raise GemmaError("GEMMA4_ENDPOINT is not configured.")
    if not api_key:
        raise GemmaError("GEMMA4_API_KEY is not configured.")
    evidence = [
        {"id": item["id"], "label": item["label"], "snippet": item.get("snippet")}
        for item in facts.get("evidence", [])
    ]
    prompt = {
        "task": (
            "Return exactly one JSON object and nothing else. Do not use Markdown "
            "code fences. Do not add an introduction, explanation, or trailing "
            "commentary. Explain only the supplied static APK evidence. Do not "
            "score, infer runtime behavior, or invent findings. The object must "
            "have claims as a JSON array. Each claims array item must be an "
            "object with text (string), classification (exactly Can, Could, or "
            "Cannot Prove), and evidenceIds (array of supplied evidence ID "
            "strings). Do not use evidence IDs as object keys. Explanations must "
            "be an object with non-empty English (en) and Hindi (hi) strings. "
            "Use only supplied evidence IDs. "
            "Keep both explanations concise. If no supplied evidence supports a "
            "claim, return an empty claims list."
        ),
        "facts": {"app": facts["app"], "evidence": evidence},
        "required_output_fields": ["claims", "explanations"],
    }
    # Build the request URL without adding the API key as a query parameter.
    request_endpoint = endpoint
    # Include the API key in the request headers as required by Google Generative AI.
    request_headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
    # Payload expected by the Google Generative AI (Gemma) endpoint.
    payload = {
        "contents": [
            {
                "parts": [{"text": json.dumps(prompt, ensure_ascii=False)}]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        },
    }
    request = urllib.request.Request(
        request_endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    request_timeout = timeout
    if request_timeout is None:
        raw_timeout = os.getenv("APK_XRAY_GEMMA_TIMEOUT", "90")
        try:
            request_timeout = float(raw_timeout)
        except ValueError as error:
            raise GemmaError("APK_XRAY_GEMMA_TIMEOUT must be a number.") from error
        if request_timeout <= 0:
            raise GemmaError("APK_XRAY_GEMMA_TIMEOUT must be greater than zero.")
    body: bytes | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=request_timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except (TimeoutError, socket.timeout) as error:
            if attempt == 1:
                raise GemmaError(
                    "Gemma request timed out.",
                    code="gemma_timeout",
                ) from error
        except urllib.error.HTTPError as error:
            # Read the response body (error details) safely.
            try:
                error_body_bytes = error.read()
                error_body = error_body_bytes.decode('utf-8', errors='replace')
            except Exception:
                error_body = ''
            # Do not leak the API key; the body should not contain it.
            message = f"Gemma request returned HTTP {error.code}."
            if error_body:
                message += f" Body: {error_body}"
            raise GemmaError(message) from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                if attempt == 1:
                    raise GemmaError(
                        "Gemma request timed out.",
                        code="gemma_timeout",
                    ) from error
                continue
            raise GemmaError(f"Gemma request failed: {error.reason}") from error
        except OSError as error:
            raise GemmaError(f"Gemma request failed: {error}") from error
    if body is None:
        raise GemmaError("Gemma request timed out.", code="gemma_timeout")
    if not body:
        raise GemmaError("Gemma response was empty.")
    if len(body) > MAX_RESPONSE_BYTES:
        raise GemmaError("Gemma response exceeded the 2 MiB limit.")
    envelope: Any = None
    generated_text: str | None = None
    try:
        envelope = json.loads(body)
        if diagnostics:
            print(
                "GEMMA_DIAGNOSTICS "
                + _response_diagnostics(envelope),
                file=sys.stderr,
            )
            for part_diagnostic in _part_diagnostics(envelope):
                print(f"GEMMA_DIAGNOSTICS {part_diagnostic}", file=sys.stderr)
        generated_text = _extract_generated_text(envelope)
        return _validate(
            _parse_generated_json(generated_text),
            {item["id"] for item in evidence},
        )
    except json.JSONDecodeError as error:
        raise GemmaError(
            "Gemma response envelope was not valid JSON."
        ) from error
    except GemmaError as error:
        if envelope is not None:
            details = f" ({_response_diagnostics(envelope)}"
            if generated_text is not None:
                details += f", generated_length={len(generated_text)}"
            details += ")"
            raise GemmaError(f"{error}{details}") from error
        raise
