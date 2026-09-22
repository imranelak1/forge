import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from forge.config import Settings
from forge.domain.identity import unauthorized

ACCESS_SECONDS = 600
SESSION_SECONDS = 30 * 24 * 60 * 60
ISSUER = "forge"
AUDIENCE = "forge-browser"
PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, type=Type.ID)
# Match nonexistent users to the same expensive verification path.
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


def now() -> datetime:
    return datetime.now(UTC)


def opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(password: str, encoded: str) -> bool:
    try:
        return PASSWORDS.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


class TokenCodec:
    def __init__(self, settings: Settings) -> None:
        self.key = settings.auth_secret.get_secret_value()

    def encode(self, payload: dict[str, Any], seconds: int, kind: str) -> str:
        issued = now()
        return jwt.encode(
            {
                **payload,
                "iat": issued,
                "exp": issued + timedelta(seconds=seconds),
                "iss": ISSUER,
                "aud": AUDIENCE,
                "kind": kind,
            },
            self.key,
            algorithm="HS256",
        )

    def decode(self, token: str, kind: str) -> dict[str, Any]:
        try:
            data: dict[str, Any] = jwt.decode(
                token,
                self.key,
                algorithms=["HS256"],
                issuer=ISSUER,
                audience=AUDIENCE,
                options={"require": ["exp", "iat", "iss", "aud", "kind"]},
            )
            if data["kind"] != kind:
                raise unauthorized()
            return data
        except jwt.PyJWTError as exc:
            raise unauthorized() from exc

    def access(self, user_id: UUID, session_id: UUID) -> str:
        return self.encode({"sub": str(user_id), "sid": str(session_id)}, ACCESS_SECONDS, "access")

    def csrf(self, session_id: UUID) -> str:
        # Deterministic session binding lets /csrf recover after reload without storing plaintext.
        return hmac.new(
            self.key.encode(), f"csrf:{session_id}".encode(), hashlib.sha256
        ).hexdigest()

    def csrf_matches(self, token: str, expected_hash: str) -> bool:
        return hmac.compare_digest(token_hash(token), expected_hash)

    def cursor(self, scope: str, boundary: str) -> str:
        return self.encode({"scope": scope, "boundary": boundary}, 3600, "cursor")

    def boundary(self, cursor: str | None, scope: str) -> UUID | None:
        if cursor is None:
            return None
        from forge.domain.identity import DomainError

        try:
            data = self.decode(cursor, "cursor")
            if data.get("scope") != scope:
                raise ValueError("scope")
            return UUID(data["boundary"])
        except (ValueError, KeyError, TypeError, DomainError) as exc:
            raise DomainError(422, "invalid_cursor", "The pagination cursor is invalid.") from exc
