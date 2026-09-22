from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.repositories.identity import IdentityRepository


class OAuthRepository(IdentityRepository):
    async def create_state(
        self,
        connection: AsyncConnection,
        *,
        state_hash: str,
        browser_hash: str,
        provider: str,
        intent: str,
        return_to: str,
        user_id: UUID | None,
        session_id: UUID | None,
        expires_at: datetime,
    ) -> None:
        await self.execute(
            connection, "DELETE FROM forge.oauth_states WHERE expires_at < now()-interval '1 day'"
        )
        await self.execute(
            connection,
            """INSERT INTO forge.oauth_states
            (state_hash,browser_hash,provider,intent,return_to,user_id,session_id,expires_at)
            VALUES (:state_hash,:browser_hash,:provider,:intent,:return_to,
                :user_id,:session_id,:expires_at)""",
            state_hash=state_hash,
            browser_hash=browser_hash,
            provider=provider,
            intent=intent,
            return_to=return_to,
            user_id=user_id,
            session_id=session_id,
            expires_at=expires_at,
        )

    async def state(
        self, connection: AsyncConnection, hashed: str, provider: str
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.oauth_states WHERE state_hash=:hashed AND provider=:provider
            AND used_at IS NULL AND expires_at > now() FOR UPDATE""",
            hashed=hashed,
            provider=provider,
        )

    async def spend_state(self, connection: AsyncConnection, hashed: str) -> None:
        await self.execute(
            connection,
            "UPDATE forge.oauth_states SET used_at=now() WHERE state_hash=:hashed",
            hashed=hashed,
        )

    async def lock_identity(self, connection: AsyncConnection, provider: str, subject: str) -> None:
        # Serialize first-use races before an external identity has a row to lock.
        await self.execute(
            connection,
            "SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))",
            key=f"oauth:{provider}:{subject}",
        )

    async def external_identity(
        self, connection: AsyncConnection, provider: str, subject: str
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            "SELECT * FROM forge.external_identities WHERE provider=:provider AND subject=:subject",
            provider=provider,
            subject=subject,
        )

    async def user_identity(
        self, connection: AsyncConnection, provider: str, user_id: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            "SELECT * FROM forge.external_identities WHERE provider=:provider AND user_id=:user_id",
            provider=provider,
            user_id=user_id,
        )

    async def add_external_identity(
        self, connection: AsyncConnection, provider: str, subject: str, user_id: UUID, email: str
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.external_identities (provider,subject,user_id,email)
            VALUES (:provider,:subject,:user_id,:email)""",
            provider=provider,
            subject=subject,
            user_id=user_id,
            email=email,
        )

    async def user_by_id(
        self, connection: AsyncConnection, user_id: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection, "SELECT * FROM forge.users WHERE id=:id FOR UPDATE", id=user_id
        )

    async def locked_session(
        self, connection: AsyncConnection, session_id: UUID, user_id: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.auth_sessions WHERE id=:id AND user_id=:user_id
            AND revoked_at IS NULL AND expires_at>now() FOR UPDATE""",
            id=session_id,
            user_id=user_id,
        )

    async def connections(
        self, connection: AsyncConnection, user_id: UUID
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            """SELECT provider,email,created_at FROM forge.external_identities
            WHERE user_id=:user_id ORDER BY provider""",
            user_id=user_id,
        )
