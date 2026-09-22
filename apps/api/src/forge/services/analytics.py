"""Read-only engineering analytics and their tenant-scoped source evidence."""

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.domain.analytics import (
    FORMULA_VERSION,
    METRICS,
    AnalyticsCursor,
    Metric,
    Window,
    empty_distribution,
    evidence_coverage,
    github_url,
    window,
)
from forge.domain.identity import Actor, DomainError, not_found
from forge.repositories.analytics import AnalyticsRepository
from forge.security.identity import now
from forge.services.identity import IdentityService
from forge.services.organizations import OrganizationService

PR_FIELDS = (
    "id",
    "repository_id",
    "repository_name",
    "number",
    "title",
    "state",
    "draft",
    "author_login",
    "opened_at",
    "updated_at",
    "closed_at",
    "merged_at",
    "head_sha",
    "base_ref",
    "merge_commit_sha",
    "first_review_at",
    "first_approved_at",
    "approval_dismissed",
    "unknown_dismissed_review_count",
)
COMMIT_FIELDS = (
    "id",
    "repository_id",
    "repository_name",
    "sha",
    "message",
    "author_login",
    "authored_at",
    "committed_at",
    "additions",
    "deletions",
    "changed_files",
    "pull_request_count",
)
ISSUE_FIELDS = (
    "id",
    "repository_id",
    "repository_name",
    "number",
    "title",
    "state",
    "author_login",
    "opened_at",
    "updated_at",
    "closed_at",
)


def distribution(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: row[key] for key in empty_distribution()}
    result["exclusions"] = {key: count for key, count in result["exclusions"].items() if count}
    return result


def pr_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {field: row[field] for field in PR_FIELDS}
    result.update(
        html_url=github_url(row["html_url"]),
        durations={metric: row[metric] for metric in METRICS},
        exclusions={metric: row[f"{metric}_exclusion"] for metric in METRICS},
        coverage={
            kind: evidence_coverage(row, kind)
            for kind in ("reviews", "transitions", "commits", "issues")
        },
    )
    if "relationship" in row:
        result["relationship"] = row["relationship"]
    return result


def commit_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {field: row[field] for field in COMMIT_FIELDS}
    result.update(
        html_url=github_url(row["html_url"]), files_coverage=evidence_coverage(row, "files")
    )
    if "relationship" in row:
        result["relationship"] = row["relationship"]
    return result


def issue_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {field: row[field] for field in ISSUE_FIELDS}
    result["html_url"] = github_url(row["html_url"])
    result["links_coverage"] = evidence_coverage(row, "links")
    if "relationship" in row:
        result["relationship"] = row["relationship"]
    return result


class AnalyticsService:
    def __init__(self, identity: IdentityService) -> None:
        self.identity = identity
        self.organizations = OrganizationService(identity)
        self.repository = AnalyticsRepository(identity.repository.engine)

    async def context(
        self,
        connection: AsyncConnection,
        actor: Actor,
        organization: UUID,
        repository: UUID | None = None,
    ) -> Mapping[str, Any] | None:
        await self.organizations.context(connection, actor, organization)
        if repository is None:
            return None
        source = await self.repository.source(connection, organization, repository)
        if source is None:
            raise not_found()
        return source

    def paging(
        self,
        scope: Mapping[str, Any],
        cursor: str | None,
        start: datetime | None = None,
        end: datetime | None = None,
        *,
        timed: bool = True,
    ) -> tuple[AnalyticsCursor, dict[str, Any] | None, Window | None]:
        codec = AnalyticsCursor(self.identity.tokens, scope)
        boundary = codec.decode(cursor)
        effective = (boundary["window"] if boundary else None) or (
            window(start, end, now()) if timed else None
        )
        if timed and boundary and (boundary["at"] is None or boundary["window"] is None):
            raise DomainError(422, "invalid_cursor", "The pagination cursor is invalid.")
        return codec, boundary, effective

    @staticmethod
    def page(
        rows: Sequence[Mapping[str, Any]],
        limit: int,
        codec: AnalyticsCursor,
        summarize: Callable[[Mapping[str, Any]], dict[str, Any]],
        effective: Window | None = None,
        sort_field: str | None = None,
    ) -> dict[str, Any]:
        cursor = None
        if len(rows) > limit:
            boundary = dict(rows[limit - 1])
            if sort_field:
                boundary["sort_at"] = boundary[sort_field]
            cursor = codec.encode(boundary, effective)
        result: dict[str, Any] = {
            "items": [summarize(row) for row in rows[:limit]],
            "next_cursor": cursor,
        }
        if effective:
            result["window"] = effective.summary()
        return result

    async def metrics(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        author: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> dict[str, Any]:
        as_of = now()
        effective = window(start, end, as_of)
        parameters = self.repository.parameters(
            organization, repository, author, selected_only=repository is None, effective=effective
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            aggregates = await self.repository.distributions(connection, parameters)
            reviews = await self.repository.review_coverage(connection, parameters)
            sources = await self.repository.repository_coverage(connection, parameters)
            ages, oldest = await self.repository.open_queue(connection, parameters, as_of)
        values = {metric: empty_distribution() for metric in METRICS}
        by_day: dict[str, dict[str, Any]] = {}
        day = effective.start.date()
        last_day = (effective.end - timedelta(microseconds=1)).date()
        while day <= last_day:
            by_day[day.isoformat()] = {
                "date": day.isoformat(),
                "merged_count": 0,
                "metrics": {metric: empty_distribution() for metric in METRICS},
            }
            if day == last_day:
                break
            day += timedelta(days=1)
        for row in aggregates:
            value = distribution(row)
            if row["is_total"]:
                values[row["metric"]] = value
            else:
                bucket = by_day[row["day"].isoformat()]
                bucket["metrics"][row["metric"]] = value
                bucket["merged_count"] = value["sample_count"] + value["excluded_count"]
        limitations = []
        if not sources["repository_count"]:
            limitations.append("no_selected_repositories")
        if sources["repositories_synced"] < sources["repository_count"]:
            limitations.append("repositories_not_synced")
        if sources["history_window_partial"]:
            limitations.append("history_window_partial")
        if sources["sources_unavailable"]:
            limitations.append("source_access_unavailable")
        if reviews["reviews_incomplete"]:
            limitations.append("incomplete_reviews")
        if reviews["unknown_dismissed_review_count"]:
            limitations.append("unknown_dismissed_review")
        if reviews["unknown_reviewer_count"]:
            limitations.append("unknown_reviewer")
        status = "partial" if limitations else "complete"
        if not sources["repository_count"] or not sources["repositories_synced"]:
            status = "unavailable"
        cycle = values["cycle_time"]
        return {
            "formula_version": FORMULA_VERSION,
            "as_of": as_of,
            "window": effective.summary(),
            "scope": {
                "repository_id": repository,
                "selected_only": repository is None,
                "repository_count": sources["repository_count"],
            },
            "merged_count": cycle["sample_count"] + cycle["excluded_count"],
            "metrics": values,
            "trend": list(by_day.values()),
            "open_queue": {
                "count": ages["sample_count"] + ages["excluded_count"],
                "age": distribution(ages),
                "oldest": [pr_summary(row) for row in oldest],
            },
            "coverage": {
                "status": status,
                "input_watermark": sources["input_watermark"],
                "repository_count": sources["repository_count"],
                "repositories_synced": sources["repositories_synced"],
                **reviews,
                "limitations": limitations,
            },
        }

    async def pull_requests(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        author: str | None,
        start: datetime | None,
        end: datetime | None,
        state: str,
        cohort: str,
        metric: Metric | None,
        eligibility: str | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        if metric:
            cohort = "merged"
        elif eligibility not in {None, "all"}:
            raise DomainError(422, "invalid_filter", "Choose a metric to filter its eligibility.")
        eligibility = eligibility or ("eligible" if metric else "all")
        scope = {
            "route": "pull-requests",
            "org": organization,
            "repository": repository,
            "author": author.casefold() if author else None,
            "from": start,
            "to": end,
            "state": state,
            "cohort": cohort,
            "metric": metric,
            "eligibility": eligibility,
            "limit": limit,
        }
        codec, boundary, effective = self.paging(scope, cursor, start, end)
        assert effective is not None
        parameters = self.repository.parameters(
            organization, repository, author, selected_only=repository is None, effective=effective
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            rows = await self.repository.pull_requests(
                connection, parameters, state, cohort, metric, eligibility, boundary, limit + 1
            )
        return self.page(rows, limit, codec, pr_summary, effective)

    async def pull_request(
        self, actor: Actor, organization: UUID, identifier: UUID
    ) -> dict[str, Any]:
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization)
            row = await self.repository.pull_request(connection, organization, identifier)
            if row is None:
                raise not_found()
            counts = await self.repository.counts(connection, organization, identifier)
        return {"pull_request": pr_summary(row), "counts": counts}

    async def commits(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID | None,
        author: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        scope = {
            "route": "commits",
            "org": organization,
            "repository": repository,
            "author": author.casefold() if author else None,
            "from": start,
            "to": end,
            "limit": limit,
        }
        codec, boundary, effective = self.paging(scope, cursor, start, end)
        assert effective is not None
        parameters = self.repository.parameters(
            organization, repository, author, selected_only=repository is None, effective=effective
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization, repository)
            rows = await self.repository.commits(connection, parameters, boundary, limit + 1)
        return self.page(rows, limit, codec, commit_summary, effective, "committed_at")

    async def commit(self, actor: Actor, organization: UUID, identifier: UUID) -> dict[str, Any]:
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization)
            row = await self.repository.commit(connection, organization, identifier)
            if row is None:
                raise not_found()
        return {"commit": commit_summary(row)}

    async def issues(
        self,
        actor: Actor,
        organization: UUID,
        repository: UUID,
        author: str | None,
        start: datetime | None,
        end: datetime | None,
        state: str,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        scope = {
            "route": "issues",
            "org": organization,
            "repository": repository,
            "author": author.casefold() if author else None,
            "from": start,
            "to": end,
            "state": state,
            "limit": limit,
        }
        codec, boundary, effective = self.paging(scope, cursor, start, end)
        assert effective is not None
        parameters = self.repository.parameters(
            organization, repository, author, selected_only=False, effective=effective
        )
        async with self.repository.snapshot(actor.user_id) as connection:
            source = await self.context(connection, actor, organization, repository)
            assert source is not None
            rows = await self.repository.issues(connection, parameters, state, boundary, limit + 1)
        return self.page(rows, limit, codec, issue_summary, effective, "updated_at") | {
            "coverage": evidence_coverage(source, "issues")
        }

    async def issue(self, actor: Actor, organization: UUID, identifier: UUID) -> dict[str, Any]:
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization)
            row = await self.repository.issue(connection, organization, identifier)
            if row is None:
                raise not_found()
        return {"issue": issue_summary(row)}

    async def evidence(
        self,
        actor: Actor,
        organization: UUID,
        parent: str,
        identifier: UUID,
        kind: str,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        scope = {
            "route": parent,
            "org": organization,
            "parent": identifier,
            "kind": kind,
            "limit": limit,
        }
        codec, boundary, _ = self.paging(scope, cursor, timed=False)
        async with self.repository.snapshot(actor.user_id) as connection:
            await self.context(connection, actor, organization)
            fetch = {
                "pull_request": self.repository.pull_request,
                "commit": self.repository.commit,
                "issue": self.repository.issue,
            }[parent]
            subject = await fetch(connection, organization, identifier)
            if subject is None:
                raise not_found()
            rows = await self.repository.evidence(
                connection,
                organization,
                subject["repository_id"],
                parent,
                identifier,
                kind,
                boundary,
                limit + 1,
            )
        summarize: Callable[[Mapping[str, Any]], dict[str, Any]]
        if kind == "commits":
            summarize = commit_summary
        elif kind == "pull-requests":
            summarize = pr_summary
        elif kind == "issues":
            summarize = issue_summary
        else:

            def summarize_child(row: Mapping[str, Any]) -> dict[str, Any]:
                return self.child_summary(row, kind, subject)

            summarize = summarize_child
        return self.page(rows, limit, codec, summarize)

    @staticmethod
    def child_summary(
        row: Mapping[str, Any], kind: str, subject: Mapping[str, Any]
    ) -> dict[str, Any]:
        if kind == "reviews":
            fields = (
                "id",
                "provider_id",
                "reviewer_login",
                "reviewer_type",
                "state",
                "submitted_at",
                "approved_at",
                "dismissed_at",
            )
            result = {field: row[field] for field in fields}
            known = row["original_state"] or row["state"]
            human = (
                row["reviewer_type"] == "User"
                and bool(row["reviewer_login"])
                and not str(row["reviewer_login"]).casefold().endswith("[bot]")
            )
            other = (
                subject["author_login"] is not None
                and str(row["reviewer_login"]).casefold() != str(subject["author_login"]).casefold()
            )
            result.update(
                html_url=github_url(row["html_url"]),
                qualifies=bool(
                    human
                    and other
                    and (row["submitted_at"] or row["approved_at"])
                    and (
                        known in {"COMMENTED", "APPROVED", "CHANGES_REQUESTED"}
                        or row["approved_at"] is not None
                    )
                ),
                approval_known=bool(known == "APPROVED" or row["approved_at"] is not None),
            )
            return result
        if kind == "transitions":
            return {
                field: row[field]
                for field in ("id", "provider_id", "kind", "occurred_at", "actor_login")
            } | {"html_url": github_url(row["html_url"])}
        if kind == "files":
            result = {
                field: row[field]
                for field in (
                    "id",
                    "filename",
                    "previous_filename",
                    "status",
                    "additions",
                    "deletions",
                    "changes",
                )
            }
            result["blob_url"] = (
                f"https://github.com/{subject['repository_name']}/blob/"
                f"{subject['sha']}/{quote(row['filename'], safe='/')}"
                if github_url(subject["html_url"]) and row["status"] != "removed"
                else None
            )
            return result
        raise ValueError("Unknown evidence kind")
