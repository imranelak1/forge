import base64
import hashlib
import json
import secrets
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta, tzinfo
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr, ValidationError

from forge.config import Settings
from forge.domain.identity import DomainError
from forge.integrations.oauth import OAuthFailure, OAuthProvider
from forge.main import create_app
from forge.security.identity import TokenCodec
from forge.services.oauth import login_target, safe_return


@pytest.mark.parametrize("provider", ["github", "google"])
def test_provider_credentials_are_optional_but_must_be_complete(provider: str) -> None:
    values = {
        "database_password": secrets.token_hex(32),
        "auth_secret": secrets.token_hex(32),
    }
    disabled = Settings(**values, **{f"{provider}_client_id": " ", f"{provider}_client_secret": ""})
    assert getattr(disabled, f"{provider}_client_id") is None
    assert getattr(disabled, f"{provider}_client_secret") is None
    for suffix in ("id", "secret"):
        with pytest.raises(ValidationError, match="both client ID and secret"):
            Settings(**values, **{f"{provider}_client_{suffix}": "configured"})
    enabled = Settings(
        **values, **{f"{provider}_client_id": " app ", f"{provider}_client_secret": "secret"}
    )
    assert getattr(enabled, f"{provider}_client_id") == "app"
    assert "secret" not in str(getattr(enabled, f"{provider}_client_secret"))


async def test_provider_discovery_is_truthful_without_credentials(settings: Settings) -> None:
    app = create_app(settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/auth/providers")
    assert response.status_code == 200
    assert response.json() == {
        "providers": [{"id": "github", "enabled": False}, {"id": "google", "enabled": False}]
    }
    await app.state.oauth_service.provider.client.aclose()
    await app.state.identity_service.repository.engine.dispose()


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.example.com/app",
        "//evil.example.com/app",
        "//[invalid",
        "/application",
        "/app/../login",
        "/app/%2e%2e/login",
        "/app\\evil",
        "/app/%5c%5cevil",
        "/app\nLocation: evil",
        "/app/%0d%0aevil",
        "/app/account#sessions",
        "/app/%61ccount",
    ],
)
def test_return_paths_cannot_leave_app(value: str) -> None:
    assert safe_return(value) == "/app"
    assert login_target(value) == "/app?oauth=signed-in"


def test_login_marker_preserves_allowed_destination_and_replaces_previous_marker() -> None:
    assert (
        login_target("/app/account?filter=active&oauth=old")
        == "/app/account?filter=active&oauth=signed-in"
    )


@pytest.mark.parametrize("provider", ["github", "google"])
async def test_authorization_uses_pkce_purpose_separation_and_minimal_scopes(
    settings: Settings, provider: str
) -> None:
    settings.github_client_id = "github-app"
    settings.github_client_secret = SecretStr("github-secret")
    settings.google_client_id = "google-app"
    settings.google_client_secret = SecretStr("google-secret")
    client = OAuthProvider(settings)
    try:
        state = secrets.token_urlsafe(32)
        url = client.authorization_url(provider, state)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        verifier = client.derive(state, "pkce")
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert query["code_challenge"] == [challenge]
        assert query["code_challenge_method"] == ["S256"]
        assert query["state"] == [state]
        assert verifier != client.derive(state, "nonce")
        assert "secret" not in url and verifier not in url
        assert query["redirect_uri"] == [
            f"http://localhost:3000/api/v1/auth/oauth/{provider}/callback"
        ]
        if provider == "github":
            assert parsed.netloc == "github.com" and query["scope"] == ["user:email"]
        else:
            assert parsed.netloc == "accounts.google.com"
            assert query["scope"] == ["openid email profile"]
            assert query["nonce"] == [client.derive(state, "nonce")]
    finally:
        await client.client.aclose()


@pytest.mark.parametrize(
    "status,body",
    [(302, b"redirect"), (200, b"invalid json"), (200, b"a" * 262145)],
    ids=["redirect", "invalid-json", "oversized-body"],
)
async def test_provider_responses_are_bounded_and_redirects_are_not_followed(
    settings: Settings, status: int, body: bytes
) -> None:
    provider = OAuthProvider(settings)
    await provider.client.aclose()
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status, content=body, headers={"Location": "https://evil.example.com"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
        provider.client = transport
        with pytest.raises(OAuthFailure) as failure:
            await provider.request_json("GET", "https://www.googleapis.com/oauth2/v3/certs")
        assert failure.value.code == "provider_unavailable"
        assert len(requests) == 1


@pytest.mark.parametrize("algorithm", ["HS256", "none"])
async def test_google_rejects_unapproved_algorithms_without_fetching_keys(
    settings: Settings, algorithm: str
) -> None:
    provider = OAuthProvider(settings)
    try:
        token = jwt.encode(
            {"sub": "123"},
            "attacker-secret" * 3 if algorithm == "HS256" else None,
            algorithm=algorithm,
            headers={"kid": "attacker"},
        )
        with pytest.raises(OAuthFailure) as failure:
            await provider.google_identity(token, "client-id", "nonce")
        assert failure.value.code == "invalid_identity"
    finally:
        await provider.client.aclose()


@pytest.mark.parametrize(
    "hosted,authoritative", [("example.com", True), ("other.example.com", False), (None, False)]
)
async def test_google_workspace_authority_requires_matching_hosted_domain(
    settings: Settings, hosted: str | None, authoritative: bool
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = {
        **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),
        "kid": "workspace-key",
        "alg": "RS256",
        "use": "sig",
    }
    issued = datetime.now(UTC)
    claims = {
        "sub": "workspace-user",
        "iss": "https://accounts.google.com",
        "aud": "client-id",
        "iat": issued,
        "exp": issued + timedelta(minutes=5),
        "nonce": "browser-nonce",
        "email": "employee@example.com",
        "email_verified": True,
        **({"hd": hosted} if hosted else {}),
    }
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "workspace-key"})
    provider = OAuthProvider(settings)
    await provider.client.aclose()

    def keys(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://www.googleapis.com/oauth2/v3/certs"
        return httpx.Response(200, json={"keys": [public]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(keys)) as transport:
        provider.client = transport
        identity = await provider.google_identity(token, "client-id", "browser-nonce")
    assert identity.email_authoritative is authoritative


FROZEN_GOOGLE_TIME = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
async def google_clock(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[OAuthProvider, Callable[[dict[str, object]], str]]]:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return (
                FROZEN_GOOGLE_TIME.astimezone(tz)
                if tz is not None
                else FROZEN_GOOGLE_TIME.replace(tzinfo=None)
            )

    monkeypatch.setattr(jwt.api_jwt, "datetime", FrozenDateTime)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = {
        **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),
        "kid": "clock-fixture",
        "alg": "RS256",
        "use": "sig",
    }
    epoch = int(FROZEN_GOOGLE_TIME.timestamp())

    def sign(overrides: dict[str, object]) -> str:
        claims = {
            "sub": "clock-user",
            "iss": "https://accounts.google.com",
            "aud": "client-id",
            "iat": epoch - 60,
            "exp": epoch + 3600,
            "nonce": "browser-nonce",
            "email": "clock-user@gmail.com",
            "email_verified": True,
            **overrides,
        }
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "clock-fixture"})

    def keys(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://www.googleapis.com/oauth2/v3/certs"
        return httpx.Response(200, json={"keys": [public]})

    provider = OAuthProvider(settings)
    await provider.client.aclose()
    async with httpx.AsyncClient(transport=httpx.MockTransport(keys)) as transport:
        provider.client = transport
        yield provider, sign


@pytest.mark.parametrize(
    "claim,offset,accepted",
    [
        ("iat", 29, True),
        ("iat", 30, True),
        ("iat", 31, False),
        ("nbf", 29, True),
        ("nbf", 30, True),
        ("nbf", 31, False),
        ("exp", -29, True),
        ("exp", -30, False),
        ("exp", -31, False),
    ],
)
async def test_google_time_claims_allow_only_thirty_seconds_of_clock_skew(
    google_clock: tuple[OAuthProvider, Callable[[dict[str, object]], str]],
    claim: str,
    offset: int,
    accepted: bool,
) -> None:
    provider, sign = google_clock
    token = sign({claim: int(FROZEN_GOOGLE_TIME.timestamp()) + offset})
    if accepted:
        identity = await provider.google_identity(token, "client-id", "browser-nonce")
        assert identity.subject == "clock-user"
    else:
        with pytest.raises(OAuthFailure) as failure:
            await provider.google_identity(token, "client-id", "browser-nonce")
        assert failure.value.code == "invalid_identity"
        expected = jwt.ExpiredSignatureError if claim == "exp" else jwt.ImmatureSignatureError
        assert isinstance(failure.value.__cause__, expected)


@pytest.mark.parametrize(
    "claim,value,reason,cause",
    [
        ("nonce", "another-browser", "nonce_mismatch", None),
        ("iss", "https://attacker.example.com", "id_token_validation", jwt.InvalidIssuerError),
        ("aud", "another-client", "id_token_validation", jwt.InvalidAudienceError),
    ],
)
async def test_google_clock_tolerance_preserves_nonce_issuer_and_audience_checks(
    google_clock: tuple[OAuthProvider, Callable[[dict[str, object]], str]],
    claim: str,
    value: str,
    reason: str,
    cause: type[Exception] | None,
) -> None:
    provider, sign = google_clock
    token = sign({"iat": int(FROZEN_GOOGLE_TIME.timestamp()) + 15, claim: value})
    with pytest.raises(OAuthFailure) as failure:
        await provider.google_identity(token, "client-id", "browser-nonce")
    assert failure.value.code == "invalid_identity"
    assert failure.value.reason == reason
    if cause is not None:
        assert isinstance(failure.value.__cause__, cause)


async def test_google_clock_tolerance_does_not_change_forge_session_validation(
    settings: Settings,
    google_clock: tuple[OAuthProvider, Callable[[dict[str, object]], str]],
) -> None:
    issued = int(FROZEN_GOOGLE_TIME.timestamp())
    token = jwt.encode(
        {
            "iss": "forge",
            "aud": "forge-browser",
            "kind": "access",
            "iat": issued + 15,
            "exp": issued + 600,
        },
        settings.auth_secret.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(DomainError) as failure:
        TokenCodec(settings).decode(token, "access")
    assert isinstance(failure.value.__cause__, jwt.ImmatureSignatureError)
