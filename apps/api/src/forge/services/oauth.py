import asyncio
import hmac
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from forge.config import Settings
from forge.domain.identity import Actor, DomainError
from forge.integrations.oauth import OAuthFailure, OAuthProvider, Provider, ProviderIdentity
from forge.repositories.oauth import OAuthRepository
from forge.security.identity import SESSION_SECONDS, now, opaque_token, token_hash
from forge.services.identity import IdentityService, SessionResult

OAUTH_SECONDS = 600
logger = logging.getLogger("forge.oauth")
AUTHORIZATION_ISSUERS = {
    "google": "https://accounts.google.com",
    "github": "https://github.com",
}


def safe_return(value: str) -> str:
    if (
        len(value) > 2048
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return "/app"
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "/app"
    decoded_path = unquote(parsed.path)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or "%" in parsed.path
        or not (parsed.path == "/app" or parsed.path.startswith("/app/"))
        or any(segment in {".", ".."} for segment in decoded_path.split("/"))
        or "\\" in decoded_path
        or any(ord(character) < 32 or ord(character) == 127 for character in decoded_path)
    ):
        return "/app"
    return value


def login_target(value: str) -> str:
    parsed = urlsplit(safe_return(value))
    query = [(key, item) for key, item in parse_qsl(parsed.query) if key != "oauth"]
    query.append(("oauth", "signed-in"))
    return urlunsplit(("", "", parsed.path, urlencode(query), parsed.fragment))


@dataclass(frozen=True)
class OAuthStart:
    authorization_url: str
    browser_binding: str


@dataclass(frozen=True)
class OAuthCallback:
    location: str
    session: SessionResult | None = None


class OAuthService:
    def __init__(self, identity: IdentityService, settings: Settings) -> None:
        self.identity = identity
        self.repository = OAuthRepository(identity.repository.engine)
        self.provider = OAuthProvider(settings)

    async def start(
        self,
        provider: Provider,
        intent: Literal["login", "link"],
        return_to: str,
        actor: Actor | None,
    ) -> OAuthStart:
        if intent == "link" and (actor is None or not actor.email_verified):
            raise DomainError(
                403, "link_unavailable", "Verify your email before connecting a sign-in provider."
            )
        state, binding = opaque_token(), opaque_token()
        try:
            url = self.provider.authorization_url(provider, state)
        except OAuthFailure as exc:
            raise DomainError(503, exc.code, "This sign-in provider is not configured.") from exc
        async with self.repository.transaction() as connection:
            await self.repository.create_state(
                connection,
                state_hash=token_hash(state),
                browser_hash=token_hash(binding),
                provider=provider,
                intent=intent,
                return_to=safe_return(return_to),
                user_id=actor.user_id if intent == "link" and actor else None,
                session_id=actor.session_id if intent == "link" and actor else None,
                expires_at=now() + timedelta(seconds=OAUTH_SECONDS),
            )
        return OAuthStart(url, binding)

    async def consume_state(
        self, provider: Provider, state: str, binding: str | None
    ) -> Mapping[str, Any]:
        if not state or len(state) > 128 or not binding or len(binding) > 128:
            raise OAuthFailure("invalid_state")
        async with self.repository.transaction() as connection:
            row = await self.repository.state(connection, token_hash(state), provider)
            if row is None or not hmac.compare_digest(row["browser_hash"], token_hash(binding)):
                raise OAuthFailure("invalid_state")
            await self.repository.spend_state(connection, token_hash(state))
        # Commit before any provider request; errors and retries never resurrect state.
        return row

    async def callback(
        self,
        provider: Provider,
        state: str,
        binding: str | None,
        code: str | None,
        error: str | None,
        access: str | None,
        issuer: str | None = None,
    ) -> OAuthCallback:
        target = "/login"
        stage = "state"
        try:
            attempt = await self.consume_state(provider, state, binding)
            stage = "callback"
            if attempt["intent"] == "link":
                target = "/app/account"
            # RFC 9207: compare decoded issuer exactly against the provider selected
            # when starting this flow. Never fetch a URL supplied by the callback.
            # An empty string also rejects duplicate issuer parameters at the route.
            if issuer is not None and issuer != AUTHORIZATION_ISSUERS[provider]:
                raise OAuthFailure("invalid_identity", reason="callback_issuer")
            if error is not None:
                raise OAuthFailure("denied")
            if not code or len(code) > 2048:
                raise OAuthFailure("invalid_identity", reason="callback_code")
            actor = None
            if attempt["intent"] == "link":
                stage = "link_session"
                try:
                    actor = await self.identity.authenticate(access)
                except DomainError as exc:
                    raise OAuthFailure("link_unavailable") from exc
                if actor.user_id != attempt["user_id"] or actor.session_id != attempt["session_id"]:
                    raise OAuthFailure("link_unavailable")
            stage = "provider_identity"
            async with asyncio.timeout(8.0):
                identity = await self.provider.exchange(provider, code, state)
            stage = "account"
            session = await self.complete(attempt, identity, actor)
            if attempt["intent"] == "link":
                return OAuthCallback("/app/account?oauth=linked")
            return OAuthCallback(login_target(attempt["return_to"]), session)
        except OAuthFailure as exc:
            # Log only our fixed codes/stages and exception class. Upstream messages,
            # callback parameters, tokens and identity claims must never be logged.
            logger.warning(
                "oauth.callback_failed",
                extra={
                    "provider": provider,
                    "oauth_stage": stage,
                    "oauth_error": exc.code,
                    "oauth_reason": exc.reason,
                    "error_type": type(exc.__cause__ or exc).__name__,
                },
            )
            return OAuthCallback(f"{target}?oauth_error={exc.code}")
        except TimeoutError:
            logger.warning(
                "oauth.callback_failed",
                extra={
                    "provider": provider,
                    "oauth_stage": stage,
                    "oauth_error": "provider_unavailable",
                    "error_type": "TimeoutError",
                },
            )
            return OAuthCallback(f"{target}?oauth_error=provider_unavailable")
        except DomainError:
            logger.warning(
                "oauth.callback_failed",
                extra={
                    "provider": provider,
                    "oauth_stage": stage,
                    "oauth_error": "provider_unavailable",
                    "error_type": "DomainError",
                },
            )
            # Preserve the callback's fixed, local error contract without upstream details.
            return OAuthCallback(f"{target}?oauth_error=provider_unavailable")

    async def complete(
        self, attempt: Mapping[str, Any], identity: ProviderIdentity, actor: Actor | None
    ) -> SessionResult | None:
        try:
            async with self.repository.transaction() as connection:
                await self.repository.lock_identity(connection, identity.provider, identity.subject)
                linked = await self.repository.external_identity(
                    connection, identity.provider, identity.subject
                )
                if attempt["intent"] == "link":
                    assert actor is not None
                    user = await self.repository.user_by_id(connection, actor.user_id)
                    session = await self.repository.locked_session(
                        connection, actor.session_id, actor.user_id
                    )
                    if user is None or not user["email_verified"] or session is None:
                        raise OAuthFailure("link_unavailable")
                    if linked and linked["user_id"] != actor.user_id:
                        raise OAuthFailure("identity_in_use")
                    previous = await self.repository.user_identity(
                        connection, identity.provider, actor.user_id
                    )
                    if previous and previous["subject"] != identity.subject:
                        raise OAuthFailure("identity_in_use")
                    if linked is None:
                        await self.repository.add_external_identity(
                            connection,
                            identity.provider,
                            identity.subject,
                            actor.user_id,
                            identity.email,
                        )
                    return None
                if linked:
                    user = await self.repository.user_by_id(connection, linked["user_id"])
                    assert user is not None
                else:
                    user = await self.repository.user_by_email(
                        connection, identity.email, lock=True
                    )
                    if user:
                        # Provider email is not proof of ownership of an existing Forge account.
                        raise OAuthFailure("account_exists")
                    if not identity.email_authoritative:
                        # Google can verify a third-party email once and retain that
                        # claim after the mailbox changes hands. The mailbox owner
                        # must create and verify a Forge account before deliberate linking.
                        raise OAuthFailure("email_unverified")
                    identifier = uuid4()
                    await self.repository.create_user(
                        connection,
                        identifier,
                        identity.name,
                        identity.email,
                        None,
                        verified=identity.email_authoritative,
                    )
                    await self.repository.add_external_identity(
                        connection, identity.provider, identity.subject, identifier, identity.email
                    )
                    user = await self.repository.user_by_id(connection, identifier)
                    assert user is not None
                session_id, refresh = uuid4(), opaque_token()
                csrf = self.identity.tokens.csrf(session_id)
                expires_at = now() + timedelta(seconds=SESSION_SECONDS)
                await self.repository.create_session(
                    connection,
                    session_id,
                    user["id"],
                    token_hash(csrf),
                    expires_at,
                    token_hash(refresh),
                )
                result_actor = Actor(
                    user["id"],
                    session_id,
                    user["name"],
                    user["email"],
                    user["email_verified"],
                    token_hash(csrf),
                )
                return SessionResult(
                    result_actor,
                    self.identity.tokens.access(user["id"], session_id),
                    refresh,
                    csrf,
                    expires_at,
                )
        except IntegrityError as exc:
            # Concurrent registrations or explicit links still fail closed at unique constraints.
            raise OAuthFailure(
                "identity_in_use" if attempt["intent"] == "link" else "account_exists"
            ) from exc

    async def connections(self, actor: Actor) -> dict[str, Any]:
        async with self.repository.transaction() as connection:
            rows = await self.repository.connections(connection, actor.user_id)
        return {"connections": rows}
