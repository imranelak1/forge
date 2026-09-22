"""Source-derived CI/deployment facts with explicit timing and classification evidence."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from forge.domain.analytics import Window, evidence_coverage, github_url

Classification = Literal["production", "nonproduction", "unknown", "all"]
DECISIVE = ("success", "failure", "timed_out", "startup_failure", "action_required")
FAILED = DECISIVE[1:]


def seconds(start: datetime | None, end: datetime | None) -> float | None:
    return (end - start).total_seconds() if start and end and end >= start else None


def full_days(effective: Window) -> tuple[datetime, datetime, int]:
    start = effective.start.replace(hour=0, minute=0, second=0, microsecond=0)
    if start < effective.start:
        try:
            start += timedelta(days=1)
        except OverflowError:
            return effective.end, effective.end, 0
    end = effective.end.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, end, max(0, (end - start).days)


def dates(effective: Window) -> list[str]:
    day = effective.start.date()
    last = (effective.end - timedelta(microseconds=1)).date()
    result = []
    while day <= last:
        result.append(day.isoformat())
        if day == last:
            break
        day += timedelta(days=1)
    return result


def day_is_full(day: str, effective: Window) -> bool:
    start, end, _ = full_days(effective)
    return start <= datetime.fromisoformat(day).replace(tzinfo=UTC) < end


def run_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        name: row[name]
        for name in (
            "id",
            "repository_id",
            "repository_name",
            "run_number",
            "event",
            "status",
            "conclusion",
            "head_sha",
            "head_branch",
            "actor_login",
            "created_at",
            "queued_at",
            "started_at",
            "completed_at",
            "completion_source",
            "duration_seconds",
            "queue_seconds",
            "duration_exclusion",
            "queue_exclusion",
        )
    }
    result.update(
        provider_id=row["provider_run_id"],
        workflow_id=row["provider_workflow_id"],
        workflow_name=row["name"],
        attempt=row["run_attempt"],
        html_url=github_url(row["html_url"]),
        jobs_coverage=evidence_coverage(row, "jobs"),
        links_coverage=evidence_coverage(row, "links"),
    )
    return result


def job_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in ("id", "name", "status", "conclusion", "started_at", "completed_at")
    } | {
        "provider_id": row["provider_job_id"],
        "html_url": github_url(row["html_url"]),
        "duration_seconds": seconds(row["started_at"], row["completed_at"]),
    }


def deployment_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        key: row[key]
        for key in (
            "id",
            "repository_id",
            "repository_name",
            "provider_id",
            "environment",
            "classification",
            "classification_source",
            "sha",
            "ref",
            "task",
            "creator_login",
            "created_at",
            "updated_at",
            "first_success_at",
            "latest_state",
            "success_exclusion",
        )
    }
    result.update(
        provider_production_environment=row["production_environment"],
        success_eligible=row["success_exclusion"] is None,
        html_url=github_url(row["html_url"]),
        statuses_coverage=evidence_coverage(row, "statuses"),
        links_coverage={
            "status": "complete" if row["commit_id"] else "partial",
            "observed_at": row["observed_at"],
            "error_code": None if row["commit_id"] else "commit_not_imported",
        },
    )
    return result


def status_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in ("id", "provider_id", "state", "created_at", "creator_login", "description")
    } | {"html_url": github_url(row["html_url"])}
