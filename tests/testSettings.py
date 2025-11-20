from config.settings import Settings
import pytest
from pydantic import ValidationError

def test_settings_validation(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "test")
    monkeypatch.setenv("MORALIS_API_KEY", "test")
    settings = Settings()  # Debe pasar
    with pytest.raises(ValidationError):
        monkeypatch.delenv("MORALIS_API_KEY")
        Settings()  # Debe fallar si required