from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from forge.domain.health import DatabaseState


class PostgresHealthRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def snapshot(self) -> DatabaseState:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                exists = await connection.scalar(
                    text("SELECT to_regclass('public.alembic_version')")
                )
                if exists is None:
                    return DatabaseState(reachable=True, revisions=frozenset())
                rows = await connection.scalars(
                    text("SELECT version_num FROM public.alembic_version")
                )
                return DatabaseState(reachable=True, revisions=frozenset(rows.all()))
        except SQLAlchemyError:
            # Never expose driver errors, which may include hostnames or credential material.
            return DatabaseState(reachable=False, revisions=frozenset())
