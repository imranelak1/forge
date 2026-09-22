"""Real database/session tests; only the external providers use a fake HTTP transport."""

import base64
import json
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import text
from test_auth import ORIGIN, PASSWORD, PREFIX, AuthHarness

from forge.config import Settings
from forge.main import create_app
from forge.migration import upgrade_database

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test DB not supplied"
    ),
]


@dataclass
class ProviderFixture:
    key: Any = field(
        default_factory=lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if str(request.url) == "https://www.googleapis.com/oauth2/v3/certs":
            key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
            return httpx.Response(
                200, json={"keys": [{**key, "kid": "fixture", "alg": "RS256", "use": "sig"}]}
            )
        if request.url.path in {"/login/oauth/access_token", "/token"}:
            form = parse_qs(request.content.decode())
            code = form["code"][0]
            record = self.records[code]
            assert form["redirect_uri"] == [
                f"{ORIGIN}/api/v1/auth/oauth/{record['provider']}/callback"
            ]
            verifier = form["code_verifier"][0]
            assert (
                base64.urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b"=").decode()
                == record["challenge"]
            )
            if record.get("outage"):
                return httpx.Response(
                    503, json={"error": "provider internal detail must not escape"}
                )
            if record["provider"] == "github":
                return httpx.Response(
                    200,
                    json={
                        "access_token": code,
                        "token_type": "bearer",
                        "scope": "read:user,user:email",
                    },
                )
            current = datetime.now(UTC)
            claims = {
                "iss": "https://accounts.google.com",
                "aud": "google-fixture-client",
                "sub": record["subject"],
                "iat": int(current.timestamp()),
                "exp": int((current + timedelta(minutes=10)).timestamp()),
                "nonce": record["nonce"],
                "email": record["email"],
                "email_verified": record.get("verified", True),
                "name": "OAuth Google",
                **record.get("claims", {}),
            }
            key = record.get("signing_key", self.key)
            token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "fixture"})
            return httpx.Response(
                200, json={"access_token": code, "token_type": "Bearer", "id_token": token}
            )
        record = self.records[request.headers["authorization"].split(" ", 1)[1]]
        if request.url.path == "/user":
            return httpx.Response(
                200, json={"id": int(record["subject"]), "login": "fixture", "name": "OAuth GitHub"}
            )
        if request.url.path == "/user/emails":
            return httpx.Response(
                200,
                json=[
                    {
                        "email": record["email"],
                        "primary": True,
                        "verified": record.get("verified", True),
                    }
                ],
            )
        raise AssertionError(f"Unexpected provider endpoint: {request.url.host}{request.url.path}")


@dataclass
class OAuthHarness:
    auth: AuthHarness
    provider: ProviderFixture

    async def start(
        self,
        client: httpx.AsyncClient,
        provider: str = "github",
        *,
        intent: str = "login",
        return_to: str = "/app",
        subject: str | None = None,
        email: str | None = None,
        **overrides: Any,
    ) -> tuple[str, str]:
        response = await self.auth.mutate(
            client,
            "POST",
            f"/auth/oauth/{provider}/start",
            {"intent": intent, "return_to": return_to},
        )
        assert response.status_code == 200, response.text
        url = urlsplit(response.json()["authorization_url"])
        assert url.scheme == "https"
        assert url.hostname == ("github.com" if provider == "github" else "accounts.google.com")
        query = parse_qs(url.query)
        assert query["code_challenge_method"] == ["S256"]
        assert "repo" not in query.get("scope", [""])[0]
        code = secrets.token_urlsafe(24)
        self.provider.records[code] = {
            "provider": provider,
            "subject": subject or str(secrets.randbelow(2**60)),
            "email": email
            or f"oauth-{uuid4().hex}@{'gmail.com' if provider == 'google' else 'example.com'}",
            "challenge": query["code_challenge"][0],
            "nonce": query.get("nonce", [""])[0],
            **overrides,
        }
        cookie = next(
            item
            for item in response.headers.get_list("set-cookie")
            if item.startswith("forge_oauth=")
        )
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert "Path=/api/v1/auth/oauth" in cookie
        return query["state"][0], code

    async def finish(
        self, client: httpx.AsyncClient, state: str, code: str, provider: str = "github"
    ) -> httpx.Response:
        return await client.get(
            f"{PREFIX}/auth/oauth/{provider}/callback", params={"state": state, "code": code}
        )


@pytest.fixture
async def oauth(tmp_path: Path) -> AsyncIterator[OAuthHarness]:
    settings = Settings(
        environment="test",
        public_origin=ORIGIN,
        auth_secret=secrets.token_hex(32),
        mail_backend="file",
        mail_directory=tmp_path / "outbox",
        github_client_id="github-fixture-client",
        github_client_secret="github-fixture-secret",
        google_client_id="google-fixture-client",
        google_client_secret="google-fixture-secret",
    )
    assert settings.database_name.endswith("_test"), "Refuse to use a non-test database"
    upgrade_database(settings)
    app = create_app(settings)
    provider = ProviderFixture()
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(app.router.lifespan_context(app))
        original = app.state.oauth_service.provider.client
        await original.aclose()
        app.state.oauth_service.provider.client = await stack.enter_async_context(
            httpx.AsyncClient(transport=httpx.MockTransport(provider.handle))
        )
        yield OAuthHarness(AuthHarness(app, settings, stack, tmp_path / "outbox"), provider)


def failure(response: httpx.Response, code: str) -> None:
    assert response.status_code == 303, response.text
    location = urlsplit(response.headers["location"])
    assert not location.netloc and location.path in {"/login", "/app/account"}
    assert parse_qs(location.query)["oauth_error"] == [code]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize("provider", ["github", "google"])
async def test_new_and_returning_identity_uses_existing_session_security(
    oauth: OAuthHarness, provider: str
) -> None:
    client = await oauth.auth.client()
    providers = (await client.get(f"{PREFIX}/auth/providers")).json()
    assert {p["id"] for p in providers["providers"] if p["enabled"]} == {"github", "google"}
    state, code = await oauth.start(client, provider, return_to="/app/account")
    record = oauth.provider.records[code]
    response = await oauth.finish(client, state, code, provider)
    assert response.status_code == 303, response.text
    assert urlsplit(response.headers["location"]).path == "/app/account"
    assert client.cookies.get("forge_access") and client.cookies.get("forge_refresh")
    assert not client.cookies.get("forge_oauth")
    user = (await client.get(f"{PREFIX}/auth/me")).json()["user"]
    assert user["email"] == record["email"] and user["email_verified"] is True
    connections = (await client.get(f"{PREFIX}/auth/connections")).json()["connections"]
    assert [connection["provider"] for connection in connections] == [provider]
    session = client.cookies.get("forge_refresh")
    assert (await oauth.auth.mutate(client, "POST", "/auth/refresh")).status_code == 200
    assert client.cookies.get("forge_refresh") != session
    assert (await oauth.auth.mutate(client, "POST", "/auth/logout")).status_code == 204
    state, code = await oauth.start(
        client, provider, subject=record["subject"], email=record["email"]
    )
    assert (await oauth.finish(client, state, code, provider)).status_code == 303
    assert (await client.get(f"{PREFIX}/auth/me")).json()["user"]["id"] == user["id"]


async def test_start_requires_csrf_and_origin(oauth: OAuthHarness) -> None:
    client = await oauth.auth.client()
    response = await client.post(
        f"{PREFIX}/auth/oauth/github/start", json={"intent": "login", "return_to": "/app"}
    )
    assert response.status_code == 403
    assert not oauth.provider.requests


@pytest.mark.parametrize(
    "provider,issuer",
    [("google", "https://accounts.google.com"), ("github", "https://github.com")],
)
async def test_callback_accepts_pinned_authorization_issuer(
    oauth: OAuthHarness, provider: str, issuer: str
) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(client, provider)
    response = await client.get(
        f"{PREFIX}/auth/oauth/{provider}/callback",
        params={"state": state, "code": code, "iss": issuer, "authuser": "0"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/app?oauth=signed-in"
    user = (await client.get(f"{PREFIX}/auth/me")).json()["user"]
    assert user["email"] == oauth.provider.records[code]["email"]
    assert user["email_verified"] is True
    assert oauth.provider.requests


@pytest.mark.parametrize(
    "provider,issuers",
    [
        ("google", ["https://attacker.example.com"]),
        ("google", ["https://accounts.google.com/"]),
        ("google", ["https://accounts.google.com", "https://accounts.google.com"]),
        ("google", ["https://attacker.example.com", "https://accounts.google.com"]),
        ("github", ["https://accounts.google.com"]),
    ],
)
async def test_callback_rejects_ambiguous_or_mismatched_issuer_before_exchange(
    oauth: OAuthHarness, provider: str, issuers: list[str]
) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(client, provider)
    response = await client.get(
        f"{PREFIX}/auth/oauth/{provider}/callback",
        params=[("state", state), ("code", code), *[("iss", issuer) for issuer in issuers]],
    )
    failure(response, "invalid_identity")
    assert not oauth.provider.requests
    assert not client.cookies.get("forge_access")
    engine = await oauth.auth.engine()
    async with engine.connect() as connection:
        consumed = await connection.scalar(
            text("SELECT used_at FROM forge.oauth_states WHERE state_hash=:value"),
            {"value": sha256(state.encode()).hexdigest()},
        )
    assert consumed is not None


async def test_state_is_hashed_browser_bound_and_one_use(oauth: OAuthHarness) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(client)
    engine = await oauth.auth.engine()
    async with engine.connect() as connection:
        stored = (
            await connection.execute(
                text(
                    "SELECT state_hash, browser_hash FROM forge.oauth_states "
                    "WHERE state_hash=:value"
                ),
                {"value": sha256(state.encode()).hexdigest()},
            )
        ).one()
        assert stored.state_hash != state
        assert stored.browser_hash != client.cookies.get("forge_oauth")
    stranger = await oauth.auth.client()
    failure(await oauth.finish(stranger, state, code), "invalid_state")
    assert not oauth.provider.requests
    assert (await oauth.finish(client, state, code)).status_code == 303
    assert (await client.get(f"{PREFIX}/auth/me")).status_code == 200
    failure(await oauth.finish(client, state, code), "invalid_state")


async def test_expired_state_and_wrong_provider_are_rejected(oauth: OAuthHarness) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(client)
    failure(await oauth.finish(client, state, code, "google"), "invalid_state")
    state, code = await oauth.start(client)
    engine = await oauth.auth.engine()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE forge.oauth_states SET expires_at=now()-interval '1 second' "
                "WHERE state_hash=:value"
            ),
            {"value": sha256(state.encode()).hexdigest()},
        )
    failure(await oauth.finish(client, state, code), "invalid_state")
    assert not oauth.provider.requests


async def test_denial_consumes_state_without_echoing_provider_content(oauth: OAuthHarness) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(client)
    cookie = client.cookies.get("forge_oauth")
    response = await client.get(
        f"{PREFIX}/auth/oauth/github/callback",
        params={
            "state": state,
            "error": "access_denied",
            "error_description": "secret<script>untrusted</script>",
        },
    )
    failure(response, "denied")
    assert "secret" not in response.text + response.headers["location"]
    client.cookies.set("forge_oauth", cookie, domain="localhost.local", path="/api/v1/auth/oauth")
    failure(await oauth.finish(client, state, code), "invalid_state")
    assert not oauth.provider.requests


@pytest.mark.parametrize("provider", ["github", "google"])
async def test_existing_email_does_not_implicitly_link(oauth: OAuthHarness, provider: str) -> None:
    existing = await oauth.auth.register()
    await oauth.auth.verify(existing)
    stranger = await oauth.auth.client()
    state, code = await oauth.start(stranger, provider, email=existing.email)
    failure(await oauth.finish(stranger, state, code, provider), "account_exists")
    assert (await stranger.get(f"{PREFIX}/auth/me")).status_code == 401
    assert (await existing.client.get(f"{PREFIX}/auth/connections")).json()["connections"] == []


@pytest.mark.parametrize("provider", ["github", "google"])
async def test_explicit_verified_account_link_then_provider_login(
    oauth: OAuthHarness, provider: str
) -> None:
    existing = await oauth.auth.register()
    await oauth.auth.verify(existing)
    state, code = await oauth.start(existing.client, provider, intent="link")
    record = oauth.provider.records[code]
    result = await oauth.finish(existing.client, state, code, provider)
    assert result.status_code == 303
    assert result.headers["location"] == "/app/account?oauth=linked"
    assert (await existing.client.get(f"{PREFIX}/auth/me")).json()["user"]["id"] == existing.user_id
    assert (await oauth.auth.mutate(existing.client, "POST", "/auth/logout")).status_code == 204
    state, code = await oauth.start(
        existing.client, provider, subject=record["subject"], email=record["email"]
    )
    assert (await oauth.finish(existing.client, state, code, provider)).status_code == 303
    assert (await existing.client.get(f"{PREFIX}/auth/me")).json()["user"]["id"] == existing.user_id


async def test_link_requires_verification_and_same_active_session(oauth: OAuthHarness) -> None:
    existing = await oauth.auth.register()
    result = await oauth.auth.mutate(
        existing.client,
        "POST",
        "/auth/oauth/github/start",
        {"intent": "link", "return_to": "/app/account"},
    )
    assert result.status_code == 403
    await oauth.auth.verify(existing)
    state, code = await oauth.start(existing.client, intent="link")
    browser_binding = existing.client.cookies.get("forge_oauth")
    access = existing.client.cookies.get("forge_access")
    assert (await oauth.auth.mutate(existing.client, "POST", "/auth/logout")).status_code == 204
    # Even stolen pre-logout cookies cannot finish a link after session revocation.
    existing.client.cookies.set(
        "forge_oauth", browser_binding, domain="localhost.local", path="/api/v1/auth/oauth"
    )
    existing.client.cookies.set("forge_access", access, domain="localhost.local", path="/api/v1")
    failure(await oauth.finish(existing.client, state, code), "link_unavailable")


async def test_provider_identity_cannot_link_to_another_user(oauth: OAuthHarness) -> None:
    owner = await oauth.auth.register()
    await oauth.auth.verify(owner)
    state, code = await oauth.start(owner.client, intent="link")
    record = oauth.provider.records[code]
    assert (await oauth.finish(owner.client, state, code)).status_code == 303
    stranger = await oauth.auth.register()
    await oauth.auth.verify(stranger)
    state, code = await oauth.start(
        stranger.client, intent="link", subject=record["subject"], email=record["email"]
    )
    failure(await oauth.finish(stranger.client, state, code), "identity_in_use")
    assert (await stranger.client.get(f"{PREFIX}/auth/connections")).json()["connections"] == []


@pytest.mark.parametrize("provider", ["github", "google"])
async def test_unverified_provider_email_is_rejected(oauth: OAuthHarness, provider: str) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(client, provider, verified=False)
    failure(await oauth.finish(client, state, code, provider), "email_unverified")
    assert (await client.get(f"{PREFIX}/auth/me")).status_code == 401


@pytest.mark.parametrize(
    "claim,value",
    [
        ("aud", "different-client"),
        ("iss", "https://attacker.example.com"),
        ("nonce", "not-this-browser"),
        ("exp", 1),
    ],
)
async def test_google_oidc_claims_are_validated(
    oauth: OAuthHarness, claim: str, value: Any
) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(client, "google", claims={claim: value})
    failure(await oauth.finish(client, state, code, "google"), "invalid_identity")
    assert (await client.get(f"{PREFIX}/auth/me")).status_code == 401


async def test_google_invalid_signature_is_rejected(oauth: OAuthHarness) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(
        client, "google", signing_key=rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )
    failure(await oauth.finish(client, state, code, "google"), "invalid_identity")


async def test_google_third_party_email_requires_explicit_verified_link(
    oauth: OAuthHarness,
) -> None:
    client = await oauth.auth.client()
    email = f"google-third-party-{uuid4().hex}@example.com"
    state, code = await oauth.start(client, "google", email=email)
    record = oauth.provider.records[code]
    failure(await oauth.finish(client, state, code, "google"), "email_unverified")
    assert (await client.get(f"{PREFIX}/auth/me")).status_code == 401
    mailbox_owner = await oauth.auth.register(email=email)
    await oauth.auth.verify(mailbox_owner)
    state, code = await oauth.start(
        mailbox_owner.client, "google", intent="link", email=email, subject=record["subject"]
    )
    assert (await oauth.finish(mailbox_owner.client, state, code, "google")).status_code == 303
    state, code = await oauth.start(client, "google", email=email, subject=record["subject"])
    assert (await oauth.finish(client, state, code, "google")).status_code == 303
    assert (await client.get(f"{PREFIX}/auth/me")).json()["user"]["id"] == mailbox_owner.user_id


async def test_oauth_only_user_can_set_password_via_verified_reset(oauth: OAuthHarness) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(client)
    email = oauth.provider.records[code]["email"]
    assert (await oauth.finish(client, state, code)).status_code == 303
    anonymous = await oauth.auth.client()
    denied = await oauth.auth.mutate(
        anonymous, "POST", "/auth/login", {"email": email, "password": PASSWORD}
    )
    assert denied.status_code == 401
    assert (
        await oauth.auth.mutate(anonymous, "POST", "/auth/password-reset/request", {"email": email})
    ).status_code == 202
    token = oauth.auth.delivered_token(email, "reset-password")
    assert (
        await oauth.auth.mutate(
            anonymous,
            "POST",
            "/auth/password-reset/confirm",
            {"token": token, "password": PASSWORD},
        )
    ).status_code == 200
    assert (await client.get(f"{PREFIX}/auth/me")).status_code == 401
    assert (
        await oauth.auth.mutate(
            anonymous, "POST", "/auth/login", {"email": email, "password": PASSWORD}
        )
    ).status_code == 200


@pytest.mark.parametrize(
    "destination",
    [
        "https://attacker.example.com/app",
        "//attacker.example.com/app",
        "/app/../../login",
        "/app\\evil",
    ],
)
async def test_return_destination_cannot_escape_app(oauth: OAuthHarness, destination: str) -> None:
    client = await oauth.auth.client()
    response = await oauth.auth.mutate(
        client, "POST", "/auth/oauth/github/start", {"intent": "login", "return_to": destination}
    )
    if response.status_code in {400, 422}:
        return
    assert response.status_code == 200
    state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
    engine = await oauth.auth.engine()
    async with engine.connect() as connection:
        target = await connection.scalar(
            text("SELECT return_to FROM forge.oauth_states WHERE state_hash=:value"),
            {"value": sha256(state.encode()).hexdigest()},
        )
        assert target == "/app"


async def test_provider_outage_returns_safe_recoverable_error(oauth: OAuthHarness) -> None:
    client = await oauth.auth.client()
    state, code = await oauth.start(client, outage=True)
    response = await oauth.finish(client, state, code)
    failure(response, "provider_unavailable")
    assert "internal detail" not in response.text + response.headers["location"]
    assert not client.cookies.get("forge_access")
