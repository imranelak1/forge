from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from forge.config import Settings
from forge.domain.identity import DomainError, require_manager
from forge.security.identity import AUDIENCE, ISSUER, TokenCodec


@pytest.mark.parametrize("role", ["viewer", "member"])
def test_non_managers_cannot_manage_memberships(role: str) -> None:
    with pytest.raises(DomainError) as error:
        require_manager(role)
    assert error.value.status == 403


@pytest.mark.parametrize("current,new", [("owner", "member"), ("member", "owner"), ("owner", None)])
def test_administrators_cannot_change_ownership(current: str, new: str | None) -> None:
    with pytest.raises(DomainError) as error:
        require_manager("admin", current, new)
    assert error.value.status == 403


def test_owners_can_manage_ownership_and_admins_can_manage_non_owners() -> None:
    require_manager("owner", "member", "owner")
    require_manager("owner", "owner", "member")
    require_manager("admin", "viewer", "member")


@pytest.mark.parametrize(
    "changed",
    [
        {"iss": "another-issuer"},
        {"aud": "another-audience"},
        {"kind": "cursor"},
        {"exp": 0},
        {"iat": 4102444800},
    ],
)
def test_signed_jwt_requires_expected_issuer_audience_kind_and_time(
    settings: Settings, changed: dict[str, object]
) -> None:
    issued = datetime.now(UTC)
    claims = {
        "sub": str(uuid4()),
        "sid": str(uuid4()),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "kind": "access",
        "iat": issued,
        "exp": issued + timedelta(minutes=10),
        **changed,
    }
    token = jwt.encode(claims, settings.auth_secret.get_secret_value(), algorithm="HS256")
    with pytest.raises(DomainError) as error:
        TokenCodec(settings).decode(token, "access")
    assert error.value.status == 401


def test_jwt_algorithm_is_an_explicit_allowlist(settings: Settings) -> None:
    issued = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "sid": str(uuid4()),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "kind": "access",
            "iat": issued,
            "exp": issued + timedelta(minutes=10),
        },
        settings.auth_secret.get_secret_value(),
        algorithm="HS384",
    )
    with pytest.raises(DomainError) as error:
        TokenCodec(settings).decode(token, "access")
    assert error.value.status == 401
