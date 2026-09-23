"""Verified administration and machine-only intake for bounded test reports."""

import hashlib
import json
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from forge.domain.identity import Actor, DomainError, not_found, require_manager
from forge.domain.tests import (
    DEFAULT_POLICY,
    parse_credential,
    payload_cipher,
    policy_summary,
    receipt,
    token_summary,
)
from forge.repositories.tests import TestRepository
from forge.security.identity import now, opaque_token, token_hash
from forge.services.identity import IdentityService
from forge.services.organizations import OrganizationService


class TestService:
    def __init__(self, identity: IdentityService) -> None:
        self.identity = identity
        self.organizations = OrganizationService(identity)
        self.repository = TestRepository(identity.repository.engine)
        self.cipher = payload_cipher(identity.tokens.key)

    async def context(
        self, connection: Any, actor: Actor, org: UUID, repository: UUID, *, manage: bool = False
    ) -> Any:
        _, member = await self.organizations.context(connection, actor, org, lock=manage)
        if manage:
            require_manager(member["role"])
            if not actor.email_verified:
                raise DomainError(
                    403, "email_unverified", "Verify your email before changing test ingestion."
                )
        source = await self.repository.source(connection, org, repository, lock=manage)
        if source is None:
            raise not_found()
        return source

    async def tokens(
        self, actor: Actor, org: UUID, repository: UUID, limit: int, cursor: str | None
    ) -> dict[str, Any]:
        scope = f"service-tokens:{org}:{repository}:{limit}"
        boundary = self.identity.tokens.boundary(cursor, scope)
        async with self.repository.transaction(actor.user_id) as connection:
            await self.context(connection, actor, org, repository)
            rows = await self.repository.many(
                connection,
                """SELECT * FROM forge.service_tokens
              WHERE organization_id=:org AND repository_id=:repo
              AND(CAST(:boundary AS uuid) IS NULL OR id>CAST(:boundary AS uuid))
              ORDER BY id LIMIT :limit""",
                org=org,
                repo=repository,
                boundary=boundary,
                limit=limit + 1,
            )
        page = self.identity.page(rows[:limit], len(rows) > limit, scope)
        return {
            "items": [token_summary(row) for row in rows[:limit]],
            "next_cursor": page["page"]["next_cursor"],
        }

    async def create_token(
        self, actor: Actor, org: UUID, repository: UUID, name: str, days: int
    ) -> dict[str, Any]:
        identifier = uuid4()
        raw = f"forge_ci_{identifier.hex}.{opaque_token()}"
        async with self.repository.transaction(actor.user_id) as connection:
            source = await self.context(connection, actor, org, repository, manage=True)
            if not self.repository.uploadable(source):
                raise DomainError(
                    409,
                    "repository_unavailable",
                    "Select an authorized repository with an active connection.",
                )
            count = await self.repository.one(
                connection,
                """SELECT count(*) AS count FROM forge.service_tokens
              WHERE organization_id=:org AND repository_id=:repo AND revoked_at IS NULL AND
              expires_at>now()""",
                org=org,
                repo=repository,
            )
            if count and count["count"] >= 20:
                raise DomainError(
                    409, "token_limit", "Revoke an unused token before creating another."
                )
            row = await self.repository.one(
                connection,
                """INSERT INTO forge.service_tokens
              (organization_id,id,repository_id,name,token_hash,token_prefix,scope,created_by,
              expires_at)
              VALUES(:org,:id,:repo,:name,:hash,:prefix,'test_reports:write',:actor,:expires)
              RETURNING *""",
                org=org,
                id=identifier,
                repo=repository,
                name=name,
                hash=token_hash(raw),
                prefix=f"forge_ci_{identifier.hex[:8]}",
                actor=actor.user_id,
                expires=now() + timedelta(days=days),
            )
            await self.repository.audit(
                connection, uuid4(), org, actor.user_id, "service_token.created", identifier
            )
        assert row
        return {"token": token_summary(row), "credential": raw}

    async def revoke_token(self, actor: Actor, org: UUID, identifier: UUID) -> None:
        async with self.repository.transaction(actor.user_id) as connection:
            await self.organizations.context(connection, actor, org, lock=True)
            row = await self.repository.one(
                connection,
                "SELECT * FROM forge.service_tokens WHERE organization_id=:org AND id=:id",
                org=org,
                id=identifier,
            )
            if row is None:
                raise not_found()
            await self.context(connection, actor, org, row["repository_id"], manage=True)
            await self.repository.execute(
                connection,
                "UPDATE forge.service_tokens SET revoked_at=coalesce(revoked_at,now()) "
                "WHERE organization_id=:org AND id=:id",
                org=org,
                id=identifier,
            )
            await self.repository.execute(
                connection,
                """UPDATE forge.jobs SET state='canceled',
              lease_token=NULL,lease_until=NULL,fence=fence+1,finished_at=now()
              WHERE organization_id=:org AND kind='test_report' AND state IN('queued','running',
              'retry')
              AND test_report_id IN(SELECT id FROM forge.test_reports
                WHERE organization_id=:org AND service_token_id=:id)""",
                org=org,
                id=identifier,
            )
            await self.repository.execute(
                connection,
                """UPDATE forge.test_reports SET payload=NULL,
              status='failed',error_code='token_revoked',processed_at=now()
              WHERE organization_id=:org AND service_token_id=:id AND status IN('queued',
              'processing')""",
                org=org,
                id=identifier,
            )
            if row["revoked_at"] is None:
                await self.repository.audit(
                    connection, uuid4(), org, actor.user_id, "service_token.revoked", identifier
                )

    async def policy(
        self, actor: Actor, org: UUID, repository: UUID, changes: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with self.repository.transaction(actor.user_id) as connection:
            await self.context(connection, actor, org, repository, manage=changes is not None)
            row = await self.repository.one(
                connection,
                "SELECT * FROM forge.test_policies "
                "WHERE organization_id=:org AND repository_id=:repo",
                org=org,
                repo=repository,
            )
            if changes is not None:
                values = {**DEFAULT_POLICY, **(dict(row) if row else {}), **changes}
                if (
                    not changes
                    or not 0 < values["failure_rate_low"] < values["failure_rate_high"] < 1
                ):
                    raise DomainError(
                        422,
                        "invalid_test_policy",
                        "Choose a nonempty policy with ordered failure-rate bounds.",
                    )
                row = await self.repository.one(
                    connection,
                    """INSERT INTO forge.test_policies
                  (organization_id,id,repository_id,window_days,min_executions,failure_rate_low,
                  failure_rate_high,
                    min_transitions,excluded_branches,updated_by,version)
                  VALUES(:org,:id,:repo,:days,:minimum,:low,:high,:flips,CAST(:branches AS
                  jsonb),:actor,2)
                  ON CONFLICT(organization_id,repository_id) DO UPDATE SET
                  window_days=EXCLUDED.window_days,
                    min_executions=EXCLUDED.min_executions,
                    failure_rate_low=EXCLUDED.failure_rate_low,
                    failure_rate_high=EXCLUDED.failure_rate_high,
                    min_transitions=EXCLUDED.min_transitions,
                    excluded_branches=EXCLUDED.excluded_branches,updated_by=EXCLUDED.updated_by,
                    updated_at=now(),version=forge.test_policies.version+1 RETURNING *""",
                    org=org,
                    id=uuid4(),
                    repo=repository,
                    days=values["window_days"],
                    minimum=values["min_executions"],
                    low=values["failure_rate_low"],
                    high=values["failure_rate_high"],
                    flips=values["min_transitions"],
                    branches=json.dumps(values["excluded_branches"]),
                    actor=actor.user_id,
                )
                await self.repository.audit(
                    connection, uuid4(), org, actor.user_id, "test_policy.updated", repository
                )
        return policy_summary(row, repository)

    async def authenticate_upload(
        self, org: UUID, repository: UUID, header: str | None
    ) -> tuple[UUID, str]:
        identifier, raw = parse_credential(header)
        async with self.repository.transaction() as connection:
            await self.repository.tenant(connection, org)
            source = await self.repository.source(connection, org, repository, lock=True)
            await self.repository.credential(connection, org, repository, identifier, raw)
            if not self.repository.uploadable(source):
                raise DomainError(
                    409, "repository_unavailable", "Repository upload access is unavailable."
                )
        return identifier, raw

    async def upload(
        self,
        org: UUID,
        repository: UUID,
        authentication: tuple[UUID, str],
        payload: bytes,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        token_id, raw = authentication
        digest = hashlib.sha256(payload).hexdigest()
        async with self.repository.transaction() as connection:
            await self.repository.tenant(connection, org)
            source = await self.repository.source(connection, org, repository, lock=True)
            await self.repository.credential(connection, org, repository, token_id, raw)
            if not self.repository.uploadable(source):
                raise DomainError(
                    409, "repository_unavailable", "Repository upload access is unavailable."
                )
            assert source
            workflow = await self.repository.one(
                connection,
                """SELECT * FROM forge.workflow_runs
              WHERE organization_id=:org AND repository_id=:repo AND provider_run_id=:provider
                AND run_attempt=:attempt""",
                org=org,
                repo=repository,
                provider=metadata["workflow_run_id"],
                attempt=metadata["run_attempt"],
            )
            if workflow is None:
                raise DomainError(
                    422,
                    "workflow_not_imported",
                    "Sync the matching workflow attempt before uploading its report.",
                )
            if metadata.get("commit_sha") and metadata["commit_sha"] != workflow["head_sha"]:
                raise DomainError(
                    409, "commit_mismatch", "The report commit must match the workflow attempt."
                )
            rows = await self.repository.many(
                connection,
                """SELECT * FROM forge.test_reports
              WHERE organization_id=:org AND repository_id=:repo AND workflow_run_id=:workflow
                AND report_key=:key AND shard=:shard ORDER BY received_at,id FOR UPDATE""",
                org=org,
                repo=repository,
                workflow=workflow["id"],
                key=metadata["report_key"],
                shard=metadata["shard"],
            )
            for existing in rows:
                if existing["content_sha256"] == digest:
                    if (
                        existing["framework"] != metadata["framework"]
                        or existing["environment"] != metadata["environment"]
                    ):
                        raise DomainError(
                            409,
                            "report_metadata_conflict",
                            "The existing report has different metadata.",
                        )
                    return receipt(existing, True)
            if any(row["status"] in {"queued", "processing"} for row in rows):
                raise DomainError(
                    409, "report_processing", "Wait for the pending report before correcting it."
                )
            active = next(
                (
                    row
                    for row in reversed(rows)
                    if row["superseded_by_id"] is None and row["status"] == "completed"
                ),
                rows[-1] if rows else None,
            )
            supersedes = metadata.get("supersedes")
            if (active is not None and supersedes != active["id"]) or (
                active is None and supersedes is not None
            ):
                raise DomainError(
                    409,
                    "report_conflict",
                    "A correction must explicitly supersede the current report.",
                )
            if (
                await self.repository.rate(connection, token_hash(f"test-upload:{token_id}"), 900)
                > 120
            ):
                raise DomainError(
                    429, "rate_limited", "This upload token has reached its report rate limit."
                )
            pending = await self.repository.one(
                connection,
                """SELECT count(*) AS count FROM forge.test_reports
              WHERE organization_id=:org AND repository_id=:repo AND status IN('queued',
              'processing')""",
                org=org,
                repo=repository,
            )
            if pending and pending["count"] >= 20:
                raise DomainError(
                    429,
                    "report_queue_full",
                    "Wait for pending reports to finish before uploading more.",
                )
            identifier, received = uuid4(), now()
            encrypted = self.cipher.encrypt(payload)
            row = await self.repository.one(
                connection,
                """INSERT INTO forge.test_reports
              (organization_id,id,repository_id,workflow_run_id,service_token_id,report_key,
              shard,framework,
                environment,branch,commit_sha,content_sha256,size_bytes,supersedes_id,received_at,
                occurred_at,time_source,payload_expires_at,payload)
              VALUES(:org,:id,:repo,:workflow,:token,:key,:shard,:framework,:environment,:branch,
              :sha,
                :hash,:size,:supersedes,:received,:occurred,:time_source,:expires,:payload)
                RETURNING *""",
                org=org,
                id=identifier,
                repo=repository,
                workflow=workflow["id"],
                token=token_id,
                key=metadata["report_key"],
                shard=metadata["shard"],
                framework=metadata["framework"],
                environment=metadata["environment"],
                branch=workflow["head_branch"],
                sha=workflow["head_sha"],
                hash=digest,
                size=len(payload),
                supersedes=supersedes,
                received=received,
                occurred=workflow["completed_at"] or received,
                time_source="workflow_completion" if workflow["completed_at"] else "received",
                expires=received + timedelta(days=1),
                payload=encrypted,
            )
            await self.repository.execute(
                connection,
                """INSERT INTO forge.jobs
              (organization_id,id,integration_id,repository_id,test_report_id,kind,dedup_key)
              VALUES(:org,:id,:integration,:repo,:report,'test_report',:key)""",
                org=org,
                id=uuid4(),
                integration=source["integration_id"],
                repo=repository,
                report=identifier,
                key=f"test-report:{identifier}",
            )
            await self.repository.execute(
                connection,
                "UPDATE forge.service_tokens SET last_used_at=now() "
                "WHERE organization_id=:org AND id=:id",
                org=org,
                id=token_id,
            )
        assert row
        return receipt(row)
