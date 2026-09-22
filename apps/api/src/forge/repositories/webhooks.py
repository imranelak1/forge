import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.repositories.pipeline import PipelineRepository


class WebhookRepository(PipelineRepository):
    async def receipt(
        self, connection: AsyncConnection, identifier: UUID
    ) -> Mapping[str, Any] | None:
        await self.execute(
            connection,
            "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
            key=f"github-delivery:{identifier}",
        )
        return await self.one(
            connection,
            "SELECT * FROM forge.webhook_receipts WHERE delivery_id=:id",
            id=identifier,
        )

    async def binding(
        self, connection: AsyncConnection, installation_id: int
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            "SELECT organization_id,integration_id FROM forge.github_installation_bindings "
            "WHERE installation_id=:id",
            id=installation_id,
        )

    async def mapped_integration(
        self,
        connection: AsyncConnection,
        organization_id: UUID,
        integration_id: UUID,
    ) -> Mapping[str, Any] | None:
        await self.tenant(connection, organization_id)
        organization = await self.one(
            connection,
            "SELECT id FROM forge.organizations WHERE id=:id AND deleted_at IS NULL FOR SHARE",
            id=organization_id,
        )
        if not organization:
            return None
        return await self.one(
            connection,
            "SELECT * FROM forge.integrations WHERE organization_id=:org AND id=:id FOR UPDATE",
            org=organization_id,
            id=integration_id,
        )

    async def selected_repository(
        self,
        connection: AsyncConnection,
        organization_id: UUID,
        integration_id: UUID,
        provider_id: int,
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            "SELECT id FROM forge.repositories WHERE organization_id=:org "
            "AND integration_id=:integration AND provider_id=:provider "
            "AND authorized AND selected FOR SHARE",
            org=organization_id,
            integration=integration_id,
            provider=provider_id,
        )

    async def create_receipt(
        self,
        connection: AsyncConnection,
        identifier: UUID,
        digest: str,
        event: str,
        state: str,
        reason: str | None,
        organization_id: UUID | None,
        integration_id: UUID | None,
    ) -> None:
        await self.execute(
            connection,
            "INSERT INTO forge.webhook_receipts "
            "(delivery_id,digest,event,status,reason,organization_id,integration_id) "
            "VALUES (:id,:digest,:event,:status,:reason,:org,:integration)",
            id=identifier,
            digest=digest,
            event=event,
            status=state,
            reason=reason,
            org=organization_id,
            integration=integration_id,
        )

    async def revoke_installation(
        self,
        connection: AsyncConnection,
        organization_id: UUID,
        integration_id: UUID,
        status: str,
    ) -> None:
        await self.execute(
            connection,
            "UPDATE forge.integrations SET status=:status,last_error='access_revoked',"
            "updated_at=now() WHERE organization_id=:org AND id=:id",
            status=status,
            org=organization_id,
            id=integration_id,
        )
        await self.cancel_integration(connection, organization_id, integration_id)
        await self.execute(
            connection,
            "UPDATE forge.repositories SET authorized=false,updated_at=now() "
            "WHERE organization_id=:org AND integration_id=:id",
            org=organization_id,
            id=integration_id,
        )

    async def revoke_repositories(
        self,
        connection: AsyncConnection,
        organization_id: UUID,
        integration_id: UUID,
        provider_ids: list[int],
    ) -> None:
        # Set-based revocation remains bounded by the body limit, not N SQL round trips.
        # Invalidate every provider response fetched before this access change, including
        # catalog pages for additions where no repository is removed.
        await self.execute(
            connection,
            "UPDATE forge.integrations SET updated_at=clock_timestamp() "
            "WHERE organization_id=:org AND id=:id",
            org=organization_id,
            id=integration_id,
        )
        await self.execute(
            connection,
            "UPDATE forge.repositories SET authorized=false,selected=false,updated_at=now() "
            "WHERE organization_id=:org AND integration_id=:id "
            "AND provider_id=ANY(CAST(:ids AS bigint[]))",
            org=organization_id,
            id=integration_id,
            ids=provider_ids,
        )
        await self.execute(
            connection,
            "UPDATE forge.jobs SET state='canceled',lease_token=NULL,lease_until=NULL,"
            "fence=fence+1,finished_at=now(),last_error='access_revoked' "
            "WHERE organization_id=:org AND integration_id=:integration "
            "AND state IN ('queued','retry','running') AND (repository_id IN ("
            "SELECT id FROM forge.repositories WHERE organization_id=:org "
            "AND integration_id=:integration AND provider_id=ANY(CAST(:ids AS bigint[]))) "
            "OR sync_run_id IN ("
            "SELECT s.id FROM forge.sync_runs s JOIN forge.repositories r "
            "ON r.organization_id=s.organization_id AND r.id=s.repository_id "
            "WHERE s.organization_id=:org AND r.integration_id=:integration "
            "AND r.provider_id=ANY(CAST(:ids AS bigint[]))) OR inbox_id IN ("
            "SELECT w.id FROM forge.webhook_inbox w JOIN forge.repositories r "
            "ON r.organization_id=w.organization_id AND r.integration_id=w.integration_id "
            "AND w.payload->'repository'->>'id'=r.provider_id::text "
            "WHERE r.organization_id=:org AND r.integration_id=:integration "
            "AND r.provider_id=ANY(CAST(:ids AS bigint[]))))",
            org=organization_id,
            integration=integration_id,
            ids=provider_ids,
        )
        await self.execute(
            connection,
            "UPDATE forge.webhook_inbox SET status='ignored',reason='access_revoked',"
            "processed_at=now(),payload='{}'::jsonb WHERE organization_id=:org "
            "AND integration_id=:integration AND status='queued' AND id IN ("
            "SELECT inbox_id FROM forge.jobs WHERE organization_id=:org "
            "AND integration_id=:integration AND state='canceled')",
            org=organization_id,
            integration=integration_id,
        )
        await self.execute(
            connection,
            "UPDATE forge.webhook_receipts SET status='ignored',reason='access_revoked' "
            "WHERE organization_id=:org AND integration_id=:integration AND status='queued' "
            "AND delivery_id IN (SELECT id FROM forge.webhook_inbox "
            "WHERE organization_id=:org AND integration_id=:integration AND status='ignored')",
            org=organization_id,
            integration=integration_id,
        )
        await self.execute(
            connection,
            "UPDATE forge.sync_runs SET status='canceled',finished_at=now(),"
            "error_code='access_revoked',next_retry_at=NULL WHERE organization_id=:org "
            "AND status IN ('queued','running','retrying') AND repository_id IN ("
            "SELECT id FROM forge.repositories WHERE organization_id=:org "
            "AND integration_id=:integration AND provider_id=ANY(CAST(:ids AS bigint[])))",
            org=organization_id,
            integration=integration_id,
            ids=provider_ids,
        )

    async def accept_inbox(
        self,
        connection: AsyncConnection,
        organization_id: UUID,
        integration_id: UUID,
        identifier: UUID,
        payload: dict[str, Any],
        event: str,
        state: str,
        reason: str | None,
    ) -> None:
        await self.execute(
            connection,
            "INSERT INTO forge.webhook_inbox "
            "(organization_id,id,integration_id,payload,event,status,reason,processed_at) "
            "VALUES (:org,:id,:integration,CAST(:payload AS jsonb),:event,:status,:reason,"
            "CASE WHEN :processed THEN now() END)",
            org=organization_id,
            id=identifier,
            integration=integration_id,
            payload=json.dumps(payload) if state == "queued" else "{}",
            event=event,
            status=state,
            reason=reason,
            processed=state == "processed",
        )
        if state == "queued":
            await self.execute(
                connection,
                "INSERT INTO forge.jobs "
                "(organization_id,id,integration_id,inbox_id,kind,dedup_key) "
                "VALUES (:org,:id,:integration,:inbox,'webhook',:dedup)",
                org=organization_id,
                id=uuid4(),
                integration=integration_id,
                inbox=identifier,
                dedup=f"webhook:{identifier}",
            )
        else:
            await self.execute(
                connection,
                "UPDATE forge.webhook_receipts SET status=:status,reason=:reason "
                "WHERE delivery_id=:id",
                status=state,
                reason=reason,
                id=identifier,
            )
