"""Metadata-only Actions/deployment records with explicit source provenance."""

from collections.abc import Mapping
from typing import Any

from forge.domain.github import actor, object_value, positive_id, sha, string, timestamp


def workflow_run(
    value: Mapping[str, Any], full_name: str, repository_provider_id: int
) -> dict[str, Any]:
    identifier, attempt = positive_id(value.get("id")), positive_id(value.get("run_attempt"))
    if attempt >= 2**31:
        raise ValueError("invalid_attempt")
    repository = value.get("repository")
    if repository is not None and object_value(repository).get("id") != repository_provider_id:
        raise ValueError("repository_mismatch")
    references = value.get("pull_requests", [])
    if not isinstance(references, list) or len(references) > 100:
        raise ValueError("invalid_pull_request_references")
    links = []
    for reference in references:
        item = object_value(reference)
        base = object_value(item.get("base", {}))
        base_repo = object_value(base.get("repo", {}))
        links.append(
            {
                "provider_id": positive_id(item.get("id")),
                "number": positive_id(item.get("number")),
                "repository_provider_id": base_repo.get("id"),
            }
        )
    created = timestamp(value.get("created_at"))
    login, _ = actor(value.get("actor"))
    return {
        "provider_run_id": identifier,
        "run_attempt": attempt,
        "provider_workflow_id": positive_id(value.get("workflow_id")),
        "run_number": positive_id(value["run_number"])
        if value.get("run_number") is not None
        else None,
        "actor_login": login,
        "name": string(value.get("name") or "Workflow", 10000),
        "path": string(value.get("path"), 4096, optional=True),
        "event": string(value.get("event"), 80),
        "head_branch": string(value.get("head_branch"), 255, optional=True),
        "head_sha": sha(value.get("head_sha")),
        "status": string(value.get("status"), 40),
        "conclusion": string(value.get("conclusion"), 40, optional=True),
        "created_at": created,
        "queued_at": created if attempt == 1 else None,
        "started_at": timestamp(value.get("run_started_at"), optional=True),
        "updated_at": timestamp(value.get("updated_at")),
        "html_url": f"https://github.com/{full_name}/actions/runs/{identifier}/attempts/{attempt}",
        "provider_pull_requests": links,
    }


def workflow_job(
    value: Mapping[str, Any], full_name: str, run_id: int, attempt: int
) -> dict[str, Any]:
    if value.get("run_id") != run_id or (
        value.get("run_attempt") is not None and value["run_attempt"] != attempt
    ):
        raise ValueError("attempt_mismatch")
    identifier = positive_id(value.get("id"))
    labels, steps = value.get("labels", []), value.get("steps", [])
    if (
        not isinstance(labels, list)
        or len(labels) > 100
        or not isinstance(steps, list)
        or len(steps) > 100
    ):
        raise ValueError("metadata_limit")
    normalized_steps = []
    for raw in steps:
        step = object_value(raw)
        normalized_steps.append(
            {
                "number": positive_id(step.get("number")),
                "name": string(step.get("name"), 1000),
                "status": string(step.get("status"), 40),
                "conclusion": string(step.get("conclusion"), 40, optional=True),
                "started_at": step.get("started_at"),
                "completed_at": step.get("completed_at"),
            }
        )
        for key in ("started_at", "completed_at"):
            at = timestamp(step.get(key), optional=True)
            normalized_steps[-1][key] = at.isoformat() if at else None
    conclusion = string(value.get("conclusion"), 40, optional=True)
    return {
        "provider_job_id": identifier,
        "name": string(value.get("name"), 10000),
        "status": string(value.get("status"), 40),
        "conclusion": conclusion,
        "started_at": timestamp(value.get("started_at"), optional=True),
        "completed_at": timestamp(value.get("completed_at"), optional=True),
        "html_url": f"https://github.com/{full_name}/actions/runs/{run_id}/job/{identifier}",
        "labels": [string(label, 255) for label in labels],
        "steps": normalized_steps,
        "failure_category": {
            "timed_out": "timeout",
            "startup_failure": "startup",
            "action_required": "action_required",
        }.get(conclusion or "", "unknown"),
    }


def optional_bool(value: object) -> bool | None:
    if value is not None and type(value) is not bool:
        raise ValueError("invalid_boolean")
    return value


def deployment(value: Mapping[str, Any], full_name: str) -> dict[str, Any]:
    identifier = positive_id(value.get("id"))
    login, _ = actor(value.get("creator"))
    return {
        "provider_id": identifier,
        "environment": string(value.get("environment"), 255),
        "production_environment": optional_bool(value.get("production_environment")),
        "transient_environment": optional_bool(value.get("transient_environment")),
        "sha": sha(value.get("sha")),
        "ref": string(value.get("ref"), 4096),
        "task": string(value.get("task") or "deploy", 100),
        "description": string(value.get("description"), 10000, optional=True),
        "creator_login": login,
        "created_at": timestamp(value.get("created_at")),
        "updated_at": timestamp(value.get("updated_at")),
        "html_url": f"https://github.com/{full_name}/deployments",
    }


def deployment_status(value: Mapping[str, Any], full_name: str) -> dict[str, Any]:
    login, _ = actor(value.get("creator"))
    return {
        "provider_id": positive_id(value.get("id")),
        "state": string(value.get("state"), 40),
        "description": string(value.get("description"), 10000, optional=True),
        "environment": string(value.get("environment"), 255, optional=True),
        "creator_login": login,
        "created_at": timestamp(value.get("created_at")),
        "updated_at": timestamp(value.get("updated_at")),
        "html_url": f"https://github.com/{full_name}/deployments",
    }
