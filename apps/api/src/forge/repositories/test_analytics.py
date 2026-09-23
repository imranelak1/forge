"""SQL-derived test cohorts and contextual flakiness evidence at execution grain."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.repositories.analytics import AnalyticsRepository

SCOPED = """WITH scoped_repositories AS (
    SELECT * FROM forge.repositories WHERE organization_id=:org
      AND (CAST(:repository AS uuid) IS NULL OR id=CAST(:repository AS uuid))
      AND (NOT :selected_only OR selected)
), workflows AS (
    SELECT w.*,max(run_attempt) FILTER (WHERE status='completed') OVER
      (PARTITION BY w.organization_id,w.repository_id,w.provider_run_id) AS latest_completed_attempt
    FROM forge.workflow_runs w JOIN scoped_repositories r
      ON r.organization_id=w.organization_id AND r.id=w.repository_id
    WHERE w.organization_id=:org
), reports AS (
    SELECT t.organization_id,t.id,t.repository_id,t.workflow_run_id,t.report_key,t.shard,
      t.framework,t.environment,t.branch,t.status,t.error_code,t.warnings,t.case_count,
      t.received_at,t.processed_at,t.superseded_by_id,
      r.full_name AS repository_name,w.provider_run_id,w.run_attempt,
      w.head_sha,w.status AS workflow_status,w.latest_completed_attempt,w.completion_source,
      w.completed_at AS source_at,coalesce(w.completed_at,t.received_at) AS sort_at,
      t.superseded_by_id AS superseded_by,jsonb_array_length(t.warnings) AS warning_count
    FROM forge.test_reports t JOIN scoped_repositories r
      ON r.organization_id=t.organization_id AND r.id=t.repository_id
    JOIN workflows w ON w.organization_id=t.organization_id
      AND w.repository_id=t.repository_id AND w.id=t.workflow_run_id
    WHERE t.organization_id=:org
      AND (CAST(:branch AS text) IS NULL OR t.branch=CAST(:branch AS text))
      AND (CAST(:environment AS text) IS NULL OR t.environment=CAST(:environment AS text))
)
"""
METRIC_REPORTS = (
    SCOPED
    + """, metric_reports AS (
    SELECT * FROM reports WHERE status='completed' AND superseded_by_id IS NULL
      AND workflow_status='completed' AND run_attempt=latest_completed_attempt
      AND source_at>=:from_time AND source_at<:to_time
)
"""
)
CASE_COLUMNS = """e.id,e.test_identity_id AS test_id,coalesce(i.classname,'') AS class_name,
    i.name,coalesce(i.file,'') AS file,i.identity_quality,e.outcome AS status,
    e.duration_seconds,e.failure_message,e.ordinal,e.retry_ordinal,e.is_final"""
CASE_JOINS = """JOIN forge.test_identities i ON i.organization_id=e.organization_id
    AND i.repository_id=e.repository_id AND i.id=e.test_identity_id"""

# report_key/shard remain part of the context: different jobs/shards are not invented retries.
# Duplicate-name ambiguity is recorded in the identity, not collapsed here.
FLAKY = (
    SCOPED
    + """, policy AS (
    SELECT r.id AS repository_id,coalesce(p.version,1) AS version,
      coalesce(p.window_days,14) AS lookback_days,coalesce(p.min_executions,10) AS min_executions,
      coalesce(p.failure_rate_low,0.05) AS failure_rate_min,
      coalesce(p.failure_rate_high,0.95) AS failure_rate_max,
      coalesce(p.min_transitions,2) AS min_flips,
      coalesce(p.excluded_branches,'[]'::jsonb) AS excluded_branches
    FROM scoped_repositories r LEFT JOIN forge.test_policies p
      ON p.organization_id=r.organization_id AND p.repository_id=r.id
), observations AS (
    SELECT e.test_identity_id AS test_id,t.repository_id,t.repository_name,
      i.name,coalesce(i.classname,'') AS class_name,coalesce(i.file,'') AS file,
      i.identity_quality,t.branch,t.environment,t.report_key,t.shard,t.head_sha,
      t.source_at,t.id AS report_id,t.workflow_run_id,t.provider_run_id,t.run_attempt,
      e.outcome='passed' AS passed,p.version,p.lookback_days,p.min_executions,
      p.failure_rate_min,p.failure_rate_max,p.min_flips,p.excluded_branches,
      md5(jsonb_build_array(e.test_identity_id,t.branch,t.environment,
        t.report_key,t.shard)::text)::uuid AS context_id
    FROM reports t JOIN forge.test_executions e
      ON e.organization_id=t.organization_id AND e.repository_id=t.repository_id
        AND e.report_id=t.id
    JOIN forge.test_identities i ON i.organization_id=e.organization_id
      AND i.repository_id=e.repository_id AND i.id=e.test_identity_id
    JOIN policy p ON p.repository_id=t.repository_id
    WHERE t.status='completed' AND t.superseded_by_id IS NULL AND t.workflow_status='completed'
      AND e.is_final AND e.outcome IN ('passed','failed','error')
      AND i.identity_quality<>'ambiguous'
      AND t.source_at>=CAST(:to_time AS timestamptz)-p.lookback_days*interval '1 day'
      AND t.source_at<:to_time
      AND (CAST(:test_id AS uuid) IS NULL OR e.test_identity_id=CAST(:test_id AS uuid))
      AND NOT (p.excluded_branches ? coalesce(t.branch,''))
), ordered AS (
    SELECT *,lag(passed) OVER context AS previous_passed,
      lag(head_sha) OVER context AS previous_sha,
      lag(provider_run_id) OVER context AS previous_provider_run_id
    FROM observations WINDOW context AS
      (PARTITION BY context_id ORDER BY source_at,provider_run_id,run_attempt,report_id)
), evidence AS (
    SELECT context_id AS id,test_id,repository_id,repository_name,name,class_name,file,
      branch,environment,report_key,shard,count(*) AS sample_count,
      count(*) FILTER (WHERE passed) AS passed_count,
      count(*) FILTER (WHERE NOT passed) AS failed_count,
      count(*) FILTER (WHERE previous_passed IS NOT NULL AND passed<>previous_passed) AS flip_count,
      count(*) FILTER (WHERE previous_passed IS NOT NULL AND passed<>previous_passed
        AND head_sha=previous_sha AND provider_run_id=previous_provider_run_id)
        AS same_sha_reversal_count,
      count(*) FILTER (WHERE NOT passed)::double precision/count(*) AS failure_fraction,
      min(source_at) AS first_at,max(source_at) AS last_at,max(source_at) AS sort_at,
      CASE WHEN branch IS NULL OR environment IS NULL OR identity_quality<>'exact'
        THEN 'reduced' ELSE 'standard' END AS confidence,
      jsonb_build_object('version',version,'lookback_days',lookback_days,'min_executions',min_executions,
        'failure_rate_min',failure_rate_min,'failure_rate_max',failure_rate_max,
        'min_flips',min_flips,'excluded_branches',excluded_branches) AS policy,
      count(*)>=min_executions AND
        count(*) FILTER (WHERE NOT passed)::double precision/count(*)
          BETWEEN failure_rate_min AND failure_rate_max
        AND count(*) FILTER (WHERE previous_passed IS NOT NULL
          AND passed<>previous_passed)>=min_flips
        AS potential_flaky
    FROM ordered GROUP BY context_id,test_id,repository_id,repository_name,name,class_name,file,
      branch,environment,report_key,shard,identity_quality,version,lookback_days,min_executions,
      failure_rate_min,failure_rate_max,min_flips,excluded_branches
)
"""
)


class TestAnalyticsRepository(AnalyticsRepository):
    __test__ = False

    @staticmethod
    def boundary(boundary: Mapping[str, Any] | None) -> dict[str, Any]:
        return {
            "boundary": boundary["id"] if boundary else None,
            "boundary_at": boundary["at"] if boundary else None,
        }

    async def metrics(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            METRIC_REPORTS
            + """
          SELECT grouping((t.source_at AT TIME ZONE 'UTC')::date)=1 AS is_total,
            (t.source_at AT TIME ZONE 'UTC')::date AS day,
            count(*) FILTER (WHERE e.outcome='passed') AS passed_count,
            count(*) FILTER (WHERE e.outcome='failed') AS failed_count,
            count(*) FILTER (WHERE e.outcome='error') AS error_count,
            count(*) FILTER (WHERE e.outcome='skipped') AS skipped_count,
            count(*) FILTER (WHERE e.outcome<>'skipped') AS eligible_count,
            count(*) FILTER (WHERE e.outcome='passed')::double precision/
              nullif(count(*) FILTER (WHERE e.outcome<>'skipped'),0) AS pass_fraction
          FROM metric_reports t JOIN forge.test_executions e
            ON e.organization_id=t.organization_id AND e.repository_id=t.repository_id
              AND e.report_id=t.id
          WHERE e.is_final
          GROUP BY GROUPING SETS ((),((t.source_at AT TIME ZONE 'UTC')::date))
        """,
            **parameters,
        )

    async def coverage(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> Mapping[str, Any]:
        row = await self.one(
            connection,
            METRIC_REPORTS
            + """, relevant_workflows AS (
          SELECT * FROM workflows WHERE status='completed' AND run_attempt=latest_completed_attempt
            AND completed_at>=:from_time AND completed_at<:to_time
            AND (CAST(:branch AS text) IS NULL OR head_branch=CAST(:branch AS text))
        ) SELECT (SELECT count(*) FROM metric_reports) AS report_count,
          (SELECT max(processed_at) FROM reports WHERE sort_at>=:from_time
            AND sort_at<:to_time) AS input_watermark,
          (SELECT count(*) FROM relevant_workflows) AS known_workflow_count,
          (SELECT count(DISTINCT workflow_run_id) FROM metric_reports) AS with_reports_count,
          (SELECT count(*) FROM relevant_workflows w WHERE NOT EXISTS
            (SELECT 1 FROM metric_reports t WHERE t.workflow_run_id=w.id)) AS missing_report_count,
          (SELECT count(*) FROM reports WHERE status IN ('queued','processing')
            AND superseded_by_id IS NULL
            AND sort_at>=:from_time AND sort_at<:to_time) AS queued_report_count,
          (SELECT count(*) FROM reports WHERE status='failed'
            AND superseded_by_id IS NULL
            AND sort_at>=:from_time AND sort_at<:to_time) AS failed_report_count,
          (SELECT count(*) FROM metric_reports WHERE warning_count>0) AS warning_report_count,
          (SELECT count(*) FROM metric_reports WHERE completion_source='jobs')
            AS completion_proxy_count,
          (SELECT count(*) FROM reports WHERE status='completed' AND superseded_by_id IS NULL
            AND (source_at IS NULL OR workflow_status<>'completed')
            AND received_at>=:from_time AND received_at<:to_time) AS unknown_link_count
        """,
            **parameters,
        )
        assert row is not None
        return row

    async def reports(
        self,
        connection: AsyncConnection,
        parameters: dict[str, Any],
        status: str | None,
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            SCOPED
            + """
          SELECT * FROM reports WHERE sort_at>=:from_time AND sort_at<:to_time
            AND (CAST(:status AS text) IS NULL OR status=CAST(:status AS text))
            AND (CAST(:boundary AS uuid) IS NULL OR (sort_at,id)<
              (CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
          ORDER BY sort_at DESC,id DESC LIMIT :limit
        """,
            **parameters,
            status=status,
            **self.boundary(boundary),
            limit=limit,
        )

    async def report(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            SCOPED + "SELECT * FROM reports WHERE id=:id",
            org=organization,
            repository=None,
            selected_only=False,
            branch=None,
            environment=None,
            id=identifier,
        )

    async def report_counts(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID
    ) -> Mapping[str, Any]:
        row = await self.one(
            connection,
            """SELECT
          (SELECT count(*) FROM forge.test_suites
            WHERE organization_id=:org AND report_id=:id) AS suites,
          (SELECT count(*) FROM forge.test_executions
            WHERE organization_id=:org AND report_id=:id) AS cases
        """,
            org=organization,
            id=identifier,
        )
        assert row is not None
        return row

    async def children(
        self,
        connection: AsyncConnection,
        organization: UUID,
        identifier: UUID,
        kind: str,
        status: str | None,
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        table = "test_suites" if kind == "suites" else "test_executions"
        columns = (
            "e.id,e.name,e.path,e.ordinal,e.case_count,e.declared_counts"
            if kind == "suites"
            else CASE_COLUMNS
        )
        join = "" if kind == "suites" else CASE_JOINS
        status_filter = (
            "true"
            if kind == "suites"
            else "(CAST(:status AS text) IS NULL OR e.outcome=CAST(:status AS text))"
        )
        return await self.many(
            connection,
            f"""SELECT {columns} FROM forge.{table} e {join}
          WHERE e.organization_id=:org AND e.report_id=:id AND {status_filter}
            AND (CAST(:boundary AS uuid) IS NULL OR e.ordinal>
              (SELECT ordinal FROM forge.{table}
                WHERE organization_id=:org AND report_id=:id AND id=:boundary))
          ORDER BY e.ordinal,e.id LIMIT :limit
        """,
            org=organization,
            id=identifier,
            status=status,
            **self.boundary(boundary),
            limit=limit,
        )

    async def test(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT id,repository_id,name,
          coalesce(classname,'') AS class_name,coalesce(file,'') AS file,identity_quality
          FROM forge.test_identities WHERE organization_id=:org AND id=:id
        """,
            org=organization,
            id=identifier,
        )

    async def history(
        self,
        connection: AsyncConnection,
        parameters: dict[str, Any],
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            SCOPED
            + f"""
          SELECT {CASE_COLUMNS},t.id AS test_run_id,t.workflow_run_id,t.provider_run_id,
            t.run_attempt,t.head_sha,t.branch,t.environment,t.source_at,t.report_key,t.shard,
            t.superseded_by_id IS NOT NULL AS superseded,t.sort_at
          FROM reports t JOIN forge.test_executions e ON e.organization_id=t.organization_id
            AND e.repository_id=t.repository_id AND e.report_id=t.id {CASE_JOINS}
          WHERE e.test_identity_id=:test_id AND t.sort_at>=:from_time AND t.sort_at<:to_time
            AND (CAST(:boundary AS uuid) IS NULL OR (t.sort_at,e.id)<
              (CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
          ORDER BY t.sort_at DESC,e.id DESC LIMIT :limit
        """,
            **parameters,
            **self.boundary(boundary),
            limit=limit,
        )

    async def candidates(
        self,
        connection: AsyncConnection,
        parameters: dict[str, Any],
        potential_only: bool,
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            FLAKY
            + """
          SELECT * FROM evidence WHERE (NOT :potential_only OR potential_flaky)
            AND (CAST(:boundary AS uuid) IS NULL OR (sort_at,id)<
              (CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
          ORDER BY sort_at DESC,id DESC LIMIT :limit
        """,
            **parameters,
            potential_only=potential_only,
            **self.boundary(boundary),
            limit=limit,
        )
