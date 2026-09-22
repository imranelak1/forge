import secrets

import pytest

from forge.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        database_password=secrets.token_hex(32),
        migration_password=secrets.token_hex(32),
        auth_secret=secrets.token_hex(32),
    )
