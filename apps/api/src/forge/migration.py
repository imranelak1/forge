from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from forge.config import Settings

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_LOCK = 913097201


def alembic_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def migration_heads() -> frozenset[str]:
    return frozenset(ScriptDirectory.from_config(alembic_config()).get_heads())


def upgrade_database(settings: Settings) -> None:
    engine = create_engine(
        settings.database_url(migration=True),
        connect_args={"connect_timeout": 5, "options": "-c lock_timeout=30000"},
        hide_parameters=True,
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
            connection.commit()
            try:
                config = alembic_config()
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
                connection.commit()
    finally:
        engine.dispose()


if __name__ == "__main__":
    upgrade_database(Settings())
