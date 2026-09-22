import asyncio
import base64
import hashlib
import hmac
import json
import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.ext.asyncio import AsyncConnection

from forge.config import Settings
from forge.domain.identity import Actor, DomainError, not_found, require_manager
from forge.integrations.github import GitHubApp, GitHubFailure, token_value
from forge.repositories.github import SYNC_FIELDS, GitHubRepository
from forge.repositories.pipeline import PipelineRepository
from forge.security.identity import now, opaque_token, token_hash
from forge.services.identity import IdentityService
from forge.services.organizations import OrganizationService

AUTHORIZATION_SECONDS = 600
logger = logging.getLogger("forge.github")
CONNECTION_FIELDS = (
    "id",
    "installation_id",
    "account_login",
    "account_type",
    "status",
    "created_at",
    "last_error",
)
REPOSITORY_FIELDS = (
    "id",
    "integration_id",
    "provider_id",
    "full_name",
    "html_url",
    "description",
    "language",
    "default_branch",
    "is_private",
    "archived",
    "authorized",
    "selected",
    "is_demo",
    "pushed_at",
    "last_synced_at",
    "pull_request_count",
    "open_pull_request_count",
    "commit_count",
    "latest_sync",
)


def sync_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in SYNC_FIELDS}


def connection_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in CONNECTION_FIELDS} | {
        "catalog_sync": row.get("catalog_sync")
    }


def provider_error(error: GitHubFailure) -> DomainError:
    details = {
        "not_configured": "The Forge GitHub App has not been configured.",
        "rate_limited": "GitHub is limiting requests. Try again after the rate limit clears.",
        "provider_unavailable": "GitHub could not be reached. Try again shortly.",
        "credentials_rejected": "GitHub rejected the authorization. Authorize the app again.",
        "access_denied": "GitHub no longer permits access to this installation.",
        "installation_suspended": "This GitHub App installation is suspended.",
        "permissions_required": (
            "Grant the GitHub App read access to contents and pull requests, "
            "and organization members for organization installations."
        ),
        "installation_admin_required": (
            "Sign in to GitHub as the installation's account owner or an organization owner."
        ),
        "capacity_exceeded": "This GitHub account exceeds the supported pagination limit.",
    }
    return DomainError(
        503 if error.retryable or error.code == "not_configured" else 409,
        error.code,
        details.get(
            error.code, "GitHub authorization could not be completed. Start a fresh attempt."
        ),
    )


class GitHubService:
    def __init__(self, identity: IdentityService, settings: Settings) -> None:
        self.identity = identity
        self.organizations = OrganizationService(identity)
        self.repository = GitHubRepository(identity.repository.engine)
        self.pipeline = PipelineRepository(identity.repository.engine)
        self.provider = GitHubApp(settings)
        self.key = settings.auth_secret.get_secret_value().encode()
        self.cipher = Fernet(
            base64.urlsafe_b64encode(
                hmac.new(self.key, b"forge:github-app:pending-token:v1", hashlib.sha256).digest()
            )
        )

    def verifier(self, state: str) -> str:
        return (
            base64.urlsafe_b64encode(
                hmac.new(self.key, f"github-app:pkce:{state}".encode(), hashlib.sha256).digest()
            )
            .decode()
            .rstrip("=")
        )

    def encrypt(self, identifier: UUID, token: str) -> str:
        return self.cipher.encrypt(
            json.dumps({"authorization_id": str(identifier), "token": token}).encode()
        ).decode()

    def decrypt(self, row: Mapping[str, Any]) -> str:
        try:
            payload = json.loads(
                self.cipher.decrypt(row["token_ciphertext"].encode(), ttl=AUTHORIZATION_SECONDS)
            )
            if payload["authorization_id"] != str(row["id"]):
                raise ValueError("binding")
            return token_value(payload["token"])
        except (InvalidToken, ValueError, TypeError, KeyError, GitHubFailure) as exc:
            raise DomainError(
                409, "invalid_authorization", "Authorize the GitHub App again."
            ) from exc

    @asynccontextmanager
    async def external(self) -> AsyncIterator[None]:
        try:
            async with asyncio.timeout(8.0):
                yield
        except GitHubFailure as exc:
            raise provider_error(exc) from exc
        except TimeoutError as exc:
            raise DomainError(
                503, "provider_unavailable", "GitHub took too long to respond. Try again."
            ) from exc

    async def manage(self, connection: AsyncConnection, actor: Actor, organization: UUID) -> None:
        _, member = await self.organizations.context(connection, actor, organization, lock=True)
        require_manager(member["role"])
        if not actor.email_verified:
            raise DomainError(
                403, "email_unverified", "Verify your Forge email before managing integrations."
            )
        if not await self.repository.live_session(connection, actor.user_id, actor.session_id):
            raise DomainError(
                401, "link_unavailable", "Sign in again before managing integrations."
            )

    async def status(self, actor: Actor, organization: UUID) -> dict[str, Any]:
        async with self.repository.transaction(actor.user_id) as connection:
            _, member = await self.organizations.context(connection, actor, organization)
            rows = await self.repository.integrations(connection, organization)
            pending = (
                await self.repository.authorization(
                    connection, organization, actor.user_id, actor.session_id
                )
                if member["role"] in {"admin", "owner"} and actor.email_verified
                else None
            )
        return {
            "configured": self.provider.configured,
            "install_url": self.provider.install_url,
            "authorization": {"id": pending["id"], "expires_at": pending["expires_at"]}
            if pending
            else None,
            "connections": [connection_summary(row) for row in rows],
        }

    async def authorize(self, actor: Actor, organization: UUID) -> tuple[str, str]:
        state, binding = opaque_token(), opaque_token()
        async with self.repository.transaction(actor.user_id) as connection:
            await self.manage(connection, actor, organization)
            try:
                url = self.provider.authorization_url(state, self.verifier(state))
            except GitHubFailure as exc:
                raise provider_error(exc) from exc
            await self.repository.create_authorization(
                connection,
                uuid4(),
                token_hash(state),
                token_hash(binding),
                organization,
                actor.user_id,
                actor.session_id,
                now() + timedelta(seconds=AUTHORIZATION_SECONDS),
            )
        return url, binding

    async def callback(
        self,
        state: str,
        binding: str | None,
        code: str | None,
        error: str | None,
        access: str | None,
        issuer: str | None,
    ) -> str:
        target = "/login?oauth_error=link_unavailable"
        try:
            if not state or len(state) > 128 or not binding or len(binding) > 128:
                raise DomainError(400, "invalid_state", "Restart the authorization.")
            async with self.repository.transaction() as connection:
                attempt = await self.repository.authorization_state(connection, token_hash(state))
                if attempt is None or not hmac.compare_digest(
                    attempt["browser_hash"], token_hash(binding)
                ):
                    raise DomainError(400, "invalid_state", "Restart the authorization.")
                await self.repository.spend_state(connection, attempt["id"])
            organization = attempt["organization_id"]
            target = f"/app/integrations?organization={organization}"
            if issuer is not None and issuer != "https://github.com/login/oauth":
                raise DomainError(400, "invalid_callback", "Restart the authorization.")
            if error is not None:
                raise DomainError(400, "denied", "GitHub authorization was canceled.")
            if not code or len(code) > 2048:
                raise DomainError(400, "invalid_callback", "Restart the authorization.")
            actor = await self.identity.authenticate(access)
            if actor.user_id != attempt["user_id"] or actor.session_id != attempt["session_id"]:
                raise DomainError(403, "link_unavailable", "Use the same signed-in Forge account.")
            async with self.repository.transaction(actor.user_id) as connection:
                await self.manage(connection, actor, organization)
            async with self.external():
                token = await self.provider.exchange_user_code(code, self.verifier(state))
            async with self.repository.transaction(actor.user_id) as connection:
                await self.manage(connection, actor, organization)
                current = await self.repository.pending_state_row(connection, attempt["id"])
                if current is None:
                    raise DomainError(409, "invalid_state", "Restart the authorization.")
                await self.repository.store_token(
                    connection,
                    attempt["id"],
                    self.encrypt(attempt["id"], token),
                    now() + timedelta(seconds=AUTHORIZATION_SECONDS),
                )
            return target + "&github=authorized"
        except DomainError as exc:
            code = exc.code if exc.code not in {"unauthorized", "not_found"} else "link_unavailable"
            logger.warning(
                "github.authorization_failed",
                extra={"provider": "github", "oauth_error": code, "error_type": type(exc).__name__},
            )
            return target if target.startswith("/login") else target + "&github_error=" + code

    async def pending(
        self, actor: Actor, organization: UUID, identifier: UUID
    ) -> Mapping[str, Any]:
        async with self.repository.transaction(actor.user_id) as connection:
            await self.manage(connection, actor, organization)
            row = await self.repository.authorization(
                connection, organization, actor.user_id, actor.session_id, identifier
            )
            if row is None:
                raise not_found()
            return row

    async def installations(
        self, actor: Actor, organization: UUID, identifier: UUID
    ) -> dict[str, Any]:
        pending = await self.pending(actor, organization, identifier)
        async with self.external():
            rows = await self.provider.user_installations(self.decrypt(pending))
        return {
            "installations": [
                {
                    "id": row["id"],
                    "account_login": row["account"]["login"],
                    "account_type": row["account"]["type"],
                    "repository_selection": row["repository_selection"],
                }
                for row in rows
            ],
            "install_url": self.provider.install_url,
        }

    async def bind(
        self, actor: Actor, organization: UUID, authorization: UUID, installation: int
    ) -> dict[str, Any]:
        async with self.repository.transaction(actor.user_id) as connection:
            await self.manage(connection, actor, organization)
            pending = await self.repository.authorization(
                connection, organization, actor.user_id, actor.session_id, authorization
            )
            if pending is None:
                raise not_found()
            previous = await self.repository.installation_integration(
                connection, organization, installation
            )
        token = self.decrypt(pending)
        async with self.external():
            visible = await self.provider.user_installations(token)
            if not any(row["id"] == installation for row in visible):
                raise GitHubFailure("access_denied")
            verified = await self.provider.installation(installation)
            await self.provider.require_account_admin(token, verified)
        async with self.repository.transaction(actor.user_id) as connection:
            await self.manage(connection, actor, organization)
            current = await self.repository.authorization(
                connection, organization, actor.user_id, actor.session_id, authorization, lock=True
            )
            if current is None:
                raise not_found()
            bound = await self.repository.lock_installation(connection, installation)
            if bound is not None and bound["organization_id"] != organization:
                raise DomainError(
                    409,
                    "installation_conflict",
                    "This installation is already connected to another Forge organization.",
                )
            source = await self.repository.installation_integration(
                connection, organization, installation, lock=True
            )
            # A disconnect or source revocation committed during provider checks
            # must win over the earlier positive GitHub response.
            before = (previous["id"], previous["updated_at"]) if previous else None
            after = (source["id"], source["updated_at"]) if source else None
            if before != after:
                raise DomainError(
                    409,
                    "integration_changed",
                    "The connection changed while checking GitHub. Refresh and try again.",
                )
            row = await self.repository.bind(
                connection,
                organization,
                uuid4(),
                installation,
                verified["account"]["login"],
                verified["account"]["type"],
            )
            await self.repository.complete_authorization(connection, authorization)
            run = await self.pipeline.enqueue_sync(
                connection,
                organization,
                row["id"],
                None,
                kind="catalog",
                requested_by=actor.user_id,
            )
            await self.repository.audit(
                connection, uuid4(), organization, actor.user_id, "github.connected", row["id"]
            )
        return {
            "connection": connection_summary(row) | {"catalog_sync": sync_summary(run)},
            "sync": sync_summary(run),
        }

    async def refresh(self, actor: Actor, organization: UUID, identifier: UUID) -> dict[str, Any]:
        async with self.repository.transaction(actor.user_id) as connection:
            await self.manage(connection, actor, organization)
            row = await self.repository.integration(connection, organization, identifier)
            if row is None or row["status"] == "disconnected":
                raise not_found()
        problem: GitHubFailure | None = None
        try:
            async with asyncio.timeout(8.0):
                await self.provider.installation(row["installation_id"])
        except GitHubFailure as exc:
            problem = exc
        except TimeoutError:
            problem = GitHubFailure("provider_unavailable", retryable=True)
        async with self.repository.transaction(actor.user_id) as connection:
            await self.manage(connection, actor, organization)
            current = await self.repository.integration(
                connection, organization, identifier, lock=True
            )
            if current is None or current["status"] == "disconnected":
                raise not_found()
            if current["updated_at"] != row["updated_at"]:
                raise DomainError(
                    409,
                    "integration_changed",
                    "The connection changed while checking GitHub. Refresh and try again.",
                )
            if problem is not None:
                if not problem.retryable:
                    status = (
                        "suspended"
                        if problem.code == "installation_suspended"
                        else "needs_attention"
                    )
                    await self.repository.set_status(
                        connection, organization, identifier, status, problem.code
                    )
                    await self.pipeline.cancel_integration(connection, organization, identifier)
            else:
                await self.repository.set_status(connection, organization, identifier, "active")
                run = await self.pipeline.enqueue_sync(
                    connection,
                    organization,
                    identifier,
                    None,
                    kind="catalog",
                    requested_by=actor.user_id,
                )
        if problem is not None:
            raise provider_error(problem)
        return {"sync": sync_summary(run)}

    async def disconnect(self, actor: Actor, organization: UUID, identifier: UUID) -> None:
        async with self.repository.transaction(actor.user_id) as connection:
            await self.manage(connection, actor, organization)
            if (
                await self.repository.integration(connection, organization, identifier, lock=True)
                is None
            ):
                raise not_found()
            await self.repository.set_status(connection, organization, identifier, "disconnected")
            await self.repository.unselect_integration(connection, organization, identifier)
            await self.pipeline.cancel_integration(connection, organization, identifier)
            await self.repository.audit(
                connection, uuid4(), organization, actor.user_id, "github.disconnected", identifier
            )

    def page(
        self, rows: Sequence[Mapping[str, Any]], limit: int, scope: str, fields: Sequence[str]
    ) -> dict[str, Any]:
        items = [{field: row[field] for field in fields} for row in rows[:limit]]
        cursor = (
            self.identity.tokens.cursor(scope, str(items[-1]["id"])) if len(rows) > limit else None
        )
        return {"items": items, "next_cursor": cursor}

    async def repositories(
        self,
        actor: Actor,
        organization: UUID,
        integration: UUID | None,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        scope = f"github-repositories:{organization}:{integration}:{limit}"
        boundary = self.identity.tokens.boundary(cursor, scope)
        async with self.repository.transaction(actor.user_id) as connection:
            await self.organizations.context(connection, actor, organization)
            if (
                integration is not None
                and await self.repository.integration(connection, organization, integration) is None
            ):
                raise not_found()
            rows = await self.repository.repositories(
                connection, organization, integration, boundary, limit + 1
            )
        return self.page(rows, limit, scope, REPOSITORY_FIELDS)

    async def selection(
        self,
        actor: Actor,
        organization: UUID,
        integration: UUID,
        changes: Sequence[tuple[UUID, bool]],
    ) -> dict[str, int]:
        if len({identifier for identifier, _ in changes}) != len(changes):
            raise DomainError(422, "invalid_selection", "Each repository can appear only once.")
        async with self.repository.transaction(actor.user_id) as connection:
            await self.manage(connection, actor, organization)
            source = await self.repository.integration(
                connection, organization, integration, lock=True
            )
            if source is None:
                raise not_found()
            for identifier, selected in sorted(changes):
                row = await self.repository.repository(
                    connection, organization, identifier, lock=True
                )
                if row is None or row["integration_id"] != integration:
                    raise not_found()
                if selected and (source["status"] != "active" or not row["authorized"]):
                    raise DomainError(
                        409,
                        "repository_unavailable",
                        "Refresh the connection before selecting this repository.",
                    )
                await self.repository.select_repository(
                    connection, organization, identifier, selected
                )
                if selected and not row["selected"]:
                    await self.pipeline.enqueue_sync(
                        connection,
                        organization,
                        integration,
                        identifier,
                        kind="history",
                        requested_by=actor.user_id,
                    )
                elif not selected:
                    await self.pipeline.cancel_repository(connection, organization, identifier)
            await self.repository.audit(
                connection,
                uuid4(),
                organization,
                actor.user_id,
                "github.selection_changed",
                integration,
            )
        return {"updated": len(changes)}

    async def sync_runs(
        self, actor: Actor, organization: UUID, repository: UUID, limit: int, cursor: str | None
    ) -> dict[str, Any]:
        scope = f"github-syncs:{organization}:{repository}:{limit}"
        boundary = self.identity.tokens.boundary(cursor, scope)
        async with self.repository.transaction(actor.user_id) as connection:
            await self.organizations.context(connection, actor, organization)
            if await self.repository.repository(connection, organization, repository) is None:
                raise not_found()
            rows = await self.repository.sync_runs(
                connection, organization, repository, boundary, limit + 1
            )
        return self.page(rows, limit, scope, SYNC_FIELDS)

    async def sync(self, actor: Actor, organization: UUID, identifier: UUID) -> dict[str, Any]:
        async with self.repository.transaction(actor.user_id) as connection:
            await self.manage(connection, actor, organization)
            row = await self.repository.repository(connection, organization, identifier)
            if row is None:
                raise not_found()
            if row["is_demo"]:
                raise DomainError(
                    409,
                    "demo_repository",
                    "This repository contains generated demonstration history "
                    "and has no live GitHub source.",
                )
            source = await self.repository.integration(
                connection, organization, row["integration_id"], lock=True
            )
            row = await self.repository.repository(connection, organization, identifier, lock=True)
            assert row is not None
            if (
                source is None
                or source["status"] != "active"
                or not row["authorized"]
                or not row["selected"]
            ):
                raise DomainError(
                    409,
                    "repository_unavailable",
                    "Select an authorized repository from an active connection first.",
                )
            run = await self.pipeline.enqueue_sync(
                connection,
                organization,
                row["integration_id"],
                identifier,
                kind="incremental",
                requested_by=actor.user_id,
            )
        return {"sync": sync_summary(run)}
