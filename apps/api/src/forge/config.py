from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORGE_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_host: str = "127.0.0.1"
    database_port: int = 5432
    database_name: str = "forge"
    database_password: SecretStr
    migration_password: SecretStr | None = None
    auth_secret: SecretStr
    public_origin: str = "http://localhost:3000"
    mail_backend: Literal["file", "smtp"] = "file"
    mail_directory: Path = Path(".local/mail")
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "Forge <noreply@forge.local>"

    @field_validator("auth_secret")
    @classmethod
    def validate_auth_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode()) < 32:
            raise ValueError("FORGE_AUTH_SECRET must contain at least 32 bytes")
        return value

    @field_validator("public_origin")
    @classmethod
    def validate_public_origin(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Public origin must be an HTTP(S) origin without a path")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production":
            if not self.public_origin.startswith("https://"):
                raise ValueError("Production requires an HTTPS public origin")
            if self.mail_backend != "smtp":
                raise ValueError("Production requires the SMTP delivery adapter")
        if self.mail_backend == "smtp":
            if not self.smtp_host or not self.smtp_username or not self.smtp_password:
                raise ValueError("SMTP host, username and password are required")
            if "@" not in self.smtp_from or "forge.local" in self.smtp_from:
                raise ValueError("SMTP requires a deliverable configured sender")
            if not 1 <= self.smtp_port <= 65535:
                raise ValueError("SMTP port must be between 1 and 65535")
        if "\r" in self.smtp_from or "\n" in self.smtp_from:
            raise ValueError("Invalid mail sender")
        return self

    @field_validator("database_password", "migration_password")
    @classmethod
    def validate_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 20:
            raise ValueError("Database credentials must contain at least 20 characters")
        return value

    @field_validator("database_port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return value

    @field_validator("database_name")
    @classmethod
    def validate_database_name(cls, value: str) -> str:
        if not value or len(value) > 63 or not value.replace("_", "").isalnum():
            raise ValueError("Database name must contain only letters, digits and underscores")
        return value

    def database_url(self, *, migration: bool = False) -> URL:
        secret = self.migration_password if migration else self.database_password
        if secret is None:
            raise ValueError("FORGE_MIGRATION_PASSWORD is required to run migrations")
        return URL.create(
            "postgresql+psycopg",
            username="forge_migrator" if migration else "forge_app",
            password=secret.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )
