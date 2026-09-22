"""Small, fixed-host OAuth clients. Provider credentials never reach the browser."""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
import jwt
from email_validator import EmailNotValidError, validate_email

from forge.config import Settings

Provider = Literal["github", "google"]
PROVIDERS: tuple[Provider, ...] = ("github", "google")
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_CLOCK_SKEW_SECONDS = 30


class OAuthFailure(Exception):
    def __init__(self, code: str, *, reason: str | None = None) -> None:
        self.code = code
        self.reason = reason or code
        super().__init__(code)


@dataclass(frozen=True)
class ProviderIdentity:
    provider: Provider
    subject: str
    email: str
    name: str
    email_authoritative: bool


def canonical_email(value: object) -> str:
    if not isinstance(value, str) or len(value) > 254:
        raise OAuthFailure("invalid_identity", reason="email_format")
    try:
        return validate_email(value, check_deliverability=False).normalized.casefold()
    except EmailNotValidError as exc:
        raise OAuthFailure("invalid_identity", reason="email_format") from exc


def display_name(value: object, email: str) -> str:
    name = value if isinstance(value, str) else email.split("@", 1)[0]
    return (
        "".join(character for character in name if character.isprintable()).strip()[:100] or "User"
    )


class OAuthProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=3.0),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            trust_env=False,
        )

    def credentials(self, provider: Provider) -> tuple[str, str]:
        identifier = getattr(self.settings, f"{provider}_client_id")
        secret = getattr(self.settings, f"{provider}_client_secret")
        if not identifier or not secret:
            raise OAuthFailure("provider_unavailable")
        return identifier, secret.get_secret_value()

    def enabled(self, provider: Provider) -> bool:
        return bool(getattr(self.settings, f"{provider}_client_id"))

    def callback(self, provider: Provider) -> str:
        return f"{self.settings.public_origin}/api/v1/auth/oauth/{provider}/callback"

    def derive(self, state: str, purpose: str) -> str:
        # State is 256 random bits. Purpose separation prevents nonce/verifier reuse;
        # a database read reveals neither the state nor its secret-derived verifier.
        digest = hmac.new(
            self.settings.auth_secret.get_secret_value().encode(),
            f"oauth:{purpose}:{state}".encode(),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    def authorization_url(self, provider: Provider, state: str) -> str:
        identifier, _ = self.credentials(provider)
        verifier = self.derive(state, "pkce")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        parameters = {
            "client_id": identifier,
            "redirect_uri": self.callback(provider),
            "state": state,
            "code_challenge": challenge.decode().rstrip("="),
            "code_challenge_method": "S256",
        }
        if provider == "github":
            parameters["scope"] = "user:email"
            endpoint = "https://github.com/login/oauth/authorize"
        else:
            parameters.update(
                {
                    "response_type": "code",
                    "scope": "openid email profile",
                    "nonce": self.derive(state, "nonce"),
                    "prompt": "select_account",
                    "access_type": "online",
                }
            )
            endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        return f"{endpoint}?{urlencode(parameters)}"

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            async with self.client.stream(
                method,
                url,
                data=data,
                headers={"Accept": "application/json", **(headers or {})},
            ) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 262144:
                        raise OAuthFailure("provider_unavailable")
                return json.loads(body)
        except (httpx.HTTPError, ValueError, UnicodeError) as exc:
            # Never expose upstream bodies, URLs or exceptions containing credentials.
            raise OAuthFailure("provider_unavailable") from exc

    async def exchange(self, provider: Provider, code: str, state: str) -> ProviderIdentity:
        identifier, secret = self.credentials(provider)
        data = {
            "client_id": identifier,
            "client_secret": secret,
            "code": code,
            "redirect_uri": self.callback(provider),
            "code_verifier": self.derive(state, "pkce"),
        }
        if provider == "github":
            token = await self.request_json(
                "POST", "https://github.com/login/oauth/access_token", data=data
            )
            if not isinstance(token, dict) or not isinstance(token.get("access_token"), str):
                raise OAuthFailure("invalid_identity")
            access = token["access_token"]
            if (
                not access
                or len(access) > 8192
                or not access.isascii()
                or any(character.isspace() or ord(character) < 32 for character in access)
            ):
                raise OAuthFailure("invalid_identity")
            headers = {
                "Authorization": f"Bearer {access}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            user = await self.request_json("GET", "https://api.github.com/user", headers=headers)
            emails = await self.request_json(
                "GET", "https://api.github.com/user/emails?per_page=100", headers=headers
            )
            if (
                not isinstance(user, dict)
                or type(user.get("id")) is not int
                or user["id"] <= 0
                or not isinstance(emails, list)
            ):
                raise OAuthFailure("invalid_identity")
            primary = next(
                (
                    item
                    for item in emails
                    if isinstance(item, dict)
                    and item.get("primary") is True
                    and item.get("verified") is True
                ),
                None,
            )
            if primary is None:
                raise OAuthFailure("email_unverified")
            email = canonical_email(primary.get("email"))
            subject = str(user["id"])
            if len(subject) > 255:
                raise OAuthFailure("invalid_identity")
            return ProviderIdentity(
                provider, subject, email, display_name(user.get("name"), email), True
            )
        data["grant_type"] = "authorization_code"
        token = await self.request_json("POST", "https://oauth2.googleapis.com/token", data=data)
        if not isinstance(token, dict) or not isinstance(token.get("id_token"), str):
            raise OAuthFailure("invalid_identity", reason="missing_id_token")
        return await self.google_identity(
            token["id_token"], identifier, self.derive(state, "nonce")
        )

    async def google_identity(self, token: str, audience: str, nonce: str) -> ProviderIdentity:
        if len(token) > 16384:
            raise OAuthFailure("invalid_identity", reason="id_token_size")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise OAuthFailure("invalid_identity", reason="id_token_header")
            # Never follow jku/x5u supplied by an untrusted token.
            jwks = await self.request_json("GET", GOOGLE_JWKS)
            if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
                raise OAuthFailure("invalid_identity", reason="signing_keys_format")
            key = next(
                (
                    item
                    for item in jwks["keys"]
                    if isinstance(item, dict)
                    and item.get("kid") == header["kid"]
                    and item.get("kty") == "RSA"
                    and item.get("use", "sig") == "sig"
                    and item.get("alg", "RS256") == "RS256"
                ),
                None,
            )
            if key is None:
                raise OAuthFailure("invalid_identity", reason="signing_key_missing")
            claims = jwt.decode(
                token,
                jwt.PyJWK.from_dict(key, algorithm="RS256").key,
                algorithms=["RS256"],
                audience=audience,
                issuer=["accounts.google.com", "https://accounts.google.com"],
                # Google and the API can differ slightly at issuance. Keep time
                # validation enabled with bounded skew only for external Google tokens.
                leeway=GOOGLE_CLOCK_SKEW_SECONDS,
                options={
                    "require": [
                        "exp",
                        "iat",
                        "iss",
                        "aud",
                        "sub",
                        "nonce",
                        "email",
                        "email_verified",
                    ]
                },
            )
            if claims.get("azp", audience) != audience or (
                isinstance(claims["aud"], list)
                and len(claims["aud"]) > 1
                and claims.get("azp") != audience
            ):
                raise OAuthFailure("invalid_identity", reason="authorized_party")
            actual_nonce = claims["nonce"]
            if (
                not isinstance(actual_nonce, str)
                or not actual_nonce.isascii()
                or not hmac.compare_digest(actual_nonce, nonce)
            ):
                raise OAuthFailure("invalid_identity", reason="nonce_mismatch")
            subject = claims["sub"]
            if (
                not isinstance(subject, str)
                or not subject
                or len(subject) > 255
                or not subject.isascii()
            ):
                raise OAuthFailure("invalid_identity", reason="subject_format")
            if claims["email_verified"] is not True:
                raise OAuthFailure("email_unverified")
            email = canonical_email(claims["email"])
            domain = email.rsplit("@", 1)[1]
            hosted = claims.get("hd")
            # Google is not authoritative for arbitrary third-party email addresses,
            # even with email_verified=true. Those users first verify a Forge account
            # through its email flow and explicitly connect Google in account settings.
            authoritative = domain == "gmail.com" or (
                isinstance(hosted, str) and bool(hosted) and hosted.casefold() == domain
            )
            return ProviderIdentity(
                "google", subject, email, display_name(claims.get("name"), email), authoritative
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise OAuthFailure("invalid_identity", reason="id_token_validation") from exc
