"""Demo history is repeatable, tenant-specific and never a live provider source."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from test_auth import AuthHarness
from test_auth import auth as auth_fixture

from forge.domain.demo import TABLES, history, identifier
from forge.domain.demo_delivery import TABLES as DELIVERY_TABLES
from forge.domain.demo_delivery import history as delivery_history
from forge.domain.demo_tests import TABLES as TEST_TABLES
from forge.domain.identity import Actor
from forge.repositories.demo import DemoRepository

auth = auth_fixture


def test_generated_history_is_repeatable_and_has_real_record_relationships() -> None:
    tenant = uuid4()
    anchor = datetime(2026, 9, 22, 12, tzinfo=UTC)
    integration = identifier(tenant, "integration")
    rows = history(tenant, integration, anchor, 2)
    assert rows == history(tenant, integration, anchor, 2)
    assert len(rows["pull_requests"]) == 90
    assert all(row["is_demo"] and not row["authorized"] for row in rows["repositories"])
    assert all(not row["html_url"] for row in rows["pull_requests"])
    assert min(row["opened_at"] for row in rows["pull_requests"]) < anchor - timedelta(days=89)
    assert max(row["opened_at"] for row in rows["pull_requests"]) > anchor - timedelta(days=2)
    pr_ids = {row["id"]: row["repository_id"] for row in rows["pull_requests"]}
    pr_authors = {row["id"]: row["author_login"] for row in rows["pull_requests"]}
    assert any(
        review["reviewer_login"] == pr_authors[review["pull_request_id"]]
        for review in rows["pull_request_reviews"]
    )
    commits = {row["id"]: row["repository_id"] for row in rows["commits"]}
    for row in rows["pull_request_commits"]:
        assert pr_ids[row["pull_request_id"]] == commits[row["commit_id"]] == row["repository_id"]
    links = [row["commit_id"] for row in rows["pull_request_commits"]]
    assert len(set(links)) < len(links)
    for items in rows.values():
        assert len({row["id"] for row in items}) == len(items)
        for row in items:
            assert row["organization_id"] == tenant
            for value in row.values():
                if isinstance(value, datetime):
                    assert value <= anchor
    other = history(uuid4(), integration, anchor, 2)
    assert not {row["id"] for row in rows["pull_requests"]} & {
        row["id"] for row in other["pull_requests"]
    }


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test DB not supplied")
async def test_seed_is_idempotent_scoped_and_cannot_queue_live_work(auth: AuthHarness) -> None:
    owner = await auth.register()
    await auth.verify(owner)
    user_id = UUID(owner.user_id)
    repository = auth.app.state.identity_service.repository
    seeder = DemoRepository(repository, "test")
    actor = Actor(user_id, UUID(owner.session_id), "Demo", owner.email, True, "")
    organizations = auth.app.state.organization_service
    first = await organizations.create(actor, "Demo One", "forge-demo-1", demo=True)
    second = await organizations.create(actor, "Demo Two", "forge-demo-2", demo=True)
    ordinary = await auth.organization(owner)
    counts = await seeder.seed(user_id, first["id"], 1)
    assert counts["pull_requests"] == 90
    assert counts["workflow_runs"] == 136
    assert counts["test_reports"] == 30
    assert counts["test_executions"] > 270
    await seeder.seed(user_id, second["id"], 2)

    async def snapshot(tenant: UUID) -> dict[str, object]:
        async with repository.transaction(user_id) as connection:
            await repository.tenant(connection, tenant)
            return {
                table: await repository.one(
                    connection,
                    f"SELECT count(*) AS count, md5(string_agg(to_jsonb(t)::text, '' ORDER BY id)) "
                    f"AS digest FROM forge.{table} t WHERE organization_id=:org",
                    org=tenant,
                )
                for table in (
                    *TABLES,
                    *DELIVERY_TABLES,
                    *TEST_TABLES,
                    "events",
                    "integrations",
                    "jobs",
                )
            }

    before = await snapshot(first["id"])
    assert await seeder.seed(user_id, first["id"], 1) == counts
    assert await snapshot(first["id"]) == before
    assert (await snapshot(second["id"]))["pull_requests"] != before["pull_requests"]
    with pytest.raises(ValueError, match="designated demo"):
        await seeder.seed(user_id, UUID(ordinary), 1)
    with pytest.raises(ValueError, match="production"):
        await DemoRepository(repository, "production").seed(user_id, first["id"], 1)
    async with repository.transaction(user_id) as connection:
        await repository.tenant(connection, first["id"])
        assert (
            await repository.one(
                connection, "SELECT id FROM forge.jobs WHERE organization_id=:org", org=first["id"]
            )
            is None
        )
        assert (
            await repository.one(
                connection,
                "SELECT installation_id FROM forge.github_installation_bindings "
                "WHERE organization_id=:org",
                org=first["id"],
            )
            is None
        )
        repo = await repository.one(
            connection,
            "SELECT id FROM forge.repositories WHERE organization_id=:org LIMIT 1",
            org=first["id"],
        )
        assert repo is not None
    response = await auth.mutate(
        owner.client, "POST", f"/organizations/{first['id']}/repositories/{repo['id']}/sync"
    )
    assert response.status_code == 409
    assert response.json()["code"] == "demo_repository"
    metrics = await owner.client.get(f"/api/v1/organizations/{first['id']}/metrics/pull-requests")
    assert metrics.status_code == 200, metrics.text
    assert metrics.json()["merged_count"] > 50
    assert metrics.json()["metrics"]["cycle_time"]["p95_seconds"] > 0
    ci = await owner.client.get(f"/api/v1/organizations/{first['id']}/metrics/ci")
    assert ci.status_code == 200, ci.text
    assert ci.json()["decisive_count"] > 40
    assert 0 < ci.json()["failure_fraction"] < 1
    assert ci.json()["coverage"]["completion_unknown_count"] == 2
    deployments = await owner.client.get(
        f"/api/v1/organizations/{first['id']}/metrics/deployments?classification=all"
    )
    assert deployments.status_code == 200, deployments.text
    assert deployments.json()["successful_count"] > 5
    assert deployments.json()["observed_success_count"] > deployments.json()["successful_count"]
    tests = await owner.client.get(f"/api/v1/organizations/{first['id']}/metrics/tests")
    assert tests.status_code == 200, tests.text
    assert 0 < tests.json()["pass_fraction"] < 1
    assert tests.json()["skipped_count"] == 28
    candidates = await owner.client.get(
        f"/api/v1/organizations/{first['id']}/tests?potential_only=true"
    )
    assert candidates.status_code == 200, candidates.text
    assert any(
        item["name"] == "refreshes_entry" and item["sample_count"] == 14 and item["potential_flaky"]
        for item in candidates.json()["items"]
    )
    async with repository.transaction(user_id) as connection:
        await repository.tenant(connection, first["id"])
        summary = await repository.one(
            connection,
            """SELECT count(*) FILTER(WHERE status='completed') AS completed,
                count(*) FILTER(WHERE superseded_by_id IS NOT NULL) AS superseded,
                count(*) FILTER(WHERE payload IS NOT NULL OR service_token_id IS NOT NULL) AS unsafe
                FROM forge.test_reports WHERE organization_id=:org""",
            org=first["id"],
        )
        assert summary == {"completed": 30, "superseded": 2, "unsafe": 0}


def test_delivery_demo_retries_and_deployments_preserve_evidence_grain() -> None:
    tenant = uuid4()
    anchor = datetime(2026, 9, 22, 12, tzinfo=UTC)
    changes = history(tenant, identifier(tenant, "integration"), anchor, 2)
    rows = delivery_history(tenant, anchor, changes)
    assert rows == delivery_history(tenant, anchor, changes)
    assert len(rows["workflow_runs"]) == 108
    assert len(rows["deployments"]) == 36
    runs = {row["id"]: row for row in rows["workflow_runs"]}
    commits = {row["id"]: row for row in changes["commits"]}
    prs = {row["id"]: row for row in changes["pull_requests"]}
    for run in runs.values():
        assert commits[run["commit_id"]]["sha"] == run["head_sha"]
        assert run["completion_source"] == ("jobs" if run["completed_at"] else None)
        if run["run_attempt"] == 2:
            previous = next(
                row
                for row in runs.values()
                if row["repository_id"] == run["repository_id"]
                and row["provider_run_id"] == run["provider_run_id"]
                and row["run_attempt"] == 1
            )
            assert previous["conclusion"] == "failure"
            assert run["conclusion"] == "success" and run["queued_at"] is None
            assert previous["created_at"] == run["created_at"]
        elif run["completed_at"]:
            jobs = [row for row in rows["workflow_jobs"] if row["workflow_run_id"] == run["id"]]
            assert max(row["completed_at"] for row in jobs) == run["completed_at"]
    for link in rows["workflow_run_pull_requests"]:
        assert (
            runs[link["workflow_run_id"]]["repository_id"]
            == prs[link["pull_request_id"]]["repository_id"]
        )
    deployments = {row["id"]: row for row in rows["deployments"]}
    successes = [row for row in rows["deployment_statuses"] if row["state"] == "success"]
    assert len(successes) == 2 * len({row["deployment_id"] for row in successes})
    assert {row["production_environment"] for row in deployments.values()} == {True, False, None}
    for deployment in deployments.values():
        assert commits[deployment["commit_id"]]["sha"] == deployment["sha"]
        assert deployment["workflow_run_id"] is None
    for items in rows.values():
        assert len({row["id"] for row in items}) == len(items)
        for row in items:
            assert row["organization_id"] == tenant
            assert not row.get("html_url")
            for value in row.values():
                if isinstance(value, datetime):
                    assert value <= anchor
