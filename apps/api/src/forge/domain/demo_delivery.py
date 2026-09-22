"""Generated CI attempts and deployment facts linked to the existing demo changes."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from forge.domain.demo import identifier

TABLES = (
    "workflow_runs",
    "workflow_jobs",
    "workflow_run_pull_requests",
    "deployment_environments",
    "deployments",
    "deployment_statuses",
)


def history(
    organization: UUID, anchor: datetime, changes: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """Use the persisted Phase 4 anchor and identities; never enqueue a provider job."""
    rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}

    def add(table: str, key: str, **values: Any) -> UUID:
        row_id = identifier(organization, f"phase5:{key}")
        rows[table].append({"organization_id": organization, "id": row_id, **values})
        return row_id

    def coverage(prefix: str, partial: bool = False) -> dict[str, Any]:
        return {
            f"{prefix}_status": "partial" if partial else "complete",
            f"{prefix}_synced_at": anchor,
            f"{prefix}_error": "demo_partial_evidence" if partial else None,
        }

    commits = {row["sha"]: row for row in changes["commits"]}
    for repo_index, repository in enumerate(changes["repositories"]):
        repo_id = repository["id"]
        environments = {}
        for name in ("production", "staging", "preview"):
            environments[name] = add(
                "deployment_environments",
                f"{repo_id}:environment:{name}",
                repository_id=repo_id,
                name=name,
                classification=None,
                updated_by=None,
                updated_at=anchor,
            )
        prs = [row for row in changes["pull_requests"] if row["repository_id"] == repo_id]
        for index, pr in enumerate(prs):
            commit = commits[pr["head_sha"]]
            created = commit["committed_at"] + timedelta(minutes=2)
            # A successful rerun is a second attempt of the same provider run.
            retry = index % 5 == 0
            conclusion = (
                "failure"
                if retry
                else (
                    "success",
                    "success",
                    "success",
                    "timed_out",
                    "success",
                    "cancelled",
                    "neutral",
                    "skipped",
                )[index % 8]
            )
            for attempt in range(1, 3 if retry else 2):
                run_key = f"{repo_id}:run:{index}:attempt:{attempt}"
                result = "success" if attempt == 2 else conclusion
                started = created + timedelta(minutes=2 + (attempt - 1) * 40)
                ended = started + timedelta(minutes=6 + index % 19)
                partial = index == 43
                completed = None if partial else ended
                run_id = add(
                    "workflow_runs",
                    run_key,
                    repository_id=repo_id,
                    provider_run_id=9_100_000_000 + repo_index * 1000 + index,
                    run_attempt=attempt,
                    provider_workflow_id=9_100_000_100 + index % 3,
                    run_number=100 + index,
                    actor_login=pr["author_login"],
                    name=("Verify changes", "Build package", "Check dependencies")[index % 3],
                    path=(
                        ".github/workflows/verify.yml",
                        ".github/workflows/build.yml",
                        ".github/workflows/dependencies.yml",
                    )[index % 3],
                    event="pull_request",
                    head_branch=f"change/{pr['number']}",
                    head_sha=commit["sha"],
                    commit_id=commit["id"],
                    status="completed",
                    conclusion=result,
                    created_at=created,
                    queued_at=created if attempt == 1 else None,
                    started_at=started,
                    completed_at=completed,
                    completion_source="jobs" if completed else None,
                    updated_at=ended,
                    html_url="",
                    observed_at=anchor,
                    **coverage("jobs", partial),
                    **coverage("links"),
                )
                add(
                    "workflow_run_pull_requests",
                    f"{run_key}:pr",
                    repository_id=repo_id,
                    workflow_run_id=run_id,
                    pull_request_id=pr["id"],
                    source="provider",
                )
                for job_index, name in enumerate(("Lint and types", "Unit tests", "Build")):
                    if partial and job_index == 2:
                        continue
                    job_result = (
                        result
                        if job_index == 2 or result in ("cancelled", "skipped")
                        else "success"
                    )
                    add(
                        "workflow_jobs",
                        f"{run_key}:job:{job_index}",
                        repository_id=repo_id,
                        workflow_run_id=run_id,
                        provider_job_id=9_200_000_000
                        + repo_index * 10000
                        + index * 10
                        + attempt * 3
                        + job_index,
                        name=name,
                        status="completed",
                        conclusion=job_result,
                        started_at=started + timedelta(seconds=job_index * 20),
                        completed_at=ended - timedelta(seconds=(2 - job_index) * 30),
                        html_url="",
                        failure_category="timeout" if job_result == "timed_out" else "unknown",
                        observed_at=anchor,
                    )
            if pr["merged_at"] is None or index % 2:
                continue
            # Deployments are separate explicit facts, not conclusions inferred from CI.
            merge = commits[pr["merge_commit_sha"]]
            deployed = merge["committed_at"] + timedelta(minutes=30)
            environment = ("production", "staging", "preview")[index % 3]
            deployment_key = f"{repo_id}:deployment:{index}"
            incomplete = index == 38
            deployment_id = add(
                "deployments",
                deployment_key,
                repository_id=repo_id,
                provider_id=9_300_000_000 + repo_index * 1000 + index,
                environment_id=environments[environment],
                environment=environment,
                production_environment={"production": True, "staging": False, "preview": None}[
                    environment
                ],
                transient_environment=environment == "preview",
                sha=merge["sha"],
                ref="main",
                task="deploy",
                description=f"Generated release for change #{pr['number']}",
                creator_login=pr["author_login"],
                created_at=deployed,
                updated_at=deployed + timedelta(minutes=20),
                html_url="",
                commit_id=merge["id"],
                workflow_run_id=None,
                workflow_provider_id=None,
                workflow_attempt=None,
                workflow_link_source=None,
                observed_at=anchor,
                **coverage("statuses", incomplete),
            )
            states = (
                ("queued", "in_progress", "failure")
                if index % 10 == 2
                else ("queued", "in_progress", "success", "success", "inactive")
            )
            for status_index, state in enumerate(states):
                occurred = deployed + timedelta(minutes=status_index * 5)
                add(
                    "deployment_statuses",
                    f"{deployment_key}:status:{status_index}",
                    repository_id=repo_id,
                    deployment_id=deployment_id,
                    provider_id=9_400_000_000 + repo_index * 10000 + index * 10 + status_index,
                    state=state,
                    description={
                        "queued": "Waiting for an available runner",
                        "in_progress": "Release started",
                        "success": "Release completed",
                        "inactive": "Superseded by a later release",
                        "failure": "Release did not complete",
                    }[state],
                    environment=environment,
                    creator_login=pr["author_login"],
                    created_at=occurred,
                    updated_at=occurred,
                    html_url="",
                    observed_at=anchor,
                )
    return rows
