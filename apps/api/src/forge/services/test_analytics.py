"""Read test evidence without turning absent reports into a healthy result."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from forge.domain.analytics import window
from forge.domain.delivery import dates
from forge.domain.identity import Actor, not_found
from forge.repositories.test_analytics import TestAnalyticsRepository
from forge.security.identity import now
from forge.services.analytics import AnalyticsService
from forge.services.identity import IdentityService

REPORT_FIELDS = (
    "id",
    "repository_id",
    "repository_name",
    "workflow_run_id",
    "provider_run_id",
    "run_attempt",
    "head_sha",
    "branch",
    "environment",
    "report_key",
    "shard",
    "status",
    "received_at",
    "source_at",
    "superseded_by",
    "case_count",
    "warning_count",
    "completion_source",
)
CASE_FIELDS = (
    "id",
    "test_id",
    "name",
    "class_name",
    "file",
    "status",
    "duration_seconds",
    "failure_message",
    "ordinal",
    "retry_ordinal",
    "is_final",
    "identity_quality",
)


def report_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in REPORT_FIELDS}


def case_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in CASE_FIELDS}


def evidence_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        key: row[key]
        for key in (
            "repository_id",
            "repository_name",
            "name",
            "class_name",
            "file",
            "branch",
            "environment",
            "report_key",
            "shard",
            "sample_count",
            "passed_count",
            "failed_count",
            "flip_count",
            "same_sha_reversal_count",
            "failure_fraction",
            "first_at",
            "last_at",
            "potential_flaky",
            "confidence",
            "policy",
        )
    }
    result["id"] = row["test_id"]
    return result


def bucket(row: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row = row or {}
    result = {
        key: row.get(key, 0)
        for key in (
            "passed_count",
            "failed_count",
            "error_count",
            "skipped_count",
            "eligible_count",
        )
    }
    result["pass_fraction"] = row.get("pass_fraction")
    return result


class TestAnalyticsService(AnalyticsService):
    __test__ = False
    repository: TestAnalyticsRepository

    def __init__(self, identity: IdentityService) -> None:
        super().__init__(identity)
        self.repository = TestAnalyticsRepository(identity.repository.engine)

    @staticmethod
    def parameters(
        organization: UUID, repository: UUID | None = None, **filters: Any
    ) -> dict[str, Any]:
        return {
            "org": organization,
            "repository": repository,
            "selected_only": repository is None,
            "branch": None,
            "environment": None,
            "test_id": None,
            **filters,
        }

    async def test_metrics(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        branch: str | None,
        environment: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> dict[str, Any]:
        as_of = now()
        effective = window(start, end, as_of)
        parameters = self.parameters(
            organization,
            repository,
            branch=branch,
            environment=environment,
            from_time=effective.start,
            to_time=effective.end,
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            rows = await self.repository.metrics(connection, parameters)
            coverage = dict(await self.repository.coverage(connection, parameters))
        total = bucket()
        trend = {date: {"date": date, **bucket()} for date in dates(effective)}
        for row in rows:
            if row["is_total"]:
                total = bucket(row)
            else:
                date = row["day"].isoformat()
                trend[date] = {"date": date, **bucket(row)}
        limitations = ["uploaded_reports_only", "expected_report_inventory_unknown"]
        for name in (
            "missing_report",
            "queued_report",
            "failed_report",
            "warning_report",
            "unknown_link",
        ):
            if coverage[f"{name}_count"]:
                limitations.append(name)
        if environment is not None:
            limitations.append("workflow_environment_not_asserted")
        if coverage["completion_proxy_count"]:
            limitations.append("job_completion_proxy")
        coverage.update(
            status="partial" if coverage["report_count"] else "unavailable",
            limitations=limitations,
        )
        return {
            "formula_version": "test-final-attempts-v1",
            "as_of": as_of,
            "window": effective.summary(),
            "scope": {
                "repository_id": repository,
                "selected_only": repository is None,
                "branch": branch,
                "environment": environment,
            },
            **total,
            "report_count": coverage.pop("report_count"),
            "trend": list(trend.values()),
            "coverage": coverage,
        }

    async def reports(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        branch: str | None,
        environment: str | None,
        start: datetime | None,
        end: datetime | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        codec, boundary, effective = self.paging(
            dict(
                entity="test_runs",
                org=organization,
                repository=repository,
                branch=branch,
                environment=environment,
                start=start,
                end=end,
                status=status,
                limit=limit,
            ),
            cursor,
            start,
            end,
        )
        assert effective
        parameters = self.parameters(
            organization,
            repository,
            branch=branch,
            environment=environment,
            from_time=effective.start,
            to_time=effective.end,
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            rows = await self.repository.reports(
                connection, parameters, status, boundary, limit + 1
            )
        return self.page(rows, limit, codec, report_summary, effective)

    async def report(self, actor: Actor, organization: UUID, identifier: UUID) -> dict[str, Any]:
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization)
            row = await self.repository.report(connection, organization, identifier)
            if row is None:
                raise not_found()
            counts = await self.repository.report_counts(connection, organization, identifier)
        return {
            "test_run": report_summary(row),
            "warnings": row["warnings"],
            "counts": dict(counts),
            "error_code": row["error_code"],
        }

    async def children(
        self,
        actor: Actor,
        organization: UUID,
        identifier: UUID,
        kind: str,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        codec, boundary, _ = self.paging(
            dict(
                org=organization,
                entity="test_run_children",
                id=identifier,
                kind=kind,
                status=status,
                limit=limit,
            ),
            cursor,
            timed=False,
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization)
            if await self.repository.report(connection, organization, identifier) is None:
                raise not_found()
            rows = await self.repository.children(
                connection,
                organization,
                identifier,
                kind,
                status,
                boundary,
                limit + 1,
            )
        summarize = (
            case_summary
            if kind == "cases"
            else lambda row: {
                key: row[key]
                for key in (
                    "id",
                    "name",
                    "path",
                    "ordinal",
                    "case_count",
                    "declared_counts",
                )
            }
        )
        return self.page(rows, limit, codec, summarize)

    async def candidates(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        branch: str | None,
        environment: str | None,
        end: datetime | None,
        potential_only: bool,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        codec, boundary, effective = self.paging(
            dict(
                entity="test_candidates",
                org=organization,
                repository=repository,
                branch=branch,
                environment=environment,
                end=end,
                potential_only=potential_only,
                limit=limit,
            ),
            cursor,
            None,
            end,
        )
        assert effective
        parameters = self.parameters(
            organization,
            repository,
            branch=branch,
            environment=environment,
            to_time=effective.end,
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            rows = await self.repository.candidates(
                connection,
                parameters,
                potential_only,
                boundary,
                limit + 1,
            )
        result = self.page(rows, limit, codec, evidence_summary, effective)
        result["as_of"] = effective.end
        return result

    async def history(
        self,
        actor: Actor,
        organization: UUID,
        identifier: UUID,
        branch: str | None,
        environment: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        codec, boundary, effective = self.paging(
            dict(
                entity="test_history",
                org=organization,
                id=identifier,
                branch=branch,
                environment=environment,
                start=start,
                end=end,
                limit=limit,
            ),
            cursor,
            start,
            end,
        )
        assert effective
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization)
            identity = await self.repository.test(connection, organization, identifier)
            if identity is None:
                raise not_found()
            parameters = self.parameters(
                organization,
                identity["repository_id"],
                test_id=identifier,
                branch=branch,
                environment=environment,
                from_time=effective.start,
                to_time=effective.end,
            )
            rows = await self.repository.history(connection, parameters, boundary, limit + 1)
            evidence = await self.repository.candidates(connection, parameters, False, None, 101)

        def summarize(row: Mapping[str, Any]) -> dict[str, Any]:
            return case_summary(row) | {
                key: row[key]
                for key in (
                    "test_run_id",
                    "workflow_run_id",
                    "provider_run_id",
                    "run_attempt",
                    "head_sha",
                    "branch",
                    "environment",
                    "source_at",
                    "report_key",
                    "shard",
                    "superseded",
                )
            }

        return self.page(rows, limit, codec, summarize, effective) | {
            "test": dict(identity),
            "evidence": [evidence_summary(row) for row in evidence[:100]],
            "evidence_truncated": len(evidence) > 100,
        }
