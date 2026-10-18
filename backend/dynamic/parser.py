
"""Evidence-oriented parser for APK-Xray Android logcat output.

This parser extracts observable log indicators. It does not determine
whether an APK is malicious based on a log message alone.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


TIMESTAMP_RE = re.compile(
    r"^(?P<timestamp>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})"
)

LOGCAT_RE = re.compile(
    r"^(?P<timestamp>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})"
    r"\s+(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<priority>[VDIWEF])\s+"
    r"(?P<tag>[^:]+):\s?(?P<message>.*)$"
)

INDICATOR_PATTERNS = [
    (
        "DYN001",
        "cleartext_network_reference",
        re.compile(r"http://", re.IGNORECASE),
        "A cleartext HTTP URL was observed in a log message.",
    ),
    (
        "DYN002",
        "permission_denial",
        re.compile(
            r"permission denial|permission denied|not allowed to access",
            re.IGNORECASE,
        ),
        "A permission-related denial was logged.",
    ),
    (
        "DYN003",
        "process_crash",
        re.compile(
            r"fatal exception|fatal signal|process has died|"
            r"force finishing activity",
            re.IGNORECASE,
        ),
        "A process crash or forced termination was logged.",
    ),
    (
        "DYN004",
        "dynamic_code_loading_reference",
        re.compile(
            r"DexClassLoader|InMemoryDexClassLoader|"
            r"PathClassLoader|DexFile\.loadDex",
            re.IGNORECASE,
        ),
        "A dynamic code-loading API was referenced in a log message.",
    ),
    (
        "DYN005",
        "root_or_debugging_reference",
        re.compile(
            r"\b(rooted|magisk|supersu|frida|xposed|"
            r"debugger connected)\b",
            re.IGNORECASE,
        ),
        "A root, instrumentation, or debugging-related term was logged.",
    ),
]


def parse_logcat_text(
    text: str,
    *,
    max_lines: int = 100_000,
    max_line_chars: int = 16_384,
) -> dict[str, Any]:
    """Parse bounded logcat text into entries and evidence-linked indicators."""
    if not isinstance(text, str):
        raise TypeError("Logcat input must be text.")

    if max_lines < 1 or max_line_chars < 1:
        raise ValueError("Parser limits must be positive.")

    entries: list[dict[str, Any]] = []
    indicators: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    seen_indicators: set[tuple[str, str]] = set()

    lines = text.splitlines()
    truncated = len(lines) > max_lines

    for line_number, original_line in enumerate(lines[:max_lines], start=1):
        line = original_line[:max_line_chars]

        match = LOGCAT_RE.match(line)
        if not match:
            continue

        entry = {
            "line_number": line_number,
            "timestamp": match.group("timestamp"),
            "pid": int(match.group("pid")),
            "tid": int(match.group("tid")),
            "priority": match.group("priority"),
            "tag": match.group("tag").strip(),
            "message": match.group("message"),
        }
        entries.append(entry)

        for rule_id, indicator_type, pattern, description in INDICATOR_PATTERNS:
            if not pattern.search(entry["message"]):
                continue

            dedupe_key = (rule_id, str(line_number))
            if dedupe_key in seen_indicators:
                continue
            seen_indicators.add(dedupe_key)

            evidence_id = f"DYN-E{len(evidence) + 1:05d}"
            message_digest = hashlib.sha256(
                entry["message"].encode("utf-8", errors="replace")
            ).hexdigest()

            evidence_item = {
                "evidence_id": evidence_id,
                "source": "android_logcat",
                "line_number": line_number,
                "timestamp": entry["timestamp"],
                "tag": entry["tag"],
                "priority": entry["priority"],
                "message_sha256": message_digest,
                "message_excerpt": entry["message"][:500],
            }
            evidence.append(evidence_item)

            indicators.append(
                {
                    "rule_id": rule_id,
                    "type": indicator_type,
                    "description": description,
                    "evidence_ids": [evidence_id],
                    "observed_at": entry["timestamp"],
                    "confidence": "observed",
                }
            )

    return {
        "parser_version": "1.0",
        "entries_parsed": len(entries),
        "indicators": indicators,
        "evidence": evidence,
        "truncated": truncated,
        "input_line_count": len(lines),
    }


def parse_logcat_file(
    path: str | Path,
    *,
    max_bytes: int = 20 * 1024 * 1024,
    max_lines: int = 100_000,
    max_line_chars: int = 16_384,
) -> dict[str, Any]:
    """Read a size-bounded logcat file and parse its contents."""
    if max_bytes < 1:
        raise ValueError("File size limit must be positive.")

    log_path = Path(path)

    try:
        with log_path.open("rb") as file_handle:
            raw = file_handle.read(max_bytes + 1)
    except OSError as exc:
        raise ValueError("Unable to read the logcat file.") from exc

    byte_truncated = len(raw) > max_bytes
    raw = raw[:max_bytes]

    text = raw.decode("utf-8", errors="replace")
    result = parse_logcat_text(
        text,
        max_lines=max_lines,
        max_line_chars=max_line_chars,
    )
    result["truncated"] = result["truncated"] or byte_truncated
    result["input_bytes_read"] = len(raw)
    result["byte_limit_reached"] = byte_truncated
    return result
