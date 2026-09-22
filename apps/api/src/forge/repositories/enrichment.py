"""Evidence writes share their tenant transaction and lease with the pipeline."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.repositories.identity import IdentityRepository

SUBJECTS = {
    "pull_request": "pull_requests",
    "commit": "commits",
    "issue": "issues",
    "repository": "repositories",
}
PREFIXES = {
    "pull_request": ("reviews", "transitions", "commits", "issues"),
    "commit": ("files",),
    "issue": ("links",),
    "repository": ("issues",),
}


class EnrichmentRepository(IdentityRepository):
    async def queue_enrichment(
        self,
        connection: AsyncConnection,
        org: UUID,
        integration: UUID,
        repo: UUID,
        kind: str,
        subject: Mapping[str, Any],
        *,
        force: bool = False,
    ) -> None:
        if kind not in SUBJECTS:
            raise ValueError("invalid_enrichment_kind")
        stage = {
            "pull_request": "details",
            "commit": "files",
            "issue": "issue_details",
            "repository": "scan_pull_requests",
        }[kind]
        payload = {
            "kind": kind,
            "subject_id": str(subject["id"]),
            "stage": stage,
            "page": 1,
            "since": (datetime.now(UTC) - timedelta(days=90)).isoformat(),
            "revision": subject["updated_at"].isoformat()
            if kind in {"pull_request", "issue"}
            else None,
        }
        row = await self.one(
            connection,
            """INSERT INTO forge.jobs
            (organization_id,id,integration_id,repository_id,kind,dedup_key,payload)
            VALUES (:org,:id,:integration,:repo,'enrichment',:key,CAST(:payload AS jsonb))
            ON CONFLICT (organization_id,dedup_key) DO UPDATE SET state='queued',
                payload=EXCLUDED.payload,available_at=now(),lease_until=NULL,lease_token=NULL,
                fence=forge.jobs.fence+1,attempts=0,last_error=NULL,finished_at=NULL
            WHERE :force OR forge.jobs.state IN ('dead','canceled') RETURNING id""",
            org=org,
            id=uuid4(),
            integration=integration,
            repo=repo,
            key=f"enrichment:{kind}:{subject['id']}",
            payload=json.dumps(payload),
            force=force,
        )
        if row:
            for prefix in PREFIXES[kind]:
                await self.coverage(connection, org, kind, subject["id"], prefix, "pending")

    async def coverage(
        self,
        connection: AsyncConnection,
        org: UUID,
        kind: str,
        identifier: UUID,
        prefix: str,
        status: str,
        error: str | None = None,
    ) -> None:
        if kind not in SUBJECTS or prefix not in PREFIXES[kind]:
            raise ValueError("invalid_coverage")
        await self.execute(
            connection,
            f"""UPDATE forge.{SUBJECTS[kind]}
            SET {prefix}_status=:status,{prefix}_error=:error,
                {prefix}_synced_at=CASE WHEN :finished THEN now() ELSE NULL END
            WHERE organization_id=:org AND id=:id""",
            org=org,
            id=identifier,
            status=status,
            error=error,
            finished=status in {"complete", "partial", "unavailable"},
        )

    async def upsert_review(
        self,
        connection: AsyncConnection,
        org: UUID,
        repo: UUID,
        pr: UUID,
        record: Mapping[str, Any],
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.pull_request_reviews
            (organization_id,id,repository_id,pull_request_id,provider_id,reviewer_login,
             reviewer_type,state,original_state,submitted_at,approved_at,html_url)
            VALUES (:org,:id,:repo,:pr,:provider_id,:reviewer_login,:reviewer_type,:state,
                    :original_state,:submitted_at,:approved_at,:html_url)
            ON CONFLICT (organization_id,pull_request_id,provider_id) DO UPDATE SET
                reviewer_login=EXCLUDED.reviewer_login,reviewer_type=EXCLUDED.reviewer_type,
                state=EXCLUDED.state,
                original_state=COALESCE(forge.pull_request_reviews.original_state,EXCLUDED.original_state),
                submitted_at=COALESCE(EXCLUDED.submitted_at,forge.pull_request_reviews.submitted_at),
                approved_at=COALESCE(forge.pull_request_reviews.approved_at,EXCLUDED.approved_at),
                html_url=EXCLUDED.html_url,observed_at=now()""",
            org=org,
            id=uuid4(),
            repo=repo,
            pr=pr,
            **record,
        )

    async def upsert_transition(
        self,
        connection: AsyncConnection,
        org: UUID,
        repo: UUID,
        pr: UUID,
        record: Mapping[str, Any],
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.pull_request_transitions
            (organization_id,id,repository_id,pull_request_id,provider_id,source_key,kind,
             occurred_at,actor_login,actor_type,html_url)
            VALUES (:org,:id,:repo,:pr,:provider_id,:source_key,:kind,:occurred_at,
                    :actor_login,:actor_type,:html_url)
            ON CONFLICT (organization_id,pull_request_id,source_key) DO NOTHING""",
            org=org,
            id=uuid4(),
            repo=repo,
            pr=pr,
            **record,
        )
        if record.get("dismissed_review_id"):
            await self.execute(
                connection,
                """UPDATE forge.pull_request_reviews
                SET original_state=COALESCE(original_state,:original),
                    approved_at=CASE WHEN :approved THEN COALESCE(approved_at,submitted_at)
                        ELSE approved_at END,
                    dismissed_at=:occurred_at
                WHERE organization_id=:org AND pull_request_id=:pr AND provider_id=:provider""",
                org=org,
                pr=pr,
                provider=record["dismissed_review_id"],
                original=record["dismissed_state"],
                approved=record["dismissed_state"] == "APPROVED",
                occurred_at=record["occurred_at"],
            )

    async def link_commit(
        self,
        connection: AsyncConnection,
        org: UUID,
        repo: UUID,
        pr: UUID,
        commit: UUID,
        relationship: str,
        url: str,
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.pull_request_commits
            (organization_id,id,repository_id,pull_request_id,commit_id,relationship,html_url)
            VALUES (:org,:id,:repo,:pr,:commit,:relationship,:url)
            ON CONFLICT (organization_id,pull_request_id,commit_id,relationship) DO NOTHING""",
            org=org,
            id=uuid4(),
            repo=repo,
            pr=pr,
            commit=commit,
            relationship=relationship,
            url=url,
        )

    async def upsert_file(
        self,
        connection: AsyncConnection,
        org: UUID,
        repo: UUID,
        commit: UUID,
        record: Mapping[str, Any],
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.commit_files
            (organization_id,id,repository_id,commit_id,filename,previous_filename,status,
             additions,deletions,changes)
            VALUES (:org,:id,:repo,:commit,:filename,:previous_filename,:status,
                    :additions,:deletions,:changes)
            ON CONFLICT (organization_id,commit_id,filename) DO UPDATE SET
                previous_filename=EXCLUDED.previous_filename,status=EXCLUDED.status,
                additions=EXCLUDED.additions,deletions=EXCLUDED.deletions,changes=EXCLUDED.changes""",
            org=org,
            id=uuid4(),
            repo=repo,
            commit=commit,
            **record,
        )

    async def upsert_issue(
        self,
        connection: AsyncConnection,
        org: UUID,
        integration: UUID,
        repo: UUID,
        record: Mapping[str, Any],
        *,
        schedule: bool = True,
    ) -> Mapping[str, Any]:
        old = await self.one(
            connection,
            """SELECT * FROM forge.issues WHERE organization_id=:org
            AND repository_id=:repo AND number=:number FOR UPDATE""",
            org=org,
            repo=repo,
            number=record["number"],
        )
        await self.execute(
            connection,
            """INSERT INTO forge.issues
            (organization_id,id,repository_id,provider_id,number,title,state,author_login,author_type,
             opened_at,updated_at,closed_at,html_url)
            VALUES (:org,:id,:repo,:provider_id,:number,:title,:state,:author_login,:author_type,
                    :opened_at,:updated_at,:closed_at,:html_url)
            ON CONFLICT (organization_id,repository_id,number) DO UPDATE SET
                title=EXCLUDED.title,state=EXCLUDED.state,author_login=EXCLUDED.author_login,
                author_type=EXCLUDED.author_type,updated_at=EXCLUDED.updated_at,
                closed_at=EXCLUDED.closed_at,html_url=EXCLUDED.html_url
            WHERE forge.issues.updated_at<=EXCLUDED.updated_at""",
            org=org,
            id=uuid4(),
            repo=repo,
            **record,
        )
        current = await self.one(
            connection,
            """SELECT * FROM forge.issues WHERE organization_id=:org
            AND repository_id=:repo AND number=:number""",
            org=org,
            repo=repo,
            number=record["number"],
        )
        assert current
        if schedule:
            await self.queue_enrichment(
                connection,
                org,
                integration,
                repo,
                "issue",
                current,
                force=bool(old and current["updated_at"] > old["updated_at"]),
            )
        return current

    async def link_issue(
        self,
        connection: AsyncConnection,
        org: UUID,
        repo: UUID,
        issue: UUID,
        pr: UUID,
        record: Mapping[str, Any],
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.issue_pull_requests
            (organization_id,id,repository_id,issue_id,pull_request_id,relationship,
             source_key,occurred_at,html_url)
            VALUES (:org,:id,:repo,:issue,:pr,'references',:source_key,:occurred_at,:html_url)
            ON CONFLICT (organization_id,issue_id,pull_request_id,source_key) DO NOTHING""",
            org=org,
            id=uuid4(),
            repo=repo,
            issue=issue,
            pr=pr,
            source_key=record["source_key"],
            occurred_at=record["occurred_at"],
            html_url=record["html_url"],
        )
