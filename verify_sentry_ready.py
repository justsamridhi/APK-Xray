"""Comprehensive verification that Sentry is ready for tracing."""

import os
import sys

# Clear environment to test .env loading
os.environ.pop("SENTRY_DSN", None)
os.environ.pop("SENTRY_TRACES_SAMPLE_RATE", None)

print("=" * 70)
print("Sentry Integration Verification")
print("=" * 70)

# Step 1: Verify .env file exists
from pathlib import Path
root_env = Path(__file__).parent / ".env"
if not root_env.exists():
    print(f"[FAIL] .env file not found at: {root_env}")
    sys.exit(1)
print(f"[PASS] .env file found at: {root_env}")

# Step 2: Load settings
import backend.config as _config_mod
_config_mod._ENV_LOADED = False
from backend.config import load_settings

settings = load_settings()

# Step 3: Verify DSN is loaded
if not settings.sentry_dsn:
    print("[FAIL] SENTRY_DSN not loaded from .env")
    sys.exit(1)

dsn_preview = settings.sentry_dsn[:50] + "..." if len(settings.sentry_dsn) > 50 else settings.sentry_dsn
print(f"[PASS] SENTRY_DSN loaded: {dsn_preview}")

# Step 4: Verify sample rate is non-zero
if settings.sentry_traces_sample_rate == 0.0:
    print("[FAIL] SENTRY_TRACES_SAMPLE_RATE is 0.0 - tracing disabled")
    print("  Add 'SENTRY_TRACES_SAMPLE_RATE=1.0' to .env")
    sys.exit(1)

print(f"[PASS] SENTRY_TRACES_SAMPLE_RATE: {settings.sentry_traces_sample_rate}")
print(f"  ({settings.sentry_traces_sample_rate * 100:.0f}% of requests will be traced)")

# Step 5: Initialize Sentry
from backend.sentry_setup import init_sentry
init_sentry(settings.sentry_dsn, settings.sentry_traces_sample_rate)

# Step 6: Verify SDK is active
import sentry_sdk
client = sentry_sdk.get_client()

if not client or not client.dsn:
    print("[FAIL] Sentry SDK not initialized")
    sys.exit(1)

print(f"[PASS] Sentry SDK initialized and active")

# Step 7: Check integrations
options = client.options if hasattr(client, 'options') else {}
integrations = options.get('integrations', [])
integration_names = [type(i).__name__ for i in integrations]

fastapi_present = any('FastApi' in name for name in integration_names)
starlette_present = any('Starlette' in name for name in integration_names)

if fastapi_present:
    print(f"[PASS] FastAPI integration enabled")
if starlette_present:
    print(f"[PASS] Starlette integration enabled")

if not (fastapi_present or starlette_present):
    print("[WARN] FastAPI/Starlette integrations not detected")

# Step 8: Import the API to confirm initialization order
print("\nTesting API module import...")
from backend.api import app
print(f"[PASS] FastAPI app initialized")

print("=" * 70)
print("[PASS] ALL CHECKS PASSED")
print("=" * 70)
print("\nNext steps:")
print("  1. Start backend:")
print("     uvicorn backend.api:app --reload --port 8000")
print()
print("  2. Upload an APK:")
print("     curl -F 'apk=@path/to/test.apk' http://127.0.0.1:8000/api/upload")
print()
print("  3. Check Sentry dashboard:")
print("     https://sentry.io → Your Project → Explore → Traces")
print()
print("  Expected: A trace appears within 30-60 seconds showing:")
print("    POST /api/upload")
print("      ├─ apk.parse")
print("      ├─ apk.report")
print("      └─ apk.persist")
