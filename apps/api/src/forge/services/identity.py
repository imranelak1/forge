import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from forge.config import Settings
from forge.domain.identity import Actor, DomainError, unauthorized
from forge.integrations.mail import MailDelivery
from forge.repositories.identity import IdentityRepository
from forge.security.identity import (
    DUMMY_HASH,
    PASSWORDS,
    SESSION_SECONDS,
    TokenCodec,
    now,
    opaque_token,
    token_hash,
    verify_password,
)


@dataclass(frozen=True)
class SessionResult:
    actor: Actor
    access: str
    refresh: str
    csrf: str
    expires_at: datetime


def actor_from(row: Mapping[str, Any]) -> Actor:
    return Actor(
        row["id"],
        row["session_id"],
        row["name"],
        row["email"],
        row["email_verified"],
        row["csrf_hash"],
    )


class IdentityService:
    def __init__(self, repository: IdentityRepository, settings: Settings) -> None:
        self.repository = repository
        self.tokens = TokenCodec(settings)
        self.mail = MailDelivery(settings)
        # Bound concurrent 64 MiB Argon2 work independently of the ASGI thread pool.
        self.password_slots = asyncio.Semaphore(2)

    async def hash_password(self, password: str) -> str:
        async with self.password_slots:
            return await run_in_threadpool(PASSWORDS.hash, password)

    async def check_password(self, password: str, encoded: str) -> bool:
        async with self.password_slots:
            return await run_in_threadpool(verify_password, password, encoded)

    async def rate_limit(self, operation: str, ip: str, account: str | None = None) -> None:
        keys = [(f"{operation}:ip:{ip}", 60)]
        if account:
            keys.append((f"{operation}:account:{account}", 10))
        blocked = False
        async with self.repository.transaction() as connection:
            for raw_key, maximum in keys:
                if await self.repository.rate(connection, token_hash(raw_key), 900) > maximum:
                    blocked = True
        if blocked:
            raise DomainError(429, "rate_limited", "Too many attempts. Try again in 15 minutes.")

    async def authenticate(self, access: str | None) -> Actor:
        if not access or len(access) > 2048:
            raise unauthorized()
        try:
            data = self.tokens.decode(access, "access")
            user_id, session_id = UUID(data["sub"]), UUID(data["sid"])
        except (KeyError, ValueError, TypeError) as exc:
            raise unauthorized() from exc
        async with self.repository.transaction() as connection:
            row = await self.repository.session(connection, session_id, user_id)
        if row is None:
            raise unauthorized()
        return actor_from(row)

    async def csrf_actor(self, access: str | None, refresh: str | None) -> Actor | None:
        if access:
            try:
                return await self.authenticate(access)
            except DomainError:
                pass
        if refresh and len(refresh) <= 128:
            async with self.repository.transaction() as connection:
                row = await self.repository.refresh(connection, token_hash(refresh))
            if row and row["revoked_at"] is None and row["expires_at"] > now():
                return actor_from(row)
        return None

    async def register(self, name: str, email: str, password: str) -> SessionResult:
        encoded = await self.hash_password(password)
        identifier, session_id = uuid4(), uuid4()
        csrf, refresh = self.tokens.csrf(session_id), opaque_token()
        expires_at = now() + timedelta(seconds=SESSION_SECONDS)
        verification = opaque_token()
        try:
            async with self.repository.transaction() as connection:
                await self.repository.create_user(connection, identifier, name, email, encoded)
                await self.repository.create_session(
                    connection,
                    session_id,
                    identifier,
                    token_hash(csrf),
                    expires_at,
                    token_hash(refresh),
                )
                await self.repository.add_identity(
                    connection,
                    identifier,
                    token_hash(verification),
                    "verify",
                    now() + timedelta(hours=24),
                )
                await self.mail.send(email, "verify", verification)
        except IntegrityError as exc:
            raise DomainError(
                409,
                "registration_unavailable",
                "An account could not be created with those details.",
            ) from exc
        actor = Actor(identifier, session_id, name, email, False, token_hash(csrf))
        return SessionResult(
            actor, self.tokens.access(identifier, session_id), refresh, csrf, expires_at
        )

    async def login(self, email: str, password: str) -> SessionResult:
        async with self.repository.transaction() as connection:
            user = await self.repository.user_by_email(connection, email, lock=True)
            encoded = (user["password_hash"] or DUMMY_HASH) if user else DUMMY_HASH
            correct = await self.check_password(password, encoded)
            if not correct or not user or not user["password_hash"]:
                raise DomainError(401, "invalid_credentials", "Email or password is incorrect.")
            if PASSWORDS.check_needs_rehash(encoded):
                new_hash = await self.hash_password(password)
                await self.repository.set_password(connection, user["id"], new_hash)
            session_id, refresh = uuid4(), opaque_token()
            csrf = self.tokens.csrf(session_id)
            expires_at = now() + timedelta(seconds=SESSION_SECONDS)
            await self.repository.create_session(
                connection,
                session_id,
                user["id"],
                token_hash(csrf),
                expires_at,
                token_hash(refresh),
            )
        actor = Actor(
            user["id"],
            session_id,
            user["name"],
            user["email"],
            user["email_verified"],
            token_hash(csrf),
        )
        return SessionResult(
            actor, self.tokens.access(user["id"], session_id), refresh, csrf, expires_at
        )

    async def refresh(self, token: str | None, csrf: str) -> SessionResult:
        if not token or len(token) > 128:
            raise unauthorized()
        hashed = token_hash(token)
        result: SessionResult | None = None
        async with self.repository.transaction() as connection:
            row = await self.repository.refresh(connection, hashed, lock=True)
            if row and row["revoked_at"] is None and row["expires_at"] > now():
                if not self.tokens.csrf_matches(csrf, row["csrf_hash"]):
                    raise DomainError(403, "csrf_failed", "Refresh the page and try again.")
                if row["used_at"] is not None:
                    # Commit revocation before raising; rollback would undo replay detection.
                    await self.repository.revoke_session(connection, row["session_id"], row["id"])
                else:
                    await self.repository.spend_refresh(connection, hashed)
                    refresh = opaque_token()
                    await self.repository.add_refresh(
                        connection, row["session_id"], token_hash(refresh)
                    )
                    actor = actor_from(row)
                    result = SessionResult(
                        actor,
                        self.tokens.access(actor.user_id, actor.session_id),
                        refresh,
                        self.tokens.csrf(actor.session_id),
                        row["expires_at"],
                    )
        if result is None:
            raise unauthorized()
        return result

    async def logout(self, actor: Actor) -> None:
        async with self.repository.transaction() as connection:
            await self.repository.revoke_session(connection, actor.session_id, actor.user_id)

    async def request_identity(self, email: str, purpose: str) -> None:
        async with self.repository.transaction() as connection:
            user = await self.repository.user_by_email(connection, email, lock=True)
            if user is None or (purpose == "verify" and user["email_verified"]):
                return
            token = opaque_token()
            expiration = now() + timedelta(hours=24 if purpose == "verify" else 1)
            await self.repository.add_identity(
                connection, user["id"], token_hash(token), purpose, expiration
            )
            await self.mail.send(email, purpose, token)

    async def confirm_identity(self, token: str, purpose: str, password: str | None = None) -> None:
        encoded = await self.hash_password(password) if password is not None else None
        async with self.repository.transaction() as connection:
            row = await self.repository.identity(connection, token_hash(token), purpose, lock=False)
            if row is not None:
                # Match request/login lock order: user first, then identity token.
                await self.repository.lock_user(connection, row["user_id"])
                row = await self.repository.identity(connection, token_hash(token), purpose)
            if row is None:
                raise DomainError(
                    400, "invalid_link", "This link is invalid or expired. Request a new one."
                )
            await self.repository.spend_identity(connection, token_hash(token))
            if purpose == "verify":
                await self.repository.verify_email(connection, row["user_id"])
            else:
                assert encoded
                await self.repository.set_password(connection, row["user_id"], encoded)
                await self.repository.revoke_all(connection, row["user_id"])

    async def list_sessions(self, actor: Actor, limit: int, cursor: str | None) -> dict[str, Any]:
        scope = f"sessions:{actor.user_id}:{limit}"
        boundary = self.tokens.boundary(cursor, scope)
        async with self.repository.transaction() as connection:
            rows = await self.repository.sessions(connection, actor.user_id, boundary, limit + 1)
        data = [{**row, "current": row["id"] == actor.session_id} for row in rows[:limit]]
        return self.page(data, len(rows) > limit, scope)

    def page(self, rows: Sequence[Mapping[str, Any]], more: bool, scope: str) -> dict[str, Any]:
        return {
            "data": rows,
            "page": {
                "has_more": more,
                "next_cursor": self.tokens.cursor(scope, str(rows[-1]["id"])) if more else None,
            },
        }

    async def revoke_session(self, actor: Actor, session_id: UUID) -> None:
        async with self.repository.transaction() as connection:
            row = await self.repository.session(connection, session_id, actor.user_id)
            if row is None:
                from forge.domain.identity import not_found

                raise not_found()
            await self.repository.revoke_session(connection, session_id, actor.user_id)
