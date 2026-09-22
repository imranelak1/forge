"""Hand-computed attempt/deployment cohorts and authenticated evidence against PostgreSQL."""

import os
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from test_analytics_integration import END, HOUR, MERGED, START, WINDOW, Facts
from test_analytics_integration import auth as auth_fixture
from test_analytics_integration import facts as facts_fixture
from test_auth import PREFIX

auth = auth_fixture
facts = facts_fixture
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test database required"
    ),
]


def provider_id() -> int:
    return secrets.randbelow(2**50) + 1


@dataclass
class DeliveryFacts(Facts):
    async def run(self, hours: float = 1, **overrides: Any) -> UUID:
        return await self.insert(
            "workflow_runs",
            {
                "repository_id": self.repository,
                "provider_run_id": provider_id(),
                "run_attempt": 1,
                "provider_workflow_id": 100,
                "name": "Build",
                "event": "push",
                "head_branch": "main",
                "head_sha": "a" * 40,
                "status": "completed",
                "conclusion": "success",
                "created_at": MERGED - HOUR * hours - timedelta(minutes=5),
                "queued_at": MERGED - HOUR * hours - timedelta(minutes=5),
                "started_at": MERGED - HOUR * hours,
                "completed_at": MERGED,
                "completion_source": "jobs",
                "updated_at": MERGED,
                "html_url": "",
                "jobs_status": "complete",
                "links_status": "complete",
                **overrides,
            },
        )

    async def job(self, run: UUID, **overrides: Any) -> UUID:
        return await self.insert(
            "workflow_jobs",
            {
                "repository_id": self.repository,
                "workflow_run_id": run,
                "provider_job_id": provider_id(),
                "name": "compile",
                "status": "completed",
                "conclusion": "success",
                "started_at": MERGED - HOUR,
                "completed_at": MERGED,
                "html_url": "",
                **overrides,
            },
        )

    async def environment(self, name: str = "release", **overrides: Any) -> UUID:
        return await self.insert(
            "deployment_environments",
            {
                "repository_id": self.repository,
                "name": name,
                **overrides,
            },
        )

    async def deploy(self, environment_id: UUID, **overrides: Any) -> UUID:
        return await self.insert(
            "deployments",
            {
                "repository_id": self.repository,
                "provider_id": provider_id(),
                "environment_id": environment_id,
                "environment": "release",
                "production_environment": True,
                "sha": "a" * 40,
                "ref": "main",
                "task": "deploy",
                "created_at": START,
                "updated_at": MERGED,
                "html_url": "",
                "statuses_status": "complete",
                **overrides,
            },
        )

    async def status(self, deployment: UUID, **overrides: Any) -> UUID:
        return await self.insert(
            "deployment_statuses",
            {
                "repository_id": self.repository,
                "deployment_id": deployment,
                "provider_id": provider_id(),
                "state": "success",
                "created_at": MERGED,
                "updated_at": MERGED,
                "html_url": "",
                **overrides,
            },
        )

    async def get(self, resource: str, **query: Any) -> dict[str, Any]:
        response = await self.owner.client.get(self.path + resource, params={**WINDOW, **query})
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
async def delivery(facts: Facts) -> DeliveryFacts:
    result = DeliveryFacts(**vars(facts))
    await result.update(
        "repositories",
        result.repository,
        ci_status="complete",
        ci_synced_at=END,
        ci_window_since=START,
        ci_window_until=END,
        deployments_status="complete",
        deployments_synced_at=END,
        deployments_window_since=START,
        deployments_window_until=END,
    )
    return result


async def test_ci_attempts_decisive_denominator_exact_percentiles_and_evidence(
    delivery: DeliveryFacts,
):
    shared_run = provider_id()
    await delivery.run(1, provider_run_id=shared_run, conclusion="failure")
    retry = await delivery.run(2, provider_run_id=shared_run, run_attempt=2, queued_at=None)
    await delivery.run(4, conclusion="timed_out")
    await delivery.run(8, conclusion="action_required")
    await delivery.run(-1, conclusion="startup_failure")
    for value in ("cancelled", "neutral", "skipped", "stale", "future_conclusion"):
        await delivery.run(20, conclusion=value)
    data = await delivery.get("/metrics/ci")
    assert data["completed_count"] == 10
    assert (data["decisive_count"], data["success_count"], data["failure_count"]) == (5, 1, 4)
    assert data["success_fraction"] == pytest.approx(0.2)
    assert data["failure_fraction"] == pytest.approx(0.8)
    duration = data["duration"]
    assert duration["sample_count"] == 4 and duration["excluded_count"] == 1
    assert duration["mean_seconds"] == 3.75 * 3600
    assert duration["median_seconds"] == 3 * 3600
    assert duration["p75_seconds"] == 5 * 3600
    assert duration["p95_seconds"] == pytest.approx(7.4 * 3600)
    assert duration["exclusions"] == {"invalid_timestamps": 1}
    assert data["queue"]["exclusions"] == {"queue_unknown": 1}
    assert data["recurring_failures"][0]["failure_count"] == 4
    assert data["recurring_failures"][0]["category"] == "unknown"
    assert data["coverage"]["completion_proxy_count"] == 10
    evidence = (await delivery.get("/workflow-runs", metric="duration"))["items"]
    assert len(evidence) == 4
    assert sum(row["duration_seconds"] for row in evidence) / 4 == duration["mean_seconds"]
    attempts = (await delivery.get("/workflow-runs", cohort="completed"))["items"]
    assert {row["attempt"] for row in attempts if row["provider_id"] == shared_run} == {1, 2}
    item = (await delivery.get(f"/workflow-runs/{retry}"))["workflow_run"]
    assert item["queued_at"] is item["queue_seconds"] is item["html_url"] is None
    assert item["completion_source"] == "jobs"


async def test_ci_half_open_filters_unknown_completion_and_zero_denominator(
    delivery: DeliveryFacts,
):
    lower = await delivery.run(
        completed_at=START,
        started_at=START - HOUR,
        queued_at=START - HOUR * 2,
        created_at=START - HOUR * 2,
    )
    await delivery.run(completed_at=END)
    await delivery.run(head_branch="feature")
    await delivery.run(provider_workflow_id=200)
    await delivery.run(completed_at=None, completion_source=None, updated_at=MERGED)
    await delivery.run(completed_at=None, completion_source=None, updated_at=END)
    await delivery.run(completed_at=None, completion_source=None, head_branch="feature")
    data = await delivery.get("/metrics/ci", branch="main", workflow=100)
    assert data["completed_count"] == 1
    assert data["coverage"]["completion_unknown_count"] == 1
    assert data["coverage"]["status"] == "partial"
    listed = await delivery.get("/workflow-runs", branch="main", workflow=100, cohort="completed")
    assert [row["id"] for row in listed["items"]] == [str(lower)]
    empty = await delivery.get("/metrics/ci", workflow=999)
    assert empty["success_fraction"] is empty["failure_fraction"] is None
    assert empty["duration"]["mean_seconds"] is None
    assert empty["coverage"]["completion_unknown_count"] == 0


async def test_explicit_pr_commit_links_do_not_multiply_attempt_metrics(delivery: DeliveryFacts):
    commit = await delivery.commit()
    run = await delivery.run(commit_id=commit)
    for _ in range(2):
        pr = await delivery.pr()
        await delivery.insert(
            "workflow_run_pull_requests",
            {
                "repository_id": delivery.repository,
                "workflow_run_id": run,
                "pull_request_id": pr,
            },
        )
    unrelated = await delivery.pr(head_sha="a" * 40)
    await delivery.job(run, conclusion="failure")
    assert (await delivery.get("/metrics/ci"))["decisive_count"] == 1
    detail = await delivery.get(f"/workflow-runs/{run}")
    assert detail["counts"] == {"jobs": 1, "pull_requests": 2, "commits": 1}
    prs = (await delivery.get(f"/workflow-runs/{run}/pull-requests"))["items"]
    assert len(prs) == 2 and str(unrelated) not in {row["id"] for row in prs}
    commits = (await delivery.get(f"/workflow-runs/{run}/commits"))["items"]
    assert [row["id"] for row in commits] == [str(commit)]
    jobs = (await delivery.get(f"/workflow-runs/{run}/jobs"))["items"]
    assert jobs[0]["conclusion"] == "failure" and "root_cause" not in jobs[0]


async def test_first_ever_success_once_and_complete_history_required(delivery: DeliveryFacts):
    environment = await delivery.environment()
    before = await delivery.deploy(environment, created_at=START - HOUR * 2)
    await delivery.status(before, created_at=START - HOUR)
    await delivery.status(before)  # Later success must not become another deployment.
    inside = await delivery.deploy(environment)
    await delivery.status(inside, created_at=START)
    await delivery.status(inside, created_at=MERGED)
    upper = await delivery.deploy(environment)
    await delivery.status(upper, created_at=END)
    partial = await delivery.deploy(environment, statuses_status="partial")
    await delivery.status(partial)
    failed = await delivery.deploy(environment)
    await delivery.status(failed, state="failure")
    data = await delivery.get("/metrics/deployments")
    assert data["successful_count"] == 1
    assert data["observed_success_count"] == 2 and data["excluded_count"] == 1
    assert data["exclusions"] == {"incomplete_statuses": 1}
    assert data["frequency_per_day"] is None
    rows = await delivery.get("/deployments", cohort="success", eligibility="eligible")
    assert [row["id"] for row in rows["items"]] == [str(inside)]
    detail = await delivery.get(f"/deployments/{before}")
    assert detail["deployment"]["first_success_at"].startswith("2025-12-31T23:")
    assert detail["counts"]["statuses"] == 2


async def test_deployment_frequency_only_full_covered_days_and_no_workflow_inference(
    delivery: DeliveryFacts,
):
    environment = await delivery.environment()
    for at in (START + HOUR * 13, MERGED + HOUR, END - HOUR):
        deployment = await delivery.deploy(environment)
        await delivery.status(deployment, created_at=at)
    for _ in range(4):
        await delivery.run()
    data = await delivery.get("/metrics/deployments", **{"from": (START + HOUR * 12).isoformat()})
    assert data["successful_count"] == 3
    assert data["fully_covered_days"] == 1
    assert data["frequency_per_day"] == 2
    assert [row["fully_covered"] for row in data["trend"]] == [False, True]
    await delivery.update("repositories", delivery.repository, deployments_status="unavailable")
    missing = await delivery.get("/metrics/deployments")
    assert missing["frequency_per_day"] is None and missing["coverage"]["status"] == "unavailable"


async def test_environment_name_does_not_classify_verified_manager_override_audited(
    delivery: DeliveryFacts,
):
    env = await delivery.environment("production")
    unknown = await delivery.deploy(env, environment="production", production_environment=None)
    await delivery.status(unknown)
    nonproduction = await delivery.deploy(
        env, environment="production", production_environment=False
    )
    await delivery.status(nonproduction)
    assert (await delivery.get("/metrics/deployments"))["successful_count"] == 0
    assert (await delivery.get("/metrics/deployments", classification="unknown"))[
        "successful_count"
    ] == 1
    path = (
        f"/organizations/{delivery.organization}/repositories/{delivery.repository}"
        "/environments/classification"
    )
    body = {"environment": "production", "classification": "production"}
    rejected = await delivery.owner.client.put(PREFIX + path, json=body)
    assert rejected.status_code == 403
    viewer = await delivery.auth.register()
    await delivery.auth.join(delivery.owner, str(delivery.organization), viewer, "viewer")
    assert (await delivery.auth.mutate(viewer.client, "PUT", path, body)).status_code == 403
    unverified = await delivery.auth.register()
    storage = delivery.auth.app.state.identity_service.repository
    async with storage.transaction() as connection:
        await storage.tenant(connection, delivery.organization)
        await storage.add_member(
            connection, uuid4(), delivery.organization, UUID(unverified.user_id), "admin"
        )
    assert (await delivery.auth.mutate(unverified.client, "PUT", path, body)).status_code == 403
    response = await delivery.auth.mutate(delivery.owner.client, "PUT", path, body)
    assert response.status_code == 200, response.text
    assert (await delivery.get("/metrics/deployments"))["successful_count"] == 2
    detail = await delivery.get(f"/deployments/{unknown}")
    assert detail["deployment"]["classification_source"] == "override"
    environment_rows = await delivery.get(f"/repositories/{delivery.repository}/environments")
    assert environment_rows["items"][0]["production_count"] == 2
    restored = await delivery.auth.mutate(
        delivery.owner.client, "PUT", path, {**body, "classification": None}
    )
    assert restored.status_code == 200
    assert (await delivery.get("/metrics/deployments"))["successful_count"] == 0
    storage = delivery.auth.app.state.identity_service.repository
    async with storage.transaction() as connection:
        await storage.tenant(connection, delivery.organization)
        audits = await storage.many(
            connection,
            "SELECT action FROM forge.audit_events WHERE organization_id=:org AND subject_id=:id",
            org=delivery.organization,
            id=env,
        )
    assert {row["action"] for row in audits} == {
        "deployment_environment.production",
        "deployment_environment.provider",
    }


async def test_cursor_filter_binding_and_chronological_tied_child_pages(delivery: DeliveryFacts):
    run_ids = {str(await delivery.run()) for _ in range(3)}
    first = await delivery.get("/workflow-runs", cohort="completed", limit=2)
    second = await delivery.get(
        "/workflow-runs", cohort="completed", limit=2, cursor=first["next_cursor"]
    )
    assert {row["id"] for row in first["items"] + second["items"]} == run_ids
    changed = await delivery.owner.client.get(
        delivery.path + "/workflow-runs",
        params={
            **WINDOW,
            "cohort": "completed",
            "limit": 2,
            "branch": "changed",
            "cursor": first["next_cursor"],
        },
    )
    assert changed.status_code == 422
    run = UUID(next(iter(run_ids)))
    late = await delivery.job(run, started_at=MERGED)
    early = await delivery.job(run, started_at=START)
    tie = await delivery.job(run, started_at=START)
    items, cursor = [], None
    for _ in range(3):
        page = await delivery.get(
            f"/workflow-runs/{run}/jobs", limit=1, **({"cursor": cursor} if cursor else {})
        )
        items.extend(page["items"])
        cursor = page["next_cursor"]
    assert [row["id"] for row in items] == [*sorted([str(early), str(tie)]), str(late)]
    assert cursor is None


async def test_tenant_isolation_retained_history_and_same_repository_links(delivery: DeliveryFacts):
    run = await delivery.run()
    environment = await delivery.environment()
    deployment = await delivery.deploy(environment)
    await delivery.status(deployment)
    await delivery.update("repositories", delivery.repository, selected=False)
    assert (await delivery.get("/metrics/ci"))["completed_count"] == 0
    assert (await delivery.get("/metrics/ci", repository=str(delivery.repository)))[
        "completed_count"
    ] == 1
    assert (await delivery.get(f"/workflow-runs/{run}"))["workflow_run"]["id"] == str(run)
    outsider = await delivery.auth.register()
    other = await delivery.auth.organization(outsider)
    for suffix in (
        f"workflow-runs/{run}",
        f"workflow-runs/{run}/jobs",
        f"deployments/{deployment}",
        f"deployments/{deployment}/statuses",
        f"repositories/{delivery.repository}/environments",
    ):
        response = await outsider.client.get(f"{PREFIX}/organizations/{other}/{suffix}")
        assert response.status_code == 404
    foreign_repo = await delivery.repo()
    with pytest.raises(IntegrityError):
        await delivery.job(run, repository_id=foreign_repo)
    with pytest.raises(IntegrityError):
        await delivery.status(deployment, repository_id=foreign_repo)
    foreign_commit = await delivery.commit(repository_id=foreign_repo)
    with pytest.raises(IntegrityError):
        await delivery.run(commit_id=foreign_commit)
    with pytest.raises(IntegrityError):
        await delivery.deploy(environment, commit_id=foreign_commit)
    foreign_pr = await delivery.pr(repository_id=foreign_repo)
    with pytest.raises(IntegrityError):
        await delivery.insert(
            "workflow_run_pull_requests",
            {
                "repository_id": delivery.repository,
                "workflow_run_id": run,
                "pull_request_id": foreign_pr,
            },
        )
