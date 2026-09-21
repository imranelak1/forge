from typing import Literal

from pydantic import SecretStr, field_validator
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
