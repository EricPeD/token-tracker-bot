from src.config.settings import Settings
import pytest
from pydantic import ValidationError
import os


@pytest.fixture(autouse=True)
def clean_env_for_settings(monkeypatch):
    # Clear environment variables relevant to Settings before each test
    for key in ["TELEGRAM_TOKEN", "MORALIS_API_KEY"]:
        if key in os.environ:
            monkeypatch.delenv(key)


def test_settings_validation_success(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "test_token")
    monkeypatch.setenv("MORALIS_API_KEY", "test_key")
    settings = Settings()
    assert settings.telegram_token == "test_token"
    assert settings.moralis_api_key == "test_key"


def test_settings_validation_missing_moralis_api_key(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "test_token")
    # MORALIS_API_KEY is not set
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # Force no .env file loading


def test_settings_validation_missing_telegram_token(monkeypatch):
    monkeypatch.setenv("MORALIS_API_KEY", "test_key")
    # TELEGRAM_TOKEN is not set
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # Force no .env file loading
