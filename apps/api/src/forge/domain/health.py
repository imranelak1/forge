from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DatabaseState:
    reachable: bool
    revisions: frozenset[str]


class HealthRepository(Protocol):
    async def snapshot(self) -> DatabaseState: ...


@dataclass(frozen=True)
class Readiness:
    database_up: bool
    migrations_current: bool

    @property
    def ready(self) -> bool:
        return self.database_up and self.migrations_current
