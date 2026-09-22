"""Tenant-bound analytics at PR grain; evidence and aggregates share eligibility SQL."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.domain.analytics import METRICS, Metric, Window
from forge.repositories.identity import IdentityRepository

# Every dynamic fragment below is authored here or chosen from a fixed internal map.
# Reviews are reduced to one row per PR before any aggregate or relationship joins.
HUMAN_REVIEW = """v.reviewer_type='User' AND v.reviewer_login IS NOT NULL
    AND p.author_login IS NOT NULL AND lower(v.reviewer_login)<>lower(p.author_login)
    AND lower(v.reviewer_login) NOT LIKE '%[bot]'"""
SUBSTANTIVE = """(coalesce(v.original_state,v.state) IN
    ('COMMENTED','APPROVED','CHANGES_REQUESTED') OR v.approved_at IS NOT NULL)"""
APPROVAL = """(coalesce(v.original_state,v.state)='APPROVED' OR v.approved_at IS NOT NULL)"""
UNKNOWN_DISMISSED = """v.state='DISMISSED' AND v.original_state IS NULL
    AND v.approved_at IS NULL"""
UNKNOWN_REVIEWER = """(v.reviewer_type IS DISTINCT FROM 'User' OR v.reviewer_login IS NULL)
    AND coalesce(v.reviewer_type,'')<>'Bot'
    AND (v.reviewer_login IS NULL OR lower(v.reviewer_login) NOT LIKE '%[bot]')
    AND (v.reviewer_login IS NULL OR p.author_login IS NULL
      OR lower(v.reviewer_login)<>lower(p.author_login))"""

PR_CTE = f"""
WITH scoped_repositories AS (
    SELECT * FROM forge.repositories r WHERE r.organization_id=:org
    AND (CAST(:repository AS uuid) IS NULL OR r.id=CAST(:repository AS uuid))
    AND (NOT :selected_only OR r.selected)
), base AS (
    SELECT p.*,r.full_name AS repository_name,review.*
    FROM forge.pull_requests p JOIN scoped_repositories r
      ON r.organization_id=p.organization_id AND r.id=p.repository_id
    LEFT JOIN LATERAL (
        SELECT min(coalesce(v.submitted_at,v.approved_at)) FILTER
          (WHERE {HUMAN_REVIEW} AND {SUBSTANTIVE}) AS first_review_at,
        min(coalesce(v.approved_at,v.submitted_at)) FILTER
          (WHERE {HUMAN_REVIEW} AND {APPROVAL}) AS first_approved_at,
        min(coalesce(v.approved_at,v.submitted_at)) FILTER
          (WHERE {HUMAN_REVIEW} AND {APPROVAL} AND v.state='DISMISSED')
          AS first_dismissed_approval_at,
        min(v.submitted_at) FILTER (WHERE {HUMAN_REVIEW} AND {UNKNOWN_DISMISSED})
          AS unknown_dismissed_at,
        count(*) FILTER (WHERE {HUMAN_REVIEW} AND {UNKNOWN_DISMISSED})
          AS unknown_dismissed_review_count,
        count(*) FILTER (WHERE {HUMAN_REVIEW} AND {UNKNOWN_DISMISSED}
          AND v.submitted_at IS NULL) AS undated_dismissed_count,
        count(*) FILTER (WHERE {HUMAN_REVIEW} AND {SUBSTANTIVE}
          AND coalesce(v.submitted_at,v.approved_at) IS NULL) AS undated_review_count,
        count(*) FILTER (WHERE {HUMAN_REVIEW} AND {APPROVAL}
          AND coalesce(v.approved_at,v.submitted_at) IS NULL) AS undated_approval_count,
        min(coalesce(v.submitted_at,v.approved_at)) FILTER
          (WHERE {UNKNOWN_REVIEWER} AND ({SUBSTANTIVE} OR {UNKNOWN_DISMISSED}))
          AS unknown_review_at,
        min(coalesce(v.approved_at,v.submitted_at)) FILTER
          (WHERE {UNKNOWN_REVIEWER} AND ({APPROVAL} OR {UNKNOWN_DISMISSED}))
          AS unknown_approval_at,
        count(*) FILTER (WHERE {UNKNOWN_REVIEWER} AND ({SUBSTANTIVE} OR {UNKNOWN_DISMISSED})
          AND coalesce(v.submitted_at,v.approved_at) IS NULL) AS undated_unknown_review_count,
        count(*) FILTER (WHERE {UNKNOWN_REVIEWER} AND ({APPROVAL} OR {UNKNOWN_DISMISSED})
          AND coalesce(v.approved_at,v.submitted_at) IS NULL) AS undated_unknown_approval_count
        FROM forge.pull_request_reviews v
        WHERE v.organization_id=p.organization_id AND v.repository_id=p.repository_id
          AND v.pull_request_id=p.id
    ) review ON true
    WHERE p.organization_id=:org
      AND (CAST(:identifier AS uuid) IS NULL OR p.id=CAST(:identifier AS uuid))
      AND (CAST(:author AS text) IS NULL OR lower(p.author_login)=lower(CAST(:author AS text)))
), validity AS (
    SELECT *,CASE WHEN merged_at IS NULL THEN 'unmerged'
        WHEN opened_at IS NULL OR merged_at<opened_at THEN 'invalid_timestamps'
        ELSE NULL END AS cycle_time_exclusion,
      coalesce(first_approved_at=first_dismissed_approval_at,false) AS approval_dismissed
    FROM base
), exclusions AS (
    SELECT *,CASE
        WHEN cycle_time_exclusion IS NOT NULL THEN cycle_time_exclusion
        WHEN reviews_status<>'complete' THEN 'incomplete_reviews'
        WHEN author_login IS NULL THEN 'missing_author'
        WHEN undated_review_count>0 THEN 'invalid_timestamps'
        WHEN undated_unknown_review_count>0 OR (unknown_review_at IS NOT NULL AND
          (first_review_at IS NULL OR unknown_review_at<=first_review_at)) THEN 'unknown_reviewer'
        WHEN undated_dismissed_count>0 OR (unknown_dismissed_at IS NOT NULL AND
          (first_review_at IS NULL OR unknown_dismissed_at<=first_review_at))
          THEN 'unknown_dismissed_review'
        WHEN first_review_at IS NULL THEN 'missing_review'
        WHEN first_review_at<opened_at OR first_review_at>merged_at THEN 'invalid_timestamps'
        ELSE NULL END AS review_wait_exclusion,
      CASE
        WHEN cycle_time_exclusion IS NOT NULL THEN cycle_time_exclusion
        WHEN reviews_status<>'complete' THEN 'incomplete_reviews'
        WHEN author_login IS NULL THEN 'missing_author'
        WHEN undated_approval_count>0 THEN 'invalid_timestamps'
        WHEN undated_unknown_approval_count>0 OR (unknown_approval_at IS NOT NULL AND
          (first_approved_at IS NULL OR unknown_approval_at<=first_approved_at))
          THEN 'unknown_reviewer'
        WHEN undated_dismissed_count>0 OR (unknown_dismissed_at IS NOT NULL AND
          (first_approved_at IS NULL OR unknown_dismissed_at<=first_approved_at))
          THEN 'unknown_dismissed_review'
        WHEN first_approved_at IS NULL THEN 'missing_approval'
        WHEN first_approved_at<opened_at OR first_approved_at>merged_at THEN 'invalid_timestamps'
        ELSE NULL END AS approval_to_merge_exclusion
    FROM validity
), facts AS (
    SELECT *,CASE WHEN cycle_time_exclusion IS NULL
      THEN extract(epoch FROM merged_at-opened_at)::double precision END AS cycle_time,
    CASE WHEN review_wait_exclusion IS NULL
      THEN extract(epoch FROM first_review_at-opened_at)::double precision END AS review_wait,
    CASE WHEN approval_to_merge_exclusion IS NULL
      THEN extract(epoch FROM merged_at-first_approved_at)::double precision
      END AS approval_to_merge
    FROM exclusions
)
"""

REASONS = (
    "unmerged",
    "invalid_timestamps",
    "incomplete_reviews",
    "missing_author",
    "unknown_dismissed_review",
    "missing_review",
    "missing_approval",
    "unknown_reviewer",
)
EXCLUSION_COUNTS = (
    "jsonb_build_object("
    + ",".join(f"'{reason}',count(*) FILTER (WHERE reason='{reason}')" for reason in REASONS)
    + ")"
)
DISTRIBUTION = f"""count(seconds) AS sample_count,
    count(*)-count(seconds) AS excluded_count,avg(seconds) AS mean_seconds,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds) AS median_seconds,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY seconds) AS p75_seconds,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY seconds) AS p95_seconds,
    {EXCLUSION_COUNTS} AS exclusions"""

COMMIT_SELECT = """SELECT c.*,r.full_name AS repository_name,
    CASE WHEN c.files_status='complete' THEN (SELECT count(*) FROM forge.commit_files f
      WHERE f.organization_id=c.organization_id AND f.repository_id=c.repository_id
        AND f.commit_id=c.id) END AS changed_files,
    (SELECT count(DISTINCT l.pull_request_id) FROM forge.pull_request_commits l
      WHERE l.organization_id=c.organization_id AND l.repository_id=c.repository_id
        AND l.commit_id=c.id) AS pull_request_count
    FROM forge.commits c JOIN forge.repositories r
      ON r.organization_id=c.organization_id AND r.id=c.repository_id
    WHERE c.organization_id=:org"""


class AnalyticsRepository(IdentityRepository):
    @asynccontextmanager
    async def snapshot(self, user: UUID) -> AsyncIterator[AsyncConnection]:
        async with self.engine.begin() as connection:
            await self.execute(
                connection, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            await self.execute(connection, "SELECT set_config('forge.organization_id','',true)")
            await self.execute(
                connection, "SELECT set_config('forge.user_id',:user,true)", user=str(user)
            )
            yield connection

    @staticmethod
    def parameters(
        organization: UUID,
        repository: UUID | None = None,
        author: str | None = None,
        identifier: UUID | None = None,
        *,
        selected_only: bool = True,
        effective: Window | None = None,
    ) -> dict[str, Any]:
        return {
            "org": organization,
            "repository": repository,
            "author": author,
            "identifier": identifier,
            "selected_only": selected_only,
            "from_time": effective.start if effective else None,
            "to_time": effective.end if effective else None,
        }

    async def source(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            "SELECT * FROM forge.repositories WHERE organization_id=:org AND id=:id",
            org=organization,
            id=identifier,
        )

    async def pull_request(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            PR_CTE + "SELECT * FROM facts",
            **self.parameters(organization, identifier=identifier, selected_only=False),
        )

    async def pull_requests(
        self,
        connection: AsyncConnection,
        parameters: dict[str, Any],
        state: str,
        cohort: str,
        metric: Metric | None,
        eligibility: str,
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        column = "merged_at" if cohort == "merged" else "updated_at"
        predicate = ""
        if metric is not None:
            assert metric in METRICS
            if eligibility == "eligible":
                predicate = f"AND {metric}_exclusion IS NULL"
            elif eligibility == "excluded":
                predicate = f"AND {metric}_exclusion IS NOT NULL"
        return await self.many(
            connection,
            PR_CTE
            + f"""
            SELECT *,{column} AS sort_at FROM facts
            WHERE {column}>=:from_time AND {column}<:to_time
            AND (:state='all' OR (:state='merged' AND merged_at IS NOT NULL) OR state=:state)
            {predicate}
            AND (CAST(:boundary AS uuid) IS NULL OR
              ({column},id)<(CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
            ORDER BY {column} DESC,id DESC LIMIT :limit""",
            **parameters,
            state=state,
            boundary=boundary["id"] if boundary else None,
            boundary_at=boundary["at"] if boundary else None,
            limit=limit,
        )

    async def distributions(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            PR_CTE
            + f""", metric_facts AS (
            SELECT (merged_at AT TIME ZONE 'UTC')::date AS day,metric,seconds,reason
            FROM facts CROSS JOIN LATERAL (VALUES
              ('cycle_time',cycle_time,cycle_time_exclusion),
              ('review_wait',review_wait,review_wait_exclusion),
              ('approval_to_merge',approval_to_merge,approval_to_merge_exclusion)
            ) measures(metric,seconds,reason)
            WHERE merged_at>=:from_time AND merged_at<:to_time
        ) SELECT metric,day,grouping(day) AS is_total,{DISTRIBUTION}
          FROM metric_facts GROUP BY GROUPING SETS ((metric),(metric,day))
          ORDER BY day,metric""",
            **parameters,
        )

    async def review_coverage(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> Mapping[str, Any]:
        row = await self.one(
            connection,
            PR_CTE
            + """SELECT
            count(*) FILTER (WHERE reviews_status='complete') AS reviews_complete,
            count(*) FILTER (WHERE reviews_status<>'complete') AS reviews_incomplete,
            count(*) FILTER (WHERE approval_dismissed) AS dismissed_approval_count,
            coalesce(sum(unknown_dismissed_review_count),0)::bigint
              AS unknown_dismissed_review_count,
            count(*) FILTER (WHERE review_wait_exclusion='unknown_reviewer'
              OR approval_to_merge_exclusion='unknown_reviewer') AS unknown_reviewer_count
            FROM facts WHERE merged_at>=:from_time AND merged_at<:to_time""",
            **parameters,
        )
        assert row is not None
        return row

    async def repository_coverage(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> Mapping[str, Any]:
        row = await self.one(
            connection,
            """SELECT count(*) AS repository_count,
            count(*) FILTER (WHERE r.last_synced_at IS NOT NULL) AS repositories_synced,
            min(r.last_synced_at) AS input_watermark,
            count(*) FILTER (WHERE (NOT r.authorized OR i.status<>'active')
              AND NOT r.is_demo) AS sources_unavailable,
            count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM forge.sync_runs s
              WHERE s.organization_id=r.organization_id AND s.repository_id=r.id
              AND s.status='succeeded' AND s.since<=:from_time AND s.until>=:to_time))
              AS history_window_partial
            FROM forge.repositories r JOIN forge.integrations i
              ON i.organization_id=r.organization_id AND i.id=r.integration_id
            WHERE r.organization_id=:org
            AND (CAST(:repository AS uuid) IS NULL OR r.id=CAST(:repository AS uuid))
            AND (NOT :selected_only OR r.selected)""",
            **parameters,
        )
        assert row is not None
        return row

    async def open_queue(
        self, connection: AsyncConnection, parameters: dict[str, Any], as_of: datetime
    ) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
        summary = await self.one(
            connection,
            PR_CTE
            + f""", ages AS (
            SELECT CASE WHEN opened_at<=:as_of THEN
              extract(epoch FROM CAST(:as_of AS timestamptz)-opened_at)::double precision
              END AS seconds,
            CASE WHEN opened_at IS NULL OR opened_at>:as_of THEN 'invalid_timestamps' END AS reason
            FROM facts WHERE state='open' AND merged_at IS NULL
        ) SELECT {DISTRIBUTION} FROM ages""",
            **parameters,
            as_of=as_of,
        )
        assert summary is not None
        oldest = await self.many(
            connection,
            PR_CTE
            + """SELECT * FROM facts
            WHERE state='open' AND merged_at IS NULL AND opened_at<=:as_of
            ORDER BY opened_at,id LIMIT 5""",
            **parameters,
            as_of=as_of,
        )
        return summary, oldest

    async def commit(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection, COMMIT_SELECT + " AND c.id=:id", org=organization, id=identifier
        )

    async def commits(
        self,
        connection: AsyncConnection,
        parameters: dict[str, Any],
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            COMMIT_SELECT
            + """
            AND (CAST(:repository AS uuid) IS NULL OR c.repository_id=CAST(:repository AS uuid))
            AND (NOT :selected_only OR r.selected)
            AND (CAST(:author AS text) IS NULL
              OR lower(c.author_login)=lower(CAST(:author AS text)))
            AND c.committed_at>=:from_time AND c.committed_at<:to_time
            AND (CAST(:boundary AS uuid) IS NULL OR (c.committed_at,c.id)<
              (CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
            ORDER BY c.committed_at DESC,c.id DESC LIMIT :limit""",
            **parameters,
            boundary=boundary["id"] if boundary else None,
            boundary_at=boundary["at"] if boundary else None,
            limit=limit,
        )

    async def issue(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT i.*,r.full_name AS repository_name
            FROM forge.issues i JOIN forge.repositories r
              ON r.organization_id=i.organization_id AND r.id=i.repository_id
            WHERE i.organization_id=:org AND i.id=:id""",
            org=organization,
            id=identifier,
        )

    async def issues(
        self,
        connection: AsyncConnection,
        parameters: dict[str, Any],
        state: str,
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            """SELECT i.*,r.full_name AS repository_name
            FROM forge.issues i JOIN forge.repositories r
              ON r.organization_id=i.organization_id AND r.id=i.repository_id
            WHERE i.organization_id=:org AND i.repository_id=:repository
            AND (CAST(:author AS text) IS NULL
              OR lower(i.author_login)=lower(CAST(:author AS text)))
            AND (:state='all' OR i.state=:state)
            AND i.updated_at>=:from_time AND i.updated_at<:to_time
            AND (CAST(:boundary AS uuid) IS NULL OR (i.updated_at,i.id)<
              (CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
            ORDER BY i.updated_at DESC,i.id DESC LIMIT :limit""",
            **parameters,
            state=state,
            boundary=boundary["id"] if boundary else None,
            boundary_at=boundary["at"] if boundary else None,
            limit=limit,
        )

    async def counts(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID
    ) -> dict[str, int]:
        result: dict[str, int] = {}
        for name, table, distinct in (
            ("reviews", "pull_request_reviews", "id"),
            ("transitions", "pull_request_transitions", "id"),
            ("commits", "pull_request_commits", "commit_id"),
            ("issues", "issue_pull_requests", "issue_id"),
        ):
            row = await self.one(
                connection,
                f"SELECT count(DISTINCT {distinct}) AS count FROM forge.{table} "
                "WHERE organization_id=:org AND pull_request_id=:id",
                org=organization,
                id=identifier,
            )
            assert row is not None
            result[name] = row["count"]
        return result

    async def evidence(
        self,
        connection: AsyncConnection,
        organization: UUID,
        repository: UUID,
        parent: str,
        identifier: UUID,
        kind: str,
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        parameters = self.parameters(organization, repository, selected_only=False)
        parameters.update(
            parent=identifier,
            boundary=boundary["id"] if boundary else None,
            boundary_at=boundary["at"] if boundary else None,
            limit=limit,
        )
        after = " AND (CAST(:boundary AS uuid) IS NULL OR id>CAST(:boundary AS uuid)) "
        if parent == "pull_request" and kind in {"reviews", "transitions"}:
            table = "pull_request_reviews" if kind == "reviews" else "pull_request_transitions"
            stamp = "coalesce(submitted_at,observed_at)" if kind == "reviews" else "occurred_at"
            return await self.many(
                connection,
                f"SELECT *,{stamp} AS sort_at FROM forge.{table} WHERE organization_id=:org "
                "AND repository_id=:repository AND pull_request_id=:parent"
                + f" AND (CAST(:boundary AS uuid) IS NULL OR ({stamp},id)>"
                "(CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid))) "
                + f"ORDER BY {stamp},id LIMIT :limit",
                **parameters,
            )
        if parent == "commit" and kind == "files":
            return await self.many(
                connection,
                "SELECT * FROM forge.commit_files WHERE organization_id=:org "
                "AND repository_id=:repository AND commit_id=:parent"
                + after
                + "ORDER BY id LIMIT :limit",
                **parameters,
            )
        if parent == "pull_request" and kind == "commits":
            return await self.many(
                connection,
                "WITH linked AS ("
                + COMMIT_SELECT
                + """
                AND c.repository_id=:repository AND EXISTS (
                  SELECT 1 FROM forge.pull_request_commits l WHERE l.organization_id=:org
                  AND l.repository_id=:repository AND l.pull_request_id=:parent
                  AND l.commit_id=c.id)
                ) SELECT *, (SELECT CASE WHEN count(DISTINCT relationship)>1
                    THEN 'member_and_merge' WHEN min(relationship)='head' THEN 'member'
                    ELSE 'merge' END FROM forge.pull_request_commits l WHERE l.organization_id=:org
                    AND l.repository_id=:repository AND l.pull_request_id=:parent
                    AND l.commit_id=linked.id) AS relationship FROM linked WHERE true
                """
                + after
                + "ORDER BY id LIMIT :limit",
                **parameters,
            )
        if parent == "pull_request" and kind == "issues":
            return await self.many(
                connection,
                """SELECT i.*,r.full_name AS repository_name,
                'references' AS relationship FROM forge.issues i JOIN forge.repositories r
                  ON r.organization_id=i.organization_id AND r.id=i.repository_id
                WHERE i.organization_id=:org AND i.repository_id=:repository
                AND EXISTS (SELECT 1 FROM forge.issue_pull_requests l WHERE l.organization_id=:org
                  AND l.repository_id=:repository AND l.pull_request_id=:parent AND l.issue_id=i.id)
                AND (CAST(:boundary AS uuid) IS NULL OR i.id>CAST(:boundary AS uuid))
                ORDER BY i.id LIMIT :limit""",
                **parameters,
            )
        if kind == "pull-requests" and parent in {"commit", "issue"}:
            if parent == "commit":
                association = """SELECT l.pull_request_id,CASE WHEN count(DISTINCT relationship)>1
                    THEN 'member_and_merge' WHEN min(relationship)='head' THEN 'member'
                    ELSE 'merge' END AS relationship FROM forge.pull_request_commits l
                    WHERE l.organization_id=:org AND l.repository_id=:repository
                      AND l.commit_id=:parent GROUP BY l.pull_request_id"""
            else:
                association = """SELECT DISTINCT l.pull_request_id,'references' AS relationship
                    FROM forge.issue_pull_requests l WHERE l.organization_id=:org
                    AND l.repository_id=:repository AND l.issue_id=:parent"""
            return await self.many(
                connection,
                PR_CTE
                + f""", associations AS ({association})
                SELECT facts.*,a.relationship FROM facts JOIN associations a
                  ON a.pull_request_id=facts.id WHERE true"""
                + after
                + "ORDER BY id LIMIT :limit",
                **parameters,
            )
        raise ValueError("Unknown evidence route")
