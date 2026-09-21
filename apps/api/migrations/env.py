from alembic import context
from sqlalchemy import create_engine, pool

from forge.config import Settings
from forge.repositories.database import Base

config = context.config


def run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        include_schemas=True,
        compare_type=True,
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url(migration=True),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    run_migrations(config.attributes["connection"])
else:
    engine = create_engine(Settings().database_url(migration=True), poolclass=pool.NullPool)
    with engine.connect() as connection:
        run_migrations(connection)
    engine.dispose()
