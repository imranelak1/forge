from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class IdentityRepository:
    """All identity SQL stays here; transaction context never survives a pooled connection."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    @asynccontextmanager
    async def transaction(self, user_id: UUID | None = None) -> AsyncIterator[AsyncConnection]:
        async with self.engine.begin() as connection:
            # Clear explicitly too, defending against accidental SET instead of SET LOCAL.
            await connection.execute(text("SELECT set_config('forge.organization_id', '', true)"))
            await connection.execute(
                text("SELECT set_config('forge.user_id', :value, true)"),
                {"value": str(user_id) if user_id else ""},
            )
            yield connection

    async def tenant(self, connection: AsyncConnection, organization_id: UUID) -> None:
        await connection.execute(
            text("SELECT set_config('forge.organization_id', :value, true)"),
            {"value": str(organization_id)},
        )

    async def one(
        self, connection: AsyncConnection, sql: str, **parameters: Any
    ) -> Mapping[str, Any] | None:
        result = await connection.execute(text(sql), parameters)
        row = result.mappings().first()
        return dict(row) if row else None

    async def many(
        self, connection: AsyncConnection, sql: str, **parameters: Any
    ) -> list[Mapping[str, Any]]:
        result = await connection.execute(text(sql), parameters)
        return [dict(row) for row in result.mappings().all()]

    async def execute(self, connection: AsyncConnection, sql: str, **parameters: Any) -> None:
        await connection.execute(text(sql), parameters)

    async def user_by_email(
        self, connection: AsyncConnection, email: str, *, lock: bool = False
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            "SELECT * FROM forge.users WHERE email=:email" + (" FOR UPDATE" if lock else ""),
            email=email,
        )

    async def create_user(
        self,
        connection: AsyncConnection,
        identifier: UUID,
        name: str,
        email: str,
        password_hash: str | None,
        *,
        verified: bool = False,
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.users (id,name,email,password_hash,email_verified)
                VALUES (:id,:name,:email,:password_hash,:verified)""",
            id=identifier,
            name=name,
            email=email,
            password_hash=password_hash,
            verified=verified,
        )

    async def lock_user(self, connection: AsyncConnection, user_id: UUID) -> None:
        await self.one(connection, "SELECT id FROM forge.users WHERE id=:id FOR UPDATE", id=user_id)

    async def set_password(self, connection: AsyncConnection, user_id: UUID, encoded: str) -> None:
        await self.execute(
            connection,
            "UPDATE forge.users SET password_hash=:encoded WHERE id=:id",
            id=user_id,
            encoded=encoded,
        )

    async def create_session(
        self,
        connection: AsyncConnection,
        identifier: UUID,
        user_id: UUID,
        csrf_hash: str,
        expires_at: datetime,
        refresh_hash: str,
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.auth_sessions (id,user_id,csrf_hash,expires_at)
                VALUES (:id,:user_id,:csrf_hash,:expires_at)""",
            id=identifier,
            user_id=user_id,
            csrf_hash=csrf_hash,
            expires_at=expires_at,
        )
        await self.add_refresh(connection, identifier, refresh_hash)

    async def add_refresh(self, connection: AsyncConnection, session_id: UUID, hashed: str) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.refresh_tokens (token_hash,session_id)
            VALUES (:hashed,:id)""",
            hashed=hashed,
            id=session_id,
        )

    async def session(
        self, connection: AsyncConnection, identifier: UUID, user_id: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT u.*,s.id AS session_id,s.csrf_hash,s.expires_at
            FROM forge.auth_sessions s JOIN forge.users u ON u.id=s.user_id
            WHERE s.id=:id AND s.user_id=:user_id
            AND s.revoked_at IS NULL AND s.expires_at>now()""",
            id=identifier,
            user_id=user_id,
        )

    async def refresh(
        self, connection: AsyncConnection, hashed: str, *, lock: bool = False
    ) -> Mapping[str, Any] | None:
        suffix = " FOR UPDATE OF s,t" if lock else ""
        return await self.one(
            connection,
            """SELECT u.*,s.id AS session_id,s.csrf_hash,
            s.expires_at,s.revoked_at,t.used_at FROM forge.refresh_tokens t
            JOIN forge.auth_sessions s ON s.id=t.session_id JOIN forge.users u ON u.id=s.user_id
            WHERE t.token_hash=:hashed"""
            + suffix,
            hashed=hashed,
        )

    async def spend_refresh(self, connection: AsyncConnection, hashed: str) -> None:
        await self.execute(
            connection,
            "UPDATE forge.refresh_tokens SET used_at=now() WHERE token_hash=:h",
            h=hashed,
        )

    async def revoke_session(
        self, connection: AsyncConnection, identifier: UUID, user_id: UUID
    ) -> None:
        await self.execute(
            connection,
            """UPDATE forge.auth_sessions SET revoked_at=now()
            WHERE id=:id AND user_id=:user_id""",
            id=identifier,
            user_id=user_id,
        )

    async def revoke_all(self, connection: AsyncConnection, user_id: UUID) -> None:
        await self.execute(
            connection,
            "UPDATE forge.auth_sessions SET revoked_at=now() WHERE user_id=:id",
            id=user_id,
        )

    async def sessions(
        self, connection: AsyncConnection, user_id: UUID, boundary: UUID | None, limit: int
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            """SELECT id,created_at,expires_at FROM forge.auth_sessions
            WHERE user_id=:id AND revoked_at IS NULL AND expires_at>now()
            AND (CAST(:boundary AS uuid) IS NULL OR id>CAST(:boundary AS uuid))
            ORDER BY id LIMIT :limit""",
            id=user_id,
            boundary=boundary,
            limit=limit,
        )

    async def add_identity(
        self,
        connection: AsyncConnection,
        user_id: UUID,
        hashed: str,
        purpose: str,
        expires_at: datetime,
    ) -> None:
        # A newly requested link invalidates outstanding links of the same purpose.
        await self.execute(
            connection,
            """UPDATE forge.identity_tokens SET used_at=now()
            WHERE user_id=:id AND purpose=:purpose AND used_at IS NULL""",
            id=user_id,
            purpose=purpose,
        )
        await self.execute(
            connection,
            """INSERT INTO forge.identity_tokens
            (token_hash,user_id,purpose,expires_at) VALUES (:hashed,:id,:purpose,:expires_at)""",
            hashed=hashed,
            id=user_id,
            purpose=purpose,
            expires_at=expires_at,
        )

    async def identity(
        self, connection: AsyncConnection, hashed: str, purpose: str, *, lock: bool = True
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.identity_tokens WHERE token_hash=:hashed
            AND purpose=:purpose AND used_at IS NULL AND expires_at>now()"""
            + (" FOR UPDATE" if lock else ""),
            hashed=hashed,
            purpose=purpose,
        )

    async def spend_identity(self, connection: AsyncConnection, hashed: str) -> None:
        await self.execute(
            connection,
            "UPDATE forge.identity_tokens SET used_at=now() WHERE token_hash=:h",
            h=hashed,
        )

    async def verify_email(self, connection: AsyncConnection, identifier: UUID) -> None:
        await self.execute(
            connection, "UPDATE forge.users SET email_verified=true WHERE id=:id", id=identifier
        )

    async def rate(self, connection: AsyncConnection, key: str, window: int) -> int:
        row = await self.one(
            connection,
            """INSERT INTO forge.rate_limits (key,window_start,attempts)
            VALUES (:key,now(),1) ON CONFLICT (key) DO UPDATE SET
            attempts=CASE WHEN forge.rate_limits.window_start < now()-make_interval(secs=>:window)
                THEN 1 ELSE forge.rate_limits.attempts+1 END,
            window_start=CASE WHEN
                forge.rate_limits.window_start < now()-make_interval(secs=>:window)
                THEN now() ELSE forge.rate_limits.window_start END RETURNING attempts""",
            key=key,
            window=window,
        )
        assert row
        # Bound storage by dropping cold keys.
        await self.execute(
            connection, "DELETE FROM forge.rate_limits WHERE window_start<now()-interval '1 day'"
        )
        return int(row["attempts"])

    async def organizations(
        self, connection: AsyncConnection, user_id: UUID, boundary: UUID | None, limit: int
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            """SELECT o.id,o.name,o.slug,o.is_demo,m.role
            FROM forge.organizations o JOIN forge.memberships m ON m.organization_id=o.id
            WHERE m.user_id=:id AND o.deleted_at IS NULL
            AND (CAST(:boundary AS uuid) IS NULL OR o.id>CAST(:boundary AS uuid))
            ORDER BY o.id LIMIT :limit""",
            id=user_id,
            boundary=boundary,
            limit=limit,
        )

    async def membership(
        self, connection: AsyncConnection, organization_id: UUID, user_id: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.memberships
            WHERE organization_id=:org AND user_id=:user_id""",
            org=organization_id,
            user_id=user_id,
        )

    async def organization(
        self, connection: AsyncConnection, identifier: UUID, *, lock: bool = False
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.organizations
            WHERE id=:id AND deleted_at IS NULL"""
            + (" FOR UPDATE" if lock else ""),
            id=identifier,
        )

    async def create_organization(
        self,
        connection: AsyncConnection,
        identifier: UUID,
        name: str,
        slug: str,
        creator: UUID,
        *,
        demo: bool = False,
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.organizations (id,name,slug,created_by,is_demo)
            VALUES (:id,:name,:slug,:creator,:demo)""",
            id=identifier,
            name=name,
            slug=slug,
            creator=creator,
            demo=demo,
        )

    async def add_member(
        self,
        connection: AsyncConnection,
        identifier: UUID,
        organization_id: UUID,
        user_id: UUID,
        role: str,
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.memberships (id,organization_id,user_id,role)
            VALUES (:id,:org,:user_id,:role)""",
            id=identifier,
            org=organization_id,
            user_id=user_id,
            role=role,
        )

    async def audit(
        self,
        connection: AsyncConnection,
        identifier: UUID,
        organization_id: UUID,
        actor_id: UUID,
        action: str,
        subject_id: UUID | None = None,
    ) -> None:
        await self.execute(
            connection,
            """INSERT INTO forge.audit_events
            (id,organization_id,actor_id,action,subject_id)
            VALUES (:id,:org,:actor,:action,:subject)""",
            id=identifier,
            org=organization_id,
            actor=actor_id,
            action=action,
            subject=subject_id,
        )

    async def rename_organization(
        self, connection: AsyncConnection, identifier: UUID, name: str
    ) -> None:
        await self.execute(
            connection,
            "UPDATE forge.organizations SET name=:name WHERE id=:id",
            name=name,
            id=identifier,
        )

    async def delete_organization(self, connection: AsyncConnection, identifier: UUID) -> None:
        await self.execute(
            connection,
            "UPDATE forge.organizations SET deleted_at=now() WHERE id=:id",
            id=identifier,
        )
        await self.execute(
            connection,
            "UPDATE forge.invitations SET revoked_at=now() WHERE organization_id=:id",
            id=identifier,
        )

    async def members(
        self, connection: AsyncConnection, organization_id: UUID, boundary: UUID | None, limit: int
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            """SELECT m.id,m.user_id,m.role,u.name,u.email
            FROM forge.memberships m JOIN forge.users u ON u.id=m.user_id
            WHERE m.organization_id=:org
            AND (CAST(:boundary AS uuid) IS NULL OR m.id>CAST(:boundary AS uuid))
            ORDER BY m.id LIMIT :limit""",
            org=organization_id,
            boundary=boundary,
            limit=limit,
        )

    async def member(
        self, connection: AsyncConnection, organization_id: UUID, identifier: UUID
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT m.id,m.user_id,m.role,u.name,u.email
            FROM forge.memberships m JOIN forge.users u ON u.id=m.user_id
            WHERE m.organization_id=:org AND m.id=:id""",
            org=organization_id,
            id=identifier,
        )

    async def owners(self, connection: AsyncConnection, organization_id: UUID) -> int:
        row = await self.one(
            connection,
            "SELECT count(*) AS count FROM forge.memberships "
            "WHERE organization_id=:org AND role='owner'",
            org=organization_id,
        )
        assert row
        return int(row["count"])

    async def change_member(
        self, connection: AsyncConnection, organization_id: UUID, identifier: UUID, role: str | None
    ) -> None:
        if role is None:
            await self.execute(
                connection,
                "DELETE FROM forge.memberships WHERE organization_id=:org AND id=:id",
                org=organization_id,
                id=identifier,
            )
        else:
            await self.execute(
                connection,
                "UPDATE forge.memberships SET role=:role WHERE organization_id=:org AND id=:id",
                org=organization_id,
                id=identifier,
                role=role,
            )

    async def add_invitation(
        self,
        connection: AsyncConnection,
        identifier: UUID,
        organization_id: UUID,
        email: str,
        role: str,
        hashed: str,
        inviter_id: UUID,
        expires_at: datetime,
    ) -> None:
        await self.execute(
            connection,
            """UPDATE forge.invitations SET revoked_at=now()
            WHERE organization_id=:org AND email=:email AND used_at IS NULL""",
            org=organization_id,
            email=email,
        )
        await self.execute(
            connection,
            """INSERT INTO forge.invitations
            (id,organization_id,email,role,token_hash,inviter_id,expires_at)
            VALUES (:id,:org,:email,:role,:hashed,:inviter,:expires_at)""",
            id=identifier,
            org=organization_id,
            email=email,
            role=role,
            hashed=hashed,
            inviter=inviter_id,
            expires_at=expires_at,
        )

    async def invitation(
        self, connection: AsyncConnection, hashed: str, email: str, *, lock: bool = False
    ) -> Mapping[str, Any] | None:
        return await self.one(
            connection,
            """SELECT * FROM forge.invitations
            WHERE token_hash=:hashed AND email=:email AND used_at IS NULL AND revoked_at IS NULL
            AND expires_at>now()"""
            + (" FOR UPDATE" if lock else ""),
            hashed=hashed,
            email=email,
        )

    async def spend_invitation(
        self, connection: AsyncConnection, organization_id: UUID, identifier: UUID
    ) -> None:
        await self.execute(
            connection,
            "UPDATE forge.invitations SET used_at=now() WHERE organization_id=:org AND id=:id",
            org=organization_id,
            id=identifier,
        )

    async def audits(
        self, connection: AsyncConnection, organization_id: UUID, boundary: UUID | None, limit: int
    ) -> list[Mapping[str, Any]]:
        return await self.many(
            connection,
            """SELECT id,actor_id,subject_id,action,created_at
            FROM forge.audit_events WHERE organization_id=:org
            AND (CAST(:boundary AS uuid) IS NULL OR id>CAST(:boundary AS uuid))
            ORDER BY id LIMIT :limit""",
            org=organization_id,
            boundary=boundary,
            limit=limit,
        )
