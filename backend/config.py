"""Runtime configuration for the APK-Xray API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Settings:
    max_upload_bytes: int = 50 * 1024 * 1024
    gemma_endpoint: str | None = None
    gemma_api_key: str | None = None
    gemma_timeout_seconds: float = 90.0
    max_zip_entries: int = 1_000
    max_total_uncompressed_bytes: int = 200 * 1024 * 1024
    max_entry_uncompressed_bytes: int = 50 * 1024 * 1024
    max_compression_ratio: float = 100.0


def load_settings() -> Settings:
    def integer(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError as error:
            raise ValueError(f"{name} must be an integer.") from error
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")
        return value

    def number(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = float(raw)
        except ValueError as error:
            raise ValueError(f"{name} must be a number.") from error
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a finite number greater than zero.")
        return value

    return Settings(
        max_upload_bytes=integer("APK_XRAY_MAX_UPLOAD_BYTES", Settings.max_upload_bytes),
        max_zip_entries=integer("APK_XRAY_MAX_ZIP_ENTRIES", Settings.max_zip_entries),
        max_total_uncompressed_bytes=integer(
            "APK_XRAY_MAX_TOTAL_UNCOMPRESSED_BYTES",
            Settings.max_total_uncompressed_bytes,
        ),
        max_entry_uncompressed_bytes=integer(
            "APK_XRAY_MAX_ENTRY_UNCOMPRESSED_BYTES",
            Settings.max_entry_uncompressed_bytes,
        ),
        max_compression_ratio=number(
            "APK_XRAY_MAX_COMPRESSION_RATIO", Settings.max_compression_ratio
        ),
        gemma_endpoint=os.getenv("GEMMA4_ENDPOINT") or None,
        gemma_api_key=os.getenv("GEMMA4_API_KEY") or None,
        gemma_timeout_seconds=number(
            "APK_XRAY_GEMMA_TIMEOUT", Settings.gemma_timeout_seconds
        ),
    )
