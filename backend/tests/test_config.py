import os
import pytest
from backend.app.config.settings import Settings


def test_default_settings():
    """Verify default settings configuration."""
    settings = Settings()
    assert settings.PROJECT_NAME == "Global Intelligence Platform"
    assert settings.VERSION == "0.1.0"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.REQUEST_TIMEOUT_SECONDS > 0
    assert settings.MAX_RETRIES >= 1


def test_env_override(monkeypatch):
    """Verify environment variables override default settings."""
    monkeypatch.setenv("PROJECT_NAME", "Custom Intel Grid")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("DEBUG", "true")

    settings = Settings()
    assert settings.PROJECT_NAME == "Custom Intel Grid"
    assert settings.REQUEST_TIMEOUT_SECONDS == 45.0
    assert settings.DEBUG is True
