"""Real fenced Actions/deployment transactions with deterministic provider transport."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from test_auth import auth  # noqa: F401
from test_enrichment_integration import EvidenceProvider, drain
from test_pipeline_integration import Pipeline, pipeline  # noqa: F401

from forge.domain import cicd
from forge.integrations.github import GitHubFailure
from forge.repositories.pipeline import LostLease, PipelineRepository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test DB not supplied"
    ),
]


def workflow(
    attempt: int = 1, *, status: str = "completed", conclusion: str | None = "failure"
) -> dict[str, Any]:
    return {
        "id": 500,
        "run_attempt": attempt,
        "workflow_id": 600,
        "run_number": 12,
        "name": "CI",
        "path": ".github/workflows/ci.yml",
        "event": "push",
        "head_branch": "main",
        "head_sha": "a" * 40,
        "status": status,
        "conclusion": conclusion,
        "repository": {"id": 1},
        "created_at": "2026-01-01T00:00:00Z",
        "run_started_at": f"2026-01-0{attempt}T00:01:00Z",
        "updated_at": f"2026-01-0{attempt}T01:00:00Z",
        "actor": {"login": "developer", "type": "User"},
        "pull_requests": [],
    }


def job(attempt: int = 1, identifier: int = 1, *, conclusion: str = "failure") -> dict[str, Any]:
    return {
        "id": attempt * 1000 + identifier,
        "run_id": 500,
        "run_attempt": attempt,
        "name": "Test",
        "status": "completed",
        "conclusion": conclusion,
        "started_at": f"2026-01-0{attempt}T00:01:00Z",
        "completed_at": f"2026-01-0{attempt}T00:04:00Z",
        "labels": ["ubuntu-latest"],
        "steps": [
            {
                "number": 1,
                "name": "Test",
                "status": "completed",
                "conclusion": conclusion,
                "started_at": None,
                "completed_at": None,
            }
        ],
    }


def deployment() -> dict[str, Any]:
    return {
        "id": 700,
        "environment": "production",
        "production_environment": False,
        "transient_environment": False,
        "sha": "a" * 40,
        "ref": "main",
        "task": "deploy",
        "description": "A deployment",
        "creator": {"login": "developer", "type": "User"},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-03T00:00:00Z",
    }


def status(identifier: int, state: str = "success", day: int = 1) -> dict[str, Any]:
    return {
        "id": identifier,
        "state": state,
        "description": "Provider state",
        "environment": "production",
        "creator": None,
        "created_at": f"2026-01-0{day}T00:00:00Z",
        "updated_at": f"2026-01-0{day}T00:00:00Z",
    }


@dataclass
class CICDProvider(EvidenceProvider):
    endpoint_failure: GitHubFailure | None = None
    capabilities: frozenset[str] = frozenset({"actions", "deployments"})
    workflow_pages: dict[int, list[dict[str, Any]]] = field(
        default_factory=lambda: {1: [workflow(2, conclusion="success")]}
    )
    attempts: dict[int, dict[str, Any]] = field(
        default_factory=lambda: {1: workflow(), 2: workflow(2, conclusion="success")}
    )
    job_pages: dict[tuple[int, int], list[dict[str, Any]]] = field(
        default_factory=lambda: {(1, 1): [job()], (2, 1): [job(2, conclusion="success")]}
    )
    deployment_pages: dict[int, list[dict[str, Any]]] = field(
        default_factory=lambda: {1: [deployment()]}
    )
    status_pages: dict[int, list[dict[str, Any]]] = field(
        default_factory=lambda: {1: [status(1), status(2, day=2), status(3, "inactive", 3)]}
    )

    async def cicd_credentials(self, identifier: int) -> tuple[str, frozenset[str]]:
        return await self.installation_token(identifier), self.capabilities

    async def workflow_runs(
        self, token: str, owner: str, name: str, page: int
    ) -> tuple[list[dict[str, Any]], int]:
        self.calls.append(("workflow_catalog", page))
        return self.workflow_pages.get(page, []), sum(
            len(values) for values in self.workflow_pages.values()
        )

    async def workflow_run(
        self, token: str, owner: str, name: str, identifier: int, attempt: int | None = None
    ) -> dict[str, Any]:
        if self.endpoint_failure:
            raise self.endpoint_failure
        self.calls.append(("workflow_attempt", attempt or max(self.attempts)))
        return self.attempts[attempt or max(self.attempts)]

    async def workflow_jobs(
        self, token: str, owner: str, name: str, identifier: int, attempt: int, page: int
    ) -> tuple[list[dict[str, Any]], int]:
        self.calls.append(("workflow_jobs", page))
        return self.job_pages.get((attempt, page), []), sum(
            len(values) for (number, _), values in self.job_pages.items() if number == attempt
        )

    async def deployments(
        self, token: str, owner: str, name: str, page: int
    ) -> list[dict[str, Any]]:
        return self.deployment_pages.get(page, [])

    async def deployment(
        self, token: str, owner: str, name: str, identifier: int
    ) -> dict[str, Any]:
        return deployment()

    async def deployment_statuses(
        self, token: str, owner: str, name: str, identifier: int, page: int
    ) -> list[dict[str, Any]]:
        self.calls.append(("deployment_statuses", page))
        return self.status_pages.get(page, [])


@pytest.fixture
async def flows(pipeline: Pipeline) -> AsyncIterator[Pipeline]:  # noqa: F811
    pipeline.repository = PipelineRepository(pipeline.repository.engine)
    pipeline.provider = CICDProvider()
    yield pipeline


async def queue(value: Pipeline, kind: str) -> None:
    async with value.repository.transaction() as connection:
        await value.repository.tenant(connection, value.organization_id)
        source = await value.repository.one(
            connection, "SELECT * FROM forge.repositories WHERE id=:id", id=value.repository_id
        )
        assert source
        await value.repository.queue_enrichment(
            connection,
            value.organization_id,
            value.integration_id,
            value.repository_id,
            kind,
            source,
            force=True,
        )


async def test_attempts_are_explicit_and_completion_uses_jobs_not_updated_time(
    flows: Pipeline,
) -> None:
    await queue(flows, "ci_repository")
    await drain(flows)
    rows = await flows.rows("SELECT * FROM forge.workflow_runs ORDER BY run_attempt")
    assert [row["conclusion"] for row in rows] == ["failure", "success"]
    assert rows[0]["queued_at"] == rows[0]["created_at"] and rows[1]["queued_at"] is None
    assert all(
        row["completion_source"] == "jobs" and row["completed_at"] < row["updated_at"]
        for row in rows
    )
    assert all(row["jobs_status"] == "complete" for row in rows)
    assert {number for name, number in flows.provider.calls if name == "workflow_attempt"} == {1, 2}
    assert len(await flows.rows("SELECT * FROM forge.workflow_jobs")) == 2
    assert not await flows.rows("SELECT * FROM forge.deployments")
    assert (await flows.rows("SELECT ci_status FROM forge.repositories"))[0][
        "ci_status"
    ] == "complete"
    # A later stale/nonterminal representation of the same attempt cannot erase its conclusion.
    changed = workflow(status="queued", conclusion=None)
    changed["updated_at"] = "2026-02-01T00:00:00Z"
    async with flows.repository.transaction() as connection:
        await flows.repository.tenant(connection, flows.organization_id)
        await flows.repository.upsert_workflow(
            connection,
            flows.organization_id,
            flows.integration_id,
            flows.repository_id,
            cicd.workflow_run(changed, "team/repo-1", 1),
            schedule=False,
        )
    current = (await flows.rows("SELECT * FROM forge.workflow_runs WHERE run_attempt=1"))[0]
    assert current["conclusion"] == "failure" and current["completed_at"] == rows[0]["completed_at"]


async def test_independent_optional_permissions_leave_working_source_active(
    flows: Pipeline,
) -> None:
    flows.provider.capabilities = frozenset({"deployments"})  # type: ignore[attr-defined]
    await queue(flows, "ci_repository")
    await queue(flows, "deployments_repository")
    await drain(flows)
    source = (await flows.rows("SELECT * FROM forge.repositories"))[0]
    assert (
        source["ci_status"] == "unavailable" and source["ci_error"] == "actions_permission_required"
    )
    assert source["deployments_status"] == "complete"
    assert (await flows.rows("SELECT status FROM forge.integrations"))[0]["status"] == "active"
    assert not await flows.rows("SELECT * FROM forge.workflow_runs")


async def test_deployment_status_history_is_idempotent_and_never_name_classified(
    flows: Pipeline,
) -> None:
    await queue(flows, "deployments_repository")
    await drain(flows)
    first = (await flows.rows("SELECT * FROM forge.deployments"))[0]
    assert first["statuses_status"] == "complete" and first["production_environment"] is False
    assert first["workflow_run_id"] is None and first["commit_id"] is None
    environment = (await flows.rows("SELECT * FROM forge.deployment_environments"))[0]
    assert environment["name"] == "production" and environment["classification"] is None
    await flows.execute("UPDATE forge.deployment_environments SET classification='production'")
    await queue(flows, "deployments_repository")
    await drain(flows)
    rows = await flows.rows("SELECT * FROM forge.deployment_statuses ORDER BY created_at")
    assert len(rows) == 3 and [row["state"] for row in rows] == ["success", "success", "inactive"]
    assert (await flows.rows("SELECT classification FROM forge.deployment_environments"))[0][
        "classification"
    ] == "production"
    assert len(await flows.rows("SELECT * FROM forge.deployments")) == 1


async def test_job_pages_retry_without_losing_checkpoint_or_claiming_completion(
    flows: Pipeline,
) -> None:
    flows.provider.attempts = {1: workflow()}  # type: ignore[attr-defined]
    flows.provider.job_pages = {
        (1, 1): [job(identifier=n) for n in range(1, 101)],
        (1, 2): [job(identifier=101)],
    }  # type: ignore[attr-defined]
    async with flows.repository.transaction() as connection:
        await flows.repository.tenant(connection, flows.organization_id)
        await flows.repository.upsert_workflow(
            connection,
            flows.organization_id,
            flows.integration_id,
            flows.repository_id,
            cicd.workflow_run(workflow(), "team/repo-1", 1),
        )
    await flows.worker.run_once()
    await flows.worker.run_once()
    row = (await flows.rows("SELECT * FROM forge.workflow_runs"))[0]
    assert row["jobs_status"] == "partial" and row["completed_at"] is None
    assert len(await flows.rows("SELECT * FROM forge.workflow_jobs")) == 100
    flows.provider.failure = GitHubFailure("rate_limited", retryable=True, retry_after=3)
    await flows.worker.run_once()
    task = (await flows.rows("SELECT * FROM forge.jobs WHERE payload->>'kind'='workflow_run'"))[0]
    assert task["state"] == "retry" and task["payload"]["page"] == 2
    flows.provider.failure = None
    await flows.execute("UPDATE forge.jobs SET available_at=now() WHERE id=:id", id=task["id"])
    await drain(flows)
    assert len(await flows.rows("SELECT * FROM forge.workflow_jobs")) == 101
    assert (await flows.rows("SELECT jobs_status FROM forge.workflow_runs"))[0][
        "jobs_status"
    ] == "complete"


async def test_new_revision_and_access_change_discard_fetched_jobs(flows: Pipeline) -> None:
    async with flows.repository.transaction() as connection:
        await flows.repository.tenant(connection, flows.organization_id)
        await flows.repository.upsert_workflow(
            connection,
            flows.organization_id,
            flows.integration_id,
            flows.repository_id,
            cicd.workflow_run(workflow(), "team/repo-1", 1),
        )
    await flows.worker.run_once()
    lease = await flows.repository.claim()
    assert lease
    work = await flows.repository.load(lease)
    assert work
    page = await flows.worker.fetch(work)
    revised = workflow()
    revised["updated_at"] = "2026-01-03T00:00:00Z"
    async with flows.repository.transaction() as connection:
        await flows.repository.tenant(connection, flows.organization_id)
        await flows.repository.upsert_workflow(
            connection,
            flows.organization_id,
            flows.integration_id,
            flows.repository_id,
            cicd.workflow_run(revised, "team/repo-1", 1),
        )
    with pytest.raises(LostLease):
        await flows.worker.persist(lease, work, page)
    assert not await flows.rows("SELECT * FROM forge.workflow_jobs")
    await flows.execute("UPDATE forge.repositories SET selected=false")
    before = len(flows.provider.calls)
    await flows.worker.run_once()
    assert len(flows.provider.calls) == before


async def test_webhooks_reconcile_authoritative_state_and_restrict_foreign_links(
    flows: Pipeline,
) -> None:
    await flows.webhook(
        "workflow_run",
        {"repository": {"id": 1}, "workflow_run": {"id": 500, "conclusion": "cancelled"}},
    )
    await drain(flows)
    assert [
        row["conclusion"]
        for row in await flows.rows("SELECT * FROM forge.workflow_runs ORDER BY run_attempt")
    ] == ["failure", "success"]
    await flows.webhook(
        "deployment_status",
        {
            "repository": {"id": 1},
            "deployment": {"id": 700},
            "deployment_status": {"state": "failure"},
        },
    )
    await drain(flows)
    assert (
        await flows.rows(
            "SELECT state FROM forge.deployment_statuses ORDER BY created_at DESC LIMIT 1"
        )
    )[0]["state"] == "inactive"
    run = (await flows.rows("SELECT * FROM forge.workflow_runs WHERE run_attempt=1"))[0]
    async with flows.repository.transaction() as connection:
        await flows.repository.tenant(connection, flows.organization_id)
        await flows.repository.upsert_workflow_job(
            connection,
            flows.organization_id,
            uuid4(),
            run["id"],
            cicd.workflow_job(job(), "team/repo-1", 500, 1),
        )
    existing = (await flows.rows("SELECT * FROM forge.workflow_jobs WHERE provider_job_id=1001"))[0]
    assert existing["repository_id"] == flows.repository_id
    assert existing["workflow_run_id"] == run["id"]
    with pytest.raises(IntegrityError):
        async with flows.repository.transaction() as connection:
            await flows.repository.tenant(connection, flows.organization_id)
            await flows.repository.upsert_workflow_job(
                connection,
                flows.organization_id,
                uuid4(),
                run["id"],
                cicd.workflow_job(job(identifier=999), "team/repo-1", 500, 1),
            )


async def test_empty_jobs_do_not_invent_completion_from_terminal_updated_at(
    flows: Pipeline,
) -> None:
    flows.provider.job_pages = {}  # type: ignore[attr-defined]
    await queue(flows, "ci_repository")
    await drain(flows)
    assert all(
        row["completed_at"] is None and row["completion_source"] is None
        for row in await flows.rows("SELECT * FROM forge.workflow_runs")
    )


async def test_optional_webhook_endpoint_denial_does_not_disable_core_integration(
    flows: Pipeline,
) -> None:
    flows.provider.endpoint_failure = GitHubFailure("access_denied")  # type: ignore[attr-defined]
    await flows.webhook("workflow_run", {"repository": {"id": 1}, "workflow_run": {"id": 500}})
    await flows.worker.run_once()
    assert (await flows.rows("SELECT status FROM forge.integrations"))[0]["status"] == "active"
    source = (await flows.rows("SELECT ci_status,ci_error FROM forge.repositories"))[0]
    assert source["ci_status"] == "failed" and source["ci_error"] == "access_denied"


async def test_late_core_import_repairs_explicit_links_without_refetching_ci(
    flows: Pipeline,
) -> None:
    from test_pipeline_integration import commit, pr

    for observed in flows.provider.attempts.values():  # type: ignore[attr-defined]
        observed["pull_requests"] = [{"id": 10001, "number": 1, "base": {"repo": {"id": 1}}}]
    await queue(flows, "ci_repository")
    await queue(flows, "deployments_repository")
    await drain(flows)
    assert all(
        row["commit_id"] is None for row in await flows.rows("SELECT * FROM forge.workflow_runs")
    )
    source_pr = pr(1)
    flows.provider.detail = source_pr
    flows.provider.changes = {1: [commit(int("a" * 40, 16))]}
    await flows.queue(kind="incremental")
    before = [
        call for call in flows.provider.calls if call[0] in {"workflow_attempt", "workflow_jobs"}
    ]
    await drain(flows)
    after = [
        call for call in flows.provider.calls if call[0] in {"workflow_attempt", "workflow_jobs"}
    ]
    assert after == before
    assert all(
        row["commit_id"] is not None
        for row in await flows.rows("SELECT * FROM forge.workflow_runs")
    )
    assert all(
        row["commit_id"] is not None for row in await flows.rows("SELECT * FROM forge.deployments")
    )
    assert all(
        row["links_status"] == "complete"
        for row in await flows.rows("SELECT * FROM forge.workflow_runs")
    )
    assert len(await flows.rows("SELECT * FROM forge.workflow_run_pull_requests")) == 2
