"""Local-only demo writes remain tenant-scoped and disconnected from provider workers."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text

from forge.domain.demo import TABLES, VERSION, history, identifier
from forge.repositories.identity import IdentityRepository


class DemoRepository:
    def __init__(self, repository: IdentityRepository, environment: str) -> None:
        self.repository = repository
        self.environment = environment

    async def seed(self, user_id: UUID, organization_id: UUID, number: int) -> dict[str, int]:
        if self.environment == "production":
            raise ValueError("Demo seeding is disabled in production.")
        async with self.repository.transaction(user_id) as connection:
            await self.repository.tenant(connection, organization_id)
            organization = await self.repository.organization(
                connection, organization_id, lock=True
            )
            member = await self.repository.membership(connection, organization_id, user_id)
            if (
                organization is None
                or not organization["is_demo"]
                or organization["slug"] != f"forge-demo-{number}"
                or member is None
                or member["role"] != "owner"
                or number not in (1, 2)
            ):
                raise ValueError("Only the owned, designated demo organizations may be seeded.")
            integration = identifier(organization_id, "integration")
            await self.repository.execute(
                connection,
                """INSERT INTO forge.integrations
                    (organization_id,id,installation_id,account_login,account_type,status)
                    VALUES (:org,:id,:installation,'forge-demo','Organization','disconnected')
                    ON CONFLICT (organization_id,id) DO NOTHING""",
                org=organization_id,
                id=integration,
                installation=9_000_000_000 + number,
            )
            event_key = f"demo:{VERSION}:anchor"
            await self.repository.execute(
                connection,
                """INSERT INTO forge.events
                    (organization_id,id,integration_id,source_key,kind,occurred_at)
                    VALUES (:org,:id,:integration,:key,'demo.history.generated',:anchor)
                    ON CONFLICT (organization_id,source_key) DO NOTHING""",
                org=organization_id,
                id=identifier(organization_id, "anchor"),
                integration=integration,
                key=event_key,
                anchor=datetime.now(UTC),
            )
            event = await self.repository.one(
                connection,
                "SELECT occurred_at FROM forge.events "
                "WHERE organization_id=:org AND source_key=:key",
                org=organization_id,
                key=event_key,
            )
            assert event is not None
            rows = history(
                organization_id, integration, event["occurred_at"], 2 if number == 1 else 1
            )
            for table in TABLES:
                items = rows[table]
                if not items:
                    continue
                # Both identifiers come exclusively from the internal generator, not user input.
                columns = ",".join(items[0])
                values = ",".join(f":{column}" for column in items[0])
                await connection.execute(
                    text(
                        f"INSERT INTO forge.{table} ({columns}) VALUES ({values}) "
                        "ON CONFLICT (organization_id,id) DO NOTHING"
                    ),
                    items,
                )
            return {table: len(items) for table, items in rows.items()}
