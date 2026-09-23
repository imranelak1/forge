"""Scoped report credentials, leases and atomic JUnit evidence persistence."""

import hmac
import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from forge.domain.identity import DomainError
from forge.domain.tests import invalid_token
from forge.integrations.junit import ParsedReport
from forge.repositories.pipeline import Lease, LostLease, PipelineRepository
from forge.security.identity import now, token_hash


class TestRepository(PipelineRepository):
    async def source(
        self, connection: AsyncConnection, org: UUID, repository: UUID, *, lock: bool = False
    ) -> Mapping[str, Any] | None:
        organization = await self.one(
            connection,
            "SELECT id FROM forge.organizations WHERE id=:org AND deleted_at IS NULL"
            + (" FOR UPDATE" if lock else ""),
            org=org,
        )
        if organization is None:
            return None
        return await self.one(
            connection,
            """SELECT r.*,i.status AS integration_status
          FROM forge.repositories r JOIN forge.integrations i ON i.organization_id=r.organization_id
          AND i.id=r.integration_id WHERE r.organization_id=:org AND r.id=:repo"""
            + (" FOR UPDATE OF i,r" if lock else ""),
            org=org,
            repo=repository,
        )

    @staticmethod
    def uploadable(source: Mapping[str, Any] | None) -> bool:
        return bool(
            source
            and source["selected"]
            and source["authorized"]
            and not source["is_demo"]
            and source["integration_status"] == "active"
        )

    async def credential(
        self,
        connection: AsyncConnection,
        org: UUID,
        repository: UUID,
        identifier: UUID,
        credential: str,
    ) -> Mapping[str, Any]:
        row = await self.one(
            connection,
            """SELECT * FROM forge.service_tokens
          WHERE organization_id=:org AND repository_id=:repo AND id=:id FOR UPDATE""",
            org=org,
            repo=repository,
            id=identifier,
        )
        if (
            row is None
            or not hmac.compare_digest(row["token_hash"], token_hash(credential))
            or (
                row["scope"] != "test_reports:write"
                or row["revoked_at"]
                or row["expires_at"] <= now()
            )
        ):
            raise invalid_token()
        return row

    async def clear_payloads(self) -> None:
        async with self.transaction() as connection:
            await self.execute(connection, "SELECT forge.clear_test_payloads()")

    async def is_report(self, lease: Lease) -> bool:
        async with self.transaction() as connection:
            await self.tenant(connection, lease.organization_id)
            row = await self.one(
                connection,
                "SELECT kind FROM forge.jobs WHERE organization_id=:org AND id=:id",
                org=lease.organization_id,
                id=lease.id,
            )
            return bool(row and row["kind"] == "test_report")

    async def report_work(
        self, connection: AsyncConnection, lease: Lease
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        org = lease.organization_id
        head = await self.one(
            connection,
            """SELECT repository_id,test_report_id FROM forge.jobs
          WHERE organization_id=:org AND id=:id AND kind='test_report'""",
            org=org,
            id=lease.id,
        )
        if head is None:
            raise LostLease
        source = await self.source(connection, org, head["repository_id"], lock=True)
        token = await self.one(
            connection,
            """SELECT t.* FROM forge.service_tokens t
          JOIN forge.test_reports r ON r.organization_id=t.organization_id
            AND r.repository_id=t.repository_id AND r.service_token_id=t.id
          WHERE r.organization_id=:org AND r.id=:id FOR UPDATE OF t""",
            org=org,
            id=head["test_report_id"],
        )
        job = await self.one(
            connection,
            """SELECT * FROM forge.jobs WHERE organization_id=:org
          AND id=:id AND state='running' AND lease_token=:token AND fence=:fence
          AND lease_until>clock_timestamp() FOR UPDATE""",
            org=org,
            id=lease.id,
            token=lease.token,
            fence=lease.fence,
        )
        if job is None:
            raise LostLease
        report = await self.one(
            connection,
            "SELECT * FROM forge.test_reports WHERE organization_id=:org AND id=:id FOR UPDATE",
            org=org,
            id=head["test_report_id"],
        )
        assert report
        if (
            not self.uploadable(source)
            or not token
            or token["revoked_at"]
            or token["expires_at"] <= now()
        ):
            raise DomainError(
                409, "ingestion_canceled", "Report authorization is no longer active."
            )
        if report["payload_expires_at"] <= now() or report["payload"] is None:
            raise DomainError(409, "payload_expired", "The pending report has expired.")
        return job, report

    async def fail_report(self, lease: Lease, code: str, *, retry: bool = False) -> None:
        async with self.transaction() as connection:
            await self.tenant(connection, lease.organization_id)
            row = await self.one(
                connection,
                """SELECT * FROM forge.jobs WHERE organization_id=:org
              AND id=:id AND state='running' AND lease_token=:token AND fence=:fence
              AND lease_until>clock_timestamp() FOR UPDATE""",
                org=lease.organization_id,
                id=lease.id,
                token=lease.token,
                fence=lease.fence,
            )
            if row is None:
                raise LostLease
            retry = retry and row["attempts"] < 3
            await self.execute(
                connection,
                """UPDATE forge.test_reports
              SET status=:status,error_code=:code,payload=CASE WHEN :retry THEN payload ELSE
              NULL END,
                processed_at=CASE WHEN :retry THEN NULL ELSE now() END
              WHERE organization_id=:org AND id=:id""",
                org=lease.organization_id,
                id=row["test_report_id"],
                status="queued" if retry else "failed",
                code=code,
                retry=retry,
            )
            await self.finish_job(
                connection,
                lease,
                state="retry" if retry else "dead",
                error=code,
                delay=5 if retry else 0,
            )

    async def persist_report(
        self, connection: AsyncConnection, report: Mapping[str, Any], parsed: ParsedReport
    ) -> None:
        org, repository, identifier = (
            report["organization_id"],
            report["repository_id"],
            report["id"],
        )
        suite_ids = {suite.key: uuid4() for suite in parsed.suites}
        suite_rows = [
            {
                "org": org,
                "repo": repository,
                "report": identifier,
                "id": suite_ids[suite.key],
                "key": suite.key,
                "parent": suite_ids[suite.parent_key] if suite.parent_key else None,
                "path": json.dumps(suite.path),
                "name": suite.name,
                "ordinal": suite.ordinal,
                "declared": json.dumps(suite.declared_counts),
                **suite.counts,
            }
            for suite in parsed.suites
        ]
        await self.batch(
            connection,
            """INSERT INTO forge.test_suites
          (organization_id,id,repository_id,report_id,source_key,parent_id,path,name,ordinal,
            declared_counts,case_count,passed_count,failed_count,error_count,skipped_count)
          VALUES(:org,:id,:repo,:report,:key,:parent,CAST(:path AS jsonb),:name,:ordinal,
            CAST(:declared AS jsonb),:tests,:passed,:failed,:error,:skipped)""",
            suite_rows,
        )
        unique = {case.identity_key: case for case in parsed.cases}
        identities = [
            {
                "org": org,
                "repo": repository,
                "id": uuid4(),
                "framework": report["framework"],
                "key": key,
                "quality": case.identity_quality,
                "classname": case.classname,
                "name": case.name,
                "file": case.file,
                "parameterization": case.parameterization,
            }
            for key, case in unique.items()
        ]
        await self.batch(
            connection,
            """INSERT INTO forge.test_identities
          (organization_id,id,repository_id,framework,identity_key,identity_quality,classname,
          name,file,parameterization)
          VALUES(:org,:id,:repo,:framework,:key,:quality,:classname,:name,:file,:parameterization)
          ON CONFLICT(organization_id,repository_id,framework,identity_key) DO NOTHING""",
            identities,
        )
        mapped: dict[str, UUID] = {}
        keys = list(unique)
        for offset in range(0, len(keys), 1000):
            rows = await self.many(
                connection,
                """SELECT id,identity_key FROM forge.test_identities
              WHERE organization_id=:org AND repository_id=:repo AND framework=:framework
                AND identity_key=ANY(CAST(:keys AS text[]))""",
                org=org,
                repo=repository,
                framework=report["framework"],
                keys=keys[offset : offset + 1000],
            )
            mapped.update({row["identity_key"]: row["id"] for row in rows})
        execution_rows = [
            {
                "org": org,
                "repo": repository,
                "id": uuid4(),
                "report": identifier,
                "suite": suite_ids[case.suite_key],
                "identity": mapped[case.identity_key],
                "ordinal": case.ordinal,
                "source": case.source_ordinal,
                "retry": case.retry_ordinal,
                "final": case.is_final,
                "outcome": case.outcome,
                "duration": case.duration_seconds,
                "message": case.message,
            }
            for case in parsed.cases
        ]
        await self.batch(
            connection,
            """INSERT INTO forge.test_executions
          (organization_id,id,repository_id,report_id,suite_id,test_identity_id,ordinal,
          source_ordinal,
            retry_ordinal,is_final,outcome,duration_seconds,failure_message)
          VALUES(:org,:id,:repo,:report,:suite,:identity,:ordinal,:source,:retry,:final,:outcome,
          :duration,:message)
          """,
            execution_rows,
        )
        final = [case.duration_seconds for case in parsed.cases if case.is_final]
        duration = (
            sum(value for value in final if value is not None)
            if final and all(value is not None for value in final)
            else None
        )
        if report["supersedes_id"]:
            await self.execute(
                connection,
                """UPDATE forge.test_reports SET superseded_by_id=:new
              WHERE organization_id=:org AND id=:old AND superseded_by_id IS NULL""",
                org=org,
                old=report["supersedes_id"],
                new=identifier,
            )
        await self.execute(
            connection,
            """UPDATE forge.test_reports
          SET status='completed',error_code=NULL,warnings=CAST(:warnings AS jsonb),
          declared_total=:declared,
            case_count=:tests,execution_count=:executions,passed_count=:passed,failed_count=:failed,
            error_count=:error,skipped_count=:skipped,duration_seconds=:duration,payload=NULL,
            processed_at=now()
          WHERE organization_id=:org AND id=:id""",
            org=org,
            id=identifier,
            warnings=json.dumps(parsed.warnings),
            declared=parsed.declared_total,
            executions=parsed.execution_count,
            duration=duration,
            **parsed.counts,
        )

    @staticmethod
    async def batch(
        connection: AsyncConnection, statement: str, rows: list[dict[str, Any]]
    ) -> None:
        for offset in range(0, len(rows), 1000):
            await connection.execute(text(statement), rows[offset : offset + 1000])
