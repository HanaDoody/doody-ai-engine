"""Test-wide guard: never hit the real LLM API.

The engine may ship with llm_config.enabled=true and a key in .env, which would
make endpoint tests fire real Sonnet 5 calls. Force the client disabled by default;
tests that exercise the LLM path monkeypatch client.complete directly.
"""
import pytest

from app.llm import client


@pytest.fixture(autouse=True)
def _llm_disabled(monkeypatch):
    monkeypatch.setattr(client, "is_enabled", lambda: False)
