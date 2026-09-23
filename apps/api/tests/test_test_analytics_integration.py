"""Hand-computed report/retry cohorts and scoped flakiness sequences in PostgreSQL."""

import json
import os
import secrets
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from test_analytics_integration import END, HOUR, MERGED, START, Facts
from test_analytics_integration import auth as auth_fixture
from test_analytics_integration import facts as facts_fixture
from test_auth import PREFIX
from test_delivery_integration import DeliveryFacts, provider_id

auth = auth_fixture
facts = facts_fixture
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated database required"
    ),
]


@dataclass
class TestFacts(DeliveryFacts):
    __test__ = False

    async def report(self, run: UUID, **overrides: Any) -> UUID:
        return await self.insert(
            "test_reports",
            {
                "repository_id": self.repository,
                "workflow_run_id": run,
                "report_key": "pytest",
                "shard": "default",
                "framework": "pytest",
                "environment": "linux",
                "branch": "main",
                "commit_sha": "a" * 40,
                "content_sha256": secrets.token_hex(32),
                "size_bytes": 100,
                "status": "completed",
                "received_at": MERGED,
                "processed_at": MERGED,
                "occurred_at": MERGED,
                "time_source": "workflow_completion",
                "payload_expires_at": END,
                **overrides,
            },
        )

    async def suite(self, report: UUID, ordinal: int = 0) -> UUID:
        return await self.insert(
            "test_suites",
            {
                "repository_id": self.repository,
                "report_id": report,
                "source_key": f"suite-{ordinal}",
                "path": json.dumps(["checks"]),
                "name": "checks",
                "ordinal": ordinal,
                "case_count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "error_count": 0,
                "skipped_count": 0,
            },
        )

    async def identity(self, **overrides: Any) -> UUID:
        return await self.insert(
            "test_identities",
            {
                "repository_id": self.repository,
                "framework": "pytest",
                "identity_key": secrets.token_hex(32),
                "identity_quality": "exact",
                "classname": "tests.Checkout",
                "name": "test_total[EUR]",
                "file": "tests/checkout.py",
                **overrides,
            },
        )

    async def execution(
        self,
        report: UUID,
        suite: UUID,
        identity: UUID,
        outcome: str = "passed",
        **overrides: Any,
    ) -> UUID:
        return await self.insert(
            "test_executions",
            {
                "repository_id": self.repository,
                "report_id": report,
                "suite_id": suite,
                "test_identity_id": identity,
                "ordinal": 0,
                "source_ordinal": 0,
                "retry_ordinal": 0,
                "is_final": True,
                "outcome": outcome,
                "duration_seconds": 0.2,
                **overrides,
            },
        )

    async def observed(
        self, run: UUID, outcome: str, identity: UUID | None = None, **overrides: Any
    ) -> UUID:
        report = await self.report(run, **overrides)
        suite = await self.suite(report)
        await self.execution(report, suite, identity or await self.identity(), outcome)
        return report


@pytest.fixture
async def tests(facts: Facts) -> TestFacts:
    return TestFacts(**vars(facts))


async def test_latest_completed_attempt_final_retry_and_supersession_denominator(tests: TestFacts):
    provider = provider_id()
    first = await tests.run(provider_run_id=provider, conclusion="failure")
    await tests.observed(first, "failed")
    final = await tests.run(provider_run_id=provider, run_attempt=2)
    report = await tests.report(final)
    suite = await tests.suite(report)
    identity = await tests.identity()
    await tests.execution(report, suite, identity, "failed", is_final=False)
    await tests.execution(report, suite, identity, "passed", ordinal=1, retry_ordinal=1)
    await tests.execution(
        report, suite, await tests.identity(), "skipped", ordinal=2, source_ordinal=1
    )
    second = await tests.run()
    await tests.observed(second, "error")
    third = await tests.run()
    old = await tests.observed(third, "failed")
    correction = await tests.observed(third, "passed", supersedes_id=old)
    await tests.update("test_reports", old, superseded_by_id=correction)
    missing_id = provider_id()
    older = await tests.run(provider_run_id=missing_id)
    await tests.observed(older, "passed")
    await tests.run(provider_run_id=missing_id, run_attempt=2)  # No report for latest attempt.
    result = await tests.get("/metrics/tests")
    assert result["passed_count"] == 2
    assert result["error_count"] == 1 and result["failed_count"] == 0
    assert result["skipped_count"] == 1 and result["eligible_count"] == 3
    assert result["pass_fraction"] == pytest.approx(2 / 3)
    assert result["report_count"] == 3
    assert result["coverage"]["known_workflow_count"] == 4
    assert result["coverage"]["missing_report_count"] == 1
    assert result["coverage"]["status"] == "partial"
    assert sum(day["eligible_count"] for day in result["trend"]) == 3
    retained = await tests.get(f"/test-runs/{old}")
    assert retained["test_run"]["superseded_by"] == str(correction)
    retry_history = await tests.get(f"/tests/{identity}/history")
    assert {row["status"] for row in retry_history["items"]} == {"failed", "passed"}


async def test_latest_completed_attempt_is_chosen_before_window_and_branch_filter(tests: TestFacts):
    provider = provider_id()
    previous = await tests.run(provider_run_id=provider)
    await tests.observed(previous, "passed")
    newer = await tests.run(provider_run_id=provider, run_attempt=2, completed_at=END + HOUR)
    await tests.observed(newer, "failed")
    result = await tests.get("/metrics/tests")
    assert result["pass_fraction"] is None and result["eligible_count"] == 0
    # An in-progress newer attempt does not displace the latest completed one.
    await tests.update("workflow_runs", newer, status="in_progress", completed_at=None)
    assert (await tests.get("/metrics/tests"))["passed_count"] == 1


async def test_empty_skipped_untimed_failed_and_queued_are_not_healthy(tests: TestFacts):
    await tests.run()  # Green CI without report.
    result = await tests.get("/metrics/tests")
    assert result["pass_fraction"] is None
    assert result["coverage"]["status"] == "unavailable"
    assert result["coverage"]["missing_report_count"] == 1
    skipped = await tests.run()
    await tests.observed(skipped, "skipped")
    untimed = await tests.run(completed_at=None)
    await tests.observed(untimed, "passed")
    await tests.report(await tests.run(), status="queued", processed_at=None)
    await tests.report(await tests.run(), status="failed", error_code="malformed_xml")
    result = await tests.get("/metrics/tests")
    assert result["pass_fraction"] is None and result["skipped_count"] == 1
    assert result["coverage"]["unknown_link_count"] == 1
    assert result["coverage"]["queued_report_count"] == 1
    assert result["coverage"]["failed_report_count"] == 1


async def test_flakiness_thresholds_contexts_skips_and_same_sha_reversals(tests: TestFacts):
    identity = await tests.identity()
    await tests.insert(
        "test_policies",
        {
            "repository_id": tests.repository,
            "min_executions": 4,
            "failure_rate_low": 0.1,
            "failure_rate_high": 0.9,
            "min_transitions": 2,
        },
    )
    provider = provider_id()
    # fail, skip, pass, fail, pass => four eligible outcomes, three transitions.
    for index, outcome in enumerate(("failed", "skipped", "passed", "failed", "passed")):
        run = await tests.run(
            provider_run_id=provider, run_attempt=index + 1, completed_at=MERGED + HOUR * index
        )
        await tests.observed(run, outcome, identity)
    # Different environment/branch/shard cannot contaminate the sequence.
    for metadata in ({"environment": "windows"}, {"branch": "feature"}, {"shard": "other"}):
        await tests.observed(await tests.run(), "failed", identity, **metadata)
    response = await tests.owner.client.get(tests.path + "/tests", params={"to": END.isoformat()})
    assert response.status_code == 200, response.text
    evidence = response.json()["items"]
    assert len(evidence) == 1
    candidate = evidence[0]
    assert candidate["sample_count"] == 4 and candidate["failed_count"] == 2
    assert candidate["failure_fraction"] == 0.5
    assert candidate["flip_count"] == 3 and candidate["same_sha_reversal_count"] == 3
    assert candidate["potential_flaky"] is True and candidate["confidence"] == "standard"
    assert candidate["policy"]["min_executions"] == 4
    history = await tests.get(f"/tests/{identity}/history")
    assert len(history["items"]) == 8
    assert len(history["evidence"]) == 4


async def test_flakiness_policy_window_excluded_branches_and_reduced_confidence(tests: TestFacts):
    identity = await tests.identity(identity_quality="fallback")
    policy = await tests.insert(
        "test_policies",
        {
            "repository_id": tests.repository,
            "window_days": 2,
            "min_executions": 2,
            "min_transitions": 1,
            "excluded_branches": json.dumps(["ignored"]),
        },
    )
    for index, outcome in enumerate(("failed", "passed")):
        run = await tests.run(completed_at=MERGED + HOUR * index)
        await tests.observed(run, outcome, identity, environment=None)
    old = await tests.run(completed_at=START - HOUR)
    await tests.observed(old, "failed", identity, environment=None)
    response = await tests.owner.client.get(tests.path + "/tests", params={"to": END.isoformat()})
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1 and items[0]["sample_count"] == 2
    assert items[0]["confidence"] == "reduced"
    await tests.update("test_policies", policy, excluded_branches=json.dumps(["main"]))
    assert (
        await tests.owner.client.get(tests.path + "/tests", params={"to": END.isoformat()})
    ).json()["items"] == []


async def test_reports_children_history_cursor_binding_and_tenant_isolation(tests: TestFacts):
    identity = await tests.identity()
    report = await tests.report(await tests.run())
    suite = await tests.suite(report)
    for ordinal in range(3):
        await tests.execution(
            report, suite, identity, ordinal=ordinal, retry_ordinal=ordinal, is_final=ordinal == 2
        )
    path = f"/test-runs/{report}/cases"
    first = await tests.get(path, limit=2)
    second = await tests.get(path, limit=2, cursor=first["next_cursor"])
    assert [row["ordinal"] for row in first["items"] + second["items"]] == [0, 1, 2]
    changed = await tests.owner.client.get(
        tests.path + path,
        params={
            "limit": 2,
            "status": "failed",
            "cursor": first["next_cursor"],
        },
    )
    assert changed.status_code == 422
    outsider = await tests.auth.register()
    other = await tests.auth.organization(outsider)
    for suffix in (f"test-runs/{report}", f"test-runs/{report}/cases", f"tests/{identity}/history"):
        assert (
            await outsider.client.get(f"{PREFIX}/organizations/{other}/{suffix}")
        ).status_code == 404
    await tests.update("repositories", tests.repository, selected=False)
    assert (await tests.get("/metrics/tests"))["eligible_count"] == 0
    assert (await tests.get("/metrics/tests", repository=str(tests.repository)))[
        "eligible_count"
    ] == 1
    foreign_repository = await tests.repo()
    foreign_identity = await tests.identity(repository_id=foreign_repository)
    with pytest.raises(IntegrityError):
        await tests.execution(report, suite, foreign_identity, ordinal=4)


async def test_metric_window_half_open_and_report_filters(tests: TestFacts):
    for at in (START - HOUR, START, END - HOUR, END):
        run = await tests.run(completed_at=at)
        await tests.observed(run, "passed")
    result = await tests.get("/metrics/tests")
    assert result["passed_count"] == 2
    listed = await tests.get("/test-runs")
    assert len(listed["items"]) == 2
    assert (await tests.get("/metrics/tests", environment="missing"))["pass_fraction"] is None
    assert (await tests.get("/test-runs", branch="missing"))["items"] == []
