"""Real PostgreSQL leases/checkpoints with only GitHub transport replaced."""

import asyncio
import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from test_auth import AuthHarness, auth  # noqa: F401

from forge.integrations.github import GitHubApp, GitHubFailure
from forge.repositories.pipeline import LostLease, PipelineRepository
from forge.workers import github as worker_module
from forge.workers.github import GitHubWorker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test DB not supplied"
    ),
]


def pr(number: int, *, state: str = "open", days: int = 1) -> dict[str, Any]:
    when = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    return {
        "id": number + 10000,
        "number": number,
        "title": f"Change {number}",
        "state": state,
        "draft": False,
        "user": {"login": "developer"},
        "head": {"sha": f"{number:040x}"},
        "base": {"ref": "main"},
        "created_at": when,
        "updated_at": when,
        "closed_at": when if state == "closed" else None,
        "merged_at": None,
    }


def commit(number: int) -> dict[str, Any]:
    when = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    return {
        "sha": f"{number:040x}",
        "author": {"login": "developer"},
        "commit": {
            "message": "A real change",
            "author": {"date": when},
            "committer": {"date": when},
        },
    }


def catalog(identifier: int) -> dict[str, Any]:
    return {
        "id": identifier,
        "owner": {"login": "team"},
        "name": f"repo-{identifier}",
        "default_branch": "main",
        "private": True,
        "archived": False,
    }


@dataclass
class Provider:
    prs: dict[int, list[dict[str, Any]]] = field(default_factory=lambda: {1: [pr(1)]})
    changes: dict[int, list[dict[str, Any]]] = field(default_factory=lambda: {1: [commit(1)]})
    repos: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=lambda: pr(1, state="closed"))
    failure: GitHubFailure | None = None
    after_fetch: Callable[[], Awaitable[None]] | None = None
    calls: list[tuple[str, int]] = field(default_factory=list)

    async def installation(self, identifier: int) -> dict[str, Any]:
        if self.failure:
            raise self.failure
        self.calls.append(("installation", identifier))
        return {"id": identifier}

    async def installation_token(self, identifier: int) -> str:
        await self.installation(identifier)
        return "memory-only-fixture-token"

    async def repositories(self, token: str, page: int) -> list[dict[str, Any]]:
        self.calls.append(("repositories", page))
        return self.repos.get(page, [])

    async def pull_requests(
        self, token: str, owner: str, name: str, page: int
    ) -> list[dict[str, Any]]:
        self.calls.append(("pull_requests", page))
        if self.after_fetch:
            await self.after_fetch()
        return self.prs.get(page, [])

    async def commits(
        self, token: str, owner: str, name: str, page: int, since: str, until: str
    ) -> list[dict[str, Any]]:
        self.calls.append(("commits", page))
        return self.changes.get(page, [])

    async def pull_request(self, token: str, owner: str, name: str, number: int) -> dict[str, Any]:
        self.calls.append(("pull_request", number))
        return self.detail


@dataclass
class Pipeline:
    repository: PipelineRepository
    provider: Provider
    organization_id: UUID
    integration_id: UUID
    repository_id: UUID

    @property
    def worker(self) -> GitHubWorker:
        return GitHubWorker(self.repository, cast(GitHubApp, self.provider))

    async def rows(self, sql: str, **parameters: Any) -> list[Any]:
        async with self.repository.transaction() as connection:
            await self.repository.tenant(connection, self.organization_id)
            return await self.repository.many(connection, sql, **parameters)

    async def execute(self, sql: str, **parameters: Any) -> None:
        async with self.repository.transaction() as connection:
            await self.repository.tenant(connection, self.organization_id)
            await self.repository.execute(connection, sql, **parameters)

    async def queue(self, *, kind: str = "history") -> Any:
        async with self.repository.transaction() as connection:
            await self.repository.tenant(connection, self.organization_id)
            return await self.repository.enqueue_sync(
                connection,
                self.organization_id,
                self.integration_id,
                None if kind == "catalog" else self.repository_id,
                kind=kind,
            )

    async def webhook(self, event: str, payload: dict[str, Any]) -> UUID:
        identifier = uuid4()
        async with self.repository.transaction() as connection:
            await self.repository.tenant(connection, self.organization_id)
            parameters = dict(
                org=self.organization_id, integration=self.integration_id, id=identifier
            )
            await self.repository.execute(
                connection,
                """INSERT INTO forge.webhook_receipts
                (delivery_id,digest,event,status,organization_id,integration_id)
                VALUES (:id,:digest,:event,'queued',:org,:integration)""",
                **parameters,
                digest="0" * 64,
                event=event,
            )
            await self.repository.execute(
                connection,
                """INSERT INTO forge.webhook_inbox
                (organization_id,id,integration_id,payload,event,status)
                VALUES (:org,:id,:integration,CAST(:payload AS jsonb),:event,'queued')""",
                **parameters,
                payload=json.dumps(payload),
                event=event,
            )
            await self.repository.execute(
                connection,
                """INSERT INTO forge.jobs
                (organization_id,id,integration_id,inbox_id,kind,dedup_key,state)
                VALUES (:org,:job,:integration,:id,'webhook',:key,'queued')""",
                **parameters,
                job=uuid4(),
                key=f"webhook:{identifier}",
            )
        return identifier


class CorePipelineRepository(PipelineRepository):
    """Keep the Phase 3 checkpoint tests scoped to core jobs.

    test_enrichment_integration replaces this with the real repository and exercises
    automatic scheduling, child pagination, cancellation, and revision invalidation.
    """

    async def queue_enrichment(
        self, connection: AsyncConnection, *args: Any, **kwargs: Any
    ) -> None:
        return None


@pytest.fixture
async def pipeline(auth: AuthHarness) -> AsyncIterator[Pipeline]:  # noqa: F811
    owner = await auth.register()
    organization = UUID(await auth.organization(owner))
    repository = CorePipelineRepository(await auth.engine())
    # Tests share one dedicated database but no live worker. Retire background jobs left by
    # completed API fixtures so this test exercises the real global dispatcher deterministically.
    migrator = await auth.engine(migration=True)
    async with migrator.begin() as connection:
        await connection.execute(
            text(
                "UPDATE forge.jobs SET state='canceled' WHERE state IN ('queued','retry','running')"
            )
        )
    integration, repo = uuid4(), uuid4()
    async with repository.transaction() as connection:
        await repository.tenant(connection, organization)
        await repository.execute(
            connection,
            """INSERT INTO forge.integrations
            (organization_id,id,installation_id,account_login,account_type)
            VALUES (:org,:id,:installation,'team','Organization')""",
            org=organization,
            id=integration,
            installation=uuid4().int % (2**62) + 1,
        )
        await repository.execute(
            connection,
            """INSERT INTO forge.repositories
            (organization_id,id,integration_id,provider_id,owner,name,full_name,html_url,
             default_branch,is_private,archived,authorized,selected)
            VALUES (:org,:id,:integration,1,'team','repo-1','team/repo-1',
             'https://github.com/team/repo-1','main',true,false,true,true)""",
            org=organization,
            id=repo,
            integration=integration,
        )
    value = Pipeline(repository, Provider(), organization, integration, repo)
    yield value
    async with repository.transaction() as connection:
        await repository.tenant(connection, organization)
        await repository.cancel_integration(connection, organization, integration)


async def test_history_pages_commit_checkpoint_and_data_together(pipeline: Pipeline) -> None:
    run = await pipeline.queue()
    assert run["until"] - run["since"] == timedelta(days=90)
    assert await pipeline.worker.run_once()
    state = (await pipeline.rows("SELECT * FROM forge.sync_runs WHERE id=:id", id=run["id"]))[0]
    assert state["stage"] == "commits" and state["checkpoint"] == {"page": 1}
    assert state["pull_requests_processed"] == 1 and state["status"] == "queued"
    assert await pipeline.worker.run_once()
    assert not await pipeline.worker.run_once()
    state = (await pipeline.rows("SELECT * FROM forge.sync_runs WHERE id=:id", id=run["id"]))[0]
    assert state["status"] == "succeeded" and state["commits_processed"] == 1
    assert len(await pipeline.rows("SELECT * FROM forge.events")) == 2
    replay = await pipeline.queue(kind="incremental")
    assert replay["since"] == run["until"] - timedelta(minutes=10)
    await pipeline.worker.run_once()
    await pipeline.worker.run_once()
    assert len(await pipeline.rows("SELECT * FROM forge.pull_requests")) == 1
    assert len(await pipeline.rows("SELECT * FROM forge.commits")) == 1


async def test_catalog_revokes_missing_repositories_only_after_last_page(
    pipeline: Pipeline,
) -> None:
    pipeline.provider.repos = {1: [catalog(number) for number in range(2, 102)], 2: [catalog(102)]}
    run = await pipeline.queue(kind="catalog")
    await pipeline.worker.run_once()
    first = (
        await pipeline.rows(
            "SELECT * FROM forge.repositories WHERE id=:id", id=pipeline.repository_id
        )
    )[0]
    assert first["authorized"] and first["selected"]
    await pipeline.worker.run_once()
    first = (
        await pipeline.rows(
            "SELECT * FROM forge.repositories WHERE id=:id", id=pipeline.repository_id
        )
    )[0]
    assert not first["authorized"] and not first["selected"]
    state = (await pipeline.rows("SELECT * FROM forge.sync_runs WHERE id=:id", id=run["id"]))[0]
    assert state["repositories_processed"] == 101 and state["status"] == "succeeded"
    assert (
        len(
            await pipeline.rows(
                "SELECT * FROM forge.repositories WHERE authorized AND NOT selected"
            )
        )
        == 101
    )


async def test_expired_worker_cannot_commit_after_reclaim(pipeline: Pipeline) -> None:
    await pipeline.queue()
    old = await pipeline.repository.claim()
    assert old
    work = await pipeline.repository.load(old)
    assert work
    page = await pipeline.worker.fetch(work)
    await pipeline.execute(
        "UPDATE forge.jobs SET lease_until=now()-interval '1 second' WHERE id=:id", id=old.id
    )
    fresh = await pipeline.repository.claim()
    assert fresh and fresh.id == old.id and fresh.fence > old.fence
    with pytest.raises(LostLease):
        await pipeline.worker.persist(old, work, page)
    assert not await pipeline.rows("SELECT * FROM forge.pull_requests")
    current = await pipeline.repository.load(fresh)
    assert current
    await pipeline.worker.persist(fresh, current, await pipeline.worker.fetch(current))
    assert len(await pipeline.rows("SELECT * FROM forge.pull_requests")) == 1


async def test_unselection_during_provider_fetch_cancels_without_writes(pipeline: Pipeline) -> None:
    await pipeline.queue()

    async def revoke() -> None:
        async with pipeline.repository.transaction() as connection:
            await pipeline.repository.tenant(connection, pipeline.organization_id)
            await pipeline.repository.execute(
                connection,
                "UPDATE forge.repositories SET selected=false WHERE id=:id",
                id=pipeline.repository_id,
            )
            await pipeline.repository.cancel_repository(
                connection, pipeline.organization_id, pipeline.repository_id
            )

    pipeline.provider.after_fetch = revoke
    await pipeline.worker.run_once()
    assert not await pipeline.rows("SELECT * FROM forge.pull_requests")
    assert (await pipeline.rows("SELECT state FROM forge.jobs"))[0]["state"] == "canceled"


async def test_retries_are_bounded_and_resume_preserves_last_successful_page(
    pipeline: Pipeline,
) -> None:
    pipeline.provider.prs = {1: [pr(number) for number in range(1, 101)]}
    run = await pipeline.queue()
    await pipeline.worker.run_once()
    pipeline.provider.failure = GitHubFailure("rate_limited", retryable=True, retry_after=6000)
    for attempt in range(1, 9):
        await pipeline.worker.run_once()
        job = (await pipeline.rows("SELECT * FROM forge.jobs WHERE sync_run_id=:id", id=run["id"]))[
            0
        ]
        assert job["attempts"] == attempt
        assert job["state"] == ("retry" if attempt < 8 else "dead")
        if attempt < 8:
            assert job["available_at"] > datetime.now(UTC) + timedelta(seconds=5900)
            await pipeline.execute(
                "UPDATE forge.jobs SET available_at=now() WHERE id=:id", id=job["id"]
            )
    failed = (await pipeline.rows("SELECT * FROM forge.sync_runs WHERE id=:id", id=run["id"]))[0]
    assert failed["status"] == "partial" and failed["checkpoint"] == {"page": 2}
    resumed = await pipeline.queue()
    assert resumed["id"] == run["id"] and resumed["checkpoint"] == {"page": 2}
    pipeline.provider.failure = None
    await pipeline.worker.run_once()
    await pipeline.worker.run_once()
    assert (await pipeline.rows("SELECT status FROM forge.sync_runs WHERE id=:id", id=run["id"]))[
        0
    ]["status"] == "succeeded"
    assert len(await pipeline.rows("SELECT * FROM forge.pull_requests")) == 100


async def test_active_requests_coalesce_and_schedule_one_fresh_pass(pipeline: Pipeline) -> None:
    run = await pipeline.queue()
    coalesced = await pipeline.queue(kind="incremental")
    assert coalesced["id"] == run["id"]
    assert len(await pipeline.rows("SELECT * FROM forge.jobs")) == 1
    await pipeline.worker.run_once()
    await pipeline.worker.run_once()
    runs = await pipeline.rows("SELECT * FROM forge.sync_runs ORDER BY created_at")
    assert [item["status"] for item in runs] == ["succeeded", "queued"]
    assert runs[1]["kind"] == "incremental"
    await pipeline.worker.run_once()
    await pipeline.worker.run_once()
    assert not await pipeline.worker.run_once()


async def test_webhook_pr_uses_authoritative_state_and_push_queues_reconciliation(
    pipeline: Pipeline,
) -> None:
    identifier = await pipeline.webhook(
        "pull_request",
        {
            "repository": {"id": 1},
            "number": 1,
            "pull_request": {"state": "open"},
        },
    )
    await pipeline.worker.run_once()
    assert (await pipeline.rows("SELECT state FROM forge.pull_requests"))[0]["state"] == "closed"
    assert ("pull_request", 1) in pipeline.provider.calls
    assert (
        await pipeline.rows("SELECT status FROM forge.webhook_inbox WHERE id=:id", id=identifier)
    )[0]["status"] == "processed"
    await pipeline.webhook(
        "push",
        {
            "repository": {"id": 1},
            "size": 5000,
            "commits": [
                {
                    "id": "a" * 40,
                    "message": "Delivered commit",
                    "author": {"username": "developer"},
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ],
        },
    )
    await pipeline.worker.run_once()
    assert len(await pipeline.rows("SELECT * FROM forge.commits")) == 1
    assert (await pipeline.rows("SELECT kind FROM forge.sync_runs"))[0]["kind"] == "incremental"


async def test_control_event_checks_live_installation_before_reactivation(
    pipeline: Pipeline,
) -> None:
    await pipeline.execute("UPDATE forge.integrations SET status='suspended',updated_at=now()")
    await pipeline.webhook("installation", {"action": "unsuspend"})
    await pipeline.worker.run_once()
    assert pipeline.provider.calls[0][0] == "installation"
    assert (await pipeline.rows("SELECT status FROM forge.integrations"))[0]["status"] == "active"
    assert (await pipeline.rows("SELECT kind FROM forge.sync_runs"))[0]["kind"] == "catalog"


async def test_deleted_organization_prevents_provider_io(pipeline: Pipeline) -> None:
    await pipeline.queue()
    await pipeline.execute(
        "UPDATE forge.organizations SET deleted_at=now() WHERE id=:id", id=pipeline.organization_id
    )
    await pipeline.worker.run_once()
    assert pipeline.provider.calls == []
    assert (await pipeline.rows("SELECT state FROM forge.jobs"))[0]["state"] == "canceled"


async def test_access_version_change_discards_an_already_fetched_page(pipeline: Pipeline) -> None:
    await pipeline.queue(kind="catalog")
    pipeline.provider.repos = {1: [catalog(1)]}
    lease = await pipeline.repository.claim()
    assert lease
    work = await pipeline.repository.load(lease)
    assert work
    page = await pipeline.worker.fetch(work)
    await pipeline.execute(
        "UPDATE forge.integrations SET updated_at=now() WHERE id=:id", id=pipeline.integration_id
    )
    await pipeline.execute(
        "UPDATE forge.repositories SET authorized=false,selected=false WHERE id=:id",
        id=pipeline.repository_id,
    )
    with pytest.raises(LostLease):
        await pipeline.worker.persist(lease, work, page)
    assert not (await pipeline.rows("SELECT authorized FROM forge.repositories"))[0]["authorized"]


async def test_reinstallation_creates_new_catalog_identity_and_preserves_history(
    pipeline: Pipeline,
) -> None:
    await pipeline.queue()
    await pipeline.worker.run_once()
    await pipeline.worker.run_once()
    old_repo = pipeline.repository_id
    await pipeline.execute("UPDATE forge.integrations SET status='disconnected'")
    await pipeline.execute("UPDATE forge.repositories SET authorized=false,selected=false")
    pipeline.integration_id = uuid4()
    await pipeline.execute(
        """INSERT INTO forge.integrations
        (organization_id,id,installation_id,account_login,account_type)
        VALUES (:org,:id,:installation,'team','Organization')""",
        org=pipeline.organization_id,
        id=pipeline.integration_id,
        installation=uuid4().int % (2**62) + 1,
    )
    pipeline.provider.repos = {1: [catalog(1)]}
    await pipeline.queue(kind="catalog")
    await pipeline.worker.run_once()
    repositories = await pipeline.rows("SELECT * FROM forge.repositories")
    assert len(repositories) == 2
    current = next(row for row in repositories if row["id"] != old_repo)
    assert current["authorized"] and not current["selected"]
    assert current["integration_id"] == pipeline.integration_id
    assert (await pipeline.rows("SELECT repository_id FROM forge.pull_requests"))[0][
        "repository_id"
    ] == old_repo
    assert (await pipeline.rows("SELECT repository_id FROM forge.commits"))[0][
        "repository_id"
    ] == old_repo


async def test_processed_payload_retention_is_bounded_and_keeps_dedup_metadata(
    pipeline: Pipeline,
) -> None:
    async with pipeline.repository.transaction() as connection:
        await pipeline.repository.tenant(connection, pipeline.organization_id)
        for number in range(103):
            identifier = uuid4()
            status = "failed" if number == 102 else "processed"
            age = 1 if number == 101 else 8
            parameters = dict(
                org=pipeline.organization_id,
                integration=pipeline.integration_id,
                id=identifier,
                status=status,
            )
            await pipeline.repository.execute(
                connection,
                """INSERT INTO forge.webhook_receipts
                (delivery_id,digest,event,status,organization_id,integration_id)
                VALUES (:id,:digest,'push',:status,:org,:integration)""",
                **parameters,
                digest="a" * 64,
            )
            await pipeline.repository.execute(
                connection,
                """INSERT INTO forge.webhook_inbox
                (organization_id,id,integration_id,payload,event,status,processed_at)
                VALUES (:org,:id,:integration,'{"private":"source payload"}'::jsonb,
                'push',:status,now()-make_interval(days=>:age))""",
                **parameters,
                age=age,
            )
    await pipeline.queue()
    await pipeline.worker.run_once()
    rows = await pipeline.rows("SELECT status,payload FROM forge.webhook_inbox")
    assert sum(row["payload"] == {} for row in rows) == 100
    assert sum(row["payload"] != {} for row in rows) == 3
    assert next(row for row in rows if row["status"] == "failed")["payload"]
    assert (
        len(
            await pipeline.rows(
                "SELECT delivery_id FROM forge.webhook_receipts WHERE organization_id=:org",
                org=pipeline.organization_id,
            )
        )
        == 103
    )


async def test_iteration_deadline_retries_and_failure_recording_is_also_bounded(
    pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "JOB_TIMEOUT_SECONDS", 0.25)
    run = await pipeline.queue()
    interrupted = asyncio.Event()

    async def stalled_fetch() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            interrupted.set()

    pipeline.provider.after_fetch = stalled_fetch
    assert await asyncio.wait_for(pipeline.worker.run_once(), timeout=2)
    assert interrupted.is_set()
    job = (await pipeline.rows("SELECT * FROM forge.jobs WHERE sync_run_id=:id", id=run["id"]))[0]
    assert job["state"] == "retry" and job["last_error"] == "processing_timeout"
    assert not await pipeline.rows("SELECT * FROM forge.pull_requests")
    state = (await pipeline.rows("SELECT * FROM forge.sync_runs WHERE id=:id", id=run["id"]))[0]
    assert state["status"] == "retrying" and state["checkpoint"] == {"page": 1}

    monkeypatch.setattr(worker_module, "FAILURE_TIMEOUT_SECONDS", 0.01)
    worker = pipeline.worker
    failure_interrupted = asyncio.Event()

    async def stalled_failure(*args: Any) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            failure_interrupted.set()

    monkeypatch.setattr(worker, "record_failure", stalled_failure)
    await pipeline.execute("UPDATE forge.jobs SET available_at=now() WHERE id=:id", id=job["id"])
    assert await asyncio.wait_for(worker.run_once(), timeout=2)
    assert failure_interrupted.is_set()
    # Failure recording remains reclaimable through the existing lease expiry.
    assert (await pipeline.rows("SELECT state FROM forge.jobs WHERE id=:id", id=job["id"]))[0][
        "state"
    ] == "running"
