from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from forge.domain.identity import Actor, DomainError, not_found, require_manager
from forge.security.identity import now, opaque_token, token_hash
from forge.services.identity import IdentityService


class OrganizationService:
    def __init__(self, identity: IdentityService) -> None:
        self.identity = identity
        self.repository = identity.repository

    async def context(
        self,
        connection: AsyncConnection,
        actor: Actor,
        organization_id: UUID,
        *,
        lock: bool = False,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        member = await self.repository.membership(connection, organization_id, actor.user_id)
        if member is None:
            raise not_found()
        await self.repository.tenant(connection, organization_id)
        organization = await self.repository.organization(connection, organization_id, lock=lock)
        if organization is None:
            raise not_found()
        if lock:
            # Re-read after obtaining the shared tenant mutation lock (roles may have changed).
            member = await self.repository.membership(connection, organization_id, actor.user_id)
            if member is None:
                raise not_found()
        return organization, member

    @staticmethod
    def summary(organization: Mapping[str, Any], role: str) -> dict[str, Any]:
        return {key: organization[key] for key in ("id", "name", "slug", "is_demo")} | {
            "role": role
        }

    async def list(self, actor: Actor, limit: int, cursor: str | None) -> dict[str, Any]:
        scope = f"organizations:{actor.user_id}:{limit}"
        boundary = self.identity.tokens.boundary(cursor, scope)
        async with self.repository.transaction(actor.user_id) as connection:
            rows = await self.repository.organizations(
                connection, actor.user_id, boundary, limit + 1
            )
        return self.identity.page(rows[:limit], len(rows) > limit, scope)

    async def create(
        self, actor: Actor, name: str, slug: str, *, demo: bool = False
    ) -> dict[str, Any]:
        identifier = uuid4()
        try:
            async with self.repository.transaction(actor.user_id) as connection:
                # Bootstrap uses a fresh server-generated tenant UUID.
                await self.repository.tenant(connection, identifier)
                await self.repository.create_organization(
                    connection, identifier, name, slug, actor.user_id, demo=demo
                )
                await self.repository.add_member(
                    connection, uuid4(), identifier, actor.user_id, "owner"
                )
                await self.repository.audit(
                    connection,
                    uuid4(),
                    identifier,
                    actor.user_id,
                    "organization.created",
                    identifier,
                )
        except IntegrityError as exc:
            raise DomainError(
                409, "organization_conflict", "An organization could not be created with that URL."
            ) from exc
        return {"id": identifier, "name": name, "slug": slug, "role": "owner", "is_demo": demo}

    async def get(self, actor: Actor, identifier: UUID) -> dict[str, Any]:
        async with self.repository.transaction(actor.user_id) as connection:
            organization, member = await self.context(connection, actor, identifier)
            return self.summary(organization, member["role"])

    async def rename(self, actor: Actor, identifier: UUID, name: str) -> dict[str, Any]:
        async with self.repository.transaction(actor.user_id) as connection:
            organization, member = await self.context(connection, actor, identifier, lock=True)
            require_manager(member["role"])
            await self.repository.rename_organization(connection, identifier, name)
            await self.repository.audit(
                connection, uuid4(), identifier, actor.user_id, "organization.renamed", identifier
            )
            return self.summary({**organization, "name": name}, member["role"])

    async def delete(self, actor: Actor, identifier: UUID) -> None:
        async with self.repository.transaction(actor.user_id) as connection:
            _, member = await self.context(connection, actor, identifier, lock=True)
            if member["role"] != "owner":
                raise DomainError(403, "forbidden", "Only an owner can delete the organization.")
            await self.repository.audit(
                connection,
                uuid4(),
                identifier,
                actor.user_id,
                "organization.deactivated",
                identifier,
            )
            await self.repository.delete_organization(connection, identifier)

    async def members(
        self, actor: Actor, identifier: UUID, limit: int, cursor: str | None
    ) -> dict[str, Any]:
        scope = f"members:{identifier}:{limit}"
        boundary = self.identity.tokens.boundary(cursor, scope)
        async with self.repository.transaction(actor.user_id) as connection:
            await self.context(connection, actor, identifier)
            rows = await self.repository.members(connection, identifier, boundary, limit + 1)
        return self.identity.page(rows[:limit], len(rows) > limit, scope)

    async def change_member(
        self, actor: Actor, identifier: UUID, member_id: UUID, role: str | None
    ) -> Mapping[str, Any] | None:
        async with self.repository.transaction(actor.user_id) as connection:
            _, manager = await self.context(connection, actor, identifier, lock=True)
            target = await self.repository.member(connection, identifier, member_id)
            if target is None:
                raise not_found()
            require_manager(manager["role"], target["role"], role)
            if (
                target["role"] == "owner"
                and role != "owner"
                and await self.repository.owners(connection, identifier) <= 1
            ):
                raise DomainError(
                    409, "last_owner", "Assign another owner before removing the last owner."
                )
            await self.repository.change_member(connection, identifier, member_id, role)
            await self.repository.audit(
                connection,
                uuid4(),
                identifier,
                actor.user_id,
                "member.removed" if role is None else f"member.role.{role}",
                member_id,
            )
            return {**target, "role": role} if role else None

    async def invite(self, actor: Actor, identifier: UUID, email: str, role: str) -> dict[str, Any]:
        invitation_id, token = uuid4(), opaque_token()
        expiration = now() + timedelta(days=7)
        async with self.repository.transaction(actor.user_id) as connection:
            _, member = await self.context(connection, actor, identifier, lock=True)
            require_manager(member["role"], new_role=role)
            await self.repository.add_invitation(
                connection,
                invitation_id,
                identifier,
                email,
                role,
                token_hash(token),
                member["id"],
                expiration,
            )
            await self.repository.audit(
                connection, uuid4(), identifier, actor.user_id, "invitation.created", invitation_id
            )
            await self.identity.mail.send(email, "invite", token)
        return {"id": invitation_id, "email": email, "role": role, "expires_at": expiration}

    async def accept(self, actor: Actor, token: str) -> dict[str, Any]:
        if not actor.email_verified:
            raise DomainError(
                403, "email_unverified", "Verify your email before accepting an invitation."
            )
        async with self.repository.transaction(actor.user_id) as connection:
            invitation = await self.repository.invitation(
                connection, token_hash(token), actor.email
            )
            if invitation is None:
                raise not_found()
            identifier = invitation["organization_id"]
            await self.repository.tenant(connection, identifier)
            organization = await self.repository.organization(connection, identifier, lock=True)
            if organization is None:
                raise not_found()
            invitation = await self.repository.invitation(
                connection, token_hash(token), actor.email, lock=True
            )
            if invitation is None:
                raise not_found()
            # The inviter must still have the role that allowed this invitation.
            inviter = (
                await self.repository.member(connection, identifier, invitation["inviter_id"])
                if invitation["inviter_id"]
                else None
            )
            if (
                inviter is None
                or inviter["role"] not in {"admin", "owner"}
                or (invitation["role"] == "owner" and inviter["role"] != "owner")
            ):
                raise not_found()
            existing = await self.repository.membership(connection, identifier, actor.user_id)
            if existing is None:
                await self.repository.add_member(
                    connection, uuid4(), identifier, actor.user_id, invitation["role"]
                )
            await self.repository.spend_invitation(connection, identifier, invitation["id"])
            await self.repository.audit(
                connection,
                uuid4(),
                identifier,
                actor.user_id,
                "invitation.accepted",
                invitation["id"],
            )
            return self.summary(organization, existing["role"] if existing else invitation["role"])

    async def audit(
        self, actor: Actor, identifier: UUID, limit: int, cursor: str | None
    ) -> dict[str, Any]:
        scope = f"audit:{identifier}:{limit}"
        boundary = self.identity.tokens.boundary(cursor, scope)
        async with self.repository.transaction(actor.user_id) as connection:
            _, member = await self.context(connection, actor, identifier)
            require_manager(member["role"])
            rows = await self.repository.audits(connection, identifier, boundary, limit + 1)
        return self.identity.page(rows[:limit], len(rows) > limit, scope)
