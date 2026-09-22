"""Actions and deployment pages use the existing access-checked fenced dispatcher."""

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.domain import cicd as normalize
from forge.domain.github import object_value, positive_id
from forge.integrations.github import GitHubApp, GitHubFailure
from forge.repositories.pipeline import Lease, LostLease, PipelineRepository, Work
from forge.workers.enrichment import EvidencePage

KINDS = {
    "cicd_links",
    "ci_repository",
    "deployments_repository",
    "workflow_discovery",
    "workflow_run",
    "deployment",
}
EVENTS = {"workflow_run", "workflow_job", "deployment", "deployment_status"}


@dataclass
class CICDPage(EvidencePage):
    pass


class CICDWorker:
    def __init__(self, repository: PipelineRepository, provider: GitHubApp) -> None:
        self.repository = repository
        self.provider = provider

    async def fetch(self, work: Work) -> CICDPage:
        assert work.repository and work.subject
        repo, subject, checkpoint = work.repository, work.subject, work.job["payload"]
        stage, page = checkpoint["stage"], checkpoint["page"]
        if type(page) is not int or not 1 <= page <= 100:
            raise GitHubFailure("capacity_exceeded")
        result = CICDPage(stage, page)
        if stage in {"link_workflows", "link_deployments"}:
            return result
        token, capabilities = await self.provider.cicd_credentials(
            work.integration["installation_id"]
        )
        capability = (
            "deployments"
            if checkpoint["kind"] in {"deployments_repository", "deployment"}
            else "actions"
        )
        if capability not in capabilities:
            result.data["unavailable"] = f"{capability}_permission_required"
            return result
        args = token, repo["owner"], repo["name"]
        if stage == "workflow_catalog":
            values, total = await self.provider.workflow_runs(*args, page)
            result.records = [
                normalize.workflow_run(row, repo["full_name"], repo["provider_id"])
                for row in values
            ]
            result.done = len(values) < 100
            result.data["total"] = total
        elif stage in {"workflow_discovery", "workflow_details"}:
            attempt = page if stage == "workflow_discovery" else subject["run_attempt"]
            if attempt > 100:
                result.data["partial"] = "provider_attempt_limit"
                return result
            value = await self.provider.workflow_run(*args, subject["provider_run_id"], attempt)
            row = normalize.workflow_run(value, repo["full_name"], repo["provider_id"])
            if (
                row["provider_run_id"] != subject["provider_run_id"]
                or row["run_attempt"] != attempt
            ):
                raise GitHubFailure("invalid_response")
            if stage == "workflow_details" and row["updated_at"] < subject["updated_at"]:
                raise GitHubFailure("source_changed", retryable=True)
            result.records = [row]
            if stage == "workflow_discovery":
                result.done = page >= min(subject["run_attempt"], 100)
                if result.done and subject["run_attempt"] > 100:
                    result.data["partial"] = "provider_attempt_limit"
        elif stage == "workflow_jobs":
            values, total = await self.provider.workflow_jobs(
                *args, subject["provider_run_id"], subject["run_attempt"], page
            )
            result.records = [
                normalize.workflow_job(
                    row, repo["full_name"], subject["provider_run_id"], subject["run_attempt"]
                )
                for row in values
            ]
            result.data["total"] = total
            result.done = len(values) < 100
        elif stage == "deployment_catalog":
            values = await self.provider.deployments(*args, page)
            result.records = [normalize.deployment(row, repo["full_name"]) for row in values]
            result.done = len(values) < 100
        elif stage == "deployment_details":
            value = await self.provider.deployment(*args, subject["provider_id"])
            row = normalize.deployment(value, repo["full_name"])
            if row["provider_id"] != subject["provider_id"]:
                raise GitHubFailure("invalid_response")
            if row["updated_at"] < subject["updated_at"]:
                raise GitHubFailure("source_changed", retryable=True)
            result.records = [row]
        elif stage == "deployment_statuses":
            values = await self.provider.deployment_statuses(*args, subject["provider_id"], page)
            result.records = [normalize.deployment_status(row, repo["full_name"]) for row in values]
            result.done = len(values) < 100
        else:
            raise GitHubFailure("invalid_checkpoint")
        if not result.done and page == 100:
            result.done = True
            result.data["partial"] = "provider_page_limit"
        return result

    async def fetch_webhook(self, work: Work) -> CICDPage:
        assert work.inbox and work.repository
        event, payload, repo = work.inbox["event"], work.inbox["payload"], work.repository
        capability = "actions" if event in {"workflow_run", "workflow_job"} else "deployments"
        stage = "workflow_webhook" if capability == "actions" else "deployment_webhook"
        result = CICDPage(stage, 1)
        token, capabilities = await self.provider.cicd_credentials(
            work.integration["installation_id"]
        )
        if capability not in capabilities:
            result.data["unavailable"] = f"{capability}_permission_required"
            return result
        args = token, repo["owner"], repo["name"]
        if capability == "actions":
            raw = object_value(payload.get(event))
            identifier = positive_id(raw.get("run_id" if event == "workflow_job" else "id"))
            value = await self.provider.workflow_run(*args, identifier)
            row = normalize.workflow_run(value, repo["full_name"], repo["provider_id"])
            if row["provider_run_id"] != identifier:
                raise GitHubFailure("invalid_response")
        else:
            identifier = positive_id(object_value(payload.get("deployment")).get("id"))
            value = await self.provider.deployment(*args, identifier)
            row = normalize.deployment(value, repo["full_name"])
            if row["provider_id"] != identifier:
                raise GitHubFailure("invalid_response")
        result.records = [row]
        return result

    async def refresh_coverage(
        self, connection: AsyncConnection, org: UUID, repository: UUID, capability: str
    ) -> None:
        source = await self.repository.one(
            connection,
            "SELECT * FROM forge.repositories WHERE organization_id=:org AND id=:id",
            org=org,
            id=repository,
        )
        assert source
        if source[f"{capability}_error"] not in {None, "enrichment_pending", "enrichment_failed"}:
            return
        if source[f"{capability}_window_until"] is None:
            return
        kinds = (
            ["ci_repository", "workflow_discovery", "workflow_run"]
            if capability == "ci"
            else ["deployments_repository", "deployment"]
        )
        pending = await self.repository.one(
            connection,
            """SELECT
            count(*) FILTER (WHERE state IN ('queued','running','retry')) AS active,
            count(*) FILTER (WHERE state='dead') AS failed FROM forge.jobs
            WHERE organization_id=:org AND repository_id=:repo AND kind='enrichment'
                AND payload->>'kind'=ANY(CAST(:kinds AS text[]))""",
            org=org,
            repo=repository,
            kinds=kinds,
        )
        assert pending
        table, prefix = (
            ("workflow_runs", "jobs") if capability == "ci" else ("deployments", "statuses")
        )
        incomplete = await self.repository.one(
            connection,
            f"""SELECT count(*) AS count
            FROM forge.{table} WHERE organization_id=:org AND repository_id=:repo
            AND {prefix}_status<>'complete'""",
            org=org,
            repo=repository,
        )
        assert incomplete
        error = (
            "enrichment_failed"
            if pending["failed"]
            else "enrichment_pending"
            if pending["active"]
            else None
        )
        if incomplete["count"]:
            error = error or "enrichment_pending"
        await self.repository.coverage(
            connection,
            org,
            "ci_repository" if capability == "ci" else "deployments_repository",
            repository,
            capability,
            "partial" if error else "complete",
            error,
        )

    async def persist(
        self, connection: AsyncConnection, lease: Lease, work: Work, result: CICDPage
    ) -> str:
        assert work.repository
        repo = self.repository
        org, integration, source = (
            lease.organization_id,
            work.integration["id"],
            work.repository["id"],
        )
        capability = "deployments" if result.stage.startswith("deployment") else "ci"
        repository_kind = (
            "deployments_repository" if capability == "deployments" else "ci_repository"
        )
        unavailable = result.data.get("unavailable")
        if work.inbox:
            if unavailable:
                await repo.coverage(
                    connection, org, repository_kind, source, capability, "unavailable", unavailable
                )
            elif capability == "ci":
                await repo.upsert_workflow(
                    connection,
                    org,
                    integration,
                    source,
                    result.records[0],
                    force=True,
                    discover=True,
                )
            else:
                await repo.upsert_deployment(
                    connection, org, integration, source, result.records[0], force=True
                )
            await repo.finish_inbox(connection, org, work.inbox["id"], "processed")
            await repo.finish_job(connection, lease)
            return "completed"
        assert work.subject
        checkpoint, subject = dict(work.job["payload"]), work.subject
        kind, stage = checkpoint["kind"], result.stage
        if (
            kind in {"workflow_run", "deployment"}
            and checkpoint["revision"] != subject["updated_at"].isoformat()
        ):
            raise LostLease
        finished, next_stage, delay = result.done, stage, 0
        partial = result.data.get("partial")
        if stage in {"link_workflows", "link_deployments"}:
            table = "workflow_runs" if stage == "link_workflows" else "deployments"
            rows = await repo.many(
                connection,
                f"""SELECT * FROM forge.{table}
                WHERE organization_id=:org AND repository_id=:repo
                AND id>CAST(:after AS uuid) ORDER BY id LIMIT 100""",
                org=org,
                repo=source,
                after=checkpoint.get("after", "00000000-0000-0000-0000-000000000000"),
            )
            for row in rows:
                if stage == "link_workflows":
                    await repo.resolve_workflow_links(connection, org, work.repository, row)
                else:
                    await repo.execute(
                        connection,
                        """UPDATE forge.deployments d
                        SET commit_id=c.id FROM forge.commits c
                        WHERE d.organization_id=:org AND d.id=:id
                        AND c.organization_id=d.organization_id AND c.repository_id=d.repository_id
                        AND c.sha=d.sha AND d.commit_id IS DISTINCT FROM c.id""",
                        org=org,
                        id=row["id"],
                    )
            if len(rows) == 100:
                checkpoint["after"] = str(rows[-1]["id"])
                finished = False
            elif stage == "link_workflows":
                checkpoint.pop("after", None)
                next_stage, finished = "link_deployments", False
        elif unavailable:
            await repo.coverage(
                connection, org, repository_kind, source, capability, "unavailable", unavailable
            )
            if kind in {"workflow_run", "deployment"}:
                await repo.coverage(
                    connection,
                    org,
                    kind,
                    subject["id"],
                    "jobs" if kind == "workflow_run" else "statuses",
                    "unavailable",
                    unavailable,
                )
            finished = True
        elif stage in {"workflow_catalog", "deployment_catalog"}:
            for row in result.records:
                if capability == "ci":
                    await repo.upsert_workflow(
                        connection, org, integration, source, row, force=True, discover=True
                    )
                else:
                    await repo.upsert_deployment(
                        connection, org, integration, source, row, force=True
                    )
            checkpoint["observed"] = checkpoint.get("observed", 0) + len(result.records)
            if result.done:
                if capability == "ci" and checkpoint["observed"] != result.data["total"]:
                    partial = partial or "catalog_count_changed"
                await repo.execute(
                    connection,
                    f"""UPDATE forge.repositories
                    SET {capability}_window_since=:since,{capability}_window_until=:until
                    WHERE organization_id=:org AND id=:id""",
                    org=org,
                    id=source,
                    since=datetime.fromisoformat(checkpoint["since"]),
                    until=datetime.fromisoformat(checkpoint["until"]),
                )
                await repo.coverage(
                    connection,
                    org,
                    repository_kind,
                    source,
                    capability,
                    "partial",
                    partial or "enrichment_pending",
                )
        elif stage == "workflow_discovery":
            for row in result.records:
                await repo.upsert_workflow(connection, org, integration, source, row, force=True)
            if partial:
                await repo.coverage(
                    connection, org, "ci_repository", source, "ci", "partial", partial
                )
        elif stage == "workflow_details":
            if result.records:
                current = await repo.upsert_workflow(
                    connection, org, integration, source, result.records[0], schedule=False
                )
                checkpoint["revision"] = current["updated_at"].isoformat()
                await repo.resolve_workflow_links(connection, org, work.repository, current)
                next_stage, finished = "workflow_jobs", False
            else:
                await repo.coverage(
                    connection, org, "workflow_run", subject["id"], "jobs", "partial", partial
                )
        elif stage == "workflow_jobs":
            for row in result.records:
                await repo.upsert_workflow_job(connection, org, source, subject["id"], row)
            if result.done:
                await repo.complete_workflow_jobs(
                    connection, org, subject, result.data["total"], partial
                )
                if subject["status"] != "completed":
                    next_stage, finished, delay = "workflow_details", False, 30
            else:
                await repo.coverage(
                    connection, org, "workflow_run", subject["id"], "jobs", "partial"
                )
        elif stage == "deployment_details":
            current = await repo.upsert_deployment(
                connection, org, integration, source, result.records[0], schedule=False
            )
            checkpoint["revision"] = current["updated_at"].isoformat()
            next_stage, finished = "deployment_statuses", False
        elif stage == "deployment_statuses":
            for row in result.records:
                await repo.upsert_deployment_status(connection, org, source, subject["id"], row)
            await repo.coverage(
                connection,
                org,
                "deployment",
                subject["id"],
                "statuses",
                "partial" if partial or not result.done else "complete",
                partial,
            )
        if partial:
            checkpoint["partial"] = partial
        checkpoint["stage"] = next_stage
        checkpoint["page"] = 1 if next_stage != stage else result.page + 1
        await repo.execute(
            connection,
            "UPDATE forge.jobs SET payload=CAST(:payload AS jsonb) "
            "WHERE organization_id=:org AND id=:id",
            org=org,
            id=lease.id,
            payload=json.dumps(checkpoint),
        )
        await repo.finish_job(
            connection,
            lease,
            state="succeeded" if finished else "queued",
            reset_attempts=True,
            delay=delay,
        )
        if not unavailable:
            await self.refresh_coverage(connection, org, source, capability)
        return "completed" if finished else "checkpointed"

    async def failure(
        self, connection: AsyncConnection, org: UUID, work: Work, code: str, retrying: bool
    ) -> None:
        assert work.subject and work.repository
        kind = work.job["payload"]["kind"]
        capability = "deployments" if kind in {"deployments_repository", "deployment"} else "ci"
        status = "partial" if retrying else "failed"
        await self.repository.coverage(
            connection,
            org,
            "deployments_repository" if capability == "deployments" else "ci_repository",
            work.repository["id"],
            capability,
            status,
            "enrichment_pending" if retrying else "enrichment_failed",
        )
        if kind in {"workflow_run", "deployment"}:
            await self.repository.coverage(
                connection,
                org,
                kind,
                work.subject["id"],
                "jobs" if kind == "workflow_run" else "statuses",
                status,
                code,
            )
