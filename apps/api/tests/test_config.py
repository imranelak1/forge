import secrets

import pytest
from pydantic import ValidationError

from forge.config import Settings


def test_weak_credentials_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(database_password="short")


def test_connection_url_escapes_password_characters() -> None:
    secret = secrets.token_hex(16) + "@:/?#%"
    settings = Settings(database_password=secret, auth_secret=secrets.token_hex(32))
    assert settings.database_url().password == secret
    assert secret not in str(settings.database_url())


def test_port_validation() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_password=secrets.token_hex(32),
            auth_secret=secrets.token_hex(32),
            database_port=70000,
        )


def test_authentication_secret_is_required_and_short_keys_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FORGE_AUTH_SECRET", raising=False)
    with pytest.raises(ValidationError, match="auth_secret"):
        Settings(database_password=secrets.token_hex(32))
    with pytest.raises(ValidationError, match="32 bytes"):
        Settings(database_password=secrets.token_hex(32), auth_secret="short-key")


@pytest.mark.parametrize(
    "origin",
    [
        "javascript:alert(1)",
        "https://example.test/path",
        "https://user:pass@example.test",
        "https://example.test?origin=evil",
    ],
)
def test_public_origin_does_not_accept_credentials_paths_or_non_http_schemes(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_password=secrets.token_hex(32),
            auth_secret=secrets.token_hex(32),
            public_origin=origin,
        )


def test_production_rejects_cleartext_origin_and_local_mail_sink() -> None:
    values = {
        "environment": "production",
        "database_password": secrets.token_hex(32),
        "auth_secret": secrets.token_hex(32),
    }
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(**values, public_origin="http://example.test")
    with pytest.raises(ValidationError, match="SMTP"):
        Settings(**values, public_origin="https://example.test", mail_backend="file")
