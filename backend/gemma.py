"""Optional, evidence-only Gemma 4 explanation adapter."""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
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
        if not isinstance(claim, dict) or not isinstance(claim.get("text"), str):
            raise GemmaError(f"Gemma claim {index} is malformed.")
        if claim.get("classification") not in {"Can", "Could", "Cannot Prove"}:
            raise GemmaError(f"Gemma claim {index} has an invalid classification.")
        ids = claim.get("evidenceIds", claim.get("evidence_ids"))
        if not isinstance(ids, list) or not all(item in evidence_ids for item in ids):
            raise GemmaError(f"Gemma claim {index} cites unknown evidence.")
        claims.append(
            {
                "id": f"claim:gemma:{index + 1}",
                "text": claim["text"].strip(),
                "classification": claim["classification"],
                "evidenceIds": ids,
                "status": "verified",
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


def _extract_token_counts(envelope: Any) -> dict[str, int | None]:
    """Extract token usage from the Gemini API ``usageMetadata`` block.

    The Gemini API returns a top-level ``usageMetadata`` object alongside
    ``candidates``.  Fields present in current API versions:
    ``promptTokenCount``, ``candidatesTokenCount``, ``totalTokenCount``.

    Returns a dict with ``input``, ``output``, and ``total`` keys.
    Values are ``None`` when the field is absent or non-integer.

    This function never raises.  If the envelope is malformed or the field
    is absent, all values are ``None`` and the caller records the source as
    ``"unavailable"``.
    """
    if not isinstance(envelope, dict):
        return {"input": None, "output": None, "total": None}
    usage = envelope.get("usageMetadata")
    if not isinstance(usage, dict):
        return {"input": None, "output": None, "total": None}

    def _int_or_none(value: Any) -> int | None:
        return value if isinstance(value, int) and value >= 0 else None

    return {
        "input": _int_or_none(usage.get("promptTokenCount")),
        "output": _int_or_none(usage.get("candidatesTokenCount")),
        "total": _int_or_none(usage.get("totalTokenCount")),
    }


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
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(
            {"contents": [{"parts": [{"text": json.dumps(prompt, ensure_ascii=False)}]}]}
        ).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
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

    # ------------------------------------------------------------------
    # Import the span helper lazily.  If Sentry is absent or disabled
    # the noop path is taken and instrumentation has zero cost.
    # ------------------------------------------------------------------
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

    body: bytes | None = None
    retry_count = 0

    # ------------------------------------------------------------------
    # gen_ai.generate: surrounds the actual HTTP call to the model
    # endpoint, including the one-retry-on-timeout policy.
    # ------------------------------------------------------------------
    with _sentry_span("gen_ai.generate", "Gemma 4 generate") as gen_span:
        gen_span.set_data("gen_ai.system", "google_gemini")
        gen_span.set_data("gen_ai.operation.name", "generate")
        gen_span.set_data("gen_ai.request.model", "gemma-4")

        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=request_timeout) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                break
            except (TimeoutError, socket.timeout) as error:
                if attempt == 1:
                    gen_span.set_data("outcome", "timeout")
                    gen_span.set_data("apk_xray.retry_count", 1)
                    raise GemmaError(
                        "Gemma request timed out.",
                        code="gemma_timeout",
                    ) from error
                retry_count = 1
            except urllib.error.HTTPError as error:
                outcome = "rate_limit" if error.code == 429 else "provider_error"
                gen_span.set_data("outcome", outcome)
                gen_span.set_data("apk_xray.retry_count", retry_count)
                raise GemmaError(f"Gemma request returned HTTP {error.code}.") from error
            except urllib.error.URLError as error:
                if isinstance(error.reason, (TimeoutError, socket.timeout)):
                    if attempt == 1:
                        gen_span.set_data("outcome", "timeout")
                        gen_span.set_data("apk_xray.retry_count", 1)
                        raise GemmaError(
                            "Gemma request timed out.",
                            code="gemma_timeout",
                        ) from error
                    retry_count = 1
                    continue
                gen_span.set_data("outcome", "network_error")
                gen_span.set_data("apk_xray.retry_count", retry_count)
                raise GemmaError(f"Gemma request failed: {error.reason}") from error
            except OSError as error:
                gen_span.set_data("outcome", "network_error")
                gen_span.set_data("apk_xray.retry_count", retry_count)
                raise GemmaError(f"Gemma request failed: {error}") from error

        if body is None:
            gen_span.set_data("outcome", "timeout")
            gen_span.set_data("apk_xray.retry_count", 1)
            raise GemmaError("Gemma request timed out.", code="gemma_timeout")
        if not body:
            gen_span.set_data("outcome", "empty_response")
            gen_span.set_data("apk_xray.retry_count", retry_count)
            raise GemmaError("Gemma response was empty.")
        if len(body) > MAX_RESPONSE_BYTES:
            gen_span.set_data("outcome", "response_too_large")
            gen_span.set_data("apk_xray.retry_count", retry_count)
            raise GemmaError("Gemma response exceeded the 2 MiB limit.")

        # Successful HTTP exchange — record retry count.
        gen_span.set_data("apk_xray.retry_count", retry_count)

    # ------------------------------------------------------------------
    # gen_ai.validate: parse the envelope, extract generated text,
    # validate the contract, and record token usage.
    # Token counts come from ``usageMetadata`` in the Gemini API
    # response.  If absent, the source is recorded as "unavailable".
    # ------------------------------------------------------------------
    envelope: Any = None
    generated_text: str | None = None

    with _sentry_span("gen_ai.validate", "Validate Gemma response") as val_span:
        val_span.set_data("gen_ai.system", "google_gemini")
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

            # Record token usage from the response envelope.
            tokens = _extract_token_counts(envelope)
            if tokens["input"] is not None:
                val_span.set_data("gen_ai.usage.input_tokens", tokens["input"])
            if tokens["output"] is not None:
                val_span.set_data("gen_ai.usage.output_tokens", tokens["output"])
            if tokens["total"] is not None:
                val_span.set_data("gen_ai.usage.total_tokens", tokens["total"])
            token_source = (
                "response_metadata"
                if any(v is not None for v in tokens.values())
                else "unavailable"
            )
            val_span.set_data("apk_xray.token_source", token_source)

            generated_text = _extract_generated_text(envelope)
            result = _validate(
                _parse_generated_json(generated_text),
                {item["id"] for item in evidence},
            )
            val_span.set_data("outcome", "ok")
            return result

        except json.JSONDecodeError as error:
            val_span.set_data("outcome", "invalid_json")
            raise GemmaError(
                "Gemma response envelope was not valid JSON."
            ) from error
        except GemmaError as error:
            val_span.set_data("outcome", "contract_violation")
            if envelope is not None:
                details = f" ({_response_diagnostics(envelope)}"
                if generated_text is not None:
                    details += f", generated_length={len(generated_text)}"
                details += ")"
                raise GemmaError(f"{error}{details}") from error
            raise
