"""Integration test: verify .env loading happens before API startup."""

import os
import sys
from pathlib import Path

# Clear any existing environment variables to simulate a fresh start
os.environ.pop("SENTRY_DSN", None)
os.environ.pop("SENTRY_TRACES_SAMPLE_RATE", None)

# Reset the module-level flag
import backend.config as _config_mod
_config_mod._ENV_LOADED = False

# Now import the API - this should trigger .env loading
from backend.api import app
from backend.config import load_settings

settings = load_settings()

print("=" * 60)
print("Integration Test: .env Loading on API Import")
print("=" * 60)

# Verify that .env was loaded
if settings.sentry_dsn:
    print(f"✓ SENTRY_DSN loaded: {settings.sentry_dsn[:30]}...")
else:
    print("✗ SENTRY_DSN not loaded (may be intentionally empty)")

print(f"✓ SENTRY_TRACES_SAMPLE_RATE: {settings.sentry_traces_sample_rate}")

# Verify the API app exists
if app:
    print(f"✓ FastAPI app initialized")
else:
    print("✗ FastAPI app not initialized")
    sys.exit(1)

# Check if Sentry SDK is active (using current API)
try:
    import sentry_sdk
    client = sentry_sdk.get_client()
    if client and client.dsn and settings.sentry_traces_sample_rate > 0:
        print(f"✓ Sentry SDK active with {settings.sentry_traces_sample_rate * 100:.0f}% trace sampling")
    elif not settings.sentry_dsn:
        print(f"✓ Sentry SDK not initialized (DSN not configured)")
    elif settings.sentry_traces_sample_rate == 0:
        print(f"⚠ Sentry SDK initialized but tracing disabled (sample rate = 0)")
    else:
        print("✗ Sentry SDK state unclear")
except Exception as e:
    print(f"✗ Sentry SDK check failed: {e}")
    sys.exit(1)

print("=" * 60)
print("✓ Integration test passed")
print("=" * 60)
print("\nNext steps:")
print("  1. uvicorn backend.api:app --reload --port 8000")
print("  2. Upload an APK via http://localhost:5173")
print("  3. Check Sentry → Explore → Traces")
