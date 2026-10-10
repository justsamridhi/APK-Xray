"""Shared backend test isolation."""

import pytest


@pytest.fixture(autouse=True)
def remove_gemma_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMMA4_API_KEY", raising=False)
