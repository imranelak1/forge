"""Generated test facts exercise the production parser, never precomputed scores."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from forge.domain.demo import history as change_history
from forge.domain.demo import identifier
from forge.domain.demo_tests import history
from forge.integrations.junit import parse_junit


def test_junit_demo_is_repeatable_scoped_and_has_eligible_flakiness_evidence() -> None:
    organization = uuid4()
    anchor = datetime(2026, 9, 23, 12, tzinfo=UTC)
    changes = change_history(organization, identifier(organization, "integration"), anchor, 2)
    generated = history(organization, anchor, changes)
    assert history(organization, anchor, changes) == generated
    assert len(generated.workflow_runs) == len(generated.workflow_jobs) == 28
    assert len(generated.reports) == 30
    runs = {row["id"]: row for row in generated.workflow_runs}
    receipts = {report.receipt["id"]: report for report in generated.reports}
    superseded = {
        report.receipt["supersedes_id"]
        for report in generated.reports
        if report.receipt["supersedes_id"] is not None
    }
    observations: dict[object, list[bool]] = {}
    identities = set()
    warnings = set()
    retries = 0
    for artifact in generated.reports:
        receipt = artifact.receipt
        workflow = runs[receipt["workflow_run_id"]]
        assert receipt["organization_id"] == workflow["organization_id"] == organization
        assert receipt["repository_id"] == workflow["repository_id"]
        assert receipt["commit_sha"] == workflow["head_sha"]
        assert receipt["service_token_id"] is None and receipt["payload"] is None
        assert anchor - timedelta(days=14) < receipt["occurred_at"] < anchor
        assert workflow["head_branch"] == "main" and receipt["environment"] == "demo"
        assert receipt["received_at"] <= anchor
        assert not workflow["html_url"]
        parsed = parse_junit(artifact.xml)
        assert parsed.counts["tests"] == 9 and parsed.counts["skipped"] == 1
        assert len(parsed.suites) == 3
        warnings.update(parsed.warnings)
        retries += sum(not case.is_final for case in parsed.cases)
        if receipt["supersedes_id"]:
            old = receipts[receipt["supersedes_id"]]
            assert old.receipt["workflow_run_id"] == receipt["workflow_run_id"]
            assert old.receipt["content_sha256"] != receipt["content_sha256"]
        if receipt["id"] not in superseded:
            cache = next(case for case in parsed.cases if case.name == "refreshes_entry")
            assert cache.identity_quality == "exact" and cache.is_final
            identities.add(cache.identity_key)
            observations.setdefault(receipt["repository_id"], []).append(cache.outcome == "passed")
    assert (
        len(identities) == 1
    )  # Repository scope is enforced by persistence, not an XML assertion.
    assert retries == 8
    assert warnings == {
        "ambiguous_duplicate_identity",
        "invalid_duration",
        "declared_count_mismatch",
    }
    for outcomes in observations.values():
        assert len(outcomes) == 14
        assert 0.05 <= outcomes.count(False) / len(outcomes) <= 0.95
        assert (
            sum(first != second for first, second in zip(outcomes, outcomes[1:], strict=False)) >= 2
        )
