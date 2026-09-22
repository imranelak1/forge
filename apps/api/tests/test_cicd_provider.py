"""Fixed provider endpoints and metadata/provenance semantics without network access."""

import json
from typing import Any

import httpx
import pytest
from test_github_provider import app_settings as app_settings_fixture
from test_github_provider import installation

from forge.config import Settings
from forge.domain import cicd
from forge.integrations.github import GitHubApp, GitHubFailure

app_settings = app_settings_fixture


@pytest.mark.parametrize("grants", [(), ("actions",), ("deployments",), ("actions", "deployments")])
async def test_actions_and_deployments_permissions_are_requested_independently(
    app_settings: Settings,
    grants: tuple[str, ...],
) -> None:
    permissions = {"contents": "read", "pull_requests": "read", **dict.fromkeys(grants, "read")}
    requests = []

    def transport(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=installation(permissions=permissions))
        requests.append(json.loads(request.content))
        return httpx.Response(201, json={"token": "fixture-token", "permissions": permissions})

    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider.client = client
        _, observed = await provider.cicd_credentials(99)
    assert observed == frozenset(grants)
    assert requests == [{"permissions": permissions}]


async def test_attempt_jobs_and_status_history_use_fixed_explicit_endpoints(
    app_settings: Settings,  # noqa: F811
) -> None:
    requests = []

    def transport(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path.endswith("/jobs"):
            return httpx.Response(200, json={"total_count": 0, "jobs": []})
        if request.url.path.endswith("/statuses"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/runs"):
            return httpx.Response(200, json={"total_count": 0, "workflow_runs": []})
        return httpx.Response(200, json={"id": 500, "run_attempt": 2})

    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider.client = client
        await provider.workflow_run("token", "team", "repo", 500, 2)
        await provider.workflow_jobs("token", "team", "repo", 500, 2, 3)
        await provider.deployment_statuses("token", "team", "repo", 700, 4)
        await provider.workflow_runs("token", "team", "repo", 1)
        with pytest.raises(GitHubFailure):
            await provider.workflow_runs("token", "team", "repo", 101)
    assert requests == [
        "https://api.github.com/repos/team/repo/actions/runs/500/attempts/2",
        "https://api.github.com/repos/team/repo/actions/runs/500/attempts/2/jobs?per_page=100&page=3",
        "https://api.github.com/repos/team/repo/deployments/700/statuses?per_page=100&page=4",
        "https://api.github.com/repos/team/repo/actions/runs?per_page=100&page=1",
    ]


def test_rerun_queue_and_completion_are_unknown_without_explicit_evidence() -> None:
    from test_cicd_pipeline import workflow

    value = workflow(2, conclusion="future_conclusion")
    row = cicd.workflow_run(value, "team/repo", 1)
    assert row["queued_at"] is None and "completed_at" not in row
    assert row["conclusion"] == "future_conclusion"
    value["repository"] = {"id": 2}
    with pytest.raises(ValueError, match="repository_mismatch"):
        cicd.workflow_run(value, "team/repo", 1)


def test_environment_name_does_not_classify_and_arbitrary_log_urls_are_discarded() -> None:
    from test_cicd_pipeline import deployment, job, status

    value = deployment()
    value.pop("production_environment")
    value["payload"] = {"workflow_run_id": 999, "secret": "do-not-retain"}
    row = cicd.deployment(value, "team/repo")
    assert row["production_environment"] is None and "payload" not in row
    source = status(1)
    source["log_url"] = "https://untrusted.example/secret"
    assert "log_url" not in cicd.deployment_status(source, "team/repo")
    raw: dict[str, Any] = job(conclusion="failure")
    raw["output"] = {"summary": "secret output"}
    normalized = cicd.workflow_job(raw, "team/repo", 500, 1)
    assert normalized["failure_category"] == "unknown" and "output" not in normalized
    assert set(normalized["steps"][0]) == {
        "number",
        "name",
        "status",
        "conclusion",
        "started_at",
        "completed_at",
    }
    raw["run_attempt"] = 2
    with pytest.raises(ValueError, match="attempt_mismatch"):
        cicd.workflow_job(raw, "team/repo", 500, 1)
