import secrets

import pytest
from pydantic import ValidationError

from forge.config import Settings


def test_weak_credentials_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(database_password="short")


def test_connection_url_escapes_password_characters() -> None:
    secret = secrets.token_hex(16) + "@:/?#%"
    settings = Settings(database_password=secret)
    assert settings.database_url().password == secret
    assert secret not in str(settings.database_url())


def test_port_validation() -> None:
    with pytest.raises(ValidationError):
        Settings(database_password=secrets.token_hex(32), database_port=70000)
