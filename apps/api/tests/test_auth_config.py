import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_requires_explicit_origin_without_path() -> None:
    with pytest.raises(ValidationError):
        Settings(api_allowed_origins="*")
    with pytest.raises(ValidationError):
        Settings(api_allowed_origins="https://frontend.example.test/app")
    with pytest.raises(ValidationError):
        Settings(app_env="production", api_allowed_origins="http://frontend.example.test")
    with pytest.raises(ValidationError):
        Settings(app_env="production", auth_cookie_secure=False)
    Settings(app_env="production", auth_cookie_secure=True)


def test_cors_accepts_explicit_loopback_origin_for_demo() -> None:
    settings = Settings(api_allowed_origins="http://127.0.0.1:3000")
    assert settings.cors_origins == ["http://127.0.0.1:3000"]
