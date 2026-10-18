"""Verify that config loads the root .env file correctly."""

import os
import sys

# Clear environment to simulate fresh start
os.environ.pop("SENTRY_DSN", None)
os.environ.pop("SENTRY_TRACES_SAMPLE_RATE", None)

# Reset module state
import backend.config as _config_mod
_config_mod._ENV_LOADED = False

# Now load settings - should read from E:\APK-Xray\.env
from backend.config import load_settings

settings = load_settings()

print("=" * 70)
print("Root .env Loading Test")
print("=" * 70)

# Check what was loaded
if settings.sentry_dsn:
    dsn_preview = settings.sentry_dsn[:50] + "..." if len(settings.sentry_dsn) > 50 else settings.sentry_dsn
    print(f"✓ SENTRY_DSN loaded: {dsn_preview}")
else:
    print("✗ SENTRY_DSN is empty")
    sys.exit(1)

print(f"✓ SENTRY_TRACES_SAMPLE_RATE: {settings.sentry_traces_sample_rate}")

# Verify the expected DSN is present
if "o4512276157628416.ingest.us.sentry.io" in settings.sentry_dsn:
    print("✓ Correct DSN from root .env file")
else:
    print("✗ Wrong DSN - not from root .env")
    sys.exit(1)

# Now test that Sentry initialization works
from backend.sentry_setup import init_sentry

init_sentry(settings.sentry_dsn, settings.sentry_traces_sample_rate)

import sentry_sdk
client = sentry_sdk.get_client()

if client and client.dsn:
    print(f"✓ Sentry SDK initialized successfully")
    print(f"  DSN configured: {str(client.dsn)[:50]}...")
else:
    print("✗ Sentry SDK not initialized")
    sys.exit(1)

print("=" * 70)
print("✓ SUCCESS: Root .env is loaded and Sentry is initialized")
print("=" * 70)
