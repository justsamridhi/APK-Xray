"""Runtime configuration for the APK-Xray API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Load .env once at module import for local development.
# Production deployments inject environment variables directly.
_ENV_LOADED = False

def _ensure_env_loaded() -> None:
    """Load .env from the project root exactly once."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv
        # Load from project root (.env), NOT backend/.env
        # backend/config.py -> backend/ -> project_root/
        root_dir = Path(__file__).parent.parent
        env_path = root_dir / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
    except ImportError:
        pass  # dotenv not installed; rely on process environment
    _ENV_LOADED = True


@dataclass(frozen=True)
class Settings:
    max_upload_bytes: int = 50 * 1024 * 1024
    gemma_endpoint: str | None = None
    gemma_api_key: str | None = None
    gemma_timeout_seconds: float = 90.0
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0


def load_settings() -> Settings:
    _ensure_env_loaded()

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
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")
        return value

    def sample_rate(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = float(raw)
        except ValueError as error:
            raise ValueError(f"{name} must be a number.") from error
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0.")
        return value

    return Settings(
        max_upload_bytes=integer("APK_XRAY_MAX_UPLOAD_BYTES", Settings.max_upload_bytes),
        gemma_endpoint=os.getenv("GEMMA4_ENDPOINT") or None,
        gemma_api_key=os.getenv("GEMMA4_API_KEY") or None,
        gemma_timeout_seconds=number(
            "APK_XRAY_GEMMA_TIMEOUT", Settings.gemma_timeout_seconds
        ),
        sentry_dsn=os.getenv("SENTRY_DSN") or None,
        sentry_traces_sample_rate=sample_rate(
            "SENTRY_TRACES_SAMPLE_RATE", Settings.sentry_traces_sample_rate
        ),
    )
