from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.repositories.identity import IdentityRepository

SYNC_FIELDS = (
    "id",
    "kind",
    "status",
    "stage",
    "since",
    "until",
    "repositories_processed",
    "pull_requests_processed",
    "commits_processed",
    "created_at",
    "started_at",
    "finished_at",
    "next_retry_at",
    "error_code",
)
SYNC_JSON = "jsonb_build_object(" + ",".join(f"'{key}',s.{key}" for key in SYNC_FIELDS) + ")"


class GitHubRepository(IdentityRepository):
    async def live_session(self, connection: AsyncConnection, user: UUID, session: UUID) -> bool:
        await self.lock_user(connection, user)
        row = await self.one(
            connection,
            """SELECT s.id FROM forge.auth_sessions s
            JOIN forge.users u ON u.id=s.user_id WHERE s.id=:session AND s.user_id=:user
            AND s.revoked_at IS NULL AND s.expires_at>now() AND u.email_verified
            FOR UPDATE OF s""",
            session=session,
            user=user,
        )
        return row is not None

    async def create_authorization(
        self,
        connection: AsyncConnection,
        identifier: UUID,
        state: str,
        browser: str,
        organization: UUID,
        user: UUID,
        session: UUID,
        expires: datetime,
    ) -> None:
        await self.execute(
            connection, "DELETE FROM forge.github_app_authorizations WHERE expires_at<now()"
        )
        await self.execute(
            connection,
            """UPDATE forge.github_app_authorizations
            SET completed_at=now(),token_ciphertext=NULL WHERE organization_id=:org
            AND user_id=:user AND session_id=:session AND completed_at IS NULL""",
            org=organization,
            user=user,
            session=session,
        )
        await self.execute(
            connection,
            """INSERT INTO forge.github_app_authorizations
            (id,state_hash,browser_hash,organization_id,user_id,session_id,expires_at)
            VALUES (:id,:state,:browser,:org,:user,:session,:expires)""",
            id=identifier,
            state=state,
            browser=browser,
            org=organization,
            user=user,
            session=session,
            expires=expires,
        )

    async def authorization_state(
        self, connection: AsyncConnection, state: str
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.github_app_authorizations
            WHERE state_hash=:state AND used_at IS NULL AND completed_at IS NULL
            AND expires_at>now() FOR UPDATE""",
            state=state,
        )

    async def spend_state(self, connection: AsyncConnection, identifier: UUID) -> None:
        await self.execute(
            connection,
            "UPDATE forge.github_app_authorizations SET used_at=now() WHERE id=:id",
            id=identifier,
        )

    async def store_token(
        self, connection: AsyncConnection, identifier: UUID, encrypted: str, expires: datetime
    ) -> None:
        await self.execute(
            connection,
            """UPDATE forge.github_app_authorizations
            SET token_ciphertext=:encrypted,expires_at=:expires
            WHERE id=:id AND completed_at IS NULL""",
            id=identifier,
            encrypted=encrypted,
            expires=expires,
        )

    async def authorization(
        self,
        connection: AsyncConnection,
        organization: UUID,
        user: UUID,
        session: UUID,
        identifier: UUID | None = None,
        *,
        lock: bool = False,
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.github_app_authorizations
            WHERE organization_id=:org AND user_id=:user AND session_id=:session
            AND (CAST(:id AS uuid) IS NULL OR id=CAST(:id AS uuid)) AND used_at IS NOT NULL
            AND token_ciphertext IS NOT NULL AND completed_at IS NULL AND expires_at>now()
            ORDER BY created_at DESC LIMIT 1"""
            + (" FOR UPDATE" if lock else ""),
            org=organization,
            user=user,
            session=session,
            id=identifier,
        )

    async def complete_authorization(self, connection: AsyncConnection, identifier: UUID) -> None:
        await self.execute(
            connection,
            """UPDATE forge.github_app_authorizations
            SET completed_at=now(),token_ciphertext=NULL WHERE id=:id""",
            id=identifier,
        )

    async def pending_state_row(
        self, connection: AsyncConnection, identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.github_app_authorizations
            WHERE id=:id AND used_at IS NOT NULL AND completed_at IS NULL AND expires_at>now()
            FOR UPDATE""",
            id=identifier,
        )

    async def integrations(
        self, connection: AsyncConnection, organization: UUID
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            f"""SELECT i.*,
            (SELECT {SYNC_JSON} FROM forge.sync_runs s WHERE s.organization_id=i.organization_id
             AND s.integration_id=i.id AND s.repository_id IS NULL
             ORDER BY s.created_at DESC,s.id DESC LIMIT 1) AS catalog_sync
            FROM forge.integrations i WHERE organization_id=:org ORDER BY created_at,id""",
            org=organization,
        )

    async def integration(
        self,
        connection: AsyncConnection,
        organization: UUID,
        identifier: UUID,
        *,
        lock: bool = False,
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.integrations
            WHERE organization_id=:org AND id=:id"""
            + (" FOR UPDATE" if lock else ""),
            org=organization,
            id=identifier,
        )

    async def lock_installation(
        self, connection: AsyncConnection, installation: int
    ) -> Mapping[str, Any] | None:
        await self.execute(
            connection,
            "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
            key=f"github-installation:{installation}",
        )
        return await self.one(
            connection,
            "SELECT * FROM forge.github_installation_bindings WHERE installation_id=:installation",
            installation=installation,
        )

    async def installation_integration(
        self,
        connection: AsyncConnection,
        organization: UUID,
        installation: int,
        *,
        lock: bool = False,
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.integrations
            WHERE organization_id=:org AND installation_id=:installation"""
            + (" FOR UPDATE" if lock else ""),
            org=organization,
            installation=installation,
        )

    async def bind(
        self,
        connection: AsyncConnection,
        organization: UUID,
        identifier: UUID,
        installation: int,
        login: str,
        account_type: str,
    ) -> Mapping[str, Any]:
        row = await self.one(
            connection,
            """INSERT INTO forge.integrations
            (organization_id,id,installation_id,account_login,account_type)
            VALUES (:org,:id,:installation,:login,:account_type)
            ON CONFLICT (organization_id,installation_id) DO UPDATE SET
            account_login=:login,account_type=:account_type,status='active',last_error=NULL,updated_at=now()
            RETURNING *""",
            org=organization,
            id=identifier,
            installation=installation,
            login=login,
            account_type=account_type,
        )
        assert row
        await self.execute(
            connection,
            """INSERT INTO forge.github_installation_bindings
            (installation_id,organization_id,integration_id) VALUES (:installation,:org,:id)
            ON CONFLICT (installation_id) DO NOTHING""",
            installation=installation,
            org=organization,
            id=row["id"],
        )
        return row

    async def set_status(
        self,
        connection: AsyncConnection,
        organization: UUID,
        identifier: UUID,
        status: str,
        error: str | None = None,
    ) -> None:
        await self.execute(
            connection,
            """UPDATE forge.integrations SET status=:status,
            last_error=:error,updated_at=now() WHERE organization_id=:org AND id=:id""",
            org=organization,
            id=identifier,
            status=status,
            error=error,
        )

    async def unselect_integration(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID
    ) -> None:
        await self.execute(
            connection,
            """UPDATE forge.repositories SET authorized=false,
            selected=false,updated_at=now() WHERE organization_id=:org AND integration_id=:id""",
            org=organization,
            id=identifier,
        )

    async def repositories(
        self,
        connection: AsyncConnection,
        organization: UUID,
        integration: UUID | None,
        boundary: UUID | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            f"""SELECT r.*,
            (SELECT count(*) FROM forge.pull_requests p
             WHERE p.organization_id=r.organization_id AND p.repository_id=r.id)
             AS pull_request_count,
            (SELECT count(*) FROM forge.pull_requests p
             WHERE p.organization_id=r.organization_id AND p.repository_id=r.id AND p.state='open')
             AS open_pull_request_count,
            (SELECT count(*) FROM forge.commits c
             WHERE c.organization_id=r.organization_id AND c.repository_id=r.id) AS commit_count,
            (SELECT {SYNC_JSON} FROM forge.sync_runs s
             WHERE s.organization_id=r.organization_id AND s.repository_id=r.id
             ORDER BY s.created_at DESC,s.id DESC LIMIT 1) AS latest_sync
            FROM forge.repositories r WHERE organization_id=:org
            AND ((CAST(:integration AS uuid) IS NULL AND selected) OR
                 (integration_id=CAST(:integration AS uuid) AND authorized))
            AND (CAST(:boundary AS uuid) IS NULL OR id>CAST(:boundary AS uuid))
            ORDER BY id LIMIT :limit""",
            org=organization,
            integration=integration,
            boundary=boundary,
            limit=limit,
        )

    async def repository(
        self,
        connection: AsyncConnection,
        organization: UUID,
        identifier: UUID,
        *,
        lock: bool = False,
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            "SELECT * FROM forge.repositories WHERE organization_id=:org AND id=:id"
            + (" FOR UPDATE" if lock else ""),
            org=organization,
            id=identifier,
        )

    async def select_repository(
        self, connection: AsyncConnection, organization: UUID, identifier: UUID, selected: bool
    ) -> None:
        await self.execute(
            connection,
            "UPDATE forge.repositories SET selected=:selected,updated_at=now() "
            "WHERE organization_id=:org AND id=:id",
            org=organization,
            id=identifier,
            selected=selected,
        )

    async def sync_runs(
        self,
        connection: AsyncConnection,
        organization: UUID,
        repository: UUID,
        boundary: UUID | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            """SELECT * FROM forge.sync_runs
            WHERE organization_id=:org AND repository_id=:repository
            AND (CAST(:boundary AS uuid) IS NULL OR id>CAST(:boundary AS uuid))
            ORDER BY id LIMIT :limit""",
            org=organization,
            repository=repository,
            boundary=boundary,
            limit=limit,
        )
