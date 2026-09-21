import asyncio

from forge.domain.health import HealthRepository, Readiness


class HealthService:
    def __init__(self, repository: HealthRepository, expected_revisions: frozenset[str]) -> None:
        self.repository = repository
        self.expected_revisions = expected_revisions

    async def readiness(self) -> Readiness:
        try:
            async with asyncio.timeout(4):
                state = await self.repository.snapshot()
        except TimeoutError:
            return Readiness(database_up=False, migrations_current=False)
        return Readiness(
            database_up=state.reachable,
            migrations_current=bool(self.expected_revisions)
            and state.revisions == self.expected_revisions,
        )
