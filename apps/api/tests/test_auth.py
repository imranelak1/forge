"""Identity security contracts against the actual application and PostgreSQL.

These tests deliberately do not mock authentication, delivery, or repositories.
The caller must opt in with a disposable database ending in ``_test``.
"""

import asyncio
import os
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import jwt
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from forge.config import Settings
from forge.main import create_app
from forge.migration import upgrade_database

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test DB not supplied"
    ),
]

ORIGIN = "http://localhost:3000"
PREFIX = "/api/v1"
PASSWORD = "Correct horse battery staple 2026!"


@dataclass
class Identity:
    client: httpx.AsyncClient
    email: str
    user_id: str
    session_id: str


@dataclass
class AuthHarness:
    app: FastAPI
    settings: Settings
    stack: AsyncExitStack
    outbox: Path
    clients: list[httpx.AsyncClient] = field(default_factory=list)

    async def engine(
        self, *, migration: bool = False, single_connection: bool = False
    ) -> AsyncEngine:
        engine = create_async_engine(
            self.settings.database_url(migration=migration),
            pool_size=1 if single_connection else 2,
            max_overflow=0,
            hide_parameters=True,
        )
        self.stack.push_async_callback(engine.dispose)
        return engine

    def delivered_token(self, email: str, route: str) -> str:
        for path in sorted(
            self.outbox.glob("*.eml"), key=lambda item: item.stat().st_mtime_ns, reverse=True
        ):
            message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
            if parseaddr(str(message["To"]))[1].lower() != email.lower():
                continue
            body = message.get_body(preferencelist=("plain",))
            assert body is not None
            match = re.search(
                re.escape(f"{ORIGIN}/{route}#token=") + r"([A-Za-z0-9_-]+)", body.get_content()
            )
            if match:
                return match.group(1)
        pytest.fail("The configured mail adapter did not deliver the expected message")

    async def verify(self, identity: Identity) -> None:
        token = self.delivered_token(identity.email, "verify-email")
        response = await self.mutate(
            identity.client, "POST", "/auth/verify-email/confirm", {"token": token}
        )
        assert response.status_code == 200, response.text

    async def invite(
        self, owner: Identity, organization_id: str, member: Identity, role: str
    ) -> str:
        response = await self.mutate(
            owner.client,
            "POST",
            f"/organizations/{organization_id}/invitations",
            {"email": member.email, "role": role},
        )
        assert response.status_code == 201, response.text
        assert "token" not in response.json()
        return self.delivered_token(member.email, "invite")

    async def join(self, owner: Identity, organization_id: str, member: Identity, role: str) -> str:
        await self.verify(member)
        token = await self.invite(owner, organization_id, member, role)
        response = await self.mutate(member.client, "POST", "/invitations/accept", {"token": token})
        assert response.status_code == 200, response.text
        response = await owner.client.get(f"{PREFIX}/organizations/{organization_id}/members")
        return next(
            item["id"] for item in response.json()["data"] if item["user_id"] == member.user_id
        )

    async def client(self) -> httpx.AsyncClient:
        # Give independent simulated browsers independent, trusted transport IPs.
        # X-Forwarded-For is intentionally never used as a rate-limit bypass.
        ip = f"192.0.2.{secrets.randbelow(250) + 1}"
        client = await self.stack.enter_async_context(
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app, client=(ip, 12345)),
                base_url=ORIGIN,
            )
        )
        self.clients.append(client)
        return client

    async def mutate(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        csrf = await client.get(f"{PREFIX}/auth/csrf")
        assert csrf.status_code == 200, csrf.text
        return await client.request(
            method,
            f"{PREFIX}{path}",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf.json()["csrf_token"]},
            json=data,
        )

    async def register(self, *, email: str | None = None) -> Identity:
        client = await self.client()
        address = email or f"security-{uuid4().hex}@example.com"
        response = await self.mutate(
            client,
            "POST",
            "/auth/register",
            {"name": "Security Test", "email": address, "password": PASSWORD},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "access_token" not in body and "refresh_token" not in body
        assert client.cookies.get("forge_access")
        assert client.cookies.get("forge_refresh")
        return Identity(client, address, body["user"]["id"], body["session_id"])

    async def organization(self, identity: Identity, name: str = "Security workspace") -> str:
        response = await self.mutate(
            identity.client,
            "POST",
            "/organizations",
            {"name": name, "slug": f"security-{uuid4().hex}"},
        )
        assert response.status_code == 201, response.text
        return str(response.json()["id"])


@pytest.fixture
async def auth(tmp_path: Path) -> AsyncIterator[AuthHarness]:
    settings = Settings(
        environment="test",
        public_origin=ORIGIN,
        auth_secret=secrets.token_hex(32),
        mail_backend="file",
        mail_directory=tmp_path / "outbox",
    )
    assert settings.database_name.endswith("_test"), "Refuse to use a non-test database"
    upgrade_database(settings)
    app = create_app(settings)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(app.router.lifespan_context(app))
        yield AuthHarness(app, settings, stack, tmp_path / "outbox")


async def test_register_login_logout_and_immediate_cookie_revocation(auth: AuthHarness) -> None:
    identity = await auth.register()
    me = await identity.client.get(f"{PREFIX}/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == identity.email
    assert me.json()["organizations"] == []

    old_access = identity.client.cookies.get("forge_access")
    logout = await auth.mutate(identity.client, "POST", "/auth/logout")
    assert logout.status_code == 204, logout.text
    assert not identity.client.cookies.get("forge_access")
    assert not identity.client.cookies.get("forge_refresh")
    identity.client.cookies.set("forge_access", old_access)
    assert (await identity.client.get(f"{PREFIX}/auth/me")).status_code == 401
    identity.client.cookies.clear()

    login = await auth.mutate(
        identity.client,
        "POST",
        "/auth/login",
        {"email": identity.email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["id"] == identity.user_id
    assert login.json()["session_id"] != identity.session_id
    cookies = login.headers.get_list("set-cookie")
    assert any("forge_access=" in cookie and "HttpOnly" in cookie for cookie in cookies)
    assert any("forge_refresh=" in cookie and "HttpOnly" in cookie for cookie in cookies)
    assert all("samesite=lax" in cookie.lower() for cookie in cookies)


@pytest.mark.parametrize("authenticated", [False, True])
async def test_origin_and_csrf_are_required_for_cookie_mutations(
    auth: AuthHarness, authenticated: bool
) -> None:
    client = (await auth.register()).client if authenticated else await auth.client()
    route = "/auth/logout" if authenticated else "/auth/login"
    payload = None if authenticated else {"email": "nobody@example.com", "password": PASSWORD}
    csrf = (await client.get(f"{PREFIX}/auth/csrf")).json()["csrf_token"]
    invalid_headers = [
        {},
        {"Origin": ORIGIN},
        {"X-CSRF-Token": csrf},
        {"Origin": "https://attacker.example", "X-CSRF-Token": csrf},
        {"Origin": ORIGIN + ".attacker.example", "X-CSRF-Token": csrf},
        {"Origin": "null", "X-CSRF-Token": csrf},
        {"Origin": ORIGIN, "X-CSRF-Token": "not-the-issued-token"},
    ]
    for headers in invalid_headers:
        response = await client.post(f"{PREFIX}{route}", headers=headers, json=payload)
        assert response.status_code == 403, response.text
    if authenticated:
        assert (await client.get(f"{PREFIX}/auth/me")).status_code == 200


async def test_csrf_token_is_bound_to_its_browser_session(auth: AuthHarness) -> None:
    first, second = await auth.register(), await auth.register()
    csrf = (await first.client.get(f"{PREFIX}/auth/csrf")).json()["csrf_token"]
    response = await second.client.post(
        f"{PREFIX}/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}
    )
    assert response.status_code == 403
    assert (await second.client.get(f"{PREFIX}/auth/me")).status_code == 200


@pytest.mark.parametrize("token", ["garbage", "e30.eyJzdWIiOiJhZG1pbiJ9."])
async def test_invalid_or_unsigned_access_token_is_rejected(auth: AuthHarness, token: str) -> None:
    client = await auth.client()
    client.cookies.set("forge_access", token)
    response = await client.get(f"{PREFIX}/auth/me")
    assert response.status_code == 401
    assert "traceback" not in response.text.lower()


async def test_bad_password_and_unknown_account_return_the_same_safe_error(
    auth: AuthHarness,
) -> None:
    identity = await auth.register()
    responses = []
    for email in [identity.email, f"missing-{uuid4().hex}@example.com"]:
        client = await auth.client()
        response = await auth.mutate(
            client, "POST", "/auth/login", {"email": email, "password": "incorrect password"}
        )
        assert response.status_code == 401
        responses.append((response.json()["code"], response.json()["detail"]))
        assert not client.cookies.get("forge_access")
    assert responses[0] == responses[1]


async def test_refresh_rotates_and_replay_revokes_the_session_family(auth: AuthHarness) -> None:
    identity = await auth.register()
    original = identity.client.cookies.get("forge_refresh")
    original_access = identity.client.cookies.get("forge_access")
    response = await auth.mutate(identity.client, "POST", "/auth/refresh")
    assert response.status_code == 200, response.text
    rotated = identity.client.cookies.get("forge_refresh")
    assert rotated and rotated != original
    assert (await identity.client.get(f"{PREFIX}/auth/me")).status_code == 200

    csrf = (await identity.client.get(f"{PREFIX}/auth/csrf")).json()["csrf_token"]
    replay = await auth.client()
    replay.cookies.set("forge_refresh", original)
    replay.cookies.set("forge_access", original_access)
    replay.cookies.set("forge_csrf", csrf)
    response = await replay.post(
        f"{PREFIX}/auth/refresh", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}
    )
    assert response.status_code == 401, response.text
    # The rejection must commit revocation before returning the error.
    assert (await identity.client.get(f"{PREFIX}/auth/me")).status_code == 401
    assert (await replay.get(f"{PREFIX}/auth/me")).status_code == 401


async def test_organization_read_write_and_membership_are_tenant_scoped(
    auth: AuthHarness,
) -> None:
    alice, bob = await auth.register(), await auth.register()
    alice_org = await auth.organization(alice, "Alice private workspace")
    bob_org = await auth.organization(bob, "Bob private workspace")
    own = await alice.client.get(f"{PREFIX}/organizations/{alice_org}")
    assert own.status_code == 200
    for path in [f"/organizations/{bob_org}", f"/organizations/{bob_org}/members"]:
        assert (await alice.client.get(f"{PREFIX}{path}")).status_code == 404
    denied = await auth.mutate(
        alice.client, "PATCH", f"/organizations/{bob_org}", {"name": "Stolen"}
    )
    assert denied.status_code == 404
    preserved = await bob.client.get(f"{PREFIX}/organizations/{bob_org}")
    assert preserved.json()["name"] == "Bob private workspace"
    response = await alice.client.get(f"{PREFIX}/organizations")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["data"]} == {alice_org}


async def test_unknown_writable_fields_cannot_assign_roles_or_tenant_context(
    auth: AuthHarness,
) -> None:
    client = await auth.client()
    response = await auth.mutate(
        client,
        "POST",
        "/auth/register",
        {
            "name": "Injected owner",
            "email": f"injection-{uuid4().hex}@example.com",
            "password": PASSWORD,
            "role": "owner",
        },
    )
    assert response.status_code == 422
    identity = await auth.register()
    response = await auth.mutate(
        identity.client,
        "POST",
        "/organizations",
        {
            "name": "Injected tenant",
            "slug": f"injected-{uuid4().hex}",
            "organization_id": str(uuid4()),
        },
    )
    assert response.status_code == 422


async def test_parallel_refresh_has_one_winner_and_replay_closes_the_family(
    auth: AuthHarness,
) -> None:
    identity = await auth.register()
    csrf = (await identity.client.get(f"{PREFIX}/auth/csrf")).json()["csrf_token"]
    access, refresh = (
        identity.client.cookies.get("forge_access"),
        identity.client.cookies.get("forge_refresh"),
    )
    clients = [await auth.client(), await auth.client()]
    for client in clients:
        client.cookies.set("forge_access", access)
        client.cookies.set("forge_refresh", refresh)
        client.cookies.set("forge_csrf", csrf)
    responses = await asyncio.gather(
        *(
            client.post(f"{PREFIX}/auth/refresh", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
            for client in clients
        )
    )
    assert sorted(response.status_code for response in responses) == [200, 401]
    assert (await identity.client.get(f"{PREFIX}/auth/me")).status_code == 401


async def test_password_and_issued_tokens_are_hashed_in_postgres(auth: AuthHarness) -> None:
    identity = await auth.register()
    refresh = identity.client.cookies.get("forge_refresh")
    verify = auth.delivered_token(identity.email, "verify-email")
    csrf = (await identity.client.get(f"{PREFIX}/auth/csrf")).json()["csrf_token"]
    engine = await auth.engine()
    async with engine.connect() as connection:
        password_hash = await connection.scalar(
            text("SELECT password_hash FROM forge.users WHERE id=:id"), {"id": identity.user_id}
        )
        assert password_hash.startswith("$argon2id$")
        assert PASSWORD not in password_hash
        refresh_hash = await connection.scalar(
            text("SELECT token_hash FROM forge.refresh_tokens WHERE session_id=:id"),
            {"id": identity.session_id},
        )
        assert refresh_hash == sha256(refresh.encode()).hexdigest()
        verify_hash = await connection.scalar(
            text(
                "SELECT token_hash FROM forge.identity_tokens "
                "WHERE user_id=:id AND purpose='verify'"
            ),
            {"id": identity.user_id},
        )
        assert verify_hash == sha256(verify.encode()).hexdigest()
        stored_csrf = await connection.scalar(
            text("SELECT csrf_hash FROM forge.auth_sessions WHERE id=:id"),
            {"id": identity.session_id},
        )
        assert stored_csrf != csrf
        for table in ["users", "auth_sessions", "refresh_tokens", "identity_tokens"]:
            rows = await connection.execute(
                text(f"SELECT row_to_json(t)::text FROM forge.{table} t")
            )
            for (row,) in rows:
                assert refresh not in row and verify not in row and PASSWORD not in row


async def test_session_revocation_is_immediate_and_cannot_target_another_user(
    auth: AuthHarness,
) -> None:
    alice, bob = await auth.register(), await auth.register()
    second = await auth.client()
    login = await auth.mutate(
        second, "POST", "/auth/login", {"email": alice.email, "password": PASSWORD}
    )
    assert login.status_code == 200
    second_session = login.json()["session_id"]
    sessions = await alice.client.get(f"{PREFIX}/auth/sessions")
    assert {item["id"] for item in sessions.json()["data"]} == {alice.session_id, second_session}
    denied = await auth.mutate(alice.client, "DELETE", f"/auth/sessions/{bob.session_id}")
    assert denied.status_code == 404
    revoked = await auth.mutate(alice.client, "DELETE", f"/auth/sessions/{second_session}")
    assert revoked.status_code == 204
    assert (await second.get(f"{PREFIX}/auth/me")).status_code == 401
    assert (await alice.client.get(f"{PREFIX}/auth/me")).status_code == 200
    assert (await bob.client.get(f"{PREFIX}/auth/me")).status_code == 200


async def test_email_verification_is_one_use_and_rejects_wrong_purpose(auth: AuthHarness) -> None:
    identity = await auth.register()
    token = auth.delivered_token(identity.email, "verify-email")
    wrong_purpose = await auth.mutate(
        identity.client,
        "POST",
        "/auth/password-reset/confirm",
        {"token": token, "password": "Replacement password that must not apply!"},
    )
    assert wrong_purpose.status_code == 400
    await auth.verify(identity)
    me = await identity.client.get(f"{PREFIX}/auth/me")
    assert me.json()["user"]["email_verified"] is True
    replay = await auth.mutate(
        identity.client, "POST", "/auth/verify-email/confirm", {"token": token}
    )
    assert replay.status_code == 400


async def test_password_reset_expires_is_one_use_and_revokes_all_sessions(
    auth: AuthHarness,
) -> None:
    identity = await auth.register()
    second = await auth.client()
    await auth.mutate(
        second, "POST", "/auth/login", {"email": identity.email, "password": PASSWORD}
    )
    reset_client = await auth.client()
    requested = await auth.mutate(
        reset_client, "POST", "/auth/password-reset/request", {"email": identity.email}
    )
    assert requested.status_code == 202
    expired = auth.delivered_token(identity.email, "reset-password")
    engine = await auth.engine(migration=True)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE forge.identity_tokens SET expires_at=now()-interval '1 second' "
                "WHERE token_hash=:hash"
            ),
            {"hash": sha256(expired.encode()).hexdigest()},
        )
    payload = {"token": expired, "password": "A replacement passphrase with enough entropy!"}
    rejected = await auth.mutate(reset_client, "POST", "/auth/password-reset/confirm", payload)
    assert rejected.status_code == 400
    assert (await identity.client.get(f"{PREFIX}/auth/me")).status_code == 200
    await auth.mutate(
        reset_client, "POST", "/auth/password-reset/request", {"email": identity.email}
    )
    token = auth.delivered_token(identity.email, "reset-password")
    assert token != expired
    payload["token"] = token
    completed = await auth.mutate(reset_client, "POST", "/auth/password-reset/confirm", payload)
    assert completed.status_code == 200
    assert (await identity.client.get(f"{PREFIX}/auth/me")).status_code == 401
    assert (await second.get(f"{PREFIX}/auth/me")).status_code == 401
    replay = await auth.mutate(reset_client, "POST", "/auth/password-reset/confirm", payload)
    assert replay.status_code == 400
    old_password = await auth.mutate(
        reset_client, "POST", "/auth/login", {"email": identity.email, "password": PASSWORD}
    )
    assert old_password.status_code == 401
    new_password = await auth.mutate(
        reset_client,
        "POST",
        "/auth/login",
        {"email": identity.email, "password": payload["password"]},
    )
    assert new_password.status_code == 200


@pytest.mark.parametrize("route", ["verify-email", "password-reset"])
async def test_identity_mail_requests_do_not_reveal_account_existence(
    auth: AuthHarness, route: str
) -> None:
    identity = await auth.register()
    client = await auth.client()
    responses = []
    for email in [identity.email, f"missing-{uuid4().hex}@example.com"]:
        response = await auth.mutate(client, "POST", f"/auth/{route}/request", {"email": email})
        assert response.status_code == 202
        responses.append(response.json())
    assert responses[0] == responses[1]
    assert all("missing-" not in file.read_text() for file in auth.outbox.glob("*.eml"))


async def test_invitation_requires_verified_matching_email_and_is_one_use(
    auth: AuthHarness,
) -> None:
    owner, member, outsider = await auth.register(), await auth.register(), await auth.register()
    organization_id = await auth.organization(owner)
    token = await auth.invite(owner, organization_id, member, "member")
    unverified = await auth.mutate(member.client, "POST", "/invitations/accept", {"token": token})
    assert unverified.status_code == 403
    await auth.verify(outsider)
    mismatched = await auth.mutate(outsider.client, "POST", "/invitations/accept", {"token": token})
    assert mismatched.status_code == 404
    await auth.verify(member)
    accepted = await auth.mutate(member.client, "POST", "/invitations/accept", {"token": token})
    assert accepted.status_code == 200
    own = await member.client.get(f"{PREFIX}/organizations/{organization_id}")
    assert own.status_code == 200 and own.json()["role"] == "member"
    replay = await auth.mutate(member.client, "POST", "/invitations/accept", {"token": token})
    assert replay.status_code == 404


async def test_revoked_membership_immediately_denies_old_session_tenant_access(
    auth: AuthHarness,
) -> None:
    owner, member = await auth.register(), await auth.register()
    organization_id = await auth.organization(owner)
    member_id = await auth.join(owner, organization_id, member, "member")
    revoked = await auth.mutate(
        owner.client, "DELETE", f"/organizations/{organization_id}/members/{member_id}"
    )
    assert revoked.status_code == 204
    assert (await member.client.get(f"{PREFIX}/auth/me")).status_code == 200
    assert (await member.client.get(f"{PREFIX}/organizations/{organization_id}")).status_code == 404


async def test_admin_cannot_grant_owner_or_modify_owner_membership(auth: AuthHarness) -> None:
    owner, admin = await auth.register(), await auth.register()
    organization_id = await auth.organization(owner)
    admin_id = await auth.join(owner, organization_id, admin, "admin")
    members = await owner.client.get(f"{PREFIX}/organizations/{organization_id}/members")
    owner_id = next(
        item["id"] for item in members.json()["data"] if item["user_id"] == owner.user_id
    )
    for member_id, role in [(admin_id, "owner"), (owner_id, "member")]:
        response = await auth.mutate(
            admin.client,
            "PATCH",
            f"/organizations/{organization_id}/members/{member_id}",
            {"role": role},
        )
        assert response.status_code == 403
    invited = await auth.mutate(
        admin.client,
        "POST",
        f"/organizations/{organization_id}/invitations",
        {"email": "new@example.com", "role": "owner"},
    )
    assert invited.status_code == 403
    deleted = await auth.mutate(
        admin.client, "DELETE", f"/organizations/{organization_id}/members/{owner_id}"
    )
    assert deleted.status_code == 403


async def test_concurrent_owner_demotion_never_removes_the_last_owner(auth: AuthHarness) -> None:
    first, second = await auth.register(), await auth.register()
    organization_id = await auth.organization(first)
    second_id = await auth.join(first, organization_id, second, "owner")
    members = await first.client.get(f"{PREFIX}/organizations/{organization_id}/members")
    first_id = next(
        item["id"] for item in members.json()["data"] if item["user_id"] == first.user_id
    )
    results = await asyncio.gather(
        auth.mutate(
            first.client,
            "PATCH",
            f"/organizations/{organization_id}/members/{first_id}",
            {"role": "admin"},
        ),
        auth.mutate(
            second.client,
            "PATCH",
            f"/organizations/{organization_id}/members/{second_id}",
            {"role": "admin"},
        ),
    )
    assert sorted(result.status_code for result in results) == [200, 409]
    members = await first.client.get(f"{PREFIX}/organizations/{organization_id}/members")
    assert sum(item["role"] == "owner" for item in members.json()["data"]) == 1


async def test_rate_limit_is_bounded_and_forwarded_ip_headers_do_not_bypass_it(
    auth: AuthHarness,
) -> None:
    client = await auth.client()
    csrf = (await client.get(f"{PREFIX}/auth/csrf")).json()["csrf_token"]
    address = f"bounded-{uuid4().hex}@example.com"
    for index in range(32):
        response = await client.post(
            f"{PREFIX}/auth/password-reset/request",
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf,
                "X-Forwarded-For": f"198.51.100.{index}",
            },
            json={"email": address},
        )
        if response.status_code == 429:
            assert 0 < int(response.headers["retry-after"]) <= 3600
            break
        assert response.status_code == 202
    else:
        pytest.fail("Identity mail requests remained unbounded after 32 attempts")


async def test_rls_without_context_denies_reads_and_writes_for_all_tenant_tables(
    auth: AuthHarness,
) -> None:
    identity = await auth.register()
    organization_id = await auth.organization(identity)
    engine = await auth.engine()
    async with engine.begin() as connection:
        for table in ["organizations", "memberships", "invitations", "audit_events"]:
            assert await connection.scalar(text(f"SELECT count(*) FROM forge.{table}")) == 0
        policies = (
            await connection.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                    "JOIN pg_namespace n ON n.oid=relnamespace "
                    "WHERE n.nspname='forge' AND relname IN "
                    "('organizations','memberships','invitations','audit_events')"
                )
            )
        ).all()
        assert len(policies) == 4
        assert all(enabled and forced for _, enabled, forced in policies)
    with pytest.raises(ProgrammingError):
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO forge.memberships (id,organization_id,user_id,role) "
                    "VALUES (:id,:org,:user,'owner')"
                ),
                {"id": str(uuid4()), "org": organization_id, "user": identity.user_id},
            )
    with pytest.raises(ProgrammingError):
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO forge.organizations (id,name,slug,created_by) "
                    "VALUES (:id,'Unauthorized root',:slug,:user)"
                ),
                {"id": str(uuid4()), "slug": uuid4().hex, "user": identity.user_id},
            )


async def test_raw_queries_and_user_bound_discovery_do_not_cross_tenants(auth: AuthHarness) -> None:
    alice, bob = await auth.register(), await auth.register()
    alice_org, bob_org = await auth.organization(alice), await auth.organization(bob)
    engine = await auth.engine()
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('forge.user_id',:user,true)"), {"user": alice.user_id}
        )
        assert set(
            (await connection.scalars(text("SELECT id::text FROM forge.organizations"))).all()
        ) == {alice_org}
        assert set(
            (await connection.scalars(text("SELECT user_id::text FROM forge.memberships"))).all()
        ) == {alice.user_id}
        await connection.execute(
            text("SELECT set_config('forge.organization_id',:org,true)"), {"org": alice_org}
        )
        for table, column in [
            ("organizations", "id"),
            ("memberships", "organization_id"),
            ("audit_events", "organization_id"),
        ]:
            assert (
                await connection.scalar(
                    text(f"SELECT count(*) FROM forge.{table} WHERE {column}=:org"),
                    {"org": bob_org},
                )
                == 0
            )
        changed = await connection.execute(
            text("UPDATE forge.organizations SET name='Cross tenant write' WHERE id=:org"),
            {"org": bob_org},
        )
        assert changed.rowcount == 0
    with pytest.raises(ProgrammingError):
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('forge.organization_id',:org,true)"), {"org": alice_org}
            )
            await connection.execute(
                text(
                    "INSERT INTO forge.memberships (id,organization_id,user_id,role) "
                    "VALUES (:id,:org,:user,'owner')"
                ),
                {"id": str(uuid4()), "org": bob_org, "user": alice.user_id},
            )


async def test_tenant_context_is_cleared_on_commit_and_rollback_before_pool_reuse(
    auth: AuthHarness,
) -> None:
    identity = await auth.register()
    organization_id = await auth.organization(identity)
    engine = await auth.engine(single_connection=True)
    async with engine.begin() as connection:
        pid = await connection.scalar(text("SELECT pg_backend_pid()"))
        await connection.execute(
            text("SELECT set_config('forge.organization_id',:org,true)"), {"org": organization_id}
        )
        await connection.execute(
            text("SELECT set_config('forge.user_id',:user,true)"), {"user": identity.user_id}
        )
        assert await connection.scalar(text("SELECT count(*) FROM forge.organizations")) == 1
    async with engine.begin() as connection:
        assert await connection.scalar(text("SELECT pg_backend_pid()")) == pid
        assert await connection.scalar(text("SELECT count(*) FROM forge.organizations")) == 0
        assert (
            await connection.scalar(text("SELECT nullif(current_setting('forge.user_id',true),'')"))
            is None
        )

    class DeliberateRollback(Exception):
        pass

    with pytest.raises(DeliberateRollback):
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('forge.organization_id',:org,true)"),
                {"org": organization_id},
            )
            await connection.execute(
                text("SELECT set_config('forge.user_id',:user,true)"), {"user": identity.user_id}
            )
            await connection.execute(
                text("UPDATE forge.organizations SET name='Must roll back' WHERE id=:org"),
                {"org": organization_id},
            )
            raise DeliberateRollback
    async with engine.begin() as connection:
        assert await connection.scalar(text("SELECT pg_backend_pid()")) == pid
        assert await connection.scalar(text("SELECT count(*) FROM forge.organizations")) == 0
        assert (
            await connection.scalar(
                text("SELECT nullif(current_setting('forge.organization_id',true),'')")
            )
            is None
        )
        assert (
            await connection.scalar(text("SELECT nullif(current_setting('forge.user_id',true),'')"))
            is None
        )
    own = await identity.client.get(f"{PREFIX}/organizations/{organization_id}")
    assert own.json()["name"] == "Security workspace"


async def test_runtime_role_can_append_but_cannot_rewrite_or_delete_audit_history(
    auth: AuthHarness,
) -> None:
    identity = await auth.register()
    organization_id = await auth.organization(identity)
    updated = await auth.mutate(
        identity.client, "PATCH", f"/organizations/{organization_id}", {"name": "Audited rename"}
    )
    assert updated.status_code == 200
    engine = await auth.engine()
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('forge.organization_id',:org,true)"), {"org": organization_id}
        )
        events = (await connection.scalars(text("SELECT action FROM forge.audit_events"))).all()
        assert len(events) >= 2
    for query in [
        "UPDATE forge.audit_events SET action='tampered'",
        "DELETE FROM forge.audit_events",
    ]:
        with pytest.raises(ProgrammingError):
            async with engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('forge.organization_id',:org,true)"),
                    {"org": organization_id},
                )
                await connection.execute(text(query))
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('forge.organization_id',:org,true)"), {"org": organization_id}
        )
        assert len(
            (await connection.scalars(text("SELECT action FROM forge.audit_events"))).all()
        ) == len(events)


async def test_invitation_foreign_key_cannot_reference_another_tenants_member(
    auth: AuthHarness,
) -> None:
    alice, bob = await auth.register(), await auth.register()
    alice_org, bob_org = await auth.organization(alice), await auth.organization(bob)
    bob_members = await bob.client.get(f"{PREFIX}/organizations/{bob_org}/members")
    bob_member = bob_members.json()["data"][0]["id"]
    engine = await auth.engine()
    with pytest.raises(IntegrityError) as error:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('forge.organization_id',:org,true)"), {"org": alice_org}
            )
            await connection.execute(
                text(
                    "INSERT INTO forge.invitations "
                    "(id,organization_id,email,role,token_hash,inviter_id,expires_at) "
                    "VALUES (:id,:org,'cross-tenant@example.com','member',:hash,:inviter,"
                    "now()+interval '1 day')"
                ),
                {
                    "id": str(uuid4()),
                    "org": alice_org,
                    "hash": secrets.token_hex(32),
                    "inviter": bob_member,
                },
            )
    assert error.value.orig.sqlstate == "23503"


async def test_membership_id_cannot_be_used_through_another_organizations_route(
    auth: AuthHarness,
) -> None:
    alice, bob = await auth.register(), await auth.register()
    alice_org, bob_org = await auth.organization(alice), await auth.organization(bob)
    bob_members = await bob.client.get(f"{PREFIX}/organizations/{bob_org}/members")
    bob_member = bob_members.json()["data"][0]["id"]
    response = await auth.mutate(
        alice.client,
        "PATCH",
        f"/organizations/{alice_org}/members/{bob_member}",
        {"role": "viewer"},
    )
    assert response.status_code == 404
    preserved = await bob.client.get(f"{PREFIX}/organizations/{bob_org}/members")
    assert preserved.json()["data"][0]["role"] == "owner"


async def test_organization_paging_cursor_is_bound_to_the_authenticated_user(
    auth: AuthHarness,
) -> None:
    alice, bob = await auth.register(), await auth.register()
    created = {await auth.organization(alice), await auth.organization(alice)}
    first = await alice.client.get(f"{PREFIX}/organizations", params={"limit": 1})
    assert first.status_code == 200
    assert first.json()["page"]["has_more"] is True
    cursor = first.json()["page"]["next_cursor"]
    next_page = await alice.client.get(
        f"{PREFIX}/organizations", params={"limit": 1, "cursor": cursor}
    )
    assert next_page.status_code == 200
    assert next_page.json()["page"]["has_more"] is False
    assert {first.json()["data"][0]["id"], next_page.json()["data"][0]["id"]} == created
    stolen = await bob.client.get(f"{PREFIX}/organizations", params={"limit": 1, "cursor": cursor})
    assert stolen.status_code == 422
    changed_limit = await alice.client.get(
        f"{PREFIX}/organizations", params={"limit": 2, "cursor": cursor}
    )
    assert changed_limit.status_code == 422


async def test_invitation_loses_authority_when_its_inviter_is_demoted(auth: AuthHarness) -> None:
    owner, admin, candidate = await auth.register(), await auth.register(), await auth.register()
    organization_id = await auth.organization(owner)
    admin_id = await auth.join(owner, organization_id, admin, "admin")
    await auth.verify(candidate)
    token = await auth.invite(admin, organization_id, candidate, "member")
    changed = await auth.mutate(
        owner.client,
        "PATCH",
        f"/organizations/{organization_id}/members/{admin_id}",
        {"role": "viewer"},
    )
    assert changed.status_code == 200
    response = await auth.mutate(candidate.client, "POST", "/invitations/accept", {"token": token})
    assert response.status_code == 404
    assert (
        await candidate.client.get(f"{PREFIX}/organizations/{organization_id}")
    ).status_code == 404


async def test_expired_access_during_tenant_mutation_can_refresh_and_retry(
    auth: AuthHarness,
) -> None:
    identity = await auth.register()
    organization_id = await auth.organization(identity)
    expired = jwt.encode(
        {
            "sub": identity.user_id,
            "sid": identity.session_id,
            "iss": "forge",
            "aud": "forge-browser",
            "kind": "access",
            "iat": datetime.now(UTC) - timedelta(minutes=11),
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        auth.settings.auth_secret.get_secret_value(),
        algorithm="HS256",
    )
    for cookie in identity.client.cookies.jar:
        if cookie.name == "forge_access":
            cookie.value = expired
    # The refresh cookie is deliberately restricted to /auth; the client needs
    # an authentication failure here so it can recover instead of showing 403.
    rejected = await auth.mutate(
        identity.client, "PATCH", f"/organizations/{organization_id}", {"name": "Recovered"}
    )
    assert rejected.status_code == 401
    refreshed = await auth.mutate(identity.client, "POST", "/auth/refresh")
    assert refreshed.status_code == 200
    retried = await auth.mutate(
        identity.client, "PATCH", f"/organizations/{organization_id}", {"name": "Recovered"}
    )
    assert retried.status_code == 200
    assert retried.json()["name"] == "Recovered"
