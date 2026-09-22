"""One page per fenced lease; no provider credentials are stored in durable jobs."""

import asyncio
import json
import logging
import random
import re
import signal
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.config import Settings
from forge.domain import github as normalize
from forge.integrations.github import GitHubApp, GitHubFailure
from forge.observability.logging import configure_logging
from forge.repositories.database import create_database_engine
from forge.repositories.pipeline import Lease, LostLease, PipelineRepository, Work

MAX_ATTEMPTS = 8
MAX_PAGES = 100
JOB_TIMEOUT_SECONDS = 50.0
FAILURE_TIMEOUT_SECONDS = 5.0
ACCESS_FAILURES = {
    "not_configured",
    "credentials_rejected",
    "access_denied",
    "installation_mismatch",
    "installation_suspended",
    "permissions_required",
}
logger = logging.getLogger("forge.worker")


def retry_delay(attempt: int, retry_after: int | None = None) -> int:
    backoff = min(3600, 1 << min(12, max(1, attempt)))
    jittered = backoff + random.randint(0, max(1, backoff // 4))
    return max(jittered, min(86400, max(1, retry_after or 0)))


@dataclass
class Page:
    records: list[dict[str, Any]] = field(default_factory=list)
    stage: str = ""
    page: int = 1
    done: bool = False
    reconcile: bool = False
    reactivate: bool = False


class GitHubWorker:
    def __init__(self, repository: PipelineRepository, provider: GitHubApp) -> None:
        self.repository = repository
        self.provider = provider

    @staticmethod
    def log(event: str, lease: Lease, error_code: str | None = None) -> None:
        logger.info(
            event,
            extra={
                "organization_id": str(lease.organization_id),
                "job_id": str(lease.id),
                "fence": lease.fence,
                "error_code": error_code,
            },
        )

    async def run_once(self) -> bool:
        lease = await self.repository.claim()
        if lease is None:
            return False
        try:
            async with asyncio.timeout(JOB_TIMEOUT_SECONDS):
                work = await self.repository.load(lease)
                if work is None:
                    self.log("github.job.canceled", lease)
                    return True
                # Repeated crashes also count toward the finite attempt budget.
                if work.job["attempts"] > MAX_ATTEMPTS:
                    raise GitHubFailure("attempts_exhausted")
                page = await self.fetch(work)
                outcome = await self.persist(lease, work, page)
            self.log(f"github.job.{outcome}", lease)
        except TimeoutError:
            await self.failed(lease, GitHubFailure("processing_timeout", retryable=True))
        except LostLease:
            self.log("github.job.discarded", lease, "stale_lease")
        except GitHubFailure as error:
            await self.failed(lease, error)
        except (ValueError, TypeError, KeyError, OverflowError):
            await self.failed(lease, GitHubFailure("invalid_response"))
        return True

    async def fetch(self, work: Work) -> Page:
        if work.inbox:
            return await self.fetch_webhook(work)
        assert work.run
        run = work.run
        number = run["checkpoint"].get("page", 1)
        if type(number) is not int or not 1 <= number <= MAX_PAGES:
            raise GitHubFailure("capacity_exceeded")
        token = await self.provider.installation_token(work.integration["installation_id"])
        stage = run["stage"]
        if stage == "repositories":
            values = await self.provider.repositories(token, number)
            return Page(
                [normalize.repository(value) for value in values],
                stage,
                number,
                done=len(values) < 100,
            )
        assert work.repository
        repo = work.repository
        if stage == "pull_requests":
            values = await self.provider.pull_requests(token, repo["owner"], repo["name"], number)
            records = [normalize.pull_request(value, repo["full_name"]) for value in values]
            # GitHub orders this endpoint by descending updated_at, so older rows close this stage.
            done = len(values) < 100 or any(row["updated_at"] < run["since"] for row in records)
            return Page(
                [row for row in records if row["updated_at"] >= run["since"]], stage, number, done
            )
        if stage != "commits":
            raise GitHubFailure("invalid_checkpoint")
        values = await self.provider.commits(
            token,
            repo["owner"],
            repo["name"],
            number,
            run["since"].isoformat(),
            run["until"].isoformat(),
        )
        records = [normalize.commit(value, repo["full_name"]) for value in values]
        return Page(
            [row for row in records if run["since"] <= row["committed_at"] <= run["until"]],
            stage,
            number,
            done=len(values) < 100,
        )

    async def fetch_webhook(self, work: Work) -> Page:
        assert work.inbox
        event, payload = work.inbox["event"], work.inbox["payload"]
        if event in {"installation", "installation_repositories"}:
            await self.provider.installation(work.integration["installation_id"])
            return Page(done=True, reconcile=True, reactivate=True)
        assert work.repository
        repo = work.repository
        if event == "pull_request":
            number = normalize.positive_id(payload.get("number"))
            token = await self.provider.installation_token(work.integration["installation_id"])
            value = await self.provider.pull_request(token, repo["owner"], repo["name"], number)
            row = normalize.pull_request(value, repo["full_name"])
            if row["number"] != number:
                raise GitHubFailure("invalid_response")
            return Page([row], "pull_requests", done=True)
        if event != "push":
            raise GitHubFailure("unsupported_event")
        values = payload.get("commits")
        if not isinstance(values, list) or len(values) > 2048:
            raise GitHubFailure("invalid_response")
        records = [
            normalize.commit(normalize.object_value(value), repo["full_name"], webhook=True)
            for value in values
        ]
        # Payload truncation is provider-defined and can change. Always reconcile a push through
        # the bounded default-branch API as well, coalescing repeated pushes into one active run.
        return Page(records, "commits", done=True, reconcile=True)

    async def persist(self, lease: Lease, original: Work, page: Page) -> str:
        repository = self.repository
        async with repository.transaction() as connection:
            await repository.tenant(connection, lease.organization_id)
            work = await repository.work(connection, lease)
            if work is None:
                return "canceled"
            if work.integration["updated_at"] != original.integration["updated_at"]:
                raise LostLease
            org, integration = lease.organization_id, work.integration["id"]
            if page.reactivate:
                await repository.execute(
                    connection,
                    """UPDATE forge.integrations
                    SET status='active',last_error=NULL,updated_at=now()
                    WHERE organization_id=:org AND id=:id AND status<>'disconnected'""",
                    org=org,
                    id=integration,
                )
            for row in page.records:
                if page.stage == "repositories":
                    assert work.run
                    await repository.upsert_repository(
                        connection, org, integration, work.run["id"], row
                    )
                elif page.stage == "pull_requests":
                    assert work.repository
                    await repository.upsert_pull_request(
                        connection, org, integration, work.repository["id"], row
                    )
                elif page.stage == "commits":
                    assert work.repository
                    await repository.upsert_commit(
                        connection, org, integration, work.repository["id"], row
                    )
            if work.inbox:
                if page.reconcile:
                    await repository.enqueue_sync(
                        connection,
                        org,
                        integration,
                        work.repository["id"] if work.repository else None,
                        kind="incremental" if work.repository else "catalog",
                    )
                await repository.finish_inbox(connection, org, work.inbox["id"], "processed")
                await repository.finish_job(connection, lease)
                return "completed"
            assert work.run
            run = work.run
            if page.stage == "repositories" and page.done:
                removed = await repository.many(
                    connection,
                    """UPDATE forge.repositories
                    SET authorized=false,selected=false,updated_at=now()
                    WHERE organization_id=:org AND integration_id=:integration AND authorized
                    AND catalog_run_id IS DISTINCT FROM :run RETURNING id""",
                    org=org,
                    integration=integration,
                    run=run["id"],
                )
                for removed_repo in removed:
                    await repository.cancel_repository(connection, org, removed_repo["id"])
            finished = page.done and page.stage in {"repositories", "commits"}
            next_stage = "commits" if page.done and page.stage == "pull_requests" else page.stage
            checkpoint = dict(run["checkpoint"])
            checkpoint["page"] = 1 if next_stage != page.stage else page.page + 1
            follow_up = finished and checkpoint.pop("resync_requested", False)
            if not finished and run["checkpoint"].get("resync_requested"):
                checkpoint["resync_requested"] = True
            counter = {
                "repositories": "repositories_processed",
                "pull_requests": "pull_requests_processed",
                "commits": "commits_processed",
            }[page.stage]
            await repository.execute(
                connection,
                f"""UPDATE forge.sync_runs SET status=:status,stage=:stage,
                checkpoint=CAST(:checkpoint AS jsonb),{counter}={counter}+:count,
                finished_at=CASE WHEN :finished THEN now() ELSE NULL END,
                next_retry_at=NULL,error_code=NULL WHERE organization_id=:org AND id=:id""",
                org=org,
                id=run["id"],
                status="succeeded" if finished else "queued",
                stage=next_stage,
                checkpoint=json.dumps(checkpoint),
                count=len(page.records),
                finished=finished,
            )
            if finished and work.repository:
                await repository.execute(
                    connection,
                    """UPDATE forge.repositories SET last_synced_at=GREATEST(last_synced_at,:until),
                    updated_at=now() WHERE organization_id=:org AND id=:id""",
                    org=org,
                    id=work.repository["id"],
                    until=run["until"],
                )
            if follow_up:
                await repository.enqueue_sync(
                    connection,
                    org,
                    integration,
                    work.repository["id"] if work.repository else None,
                    kind="incremental" if work.repository else "catalog",
                )
            await repository.finish_job(
                connection, lease, state="succeeded" if finished else "queued", reset_attempts=True
            )
        return "completed" if finished else "checkpointed"

    async def failed(self, lease: Lease, error: GitHubFailure) -> None:
        try:
            async with asyncio.timeout(FAILURE_TIMEOUT_SECONDS):
                await self.record_failure(lease, error)
        except TimeoutError:
            # Leave the durable lease to expire if the database cannot record the failure.
            # The next claim increments attempts; never log driver/provider exception text.
            self.log("github.job.failure_deferred", lease, "processing_timeout")

    async def record_failure(self, lease: Lease, error: GitHubFailure) -> None:
        repository = self.repository
        code = error.code if re.fullmatch(r"[a-z_]{1,80}", error.code) else "provider_failure"
        try:
            async with repository.transaction() as connection:
                await repository.tenant(connection, lease.organization_id)
                work = await repository.work(connection, lease)
                if work is None:
                    return
                retrying = error.retryable and work.job["attempts"] < MAX_ATTEMPTS
                delay = retry_delay(work.job["attempts"], error.retry_after) if retrying else 0
                if work.run:
                    partial = any(
                        work.run[column] > 0
                        for column in (
                            "repositories_processed",
                            "pull_requests_processed",
                            "commits_processed",
                        )
                    )
                    status = "retrying" if retrying else "partial" if partial else "failed"
                    await repository.execute(
                        connection,
                        """UPDATE forge.sync_runs SET status=:status,error_code=:code,
                        next_retry_at=CASE WHEN :retrying
                            THEN now()+make_interval(secs=>:delay) ELSE NULL END,
                        finished_at=CASE WHEN :retrying THEN NULL ELSE now() END
                        WHERE organization_id=:org AND id=:id""",
                        org=lease.organization_id,
                        id=work.run["id"],
                        status=status,
                        code=code,
                        retrying=retrying,
                        delay=delay,
                    )
                if work.inbox and not retrying:
                    await repository.finish_inbox(
                        connection, lease.organization_id, work.inbox["id"], "failed", code
                    )
                if not retrying and code in ACCESS_FAILURES:
                    await repository.execute(
                        connection,
                        """UPDATE forge.integrations
                        SET status=:status,last_error=:code,updated_at=now()
                        WHERE organization_id=:org AND id=:id AND status<>'disconnected'""",
                        org=lease.organization_id,
                        id=work.integration["id"],
                        code=code,
                        status="suspended"
                        if code == "installation_suspended"
                        else "needs_attention",
                    )
                await repository.finish_job(
                    connection,
                    lease,
                    state="retry" if retrying else "dead",
                    error=code,
                    delay=delay,
                )
            self.log("github.job.retry" if retrying else "github.job.failed", lease, code)
        except LostLease:
            self.log("github.job.discarded", lease, "stale_lease")


async def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    engine = create_database_engine(settings)
    provider = GitHubApp(settings)
    worker = GitHubWorker(PipelineRepository(engine), provider)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for value in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(value, stop.set)
        except NotImplementedError:
            signal.signal(value, lambda *_: loop.call_soon_threadsafe(stop.set))
    try:
        while not stop.is_set():
            try:
                processed = await worker.run_once()
                await asyncio.to_thread(Path("/tmp/forge-worker-heartbeat").touch)
            except Exception:
                # SQLAlchemy hides parameters; do not print unknown provider/driver exception text.
                logger.error("github_worker_iteration_failed")
                processed = False
            if not processed:
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=2)
    finally:
        await provider.client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
