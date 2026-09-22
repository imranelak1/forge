"""Authenticated delivery evidence and versioned source-derived metrics."""

from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from forge.domain.analytics import empty_distribution, window
from forge.domain.delivery import (
    DECISIVE,
    dates,
    day_is_full,
    deployment_summary,
    full_days,
    job_summary,
    run_summary,
    status_summary,
)
from forge.domain.identity import Actor, DomainError, not_found, require_manager
from forge.repositories.delivery import DeliveryRepository
from forge.security.identity import now
from forge.services.analytics import AnalyticsService, commit_summary, pr_summary
from forge.services.identity import IdentityService


def coverage(sources: Mapping[str, Any], extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    limitations = []
    for key, code in (
        ("source_incomplete", "source_incomplete"),
        ("history_window_partial", "history_window_partial"),
        ("sources_unavailable", "source_access_unavailable"),
    ):
        if sources[key]:
            limitations.append(code)
    if not sources["repository_count"]:
        limitations.append("no_selected_repositories")
    extra = extra or {}
    for key in ("completion_unknown_count", "jobs_incomplete_count", "statuses_incomplete_count"):
        if extra.get(key):
            limitations.append(key.removesuffix("_count"))
    status = "partial" if limitations else "complete"
    if (
        not sources["repository_count"]
        or sources["repositories_unavailable"] == sources["repository_count"]
    ):
        status = "unavailable"
    # Timing quality is explicit; it does not change whether the source was fully enumerated.
    if extra.get("completion_proxy_count"):
        limitations.append("job_completion_proxy")
    return {
        "status": status,
        "input_watermark": sources["input_watermark"],
        "repository_count": sources["repository_count"],
        "repositories_complete": sources["repositories_complete"],
        "limitations": limitations,
        **extra,
    }


def ci_bucket(row: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row = row or {}
    result = {
        key: row.get(key, 0)
        for key in ("completed_count", "decisive_count", "success_count", "failure_count")
    }
    decisive = result["decisive_count"]
    result["success_fraction"] = result["success_count"] / decisive if decisive else None
    result["failure_fraction"] = result["failure_count"] / decisive if decisive else None
    for metric in ("duration", "queue"):
        result[metric] = {
            key: row.get(f"{metric}_{key}", default)
            for key, default in empty_distribution().items()
        }
    return result


class DeliveryService(AnalyticsService):
    repository: DeliveryRepository

    def __init__(self, identity: IdentityService) -> None:
        super().__init__(identity)
        self.repository = DeliveryRepository(identity.repository.engine)

    @staticmethod
    def parameters(
        organization: UUID, repository: UUID | None = None, **filters: Any
    ) -> dict[str, Any]:
        return {
            "org": organization,
            "repository": repository,
            "selected_only": repository is None,
            "workflow": None,
            "branch": None,
            "environment": None,
            "classification": "all",
            **filters,
        }

    async def ci_metrics(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        workflow: int | None,
        branch: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> dict[str, Any]:
        as_of = now()
        effective = window(start, end, as_of)
        parameters = self.parameters(
            organization,
            repository,
            workflow=workflow,
            branch=branch,
            from_time=effective.start,
            to_time=effective.end,
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            rows = await self.repository.ci_aggregates(connection, parameters)
            breakdown = await self.repository.ci_breakdown(connection, parameters)
            sources = await self.repository.source_coverage(connection, parameters, "ci")
            evidence = await self.repository.ci_evidence_coverage(connection, parameters)
            recurring = await self.repository.recurring_failures(connection, parameters)
        total = ci_bucket()
        daily = {day: {"date": day, **ci_bucket()} for day in dates(effective)}
        for row in rows:
            if row["is_total"]:
                total = ci_bucket(row)
            else:
                day = row["day"].isoformat()
                daily[day] = {"date": day, **ci_bucket(row)}
        conclusions: Counter[str] = Counter()
        for row in breakdown:
            conclusions[row["conclusion"]] += row["count"]
            if row["conclusion"] in DECISIVE:
                for metric in ("duration", "queue"):
                    reason = row[f"{metric}_exclusion"]
                    if reason:
                        for destination in (total, daily[row["day"].isoformat()]):
                            excluded = destination[metric]["exclusions"]
                            excluded[reason] = excluded.get(reason, 0) + row["count"]
        return {
            "formula_version": "ci-attempts-v1",
            "as_of": as_of,
            "window": effective.summary(),
            "scope": {
                "repository_id": repository,
                "selected_only": repository is None,
                "repository_count": sources["repository_count"],
                "workflow_id": workflow,
                "branch": branch,
            },
            **total,
            "conclusions": dict(conclusions),
            "trend": list(daily.values()),
            "recurring_failures": recurring,
            "coverage": coverage(sources, evidence),
        }

    async def deployment_metrics(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        environment: str | None,
        classification: str,
        start: datetime | None,
        end: datetime | None,
    ) -> dict[str, Any]:
        as_of = now()
        effective = window(start, end, as_of)
        parameters = self.parameters(
            organization,
            repository,
            environment=environment,
            classification=classification,
            from_time=effective.start,
            to_time=effective.end,
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            rows = await self.repository.deployment_aggregates(connection, parameters)
            breakdown = await self.repository.deployment_breakdown(connection, parameters)
            sources = await self.repository.source_coverage(connection, parameters, "deployments")
            evidence = await self.repository.deployment_evidence_coverage(connection, parameters)
        observed = coverage(sources, evidence)
        daily: dict[str, dict[str, Any]] = {
            day: {
                "date": day,
                "successful_count": 0,
                "observed_success_count": 0,
                "fully_covered": observed["status"] == "complete" and day_is_full(day, effective),
            }
            for day in dates(effective)
        }
        total: dict[str, Any] = {
            "successful_count": 0,
            "observed_success_count": 0,
            "excluded_count": 0,
        }
        for row in rows:
            if row["is_total"]:
                total = {key: row[key] for key in total}
            else:
                daily[row["day"].isoformat()].update(
                    successful_count=row["successful_count"],
                    observed_success_count=row["observed_success_count"],
                )
        states = {row["key"]: row["count"] for row in breakdown if row["kind"] == "state"}
        exclusions = {row["key"]: row["count"] for row in breakdown if row["kind"] == "exclusion"}
        days = full_days(effective)[2] if observed["status"] == "complete" else 0
        full_success = sum(
            row["successful_count"] for row in daily.values() if row["fully_covered"]
        )
        return {
            "formula_version": "deployments-v1",
            "as_of": as_of,
            "window": effective.summary(),
            "scope": {
                "repository_id": repository,
                "selected_only": repository is None,
                "repository_count": sources["repository_count"],
                "environment": environment,
                "classification": classification,
            },
            **total,
            "exclusions": exclusions,
            "created_count": sum(states.values()),
            "states": states,
            "fully_covered_days": days,
            "frequency_per_day": full_success / days if days else None,
            "trend": list(daily.values()),
            "coverage": observed,
        }

    async def runs(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        workflow: int | None,
        branch: str | None,
        start: datetime | None,
        end: datetime | None,
        cohort: str,
        outcome: str,
        metric: str | None,
        eligibility: str | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        scope = dict(
            entity="workflow_runs",
            org=organization,
            repository=repository,
            workflow=workflow,
            branch=branch,
            start=start,
            end=end,
            cohort=cohort,
            outcome=outcome,
            metric=metric,
            eligibility=eligibility,
            limit=limit,
        )
        codec, boundary, effective = self.paging(scope, cursor, start, end)
        assert effective
        parameters = self.parameters(
            organization,
            repository,
            workflow=workflow,
            branch=branch,
            from_time=effective.start,
            to_time=effective.end,
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            rows = await self.repository.runs(
                connection,
                parameters,
                cohort,
                outcome,
                metric,
                eligibility or ("eligible" if metric else "all"),
                boundary,
                limit + 1,
            )
            sources = await self.repository.source_coverage(connection, parameters, "ci")
            evidence = await self.repository.ci_evidence_coverage(connection, parameters)
        return self.page(rows, limit, codec, run_summary, effective) | {
            "coverage": coverage(sources, evidence)
        }

    async def deployments(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        environment: str | None,
        classification: str,
        start: datetime | None,
        end: datetime | None,
        cohort: str,
        eligibility: str,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        scope = dict(
            entity="deployments",
            org=organization,
            repository=repository,
            environment=environment,
            classification=classification,
            start=start,
            end=end,
            cohort=cohort,
            eligibility=eligibility,
            limit=limit,
        )
        codec, boundary, effective = self.paging(scope, cursor, start, end)
        assert effective
        parameters = self.parameters(
            organization,
            repository,
            environment=environment,
            classification=classification,
            from_time=effective.start,
            to_time=effective.end,
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            rows = await self.repository.deployments(
                connection, parameters, cohort, eligibility, boundary, limit + 1
            )
            sources = await self.repository.source_coverage(connection, parameters, "deployments")
            evidence = await self.repository.deployment_evidence_coverage(connection, parameters)
        return self.page(rows, limit, codec, deployment_summary, effective) | {
            "coverage": coverage(sources, evidence)
        }

    async def detail(
        self, actor: Actor, organization: UUID, identifier: UUID, parent: str
    ) -> dict[str, Any]:
        parameters = self.parameters(organization, selected_only=False)
        fetch = self.repository.run if parent == "run" else self.repository.deployment
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization)
            row = await fetch(connection, parameters, identifier)
            if row is None:
                raise not_found()
            counts = await self.repository.delivery_counts(
                connection, organization, identifier, parent
            )
        key = "workflow_run" if parent == "run" else "deployment"
        summarize = run_summary if parent == "run" else deployment_summary
        return {key: summarize(row), "counts": counts}

    async def children(
        self,
        actor: Actor,
        organization: UUID,
        identifier: UUID,
        parent: str,
        kind: str,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        codec, boundary, _ = self.paging(
            dict(org=organization, parent=parent, id=identifier, kind=kind, limit=limit),
            cursor,
            timed=False,
        )
        if boundary and kind in {"jobs", "statuses"} and boundary["at"] is None:
            raise DomainError(422, "invalid_cursor", "The pagination cursor is invalid.")
        parameters = self.parameters(organization, selected_only=False)
        fetch = self.repository.run if parent == "run" else self.repository.deployment
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization)
            if await fetch(connection, parameters, identifier) is None:
                raise not_found()
            rows = await self.repository.delivery_evidence(
                connection, organization, identifier, parent, kind, boundary, limit + 1
            )
        summarize = {
            "jobs": job_summary,
            "statuses": status_summary,
            "pull-requests": pr_summary,
            "commits": commit_summary,
        }[kind]
        return self.page(rows, limit, codec, summarize)

    async def environments(
        self, actor: Actor, organization: UUID, repository: UUID
    ) -> dict[str, Any]:
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            items = await self.repository.environments(connection, organization, repository)
        return {"items": items}

    async def classify(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID,
        environment: str,
        classification: str | None,
    ) -> dict[str, Any]:
        async with self.repository.transaction(actor.user_id) as connection:
            _, member = await self.organizations.context(connection, actor, organization, lock=True)
            require_manager(member["role"])
            if not actor.email_verified:
                raise DomainError(
                    403, "email_unverified", "Verify your email before classifying environments."
                )
            row = await self.repository.one(
                connection,
                """SELECT e.* FROM forge.deployment_environments e
              WHERE e.organization_id=:org AND e.repository_id=:repo AND e.name=:name
              AND EXISTS (SELECT 1 FROM forge.deployments d
                WHERE d.organization_id=e.organization_id
                AND d.repository_id=e.repository_id AND d.environment_id=e.id) FOR UPDATE OF e""",
                org=organization,
                repo=repository,
                name=environment,
            )
            if row is None:
                raise not_found()
            await self.repository.execute(
                connection,
                """UPDATE forge.deployment_environments
              SET classification=:value,updated_by=:actor,updated_at=now()
              WHERE organization_id=:org AND repository_id=:repo AND id=:id""",
                org=organization,
                repo=repository,
                id=row["id"],
                actor=actor.user_id,
                value=classification,
            )
            await self.repository.audit(
                connection,
                uuid4(),
                organization,
                actor.user_id,
                f"deployment_environment.{classification or 'provider'}",
                row["id"],
            )
        return {"environment": environment, "override": classification}
