import os

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from forge.config import Settings
from forge.migration import alembic_config, migration_heads, upgrade_database
from forge.repositories.database import create_database_engine
from forge.repositories.health import PostgresHealthRepository
from forge.services.health import HealthService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test DB not supplied"
    ),
]


async def test_migration_round_trip_and_runtime_privileges() -> None:
    settings = Settings()
    assert settings.database_name.endswith("_test"), "Refuse destructive checks outside a test DB"
    upgrade_database(settings)
    upgrade_database(settings)  # Safe repeat startup.
    engine = create_database_engine(settings)
    service = HealthService(PostgresHealthRepository(engine), migration_heads())
    try:
        assert (await service.readiness()).ready
        async with engine.connect() as connection:
            role = (
                await connection.execute(
                    text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
            ).one()
            assert role == (False, False)
            owner = await connection.scalar(
                text("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'forge'")
            )
            assert owner == "forge_migrator"
        with pytest.raises(ProgrammingError):
            async with engine.begin() as connection:
                await connection.execute(text("CREATE TABLE forge.forbidden (id integer)"))
    finally:
        await engine.dispose()


async def test_schema_downgrade_is_visible_to_readiness() -> None:
    settings = Settings()
    assert settings.database_name.endswith("_test")
    upgrade_database(settings)
    engine = create_database_engine(settings)
    migration_engine = create_engine(settings.database_url(migration=True))
    try:
        with migration_engine.connect() as connection:
            config = alembic_config()
            config.attributes["connection"] = connection
            command.downgrade(config, "base")
        service = HealthService(PostgresHealthRepository(engine), migration_heads())
        state = await service.readiness()
        assert state.database_up and not state.migrations_current
        upgrade_database(settings)
        assert (await service.readiness()).ready
    finally:
        await engine.dispose()
        migration_engine.dispose()
