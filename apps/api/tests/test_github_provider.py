import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from forge.config import Settings
from forge.integrations.github import API_VERSION, GitHubApp, GitHubFailure


def app_values(key: rsa.RSAPrivateKey | None = None) -> dict[str, Any]:
    key = key or rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return {
        "github_app_id": 12345,
        "github_app_slug": "forge-fixture",
        "github_app_client_id": "fixture-app-client",
        "github_app_client_secret": "fixture-app-secret",
        "github_app_private_key_base64": base64.b64encode(pem).decode(),
        "github_app_webhook_secret": secrets.token_hex(32),
    }


def installation(**changes: Any) -> dict[str, Any]:
    return {
        "id": 99,
        "app_id": 12345,
        "suspended_at": None,
        "account": {"id": 10, "login": "fixture-org", "type": "Organization"},
        "permissions": {"contents": "read", "pull_requests": "read", "members": "read"},
        "repository_selection": "selected",
        **changes,
    }


@pytest.fixture
def app_settings(settings: Settings) -> Settings:
    return Settings(**{**settings.model_dump(), **app_values()})


def test_github_app_configuration_is_optional_and_all_or_none(settings: Settings) -> None:
    values = app_values()
    disabled = Settings(**{**settings.model_dump(), **dict.fromkeys(values, "")})
    assert disabled.github_app_id is None
    for field in values:
        with pytest.raises(ValidationError, match="all six"):
            Settings(**{**settings.model_dump(), **values, field: ""})


@pytest.mark.parametrize(
    "field,value",
    [
        ("github_app_id", -1),
        ("github_app_slug", "../another-app"),
        ("github_app_private_key_base64", "not-base64"),
        ("github_app_private_key_base64", base64.b64encode(b"not a private key").decode()),
        ("github_app_webhook_secret", "short"),
    ],
)
def test_github_app_rejects_unsafe_configuration(
    settings: Settings, field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        Settings(**{**settings.model_dump(), **app_values(), field: value})


def test_worker_requires_https_but_not_api_mail_credentials(settings: Settings) -> None:
    values = {
        **settings.model_dump(),
        "environment": "production",
        "component": "worker",
        "smtp_username": None,
        "smtp_password": None,
    }
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(**values)
    worker = Settings(**{**values, "public_origin": "https://forge.example.com"})
    assert worker.mail_backend == "file" and worker.smtp_password is None
    with pytest.raises(ValidationError, match="SMTP"):
        Settings(**{**values, "component": "api", "public_origin": "https://forge.example.com"})


async def test_app_jwt_and_authorization_use_app_credentials_and_pkce(
    app_settings: Settings,
) -> None:
    provider = GitHubApp(app_settings)
    try:
        assert provider.private_key is not None
        claims = jwt.decode(
            provider.app_jwt(),
            provider.private_key.public_key(),
            algorithms=["RS256"],
            issuer="fixture-app-client",
        )
        current = datetime.now(UTC).timestamp()
        assert current - 65 <= claims["iat"] <= current - 59
        assert current + 530 <= claims["exp"] <= current + 600
        verifier, state = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        query = parse_qs(urlsplit(provider.authorization_url(state, verifier)).query)
        assert query["client_id"] == ["fixture-app-client"]
        assert query["redirect_uri"] == [
            "http://localhost:3000/api/v1/integrations/github/callback"
        ]
        assert query["state"] == [state] and "scope" not in query and "client_secret" not in query
        assert query["code_challenge_method"] == ["S256"]
        assert query["code_challenge"] == [
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        ]
        assert provider.install_url == "https://github.com/apps/forge-fixture/installations/new"
    finally:
        await provider.client.aclose()


@pytest.mark.parametrize(
    "status,headers,code,retryable",
    [
        (429, {"retry-after": "47"}, "rate_limited", True),
        (403, {"x-ratelimit-remaining": "0", "retry-after": "47"}, "rate_limited", True),
        (403, {}, "access_denied", False),
        (404, {}, "access_denied", False),
        (401, {}, "credentials_rejected", False),
        (503, {}, "provider_unavailable", True),
        (302, {"location": "https://attacker.example.com"}, "invalid_response", False),
    ],
)
async def test_provider_statuses_are_safe_and_retryable_only_when_appropriate(
    app_settings: Settings,
    status: int,
    headers: dict[str, str],
    code: str,
    retryable: bool,
) -> None:
    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "api.github.com"
        assert request.headers["x-github-api-version"] == API_VERSION
        return httpx.Response(status, headers=headers, json={"error": "secret-token-never-log"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        provider.client = transport
        with pytest.raises(GitHubFailure) as failure:
            await provider.repositories("installation-token", 1)
    assert failure.value.code == code and failure.value.retryable is retryable
    assert "secret-token" not in str(failure.value)
    if code == "rate_limited":
        assert failure.value.retry_after == 47
    assert len(requests) == 1


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"app_id": 777}, "installation_mismatch"),
        ({"suspended_at": "2026-09-22T12:00:00Z"}, "installation_suspended"),
        ({"permissions": {"contents": "read"}}, "permissions_required"),
        ({"id": -1}, "invalid_response"),
    ],
)
async def test_installation_requires_matching_app_active_access_and_permissions(
    app_settings: Settings,
    changes: dict[str, Any],
    code: str,
) -> None:
    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=installation(**changes)))
    ) as transport:
        provider.client = transport
        with pytest.raises(GitHubFailure) as failure:
            await provider.installation(99)
    assert failure.value.code == code


async def test_user_installations_pagination_is_bounded_and_never_follows_link_urls(
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("forge.integrations.github.MAX_PAGES", 2)
    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    pages = []

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.github.com" and request.url.path == "/user/installations"
        pages.append(request.url.params["page"])
        return httpx.Response(
            200,
            json={"installations": [installation(id=index + 1) for index in range(100)]},
            headers={"link": '<https://attacker.example.com>; rel="next"'},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        provider.client = transport
        with pytest.raises(GitHubFailure) as failure:
            await provider.user_installations("user-token")
    assert failure.value.code == "capacity_exceeded" and pages == ["1", "2"]


@pytest.mark.parametrize(
    "account_type,body,accepted",
    [
        ("User", {"id": 10}, True),
        ("User", {"id": 11}, False),
        ("Organization", {"state": "active", "role": "admin", "organization": {"id": 10}}, True),
        ("Organization", {"state": "active", "role": "member", "organization": {"id": 10}}, False),
        ("Organization", {"state": "pending", "role": "admin", "organization": {"id": 10}}, False),
        ("Organization", {"state": "active", "role": "admin", "organization": {"id": 11}}, False),
    ],
)
async def test_binding_requires_authority_over_entire_installation_account(
    app_settings: Settings,
    account_type: str,
    body: dict[str, Any],
    accepted: bool,
) -> None:
    provider = GitHubApp(app_settings)
    await provider.client.aclose()

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer user-token"
        expected = "/user" if account_type == "User" else "/user/memberships/orgs/fixture-org"
        assert request.url.path == expected
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        provider.client = transport
        target = installation(account={"id": 10, "login": "fixture-org", "type": account_type})
        if accepted:
            await provider.require_account_admin("user-token", target)
        else:
            with pytest.raises(GitHubFailure) as failure:
                await provider.require_account_admin("user-token", target)
            assert failure.value.code == "installation_admin_required"


async def test_installation_token_is_narrowed_after_fresh_app_installation_check(
    app_settings: Settings,
) -> None:
    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    paths = []

    def respond(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        assert request.headers["authorization"].startswith("Bearer ey")
        if request.url.path.endswith("/access_tokens"):
            assert json.loads(request.content) == {
                "permissions": {"contents": "read", "pull_requests": "read"}
            }
            return httpx.Response(
                201,
                json={
                    "token": "ephemeral-installation-token",
                    "permissions": {"contents": "read", "pull_requests": "read"},
                },
            )
        return httpx.Response(200, json=installation())

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        provider.client = transport
        assert await provider.installation_token(99) == "ephemeral-installation-token"
    assert paths == ["/app/installations/99", "/app/installations/99/access_tokens"]


@pytest.mark.parametrize(
    "owner,name",
    [
        ("../evil", "repo"),
        ("owner", ".."),
        ("owner", "repo?leak=1"),
        ("https://attacker.example.com", "repo"),
    ],
)
async def test_repository_paths_cannot_redirect_provider_requests(
    app_settings: Settings, owner: str, name: str
) -> None:
    provider = GitHubApp(app_settings)
    try:
        with pytest.raises(GitHubFailure) as failure:
            await provider.pull_requests("token", owner, name, 1)
        assert failure.value.code == "invalid_resource"
    finally:
        await provider.client.aclose()


@pytest.mark.parametrize(
    "message,empty", [("Git Repository is empty.", True), ("Another conflict", False)]
)
async def test_empty_commit_history_is_supported_without_hiding_other_conflicts(
    app_settings: Settings,
    message: str,
    empty: bool,
) -> None:
    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(409, json={"message": message}))
    ) as transport:
        provider.client = transport
        if empty:
            assert (
                await provider.commits(
                    "token",
                    "owner",
                    "repository",
                    1,
                    "2026-06-01T00:00:00Z",
                    "2026-09-22T00:00:00Z",
                )
                == []
            )
        else:
            with pytest.raises(GitHubFailure) as failure:
                await provider.commits(
                    "token",
                    "owner",
                    "repository",
                    1,
                    "2026-06-01T00:00:00Z",
                    "2026-09-22T00:00:00Z",
                )
            assert failure.value.code == "repository_conflict"


async def test_provider_response_size_is_bounded(
    app_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("forge.integrations.github.MAX_RESPONSE_BYTES", 8)
    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"repositories": []}))
    ) as transport:
        provider.client = transport
        with pytest.raises(GitHubFailure) as failure:
            await provider.repositories("token", 1)
        assert failure.value.code == "response_too_large"
