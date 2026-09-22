"""GitHub App authorization and tenant boundary tests with real PostgreSQL transactions."""

import base64
import hashlib
import hmac
import json
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from test_auth import ORIGIN, PREFIX, AuthHarness, Identity
from test_github_provider import app_values, installation

from forge.config import Settings
from forge.main import create_app
from forge.migration import upgrade_database

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test database required"
    ),
]


@dataclass
class AppFixture:
    installation_id: int = field(default_factory=lambda: secrets.randbelow(2**50) + 1)
    records: dict[str, str] = field(default_factory=dict)
    requests: list[str] = field(default_factory=list)
    role: str = "admin"
    suspended: bool = False
    accessible: bool = True
    user_token: str = "app-user-token-do-not-return"

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.path)
        target = installation(
            id=self.installation_id, suspended_at="2026-09-22T12:00:00Z" if self.suspended else None
        )
        if request.url.path == "/login/oauth/access_token":
            assert request.url.host == "github.com"
            form = parse_qs(request.content.decode())
            assert form["client_id"] == ["fixture-app-client"]
            assert form["client_secret"] == ["fixture-app-secret"]
            assert form["redirect_uri"] == [f"{ORIGIN}/api/v1/integrations/github/callback"]
            verifier = form["code_verifier"][0]
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .decode()
                .rstrip("=")
            )
            assert self.records[form["code"][0]] == challenge
            return httpx.Response(
                200,
                json={"access_token": self.user_token, "token_type": "bearer", "expires_in": 28800},
            )
        assert request.url.host == "api.github.com"
        if request.url.path == "/user/installations":
            assert request.headers["authorization"] == f"Bearer {self.user_token}"
            return httpx.Response(200, json={"installations": [target] if self.accessible else []})
        if request.url.path == f"/app/installations/{self.installation_id}":
            assert request.headers["authorization"].startswith("Bearer ey")
            return httpx.Response(200, json=target)
        if request.url.path == "/user/memberships/orgs/fixture-org":
            return httpx.Response(
                200, json={"state": "active", "role": self.role, "organization": {"id": 10}}
            )
        raise AssertionError("Unexpected provider path")


@dataclass
class AppHarness:
    auth: AuthHarness
    provider: AppFixture

    async def owner(self) -> tuple[Identity, str]:
        owner = await self.auth.register()
        await self.auth.verify(owner)
        return owner, await self.auth.organization(owner)

    async def start(self, owner: Identity, organization: str) -> tuple[str, str]:
        response = await self.auth.mutate(
            owner.client, "POST", f"/organizations/{organization}/integrations/github/authorize", {}
        )
        assert response.status_code == 200, response.text
        query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
        assert query["client_id"] == ["fixture-app-client"]
        assert "scope" not in query
        code = secrets.token_urlsafe(24)
        self.provider.records[code] = query["code_challenge"][0]
        cookie = next(
            value
            for value in response.headers.get_list("set-cookie")
            if value.startswith("forge_github_app=")
        )
        assert "HttpOnly" in cookie and "Path=/api/v1/integrations/github" in cookie
        return query["state"][0], code

    async def callback(self, client: httpx.AsyncClient, state: str, code: str) -> httpx.Response:
        return await client.get(
            f"{PREFIX}/integrations/github/callback",
            params={"state": state, "code": code, "iss": "https://github.com/login/oauth"},
        )

    async def pending(self, owner: Identity, organization: str) -> str:
        state, code = await self.start(owner, organization)
        callback = await self.callback(owner.client, state, code)
        assert callback.status_code == 303
        assert parse_qs(urlsplit(callback.headers["location"]).query).get("github") == [
            "authorized"
        ], callback.headers["location"]
        status = await owner.client.get(
            f"{PREFIX}/organizations/{organization}/integrations/github"
        )
        assert status.status_code == 200, status.text
        return str(status.json()["authorization"]["id"])

    async def bind(
        self, owner: Identity, organization: str, pending: str | None = None
    ) -> httpx.Response:
        pending = pending or await self.pending(owner, organization)
        return await self.auth.mutate(
            owner.client,
            "POST",
            f"/organizations/{organization}/integrations/github/connections",
            {"authorization_id": pending, "installation_id": self.provider.installation_id},
        )

    async def repository(
        self, organization: str, integration: str, *, selected: bool = False
    ) -> str:
        engine = await self.auth.engine()
        identifier = uuid4()
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('forge.organization_id', :org, true)"),
                {"org": organization},
            )
            await connection.execute(
                text("""INSERT INTO forge.repositories
                (organization_id,id,integration_id,provider_id,owner,name,full_name,html_url,
                 default_branch,is_private,archived,selected)
                VALUES (:org,:id,:integration,:provider,'fixture-org','project',
                'fixture-org/project',
                'https://github.com/fixture-org/project','main',true,false,:selected)"""),
                {
                    "org": UUID(organization),
                    "id": identifier,
                    "integration": UUID(integration),
                    "provider": secrets.randbelow(2**50) + 1,
                    "selected": selected,
                },
            )
        return str(identifier)


@pytest.fixture
async def github(tmp_path: Path) -> AsyncIterator[AppHarness]:
    settings = Settings(
        environment="test",
        public_origin=ORIGIN,
        auth_secret=secrets.token_hex(32),
        mail_backend="file",
        mail_directory=tmp_path / "outbox",
        **app_values(),
    )
    assert settings.database_name.endswith("_test")
    upgrade_database(settings)
    app = create_app(settings)
    provider = AppFixture()
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(app.router.lifespan_context(app))
        await app.state.github_service.provider.client.aclose()
        app.state.github_service.provider.client = await stack.enter_async_context(
            httpx.AsyncClient(transport=httpx.MockTransport(provider.handle))
        )
        yield AppHarness(AuthHarness(app, settings, stack, tmp_path / "outbox"), provider)


async def test_app_authorization_is_browser_bound_encrypted_one_use_and_enqueues_catalog(
    github: AppHarness,
) -> None:
    owner, organization = await github.owner()
    state, code = await github.start(owner, organization)
    stranger = await github.auth.client()
    rejected = await github.callback(stranger, state, code)
    assert rejected.headers["location"] == "/login?oauth_error=link_unavailable"
    assert not github.provider.requests
    callback = await github.callback(owner.client, state, code)
    assert callback.status_code == 303 and "github=authorized" in callback.headers["location"]
    assert not owner.client.cookies.get("forge_github_app")
    engine = await github.auth.engine()
    async with engine.connect() as connection:
        attempt = (
            (
                await connection.execute(
                    text("SELECT * FROM forge.github_app_authorizations WHERE state_hash=:state"),
                    {"state": hashlib.sha256(state.encode()).hexdigest()},
                )
            )
            .mappings()
            .one()
        )
    assert attempt["state_hash"] != state and attempt["used_at"] is not None
    assert github.provider.user_token not in attempt["token_ciphertext"]
    status = await owner.client.get(f"{PREFIX}/organizations/{organization}/integrations/github")
    assert github.provider.user_token not in status.text
    authorization = status.json()["authorization"]["id"]
    accessible = await owner.client.get(
        f"{PREFIX}/organizations/{organization}/integrations/github/authorizations/{authorization}/installations"
    )
    assert (
        accessible.status_code == 200
        and accessible.json()["installations"][0]["id"] == github.provider.installation_id
    )
    bound = await github.bind(owner, organization, authorization)
    assert bound.status_code == 201, bound.text
    assert bound.json()["connection"]["status"] == "active"
    assert bound.json()["sync"]["kind"] == "catalog" and bound.json()["sync"]["status"] == "queued"
    assert github.provider.user_token not in bound.text
    assert (await github.bind(owner, organization, authorization)).status_code == 404
    async with engine.connect() as connection:
        completed = (
            await connection.execute(
                text(
                    "SELECT token_ciphertext,completed_at FROM forge.github_app_authorizations "
                    "WHERE id=:id"
                ),
                {"id": UUID(authorization)},
            )
        ).one()
    assert completed.token_ciphertext is None and completed.completed_at is not None


async def test_authorization_requires_verified_manager_and_csrf(github: AppHarness) -> None:
    owner = await github.auth.register()
    organization = await github.auth.organization(owner)
    path = f"/organizations/{organization}/integrations/github/authorize"
    assert (await github.auth.mutate(owner.client, "POST", path, {})).status_code == 403
    await github.auth.verify(owner)
    assert (await owner.client.post(f"{PREFIX}{path}", json={})).status_code == 403
    viewer = await github.auth.register()
    await github.auth.join(owner, organization, viewer, "viewer")
    assert (await github.auth.mutate(viewer.client, "POST", path, {})).status_code == 403
    outsider, _ = await github.owner()
    assert (await github.auth.mutate(outsider.client, "POST", path, {})).status_code == 404
    assert not github.provider.requests


async def test_callback_rechecks_same_session_and_role_before_exchange(github: AppHarness) -> None:
    owner, organization = await github.owner()
    admin = await github.auth.register()
    member_id = await github.auth.join(owner, organization, admin, "admin")
    state, code = await github.start(admin, organization)
    assert (
        await github.auth.mutate(
            owner.client,
            "PATCH",
            f"/organizations/{organization}/members/{member_id}",
            {"role": "member"},
        )
    ).status_code == 200
    rejected = await github.callback(admin.client, state, code)
    assert "github_error=forbidden" in rejected.headers["location"]
    assert not github.provider.requests
    state, code = await github.start(owner, organization)
    assert (await github.auth.mutate(owner.client, "POST", "/auth/logout")).status_code == 204
    rejected = await github.callback(owner.client, state, code)
    assert "link_unavailable" in rejected.headers["location"]
    assert not github.provider.requests


async def test_binding_rechecks_source_authority_and_denies_other_org_or_session(
    github: AppHarness,
) -> None:
    owner, organization = await github.owner()
    pending = await github.pending(owner, organization)
    github.provider.role = "member"
    rejected = await github.bind(owner, organization, pending)
    assert rejected.status_code == 409 and rejected.json()["code"] == "installation_admin_required"
    github.provider.role = "admin"
    github.provider.accessible = False
    rejected = await github.bind(owner, organization, pending)
    assert rejected.status_code == 409 and rejected.json()["code"] == "access_denied"
    github.provider.accessible = True
    assert (await github.bind(owner, organization, pending)).status_code == 201
    other, other_org = await github.owner()
    pending_other = await github.pending(other, other_org)
    rejected = await github.bind(other, other_org, pending_other)
    assert rejected.status_code == 409 and rejected.json()["code"] == "installation_conflict"
    assert (await github.bind(other, organization, pending)).status_code == 404


async def test_selected_repository_sync_is_coalesced_and_tenant_scoped(github: AppHarness) -> None:
    owner, organization = await github.owner()
    bound = await github.bind(owner, organization)
    assert bound.status_code == 201, bound.text
    integration = bound.json()["connection"]["id"]
    repository = await github.repository(organization, integration)
    select_path = (
        f"/organizations/{organization}/integrations/github/connections/{integration}/selection"
    )
    selected = await github.auth.mutate(
        owner.client, "POST", select_path, {"changes": [{"id": repository, "selected": True}]}
    )
    assert selected.status_code == 200 and selected.json() == {"updated": 1}
    catalog = await owner.client.get(f"{PREFIX}/organizations/{organization}/repositories")
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["items"][0]["id"] == repository
    assert catalog.json()["items"][0]["commit_count"] == 0
    sync_path = f"/organizations/{organization}/repositories/{repository}/sync"
    first = await github.auth.mutate(owner.client, "POST", sync_path, {})
    second = await github.auth.mutate(owner.client, "POST", sync_path, {})
    assert first.status_code == second.status_code == 202
    assert first.json()["sync"]["id"] == second.json()["sync"]["id"]
    other, other_org = await github.owner()
    assert (
        await other.client.get(f"{PREFIX}/organizations/{organization}/repositories")
    ).status_code == 404
    assert (
        await github.auth.mutate(
            other.client, "POST", f"/organizations/{other_org}/repositories/{repository}/sync", {}
        )
    ).status_code == 404
    assert (
        await github.auth.mutate(
            owner.client, "POST", select_path, {"changes": [{"id": repository, "selected": False}]}
        )
    ).status_code == 200
    runs = await owner.client.get(
        f"{PREFIX}/organizations/{organization}/repositories/{repository}/sync-runs"
    )
    assert runs.status_code == 200 and runs.json()["items"][0]["status"] == "canceled"
    assert (await owner.client.get(f"{PREFIX}/organizations/{organization}/repositories")).json()[
        "items"
    ] == []


async def test_disconnect_retains_binding_and_history_but_cancels_work(github: AppHarness) -> None:
    owner, organization = await github.owner()
    bound = await github.bind(owner, organization)
    assert bound.status_code == 201, bound.text
    integration = bound.json()["connection"]["id"]
    repository = await github.repository(organization, integration, selected=True)
    path = f"/organizations/{organization}/integrations/github/connections/{integration}"
    assert (await github.auth.mutate(owner.client, "DELETE", path)).status_code == 204
    status = (
        await owner.client.get(f"{PREFIX}/organizations/{organization}/integrations/github")
    ).json()
    assert status["connections"][0]["status"] == "disconnected"
    assert status["connections"][0]["catalog_sync"]["status"] == "canceled"
    assert (
        await github.auth.mutate(owner.client, "POST", path + "/refresh", {})
    ).status_code == 404
    engine = await github.auth.engine()
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('forge.organization_id', :org, true)"), {"org": organization}
        )
        row = (
            await connection.execute(
                text("SELECT selected,authorized FROM forge.repositories WHERE id=:id"),
                {"id": UUID(repository)},
            )
        ).one()
    assert not row.selected and not row.authorized
    reconnected = await github.bind(owner, organization)
    assert reconnected.status_code == 201, reconnected.text
    assert reconnected.json()["connection"]["id"] == integration


async def test_refresh_records_suspension_and_reactivates_only_after_positive_check(
    github: AppHarness,
) -> None:
    owner, organization = await github.owner()
    bound = await github.bind(owner, organization)
    assert bound.status_code == 201, bound.text
    integration = bound.json()["connection"]["id"]
    github.provider.suspended = True
    path = f"/organizations/{organization}/integrations/github/connections/{integration}/refresh"
    failed = await github.auth.mutate(owner.client, "POST", path, {})
    assert failed.status_code == 409 and failed.json()["code"] == "installation_suspended"
    status = (
        await owner.client.get(f"{PREFIX}/organizations/{organization}/integrations/github")
    ).json()
    assert status["connections"][0]["status"] == "suspended"
    github.provider.suspended = False
    assert (await github.auth.mutate(owner.client, "POST", path, {})).status_code == 202
    status = (
        await owner.client.get(f"{PREFIX}/organizations/{organization}/integrations/github")
    ).json()
    assert status["connections"][0]["status"] == "active"


async def test_binding_does_not_overwrite_revocation_received_during_provider_check(
    github: AppHarness,
) -> None:
    owner, organization = await github.owner()
    bound = await github.bind(owner, organization)
    assert bound.status_code == 201, bound.text
    integration = bound.json()["connection"]["id"]
    pending = await github.pending(owner, organization)
    secret = github.auth.settings.github_app_webhook_secret
    assert secret is not None
    body = json.dumps(
        {"installation": {"id": github.provider.installation_id}, "action": "suspend"}
    ).encode()
    signature = hmac.new(secret.get_secret_value().encode(), body, hashlib.sha256).hexdigest()
    revoked = False

    async def revoke_during_lookup(request: httpx.Request) -> httpx.Response:
        nonlocal revoked
        # Return the positive response fetched before the revocation arrived.
        response = github.provider.handle(request)
        if request.url.path == f"/app/installations/{github.provider.installation_id}":
            delivered = await owner.client.post(
                f"{PREFIX}/webhooks/github",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Delivery": str(uuid4()),
                    "X-GitHub-Event": "installation",
                    "X-Hub-Signature-256": f"sha256={signature}",
                },
            )
            assert delivered.status_code == 202, delivered.text
            revoked = True
        return response

    provider = github.auth.app.state.github_service.provider
    await provider.client.aclose()
    provider.client = await github.auth.stack.enter_async_context(
        httpx.AsyncClient(transport=httpx.MockTransport(revoke_during_lookup))
    )
    rejected = await github.bind(owner, organization, pending)
    assert revoked
    assert rejected.status_code == 409 and rejected.json()["code"] == "integration_changed"
    status = (
        await owner.client.get(f"{PREFIX}/organizations/{organization}/integrations/github")
    ).json()
    assert status["connections"][0]["id"] == integration
    assert status["connections"][0]["status"] == "suspended"
    assert status["connections"][0]["last_error"] == "access_revoked"
    assert status["connections"][0]["catalog_sync"]["status"] == "canceled"
    assert status["authorization"]["id"] == pending


@pytest.mark.parametrize("failure", ["issuer", "denial"])
async def test_app_callback_denial_or_wrong_issuer_consumes_state_without_exchange(
    github: AppHarness,
    failure: str,
) -> None:
    owner, organization = await github.owner()
    state, code = await github.start(owner, organization)
    query = {"state": state, "code": code, "iss": "https://github.com/login/oauth"}
    if failure == "issuer":
        query["iss"] = "https://github.com"
    else:
        query["error"] = "access_denied"
    response = await owner.client.get(f"{PREFIX}/integrations/github/callback", params=query)
    expected = "invalid_callback" if failure == "issuer" else "denied"
    assert (
        response.status_code == 303 and f"github_error={expected}" in response.headers["location"]
    )
    assert not github.provider.requests
    engine = await github.auth.engine()
    async with engine.connect() as connection:
        used = await connection.scalar(
            text("SELECT used_at FROM forge.github_app_authorizations WHERE state_hash=:hash"),
            {"hash": hashlib.sha256(state.encode()).hexdigest()},
        )
    assert used is not None


async def test_pending_authorization_is_bound_to_user_and_expires(github: AppHarness) -> None:
    owner, organization = await github.owner()
    pending = await github.pending(owner, organization)
    admin = await github.auth.register()
    await github.auth.join(owner, organization, admin, "admin")
    github.provider.requests.clear()
    assert (await github.bind(admin, organization, pending)).status_code == 404
    assert not github.provider.requests
    engine = await github.auth.engine()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE forge.github_app_authorizations SET expires_at=now()-interval '1 second' "
                "WHERE id=:id"
            ),
            {"id": UUID(pending)},
        )
    assert (await github.bind(owner, organization, pending)).status_code == 404
    assert not github.provider.requests
    status = (
        await owner.client.get(f"{PREFIX}/organizations/{organization}/integrations/github")
    ).json()
    assert status["authorization"] is None


async def test_app_authorization_expired_state_never_reaches_provider(github: AppHarness) -> None:
    owner, organization = await github.owner()
    state, code = await github.start(owner, organization)
    engine = await github.auth.engine()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE forge.github_app_authorizations SET expires_at=now()-interval '1 second' "
                "WHERE state_hash=:hash"
            ),
            {"hash": hashlib.sha256(state.encode()).hexdigest()},
        )
    response = await github.callback(owner.client, state, code)
    assert response.headers["location"] == "/login?oauth_error=link_unavailable"
    assert not github.provider.requests
