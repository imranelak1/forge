"""Tenant-scoped persistence and fenced, transactional sync checkpoints."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.repositories.identity import IdentityRepository

ACTIVE_RUNS = "('queued','running','retrying')"


class LostLease(Exception):
    """The caller must discard fetched data rather than committing it."""


@dataclass(frozen=True)
class Lease:
    organization_id: UUID
    id: UUID
    token: UUID
    fence: int


@dataclass
class Work:
    job: Mapping[str, Any]
    integration: Mapping[str, Any]
    run: Mapping[str, Any] | None
    repository: Mapping[str, Any] | None
    inbox: Mapping[str, Any] | None


class PipelineRepository(IdentityRepository):
    async def enqueue_sync(
        self,
        connection: AsyncConnection,
        organization_id: UUID,
        integration_id: UUID,
        repository_id: UUID | None,
        *,
        kind: str = "history",
        requested_by: UUID | None = None,
    ) -> Mapping[str, Any]:
        if kind not in {"catalog", "history", "incremental"} or (
            (kind == "catalog") != (repository_id is None)
        ):
            raise ValueError("invalid_sync_kind")
        # Callers hold the organization lock; the integration serializes active-run creation.
        integration = await self.one(
            connection,
            "SELECT id FROM forge.integrations WHERE organization_id=:org AND id=:id FOR UPDATE",
            org=organization_id,
            id=integration_id,
        )
        if not integration:
            raise ValueError("integration_unavailable")
        active = await self.one(
            connection,
            f"""SELECT * FROM forge.sync_runs WHERE organization_id=:org
            AND integration_id=:integration
            AND repository_id IS NOT DISTINCT FROM CAST(:repo AS uuid)
            AND status IN {ACTIVE_RUNS} ORDER BY created_at DESC LIMIT 1 FOR UPDATE""",
            org=organization_id,
            integration=integration_id,
            repo=repository_id,
        )
        if active:
            # Events can arrive after this run's frozen upper bound or an already-read page.
            # Coalesce now, but durably request one fresh pass after this run completes.
            refreshed = await self.one(
                connection,
                """UPDATE forge.sync_runs SET checkpoint=jsonb_set(checkpoint,
                '{resync_requested}','true'::jsonb)
                WHERE organization_id=:org AND id=:id RETURNING *""",
                org=organization_id,
                id=active["id"],
            )
            assert refreshed
            return refreshed
        previous = await self.one(
            connection,
            """SELECT * FROM forge.sync_runs
            WHERE organization_id=:org AND integration_id=:integration
            AND repository_id IS NOT DISTINCT FROM CAST(:repo AS uuid)
            ORDER BY created_at DESC,id DESC LIMIT 1 FOR UPDATE""",
            org=organization_id,
            integration=integration_id,
            repo=repository_id,
        )
        if previous and previous["status"] in {"failed", "partial"}:
            run = await self.one(
                connection,
                """UPDATE forge.sync_runs SET status='queued',finished_at=NULL,next_retry_at=NULL,
                error_code=NULL WHERE organization_id=:org AND id=:id RETURNING *""",
                org=organization_id,
                id=previous["id"],
            )
        else:
            until = datetime.now(UTC)
            since = until - timedelta(days=90)
            if repository_id is not None and kind == "incremental":
                repo = await self.one(
                    connection,
                    "SELECT last_synced_at FROM forge.repositories "
                    "WHERE organization_id=:org AND id=:id",
                    org=organization_id,
                    id=repository_id,
                )
                if repo and repo["last_synced_at"]:
                    since = min(until, repo["last_synced_at"]) - timedelta(minutes=10)
            run = await self.one(
                connection,
                """INSERT INTO forge.sync_runs
                (organization_id,id,integration_id,repository_id,kind,status,stage,since,until,
                 checkpoint,requested_by) VALUES
                (:org,:id,:integration,:repo,:kind,'queued',:stage,:since,:until,
                 CAST(:checkpoint AS jsonb),:actor) RETURNING *""",
                org=organization_id,
                id=uuid4(),
                integration=integration_id,
                repo=repository_id,
                kind=kind,
                stage="repositories" if repository_id is None else "pull_requests",
                since=since,
                until=until,
                checkpoint=json.dumps({"page": 1}),
                actor=requested_by,
            )
        assert run
        await self.execute(
            connection,
            """INSERT INTO forge.jobs
            (organization_id,id,integration_id,sync_run_id,kind,dedup_key,state)
            VALUES (:org,:id,:integration,:run,'sync',:key,'queued')
            ON CONFLICT (organization_id,dedup_key) DO UPDATE SET state='queued',
            available_at=now(),lease_until=NULL,lease_token=NULL,fence=forge.jobs.fence+1,
            attempts=0,last_error=NULL,finished_at=NULL""",
            org=organization_id,
            id=uuid4(),
            integration=integration_id,
            run=run["id"],
            key=f"sync:{run['id']}",
        )
        return run

    async def cancel_integration(
        self, connection: AsyncConnection, org: UUID, integration_id: UUID
    ) -> None:
        await self._cancel(connection, org, "integration_id=:target", integration_id)

    async def cancel_repository(
        self, connection: AsyncConnection, org: UUID, repository_id: UUID
    ) -> None:
        await self._cancel(connection, org, "repository_id=:target", repository_id)

    async def _cancel(
        self, connection: AsyncConnection, org: UUID, condition: str, target: UUID
    ) -> None:
        await self.execute(
            connection,
            f"""UPDATE forge.sync_runs SET status='canceled',finished_at=now(),next_retry_at=NULL
            WHERE organization_id=:org AND {condition} AND status IN {ACTIVE_RUNS}""",
            org=org,
            target=target,
        )
        job_condition = (
            "integration_id=:target"
            if condition.startswith("integration_id")
            else "sync_run_id IN (SELECT id FROM forge.sync_runs "
            "WHERE organization_id=:org AND repository_id=:target) OR inbox_id IN "
            "(SELECT w.id FROM forge.webhook_inbox w JOIN forge.repositories r "
            "ON r.organization_id=w.organization_id AND r.integration_id=w.integration_id "
            "AND w.payload->'repository'->>'id'=r.provider_id::text "
            "WHERE r.organization_id=:org AND r.id=:target)"
        )
        await self.execute(
            connection,
            f"""UPDATE forge.jobs SET state='canceled',finished_at=now(),lease_until=NULL,
            lease_token=NULL,fence=fence+1 WHERE organization_id=:org AND ({job_condition})
            AND state IN ('queued','running','retry')""",
            org=org,
            target=target,
        )
        await self.execute(
            connection,
            """UPDATE forge.webhook_inbox
            SET status='ignored',reason='access_changed',processed_at=now()
            WHERE organization_id=:org AND status='queued' AND id IN
            (SELECT inbox_id FROM forge.jobs WHERE organization_id=:org AND state='canceled')""",
            org=org,
        )
        await self.execute(
            connection,
            """UPDATE forge.webhook_receipts SET status='ignored',reason='access_changed'
            WHERE organization_id=:org AND status='queued' AND delivery_id IN
            (SELECT id FROM forge.webhook_inbox WHERE organization_id=:org AND status='ignored')""",
            org=org,
        )

    async def claim(self) -> Lease | None:
        token = uuid4()
        async with self.transaction() as connection:
            row = await self.one(connection, "SELECT * FROM forge.claim_job(:token)", token=token)
        if row is None:
            return None
        return Lease(row["organization_id"], row["id"], token, row["fence"])

    async def work(self, connection: AsyncConnection, lease: Lease) -> Work | None:
        """Lock scope first, then job, matching service revocation lock order."""
        head = await self.one(
            connection,
            "SELECT integration_id FROM forge.jobs WHERE organization_id=:org AND id=:id",
            org=lease.organization_id,
            id=lease.id,
        )
        if head is None:
            raise LostLease
        integration = await self.one(
            connection,
            """SELECT i.* FROM forge.integrations i
            JOIN forge.organizations o ON o.id=i.organization_id
            WHERE i.organization_id=:org AND i.id=:id AND o.deleted_at IS NULL FOR UPDATE OF o,i""",
            org=lease.organization_id,
            id=head["integration_id"],
        )
        job = await self.one(
            connection,
            """SELECT * FROM forge.jobs WHERE organization_id=:org AND id=:id AND state='running'
            AND lease_token=:token AND fence=:fence AND lease_until>clock_timestamp() FOR UPDATE""",
            org=lease.organization_id,
            id=lease.id,
            token=lease.token,
            fence=lease.fence,
        )
        if job is None:
            raise LostLease
        run = None
        inbox = None
        repo = None
        if job["sync_run_id"]:
            run = await self.one(
                connection,
                "SELECT * FROM forge.sync_runs WHERE organization_id=:org AND id=:id FOR UPDATE",
                org=lease.organization_id,
                id=job["sync_run_id"],
            )
            if run and run["repository_id"]:
                repo = await self.one(
                    connection,
                    "SELECT * FROM forge.repositories "
                    "WHERE organization_id=:org AND id=:id FOR UPDATE",
                    org=lease.organization_id,
                    id=run["repository_id"],
                )
        elif job["inbox_id"]:
            inbox = await self.one(
                connection,
                "SELECT * FROM forge.webhook_inbox "
                "WHERE organization_id=:org AND id=:id FOR UPDATE",
                org=lease.organization_id,
                id=job["inbox_id"],
            )
            raw_repo = inbox["payload"].get("repository") if inbox else None
            provider_id = raw_repo.get("id") if isinstance(raw_repo, dict) else None
            if isinstance(provider_id, int) and not isinstance(provider_id, bool):
                repo = await self.one(
                    connection,
                    """SELECT * FROM forge.repositories WHERE organization_id=:org
                    AND integration_id=:integration AND provider_id=:provider FOR UPDATE""",
                    org=lease.organization_id,
                    integration=job["integration_id"],
                    provider=provider_id,
                )
        requires_repo = bool(run and run["repository_id"]) or bool(
            inbox and inbox["event"] in {"push", "pull_request"}
        )
        control = bool(inbox and inbox["event"] in {"installation", "installation_repositories"})
        if (
            not integration
            or integration["status"] == "disconnected"
            or (integration["status"] != "active" and not control)
            or (requires_repo and (not repo or not repo["authorized"] or not repo["selected"]))
            or (run and run["status"] not in {"queued", "running", "retrying"})
            or (not run and not inbox)
        ):
            await self.finish_job(connection, lease, state="canceled")
            if run and run["status"] in {"queued", "running", "retrying"}:
                await self.execute(
                    connection,
                    """UPDATE forge.sync_runs
                    SET status='canceled',finished_at=now(),next_retry_at=NULL
                    WHERE organization_id=:org AND id=:id""",
                    org=lease.organization_id,
                    id=run["id"],
                )
            if inbox:
                await self.finish_inbox(
                    connection, lease.organization_id, inbox["id"], "ignored", "access_changed"
                )
            return None
        return Work(job, integration, run, repo, inbox)

    async def load(self, lease: Lease) -> Work | None:
        async with self.transaction() as connection:
            await self.tenant(connection, lease.organization_id)
            await self.clear_processed_payloads(connection, lease.organization_id)
            work = await self.work(connection, lease)
            if work and work.run:
                await self.execute(
                    connection,
                    """UPDATE forge.sync_runs
                    SET status='running',started_at=COALESCE(started_at,now()),
                    next_retry_at=NULL WHERE organization_id=:org AND id=:id""",
                    org=lease.organization_id,
                    id=work.run["id"],
                )
            return work

    async def clear_processed_payloads(
        self, connection: AsyncConnection, organization_id: UUID
    ) -> None:
        """Opportunistic retention under tenant RLS; receipts and job dedup keys are retained."""
        await self.execute(
            connection,
            """WITH expired AS (
                SELECT id FROM forge.webhook_inbox WHERE organization_id=:org
                AND status='processed' AND processed_at<now()-interval '7 days'
                AND payload<>'{}'::jsonb ORDER BY processed_at,id
                LIMIT 100 FOR UPDATE SKIP LOCKED
            ) UPDATE forge.webhook_inbox SET payload='{}'::jsonb
            WHERE organization_id=:org AND id IN (SELECT id FROM expired)""",
            org=organization_id,
        )

    async def finish_job(
        self,
        connection: AsyncConnection,
        lease: Lease,
        *,
        state: str = "succeeded",
        error: str | None = None,
        delay: int = 0,
        reset_attempts: bool = False,
    ) -> None:
        row = await self.one(
            connection,
            """UPDATE forge.jobs
            SET state=:state,lease_token=NULL,lease_until=NULL,last_error=:error,
            available_at=now()+make_interval(secs=>:delay),
            attempts=CASE WHEN :reset THEN 0 ELSE attempts END,
            finished_at=CASE WHEN :terminal THEN now() ELSE NULL END
            WHERE organization_id=:org AND id=:id AND state='running' AND lease_token=:token
            AND fence=:fence AND lease_until>clock_timestamp() RETURNING id""",
            org=lease.organization_id,
            id=lease.id,
            token=lease.token,
            fence=lease.fence,
            state=state,
            terminal=state in {"succeeded", "dead", "canceled"},
            error=error,
            delay=delay,
            reset=reset_attempts,
        )
        if row is None:
            raise LostLease

    async def finish_inbox(
        self,
        connection: AsyncConnection,
        org: UUID,
        identifier: UUID,
        status: str,
        reason: str | None = None,
    ) -> None:
        await self.execute(
            connection,
            """UPDATE forge.webhook_inbox SET status=:status,reason=:reason,processed_at=now()
            WHERE organization_id=:org AND id=:id""",
            org=org,
            id=identifier,
            status=status,
            reason=reason,
        )
        await self.execute(
            connection,
            """UPDATE forge.webhook_receipts SET status=:status,reason=:reason
            WHERE organization_id=:org AND delivery_id=:id""",
            org=org,
            id=identifier,
            status=status,
            reason=reason,
        )

    async def upsert_repository(
        self,
        connection: AsyncConnection,
        org: UUID,
        integration: UUID,
        run: UUID,
        record: Mapping[str, Any],
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.repositories
            (organization_id,id,integration_id,provider_id,owner,name,full_name,html_url,description,
             language,default_branch,is_private,archived,authorized,catalog_run_id,pushed_at)
            VALUES (:org,:id,:integration,:provider_id,:owner,:name,:full_name,:html_url,
             :description,:language,:default_branch,:is_private,:archived,true,:run,:pushed_at)
            ON CONFLICT (organization_id,integration_id,provider_id) DO UPDATE SET
            owner=EXCLUDED.owner,name=EXCLUDED.name,full_name=EXCLUDED.full_name,
            html_url=EXCLUDED.html_url,description=EXCLUDED.description,language=EXCLUDED.language,
            default_branch=EXCLUDED.default_branch,is_private=EXCLUDED.is_private,
            archived=EXCLUDED.archived,authorized=true,catalog_run_id=EXCLUDED.catalog_run_id,
            pushed_at=EXCLUDED.pushed_at,updated_at=now()""",
            org=org,
            id=uuid4(),
            integration=integration,
            run=run,
            **record,
        )

    async def upsert_pull_request(
        self,
        connection: AsyncConnection,
        org: UUID,
        integration: UUID,
        repo: UUID,
        record: Mapping[str, Any],
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.pull_requests
            (organization_id,id,repository_id,provider_id,number,title,state,draft,author_login,
             head_sha,base_ref,opened_at,updated_at,closed_at,merged_at,html_url)
            VALUES (:org,:id,:repo,:provider_id,:number,:title,:state,:draft,:author_login,
             :head_sha,:base_ref,:opened_at,:updated_at,:closed_at,:merged_at,:html_url)
            ON CONFLICT (organization_id,repository_id,number) DO UPDATE SET
            provider_id=EXCLUDED.provider_id,title=EXCLUDED.title,state=EXCLUDED.state,
            draft=EXCLUDED.draft,author_login=EXCLUDED.author_login,head_sha=EXCLUDED.head_sha,
            base_ref=EXCLUDED.base_ref,updated_at=EXCLUDED.updated_at,closed_at=EXCLUDED.closed_at,
            merged_at=EXCLUDED.merged_at,html_url=EXCLUDED.html_url
            WHERE forge.pull_requests.updated_at<=EXCLUDED.updated_at""",
            org=org,
            id=uuid4(),
            repo=repo,
            **record,
        )
        await self.event(
            connection,
            org,
            integration,
            repo,
            f"pr:{repo}:{record['number']}:{record['updated_at'].isoformat()}",
            "pull_request.updated",
            record["updated_at"],
            {"number": record["number"], "state": record["state"]},
        )

    async def upsert_commit(
        self,
        connection: AsyncConnection,
        org: UUID,
        integration: UUID,
        repo: UUID,
        record: Mapping[str, Any],
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.commits
            (organization_id,id,repository_id,sha,message,author_login,authored_at,committed_at,html_url)
            VALUES (:org,:id,:repo,:sha,:message,:author_login,:authored_at,:committed_at,:html_url)
            ON CONFLICT (organization_id,repository_id,sha) DO UPDATE SET
            message=EXCLUDED.message,author_login=COALESCE(EXCLUDED.author_login,forge.commits.author_login),
            authored_at=EXCLUDED.authored_at,committed_at=EXCLUDED.committed_at,html_url=EXCLUDED.html_url""",
            org=org,
            id=uuid4(),
            repo=repo,
            **record,
        )
        await self.event(
            connection,
            org,
            integration,
            repo,
            f"commit:{repo}:{record['sha']}",
            "commit.recorded",
            record["committed_at"],
            {"sha": record["sha"]},
        )

    async def event(
        self,
        connection: AsyncConnection,
        org: UUID,
        integration: UUID,
        repo: UUID,
        source: str,
        kind: str,
        occurred: datetime,
        payload: Mapping[str, Any],
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.events
            (organization_id,id,integration_id,repository_id,source_key,kind,occurred_at,payload)
            VALUES (:org,:id,:integration,:repo,:source,:kind,:occurred,CAST(:payload AS jsonb))
            ON CONFLICT (organization_id,source_key) DO NOTHING""",
            org=org,
            id=uuid4(),
            integration=integration,
            repo=repo,
            source=source,
            kind=kind,
            occurred=occurred,
            payload=json.dumps(payload),
        )
