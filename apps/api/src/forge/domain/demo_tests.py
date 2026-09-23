"""Synthetic JUnit artifacts and explicit demo CI parents, never metric values."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID

from forge.domain.demo import identifier

TABLES = ("test_reports", "test_suites", "test_identities", "test_executions")


@dataclass(frozen=True, slots=True)
class DemoReport:
    receipt: dict[str, Any]
    xml: bytes


@dataclass(frozen=True, slots=True)
class TestHistory:
    __test__ = False
    workflow_runs: tuple[dict[str, Any], ...]
    workflow_jobs: tuple[dict[str, Any], ...]
    reports: tuple[DemoReport, ...]


def report_xml(index: int, *, uncorrected: bool = False) -> bytes:
    """Nine leaf cases, explicit retries and honest quality examples in small XML."""
    failure = index % 3 == 0 or uncorrected
    error = index % 5 == 0
    cache = (
        '<failure message="Synthetic cache response differed">Expected fresh entry.</failure>'
        if failure
        else ""
    )
    timeout = (
        '<error message="Synthetic service timeout">Fixture endpoint unavailable.</error>'
        if error
        else ""
    )
    retry = (
        '<flakyFailure message="Synthetic first attempt failed">'
        "<stackTrace>Fixture retry evidence.</stackTrace></flakyFailure>"
        if index % 4 == 0
        else ""
    )
    declared = 10 if index == 4 else 9
    duration = "-1" if index == 3 else "0.08"
    suite = f'''<testsuite name="Synthetic test history" tests="{declared}"
      failures="{int(failure)}" errors="{int(error)}" skipped="1">
      <testsuite name="Core" tests="5" failures="{int(failure)}" errors="0" skipped="1">
        <testcase classname="DemoConfiguration" file="tests/demo_config.py"
          name="loads_defaults" time="{duration}"/>
        <testcase classname="DemoCache" file="tests/demo_cache.py"
          name="refreshes_entry" time="0.15">{cache}</testcase>
        <testcase classname="DemoParser" file="tests/demo_parser.py"
          name="parses_value[valid]" time="0.04"/>
        <testcase classname="DemoParser" file="tests/demo_parser.py"
          name="parses_value[empty]" time="0.03"/>
        <testcase classname="DemoPlatform" name="optional_platform" time="0">
          <skipped message="Synthetic unsupported platform"/></testcase>
      </testsuite>
      <testsuite name="Edge cases" tests="4" failures="0" errors="{int(error)}" skipped="0">
        <testcase classname="DemoConsistency" name="eventually_consistent" time="0.11">
          {retry}</testcase>
        <testcase classname="DemoService" name="responds_before_timeout" time="0.22">
          {timeout}</testcase>
        <testcase classname="DemoDuplicate" name="same_display_name" time="0.01"/>
        <testcase classname="DemoDuplicate" name="same_display_name" time="0.02"/>
      </testsuite>
    </testsuite>'''
    document = f'<testsuites tests="{declared}">{suite}</testsuites>' if index % 2 else suite
    return document.encode("utf-8")


def history(
    organization: UUID, anchor: datetime, changes: dict[str, list[dict[str, Any]]]
) -> TestHistory:
    """Reuse the saved demo anchor; one stable branch/environment/shard for 14 samples."""
    workflows: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []
    reports: list[DemoReport] = []
    for repo_index, repository in enumerate(changes["repositories"]):
        repo = repository["id"]
        commit = max(
            (
                item
                for item in changes["commits"]
                if item["repository_id"] == repo
                and item["committed_at"] < anchor - timedelta(days=14)
            ),
            key=lambda item: item["committed_at"],
        )
        for index in range(14):
            key = f"phase6:{repo}:daily:{index}"
            workflow_id = identifier(organization, f"{key}:workflow")
            completed = anchor - timedelta(days=13 - index, hours=1)
            started = completed - timedelta(minutes=8)
            queued = started - timedelta(seconds=30)
            conclusion = "failure" if index % 3 == 0 or index % 5 == 0 else "success"
            workflows.append(
                {
                    "organization_id": organization,
                    "id": workflow_id,
                    "repository_id": repo,
                    "provider_run_id": 9_400_000_000 + repo_index * 1000 + index,
                    "run_attempt": 1,
                    "provider_workflow_id": 9_400_000_100 + repo_index,
                    "run_number": index + 1,
                    "actor_login": "forge-demo",
                    "name": "Synthetic test history",
                    "path": ".github/workflows/demo-tests.yml",
                    "event": "workflow_dispatch",
                    "head_branch": "main",
                    "head_sha": commit["sha"],
                    "commit_id": commit["id"],
                    "status": "completed",
                    "conclusion": conclusion,
                    "created_at": queued,
                    "queued_at": queued,
                    "started_at": started,
                    "completed_at": completed,
                    "completion_source": "jobs",
                    "updated_at": completed,
                    "html_url": "",
                    "observed_at": anchor,
                    "jobs_status": "complete",
                    "jobs_error": None,
                    "jobs_synced_at": anchor,
                    "links_status": "complete",
                    "links_error": None,
                    "links_synced_at": anchor,
                }
            )
            jobs.append(
                {
                    "organization_id": organization,
                    "id": identifier(organization, f"{key}:job"),
                    "repository_id": repo,
                    "workflow_run_id": workflow_id,
                    "provider_job_id": 9_500_000_000 + repo_index * 1000 + index,
                    "name": "Synthetic JUnit examples",
                    "status": "completed",
                    "conclusion": conclusion,
                    "started_at": started,
                    "completed_at": completed,
                    "html_url": "",
                    "failure_category": "unknown",
                    "observed_at": anchor,
                }
            )
            original_id = identifier(organization, f"{key}:report")
            # The last original report contains a known synthetic reporting error;
            # an explicit correction replaces it only after real persistence succeeds.
            for correction in range(2 if index == 13 else 1):
                xml = report_xml(index, uncorrected=index == 13 and correction == 0)
                received = completed + timedelta(minutes=1 + correction * 5)
                receipt = {
                    "organization_id": organization,
                    "id": identifier(organization, f"{key}:correction")
                    if correction
                    else original_id,
                    "repository_id": repo,
                    "workflow_run_id": workflow_id,
                    "service_token_id": None,
                    "report_key": "synthetic-unit-tests",
                    "shard": "default",
                    "framework": "junit",
                    "environment": "demo",
                    "branch": "main",
                    "commit_sha": commit["sha"],
                    "content_sha256": sha256(xml).hexdigest(),
                    "size_bytes": len(xml),
                    "status": "queued",
                    "supersedes_id": original_id if correction else None,
                    "received_at": received,
                    "occurred_at": completed,
                    "time_source": "workflow_completion",
                    "payload_expires_at": received + timedelta(days=1),
                    "payload": None,
                }
                reports.append(DemoReport(receipt, xml))
    return TestHistory(tuple(workflows), tuple(jobs), tuple(reports))
