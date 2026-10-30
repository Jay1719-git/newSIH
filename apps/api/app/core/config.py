from __future__ import annotations

import base64
import binascii
import json
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "WEAVE API"
    app_env: Literal["synthetic", "development", "test", "production"] = "synthetic"
    api_base_path: str = "/api/v1"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_allowed_origins: str = ""
    auth_cookie_secure: bool = False
    database_url: SecretStr | None = None
    log_level: str = "INFO"
    apaar_hmac_key: SecretStr | None = None
    apaar_hmac_key_version: str = "v1"
    apaar_hmac_previous_keys: SecretStr | None = None
    duplicate_name_similarity_threshold: float = Field(default=0.88, ge=0.5, le=1.0)
    verification_signing_private_key: SecretStr | None = None
    verification_issuer: str = "weave.local"

    @model_validator(mode="after")
    def validate_cors_configuration(self) -> Settings:
        origins = self.cors_origins
        if any("*" in origin for origin in origins):
            raise ValueError("API_ALLOWED_ORIGINS must use explicit origins, not '*'.")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("API_ALLOWED_ORIGINS entries must be origin URLs without paths.")
            if self.app_env == "production" and parsed.scheme != "https":
                raise ValueError("Production CORS origins must use HTTPS.")
        if self.app_env == "production" and not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE must be enabled in production.")
        return self

    @field_validator("api_base_path")
    @classmethod
    def normalize_base_path(cls, value: str) -> str:
        normalized = "/" + value.strip("/")
        if normalized == "/":
            raise ValueError("API_BASE_PATH cannot be the root path")
        return normalized

    @field_validator("api_port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("API_PORT must be between 1 and 65535")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_allowed_origins.split(",") if origin.strip()]

    def require_apaar_hmac_key(self) -> bytes:
        """Return a configured 32-byte key for identity matching, with no hash fallback."""
        if self.apaar_hmac_key is None:
            raise RuntimeError("APAAR_HMAC_KEY is required for APAAR matching operations")

        encoded = self.apaar_hmac_key.get_secret_value().strip()
        try:
            key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        except (ValueError, binascii.Error) as exc:
            raise RuntimeError("APAAR_HMAC_KEY must be URL-safe base64") from exc
        if len(key) < 32:
            raise RuntimeError("APAAR_HMAC_KEY must decode to at least 32 bytes")
        return key

    def require_apaar_hmac_keyring(self) -> dict[str, bytes]:
        """Return active and retained rotation keys; retained keys enable safe overlap matching."""
        current = self.require_apaar_hmac_key()
        keys = {self.apaar_hmac_key_version: current}
        if self.apaar_hmac_previous_keys is not None:
            try:
                encoded_keys = json.loads(self.apaar_hmac_previous_keys.get_secret_value())
            except (TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError("APAAR_HMAC_PREVIOUS_KEYS must be a JSON object") from exc
            if not isinstance(encoded_keys, dict):
                raise RuntimeError("APAAR_HMAC_PREVIOUS_KEYS must be a JSON object")
            for version, encoded in encoded_keys.items():
                if not isinstance(version, str) or not version or not isinstance(encoded, str):
                    raise RuntimeError(
                        "APAAR_HMAC_PREVIOUS_KEYS entries must map versions to base64 keys"
                    )
                if version in keys:
                    raise RuntimeError("APAAR HMAC key versions must be unique")
                try:
                    decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
                except (ValueError, binascii.Error) as exc:
                    raise RuntimeError("A retained APAAR HMAC key is not URL-safe base64") from exc
                if len(decoded) < 32:
                    raise RuntimeError(
                        "Every retained APAAR HMAC key must decode to at least 32 bytes"
                    )
                keys[version] = decoded
        return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()
