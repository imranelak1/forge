"""Tenant-scoped immutable attempt identities, status history and explicit links."""

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.repositories.enrichment import EnrichmentRepository


class CICDRepository(EnrichmentRepository):
    async def upsert_workflow(
        self,
        connection: AsyncConnection,
        org: UUID,
        integration: UUID,
        repo: UUID,
        record: Mapping[str, Any],
        *,
        schedule: bool = True,
        force: bool = False,
        discover: bool = False,
    ) -> Mapping[str, Any]:
        old = await self.one(
            connection,
            """SELECT * FROM forge.workflow_runs WHERE organization_id=:org
            AND repository_id=:repo AND provider_run_id=:provider
            AND run_attempt=:attempt FOR UPDATE""",
            org=org,
            repo=repo,
            provider=record["provider_run_id"],
            attempt=record["run_attempt"],
        )
        data = {**record, "provider_pull_requests": json.dumps(record["provider_pull_requests"])}
        await self.execute(
            connection,
            """INSERT INTO forge.workflow_runs
            (organization_id,id,repository_id,provider_run_id,run_attempt,provider_workflow_id,
             run_number,actor_login,name,path,event,head_branch,head_sha,status,conclusion,
             created_at,queued_at,started_at,updated_at,html_url,provider_pull_requests)
            VALUES (:org,:id,:repo,:provider_run_id,:run_attempt,:provider_workflow_id,
             :run_number,:actor_login,:name,:path,:event,:head_branch,:head_sha,:status,:conclusion,
             :created_at,:queued_at,:started_at,:updated_at,:html_url,
             CAST(:provider_pull_requests AS jsonb))
            ON CONFLICT (organization_id,repository_id,provider_run_id,run_attempt) DO UPDATE SET
                name=EXCLUDED.name,path=EXCLUDED.path,head_branch=EXCLUDED.head_branch,
                actor_login=EXCLUDED.actor_login,
                status=CASE WHEN forge.workflow_runs.status='completed'
                    THEN forge.workflow_runs.status
                    ELSE EXCLUDED.status END,
                conclusion=CASE WHEN forge.workflow_runs.status='completed'
                    AND forge.workflow_runs.conclusion IS NOT NULL
                    THEN forge.workflow_runs.conclusion
                    ELSE EXCLUDED.conclusion END,
                started_at=COALESCE(forge.workflow_runs.started_at,EXCLUDED.started_at),
                updated_at=EXCLUDED.updated_at,html_url=EXCLUDED.html_url,
                provider_pull_requests=EXCLUDED.provider_pull_requests,observed_at=now()
            WHERE forge.workflow_runs.updated_at<=EXCLUDED.updated_at""",
            org=org,
            id=uuid4(),
            repo=repo,
            **data,
        )
        row = await self.one(
            connection,
            """SELECT * FROM forge.workflow_runs WHERE organization_id=:org
            AND repository_id=:repo AND provider_run_id=:provider AND run_attempt=:attempt""",
            org=org,
            repo=repo,
            provider=record["provider_run_id"],
            attempt=record["run_attempt"],
        )
        assert row
        if schedule:
            await self.queue_enrichment(
                connection,
                org,
                integration,
                repo,
                "workflow_run",
                row,
                force=force or bool(old and row["updated_at"] > old["updated_at"]),
            )
        if discover:
            await self.queue_enrichment(
                connection, org, integration, repo, "workflow_discovery", row, force=True
            )
        return row

    async def resolve_workflow_links(
        self,
        connection: AsyncConnection,
        org: UUID,
        repo: Mapping[str, Any],
        run: Mapping[str, Any],
    ) -> None:
        commit = await self.one(
            connection,
            """SELECT id FROM forge.commits
            WHERE organization_id=:org AND repository_id=:repo AND sha=:sha""",
            org=org,
            repo=repo["id"],
            sha=run["head_sha"],
        )
        error = None if commit else "commit_not_imported"
        await self.execute(
            connection,
            "UPDATE forge.workflow_runs SET commit_id=:commit "
            "WHERE organization_id=:org AND id=:id",
            org=org,
            id=run["id"],
            commit=commit["id"] if commit else None,
        )
        for reference in run["provider_pull_requests"]:
            if reference.get("repository_provider_id") not in {None, repo["provider_id"]}:
                error = "outside_repository_reference"
                continue
            pr = await self.one(
                connection,
                """SELECT id FROM forge.pull_requests
                WHERE organization_id=:org AND repository_id=:repo AND provider_id=:provider
                AND number=:number""",
                org=org,
                repo=repo["id"],
                provider=reference["provider_id"],
                number=reference["number"],
            )
            if pr is None:
                error = "pull_request_not_imported"
                continue
            await self.execute(
                connection,
                """INSERT INTO forge.workflow_run_pull_requests
                (organization_id,id,repository_id,workflow_run_id,pull_request_id)
                VALUES (:org,:id,:repo,:run,:pr)
                ON CONFLICT (organization_id,workflow_run_id,pull_request_id) DO NOTHING""",
                org=org,
                id=uuid4(),
                repo=repo["id"],
                run=run["id"],
                pr=pr["id"],
            )
        await self.coverage(
            connection,
            org,
            "workflow_run",
            run["id"],
            "links",
            "partial" if error else "complete",
            error,
        )

    async def upsert_workflow_job(
        self,
        connection: AsyncConnection,
        org: UUID,
        repo: UUID,
        run: UUID,
        record: Mapping[str, Any],
    ) -> None:
        data = {
            **record,
            "labels": json.dumps(record["labels"]),
            "steps": json.dumps(record["steps"]),
        }
        await self.execute(
            connection,
            """INSERT INTO forge.workflow_jobs
            (organization_id,id,repository_id,workflow_run_id,provider_job_id,name,status,conclusion,
             started_at,completed_at,html_url,labels,steps,failure_category)
            VALUES (:org,:id,:repo,:run,:provider_job_id,:name,:status,:conclusion,
             :started_at,:completed_at,:html_url,CAST(:labels AS jsonb),
             CAST(:steps AS jsonb),:failure_category)
            ON CONFLICT (organization_id,workflow_run_id,provider_job_id) DO UPDATE SET
                status=CASE WHEN forge.workflow_jobs.status='completed'
                    THEN forge.workflow_jobs.status
                    ELSE EXCLUDED.status END,
                conclusion=CASE WHEN forge.workflow_jobs.status='completed'
                    AND forge.workflow_jobs.conclusion IS NOT NULL
                    THEN forge.workflow_jobs.conclusion
                    ELSE EXCLUDED.conclusion END,
                started_at=COALESCE(forge.workflow_jobs.started_at,EXCLUDED.started_at),
                completed_at=COALESCE(forge.workflow_jobs.completed_at,EXCLUDED.completed_at),
                failure_category=CASE WHEN forge.workflow_jobs.status='completed'
                    THEN forge.workflow_jobs.failure_category ELSE EXCLUDED.failure_category END,
                steps=EXCLUDED.steps,labels=EXCLUDED.labels,observed_at=now()""",
            org=org,
            id=uuid4(),
            repo=repo,
            run=run,
            **data,
        )

    async def complete_workflow_jobs(
        self,
        connection: AsyncConnection,
        org: UUID,
        run: Mapping[str, Any],
        total: int,
        error: str | None,
    ) -> None:
        counts = await self.one(
            connection,
            """SELECT count(*) AS count,
            count(*) FILTER (WHERE status<>'completed' OR
                (completed_at IS NULL AND conclusion IS DISTINCT FROM 'skipped')) AS incomplete,
            max(completed_at) AS completed_at FROM forge.workflow_jobs
            WHERE organization_id=:org AND workflow_run_id=:run""",
            org=org,
            run=run["id"],
        )
        assert counts
        if counts["count"] != total:
            error = error or "job_count_changed"
        if run["status"] != "completed" or counts["incomplete"]:
            error = error or "workflow_in_progress"
        await self.coverage(
            connection,
            org,
            "workflow_run",
            run["id"],
            "jobs",
            "partial" if error else "complete",
            error,
        )
        if not error and counts["count"] and counts["completed_at"]:
            await self.execute(
                connection,
                """UPDATE forge.workflow_runs
                SET completed_at=COALESCE(completed_at,:completed),
                    completion_source=COALESCE(completion_source,'jobs')
                WHERE organization_id=:org AND id=:id""",
                org=org,
                id=run["id"],
                completed=counts["completed_at"],
            )

    async def upsert_deployment(
        self,
        connection: AsyncConnection,
        org: UUID,
        integration: UUID,
        repo: UUID,
        record: Mapping[str, Any],
        *,
        schedule: bool = True,
        force: bool = False,
    ) -> Mapping[str, Any]:
        environment = await self.one(
            connection,
            """INSERT INTO forge.deployment_environments
            (organization_id,id,repository_id,name) VALUES (:org,:id,:repo,:name)
            ON CONFLICT (organization_id,repository_id,name) DO UPDATE SET name=EXCLUDED.name
            RETURNING id""",
            org=org,
            id=uuid4(),
            repo=repo,
            name=record["environment"],
        )
        assert environment
        old = await self.one(
            connection,
            """SELECT * FROM forge.deployments
            WHERE organization_id=:org AND repository_id=:repo
            AND provider_id=:provider FOR UPDATE""",
            org=org,
            repo=repo,
            provider=record["provider_id"],
        )
        commit = await self.one(
            connection,
            "SELECT id FROM forge.commits WHERE organization_id=:org "
            "AND repository_id=:repo AND sha=:sha",
            org=org,
            repo=repo,
            sha=record["sha"],
        )
        await self.execute(
            connection,
            """INSERT INTO forge.deployments
            (organization_id,id,repository_id,provider_id,environment_id,environment,
             production_environment,transient_environment,sha,ref,task,description,creator_login,
             created_at,updated_at,html_url,commit_id)
            VALUES (:org,:id,:repo,:provider_id,:environment_id,:environment,
             :production_environment,:transient_environment,:sha,:ref,:task,:description,:creator_login,
             :created_at,:updated_at,:html_url,:commit)
            ON CONFLICT (organization_id,repository_id,provider_id) DO UPDATE SET
                environment_id=EXCLUDED.environment_id,environment=EXCLUDED.environment,
                production_environment=EXCLUDED.production_environment,
                transient_environment=EXCLUDED.transient_environment,description=EXCLUDED.description,
                updated_at=EXCLUDED.updated_at,commit_id=COALESCE(EXCLUDED.commit_id,forge.deployments.commit_id),
                observed_at=now() WHERE forge.deployments.updated_at<=EXCLUDED.updated_at""",
            org=org,
            id=uuid4(),
            repo=repo,
            environment_id=environment["id"],
            commit=commit["id"] if commit else None,
            **record,
        )
        row = await self.one(
            connection,
            """SELECT * FROM forge.deployments
            WHERE organization_id=:org AND repository_id=:repo AND provider_id=:provider""",
            org=org,
            repo=repo,
            provider=record["provider_id"],
        )
        assert row
        if schedule:
            await self.queue_enrichment(
                connection,
                org,
                integration,
                repo,
                "deployment",
                row,
                force=force or bool(old and row["updated_at"] > old["updated_at"]),
            )
        return row

    async def upsert_deployment_status(
        self,
        connection: AsyncConnection,
        org: UUID,
        repo: UUID,
        deployment: UUID,
        record: Mapping[str, Any],
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.deployment_statuses
            (organization_id,id,repository_id,deployment_id,provider_id,state,description,environment,
             creator_login,created_at,updated_at,html_url)
            VALUES (:org,:id,:repo,:deployment,:provider_id,:state,:description,:environment,
             :creator_login,:created_at,:updated_at,:html_url)
            ON CONFLICT (organization_id,deployment_id,provider_id) DO NOTHING""",
            org=org,
            id=uuid4(),
            repo=repo,
            deployment=deployment,
            **record,
        )
