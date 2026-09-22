"""Attempt/deployment-grain analytics; source relationships cannot multiply metric facts."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.repositories.analytics import COMMIT_SELECT, PR_CTE, AnalyticsRepository

DECISIVE_SQL = "('success','failure','timed_out','startup_failure','action_required')"
SCOPED = """WITH scoped_repositories AS (
    SELECT r.* FROM forge.repositories r WHERE r.organization_id=:org
    AND (CAST(:repository AS uuid) IS NULL OR r.id=CAST(:repository AS uuid))
    AND (NOT :selected_only OR r.selected)
)"""
RUN_CTE = (
    SCOPED
    + f""", base AS (
    SELECT w.*,r.full_name AS repository_name,
      CASE WHEN w.status<>'completed' OR w.completed_at IS NULL THEN 'completion_unknown'
        WHEN coalesce(w.conclusion,'') NOT IN {DECISIVE_SQL} THEN 'non_decisive'
        WHEN w.started_at IS NULL THEN 'start_unknown'
        WHEN w.completed_at<w.started_at THEN 'invalid_timestamps' END AS duration_exclusion,
      CASE WHEN w.status<>'completed' OR w.completed_at IS NULL THEN 'completion_unknown'
        WHEN coalesce(w.conclusion,'') NOT IN {DECISIVE_SQL} THEN 'non_decisive'
        WHEN w.queued_at IS NULL THEN 'queue_unknown'
        WHEN w.started_at IS NULL THEN 'start_unknown'
        WHEN w.started_at<w.queued_at THEN 'invalid_timestamps' END AS queue_exclusion
    FROM forge.workflow_runs w JOIN scoped_repositories r
      ON r.organization_id=w.organization_id AND r.id=w.repository_id
    WHERE w.organization_id=:org
      AND (CAST(:workflow AS bigint) IS NULL OR w.provider_workflow_id=CAST(:workflow AS bigint))
      AND (CAST(:branch AS text) IS NULL OR w.head_branch=CAST(:branch AS text))
), facts AS (
    SELECT *, CASE WHEN duration_exclusion IS NULL THEN
      extract(epoch FROM completed_at-started_at)::double precision END AS duration_seconds,
      CASE WHEN queue_exclusion IS NULL THEN
      extract(epoch FROM started_at-queued_at)::double precision END AS queue_seconds
    FROM base
)"""
)
DEPLOYMENT_CTE = (
    SCOPED
    + """, base AS (
    SELECT d.*,r.full_name AS repository_name,
      coalesce(e.classification,CASE WHEN d.production_environment THEN 'production'
        WHEN d.production_environment=false THEN 'nonproduction' ELSE 'unknown' END)
        AS classification,
      CASE WHEN e.classification IS NOT NULL THEN 'override'
        WHEN d.production_environment IS NOT NULL THEN 'provider' ELSE 'unknown' END
        AS classification_source,
      status.first_success_at,status.latest_state,
      CASE WHEN d.statuses_status<>'complete' THEN 'incomplete_statuses'
        WHEN status.first_success_at IS NULL THEN 'no_success'
        WHEN status.first_success_at<d.created_at THEN 'invalid_timestamps' END
        AS success_exclusion
    FROM forge.deployments d JOIN scoped_repositories r
      ON r.organization_id=d.organization_id AND r.id=d.repository_id
    JOIN forge.deployment_environments e ON e.organization_id=d.organization_id
      AND e.repository_id=d.repository_id AND e.id=d.environment_id
    LEFT JOIN LATERAL (
      SELECT min(s.created_at) FILTER (WHERE s.state='success') AS first_success_at,
        (array_agg(s.state ORDER BY s.created_at DESC,s.provider_id DESC,s.id DESC))[1]
          AS latest_state
      FROM forge.deployment_statuses s WHERE s.organization_id=d.organization_id
        AND s.repository_id=d.repository_id AND s.deployment_id=d.id
    ) status ON true WHERE d.organization_id=:org
      AND (CAST(:environment AS text) IS NULL OR d.environment=CAST(:environment AS text))
), facts AS (SELECT * FROM base WHERE :classification='all' OR classification=:classification)
"""
)
COMPLETED = "status='completed' AND completed_at>=:from_time AND completed_at<:to_time"


def distribution_sql(field: str) -> str:
    return f"""count({field}_seconds) AS {field}_sample_count,
      count(*) FILTER (WHERE conclusion IN {DECISIVE_SQL} AND {field}_seconds IS NULL)
        AS {field}_excluded_count,
      avg({field}_seconds) AS {field}_mean_seconds,
      percentile_cont(0.5) WITHIN GROUP (ORDER BY {field}_seconds) AS {field}_median_seconds,
      percentile_cont(0.75) WITHIN GROUP (ORDER BY {field}_seconds) AS {field}_p75_seconds,
      percentile_cont(0.95) WITHIN GROUP (ORDER BY {field}_seconds) AS {field}_p95_seconds"""


class DeliveryRepository(AnalyticsRepository):
    async def source_coverage(
        self, connection: AsyncConnection, parameters: dict[str, Any], kind: str
    ) -> Mapping[str, Any]:
        if kind not in {"ci", "deployments"}:
            raise ValueError("invalid_coverage")
        row = await self.one(
            connection,
            SCOPED
            + f"""
          SELECT count(*) AS repository_count,
          count(*) FILTER (WHERE r.{kind}_status='complete') AS repositories_complete,
          count(*) FILTER (WHERE r.{kind}_status IN ('pending','unavailable','failed'))
            AS repositories_unavailable,
          count(*) FILTER (WHERE r.{kind}_status<>'complete') AS source_incomplete,
          count(*) FILTER (WHERE r.{kind}_window_since IS NULL OR r.{kind}_window_until IS NULL
            OR r.{kind}_window_since>:from_time OR r.{kind}_window_until<:to_time)
            AS history_window_partial,
          count(*) FILTER (WHERE NOT r.is_demo AND (NOT r.authorized OR i.status<>'active'))
            AS sources_unavailable,
          min(r.{kind}_synced_at) AS input_watermark
          FROM scoped_repositories r JOIN forge.integrations i
            ON i.organization_id=r.organization_id AND i.id=r.integration_id
          """,
            **parameters,
        )
        assert row is not None
        return row

    async def ci_aggregates(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            RUN_CTE
            + f"""
          SELECT (completed_at AT TIME ZONE 'UTC')::date AS day,
          grouping((completed_at AT TIME ZONE 'UTC')::date)=1 AS is_total,
          count(*) AS completed_count,
          count(*) FILTER (WHERE conclusion IN {DECISIVE_SQL}) AS decisive_count,
          count(*) FILTER (WHERE conclusion='success') AS success_count,
          count(*) FILTER (WHERE conclusion IN {DECISIVE_SQL} AND conclusion<>'success')
            AS failure_count,
          {distribution_sql("duration")},{distribution_sql("queue")}
          FROM facts WHERE {COMPLETED}
          GROUP BY GROUPING SETS ((),((completed_at AT TIME ZONE 'UTC')::date))
          """,
            **parameters,
        )

    async def ci_breakdown(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            RUN_CTE
            + f"""
          SELECT coalesce(conclusion,'unknown') AS conclusion,duration_exclusion,queue_exclusion,
          (completed_at AT TIME ZONE 'UTC')::date AS day,count(*) AS count
          FROM facts WHERE {COMPLETED}
          GROUP BY conclusion,duration_exclusion,queue_exclusion,day
          """,
            **parameters,
        )

    async def ci_evidence_coverage(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> Mapping[str, Any]:
        row = await self.one(
            connection,
            RUN_CTE
            + f"""
          SELECT count(*) FILTER (WHERE status='completed' AND completed_at IS NULL
            AND updated_at>=:from_time AND updated_at<:to_time) AS completion_unknown_count,
          count(*) FILTER (WHERE {COMPLETED} AND completion_source='jobs')
            AS completion_proxy_count,
          count(*) FILTER (WHERE jobs_status<>'complete' AND
            (({COMPLETED}) OR (updated_at>=:from_time AND updated_at<:to_time)))
            AS jobs_incomplete_count FROM facts
          """,
            **parameters,
        )
        assert row is not None
        return row

    async def recurring_failures(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            RUN_CTE
            + f"""
          SELECT repository_id,repository_name,provider_workflow_id AS workflow_id,
            (array_agg(name ORDER BY completed_at DESC,id DESC))[1] AS workflow_name,
            count(*) AS decisive_count,
            count(*) FILTER (WHERE conclusion<>'success') AS failure_count,
            count(*) FILTER (WHERE conclusion<>'success')::double precision/count(*)
              AS failure_fraction,'unknown' AS category
          FROM facts WHERE {COMPLETED} AND conclusion IN {DECISIVE_SQL}
          GROUP BY repository_id,repository_name,provider_workflow_id
          HAVING count(*) FILTER (WHERE conclusion<>'success')>=2
          ORDER BY failure_count DESC,repository_id,provider_workflow_id LIMIT 20
          """,
            **parameters,
        )

    async def run(
        self, connection: AsyncConnection, parameters: dict[str, Any], identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection, RUN_CTE + " SELECT * FROM facts WHERE id=:id", **parameters, id=identifier
        )

    async def runs(
        self,
        connection: AsyncConnection,
        parameters: dict[str, Any],
        cohort: str,
        outcome: str,
        metric: str | None,
        eligibility: str,
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        stamp = "completed_at" if cohort == "completed" or metric else "created_at"
        outcome_filter = {
            "all": "true",
            "success": "conclusion='success'",
            "failure": f"conclusion IN {DECISIVE_SQL} AND conclusion<>'success'",
            "other": f"coalesce(conclusion,'') NOT IN {DECISIVE_SQL}",
        }[outcome]
        metric_filter = "true"
        if metric in {"duration", "queue"}:
            metric_filter = f"status='completed' AND conclusion IN {DECISIVE_SQL}"
            if eligibility in {"eligible", "excluded"}:
                metric_filter += f" AND {metric}_exclusion IS " + (
                    "NULL" if eligibility == "eligible" else "NOT NULL"
                )
        return await self.many(
            connection,
            RUN_CTE
            + f"""
          SELECT *,{stamp} AS sort_at FROM facts WHERE {stamp}>=:from_time AND {stamp}<:to_time
          AND (:completed=false OR status='completed') AND ({outcome_filter}) AND ({metric_filter})
          AND (CAST(:boundary AS uuid) IS NULL OR ({stamp},id)<
            (CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
          ORDER BY {stamp} DESC,id DESC LIMIT :limit
          """,
            **parameters,
            completed=cohort == "completed" or bool(metric),
            **self.boundary(boundary),
            limit=limit,
        )

    @staticmethod
    def boundary(value: Mapping[str, Any] | None) -> dict[str, Any]:
        return {
            "boundary": value["id"] if value else None,
            "boundary_at": value["at"] if value else None,
        }

    async def deployment(
        self, connection: AsyncConnection, parameters: dict[str, Any], identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            DEPLOYMENT_CTE + " SELECT * FROM facts WHERE id=:id",
            **parameters,
            id=identifier,
        )

    async def deployments(
        self,
        connection: AsyncConnection,
        parameters: dict[str, Any],
        cohort: str,
        eligibility: str,
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        stamp = "first_success_at" if cohort == "success" else "created_at"
        valid = "true"
        if cohort == "success" and eligibility in {"eligible", "excluded"}:
            valid = "success_exclusion IS " + ("NULL" if eligibility == "eligible" else "NOT NULL")
        return await self.many(
            connection,
            DEPLOYMENT_CTE
            + f"""
          SELECT *,{stamp} AS sort_at FROM facts WHERE {stamp}>=:from_time AND {stamp}<:to_time
          AND ({valid}) AND (CAST(:boundary AS uuid) IS NULL OR ({stamp},id)<
            (CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
          ORDER BY {stamp} DESC,id DESC LIMIT :limit
          """,
            **parameters,
            **self.boundary(boundary),
            limit=limit,
        )

    async def deployment_aggregates(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            DEPLOYMENT_CTE
            + """
          SELECT (first_success_at AT TIME ZONE 'UTC')::date AS day,
            grouping((first_success_at AT TIME ZONE 'UTC')::date)=1 AS is_total,
            count(*) AS observed_success_count,
            count(*) FILTER (WHERE success_exclusion IS NULL) AS successful_count,
            count(*) FILTER (WHERE success_exclusion IS NOT NULL) AS excluded_count
          FROM facts WHERE first_success_at>=:from_time AND first_success_at<:to_time
          GROUP BY GROUPING SETS ((),((first_success_at AT TIME ZONE 'UTC')::date))
          """,
            **parameters,
        )

    async def deployment_breakdown(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            DEPLOYMENT_CTE
            + """
          SELECT 'state' AS kind,coalesce(latest_state,'unknown') AS key,count(*) AS count
          FROM facts WHERE created_at>=:from_time AND created_at<:to_time GROUP BY latest_state
          UNION ALL SELECT 'exclusion',success_exclusion,count(*) FROM facts
          WHERE first_success_at>=:from_time AND first_success_at<:to_time
            AND success_exclusion IS NOT NULL GROUP BY success_exclusion
          """,
            **parameters,
        )

    async def deployment_evidence_coverage(
        self, connection: AsyncConnection, parameters: dict[str, Any]
    ) -> Mapping[str, Any]:
        row = await self.one(
            connection,
            DEPLOYMENT_CTE
            + """
          SELECT count(*) FILTER (WHERE statuses_status<>'complete') AS statuses_incomplete_count
          FROM facts WHERE created_at<:to_time
          """,
            **parameters,
        )
        assert row is not None
        return row

    async def delivery_evidence(
        self,
        connection: AsyncConnection,
        org: UUID,
        identifier: UUID,
        parent: str,
        kind: str,
        boundary: Mapping[str, Any] | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        values: dict[str, Any] = {
            "org": org,
            "id": identifier,
            **self.boundary(boundary),
            "limit": limit,
        }
        if kind == "jobs":
            return await self.many(
                connection,
                """SELECT j.*,
              coalesce(j.started_at,w.created_at) AS sort_at
              FROM forge.workflow_jobs j JOIN forge.workflow_runs w
                ON w.organization_id=j.organization_id AND w.repository_id=j.repository_id
                AND w.id=j.workflow_run_id WHERE j.organization_id=:org AND w.id=:id
              AND (CAST(:boundary AS uuid) IS NULL OR (coalesce(j.started_at,w.created_at),j.id)>
                (CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
              ORDER BY sort_at,j.id LIMIT :limit""",
                **values,
            )
        if kind == "statuses":
            return await self.many(
                connection,
                """SELECT s.*,s.created_at AS sort_at
              FROM forge.deployment_statuses s WHERE s.organization_id=:org AND s.deployment_id=:id
              AND (CAST(:boundary AS uuid) IS NULL OR (s.created_at,s.id)>
                (CAST(:boundary_at AS timestamptz),CAST(:boundary AS uuid)))
              ORDER BY s.created_at,s.id LIMIT :limit""",
                **values,
            )
        if kind == "pull-requests":
            return await self.many(
                connection,
                PR_CTE
                + """ SELECT f.* FROM facts f
              WHERE EXISTS (SELECT 1 FROM forge.workflow_run_pull_requests x
                WHERE x.organization_id=f.organization_id AND x.repository_id=f.repository_id
                AND x.pull_request_id=f.id AND x.workflow_run_id=:id)
              AND (CAST(:boundary AS uuid) IS NULL OR f.id>CAST(:boundary AS uuid))
              ORDER BY f.id LIMIT :limit""",
                **values,
                repository=None,
                selected_only=False,
                author=None,
                identifier=None,
            )
        table = "workflow_runs" if parent == "run" else "deployments"
        return await self.many(
            connection,
            COMMIT_SELECT
            + f"""
          AND EXISTS (SELECT 1 FROM forge.{table} p WHERE p.organization_id=c.organization_id
            AND p.repository_id=c.repository_id AND p.commit_id=c.id AND p.id=:id)
          AND (CAST(:boundary AS uuid) IS NULL OR c.id>CAST(:boundary AS uuid))
          ORDER BY c.id LIMIT :limit""",
            **values,
        )

    async def delivery_counts(
        self, connection: AsyncConnection, org: UUID, identifier: UUID, parent: str
    ) -> Mapping[str, Any]:
        if parent == "run":
            sql = """SELECT (SELECT count(*) FROM forge.workflow_jobs j
              WHERE j.organization_id=w.organization_id AND j.repository_id=w.repository_id
                AND j.workflow_run_id=w.id) AS jobs,
              (SELECT count(*) FROM forge.workflow_run_pull_requests p
              WHERE p.organization_id=w.organization_id AND p.repository_id=w.repository_id
                AND p.workflow_run_id=w.id) AS pull_requests,
              CASE WHEN w.commit_id IS NULL THEN 0 ELSE 1 END AS commits
              FROM forge.workflow_runs w WHERE organization_id=:org AND id=:id"""
        else:
            sql = """SELECT (SELECT count(*) FROM forge.deployment_statuses s
              WHERE s.organization_id=d.organization_id AND s.repository_id=d.repository_id
                AND s.deployment_id=d.id) AS statuses,
              CASE WHEN d.commit_id IS NULL THEN 0 ELSE 1 END AS commits
              FROM forge.deployments d WHERE organization_id=:org AND id=:id"""
        row = await self.one(connection, sql, org=org, id=identifier)
        assert row is not None
        return row

    async def environments(
        self, connection: AsyncConnection, org: UUID, repository: UUID
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            """SELECT e.name AS environment,
          e.classification AS override,count(d.id) AS deployment_count,
          count(d.id) FILTER (WHERE coalesce(e.classification,
            CASE WHEN d.production_environment THEN 'production' END)='production')
            AS production_count,
          count(d.id) FILTER (WHERE coalesce(e.classification,
            CASE WHEN d.production_environment=false THEN 'nonproduction' END)='nonproduction')
            AS nonproduction_count,
          count(d.id) FILTER (WHERE e.classification IS NULL AND d.production_environment IS NULL)
            AS unknown_count
          FROM forge.deployment_environments e JOIN forge.deployments d
            ON d.organization_id=e.organization_id AND d.repository_id=e.repository_id
              AND d.environment_id=e.id
          WHERE e.organization_id=:org AND e.repository_id=:repository
          GROUP BY e.id,e.name,e.classification ORDER BY e.name,e.id""",
            org=org,
            repository=repository,
        )
