"""OAuth diagnostics describe failure boundaries without disclosing callback secrets."""

import io
import json
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest

from forge.domain.identity import DomainError
from forge.integrations.oauth import OAuthFailure
from forge.observability.logging import JsonFormatter
from forge.services.oauth import OAuthService

SENTINELS = {
    "state": "sensitive-state-value",
    "binding": "sensitive-browser-binding",
    "code": "sensitive-authorization-code",
    "access": "sensitive-access-token",
    "email": "sensitive-person@example.com",
    "secret": "sensitive-client-secret",
    "url": "https://sensitive.example.com/token?code=sensitive-query",
    "error": "sensitive-raw-provider-error",
}
SENSITIVE_MESSAGE = " ".join(SENTINELS.values())


@dataclass
class LoggingHarness:
    service: OAuthService
    consume: AsyncMock
    exchange: AsyncMock
    complete: AsyncMock
    output: io.StringIO


@pytest.fixture
def diagnostic(monkeypatch: pytest.MonkeyPatch) -> LoggingHarness:
    # Bypass construction deliberately: no settings, database, HTTP clients or real credentials.
    service = object.__new__(OAuthService)
    consume = AsyncMock(return_value={"intent": "login", "return_to": "/app"})
    exchange = AsyncMock(return_value=object())
    complete = AsyncMock(return_value=None)
    monkeypatch.setattr(service, "consume_state", consume)
    monkeypatch.setattr(service, "complete", complete)
    monkeypatch.setattr(service, "provider", SimpleNamespace(exchange=exchange), raising=False)
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("forge.oauth")
    monkeypatch.setattr(logger, "handlers", [handler])
    monkeypatch.setattr(logger, "propagate", False)
    monkeypatch.setattr(logger, "level", logging.WARNING)
    return LoggingHarness(service, consume, exchange, complete, output)


def assert_safe_record(
    diagnostic: LoggingHarness,
    *,
    stage: str,
    code: str,
    error_type: str,
    reason: str | None = None,
) -> None:
    serialized = diagnostic.output.getvalue()
    for sensitive in SENTINELS.values():
        assert sensitive not in serialized
    records = serialized.splitlines()
    assert len(records) == 1
    record = json.loads(records[0])
    expected_fields = {
        "timestamp",
        "level",
        "service",
        "event",
        "provider",
        "oauth_stage",
        "oauth_error",
        "error_type",
    }
    if reason is not None:
        expected_fields.add("oauth_reason")
        assert record["oauth_reason"] == reason
    assert set(record) == expected_fields
    assert record["event"] == "oauth.callback_failed"
    assert record["level"] == "WARNING"
    assert record["service"] == "forge-api"
    assert record["provider"] == "google"
    assert record["oauth_stage"] == stage
    assert record["oauth_error"] == code
    assert record["error_type"] == error_type


async def test_provider_identity_log_keeps_exception_class_but_redacts_message(
    diagnostic: LoggingHarness,
) -> None:
    async def invalid_token(*_: object) -> None:
        raise OAuthFailure("invalid_identity", reason="id_token_validation") from (
            jwt.ImmatureSignatureError(SENSITIVE_MESSAGE)
        )

    diagnostic.exchange.side_effect = invalid_token
    result = await diagnostic.service.callback(
        "google",
        SENTINELS["state"],
        SENTINELS["binding"],
        SENTINELS["code"],
        None,
        SENTINELS["access"],
        issuer="https://accounts.google.com",
    )
    assert result.location == "/login?oauth_error=invalid_identity"
    diagnostic.exchange.assert_awaited_once()
    diagnostic.complete.assert_not_awaited()
    assert_safe_record(
        diagnostic,
        stage="provider_identity",
        code="invalid_identity",
        error_type="ImmatureSignatureError",
        reason="id_token_validation",
    )


async def test_state_log_is_distinct_and_does_not_disclose_browser_binding(
    diagnostic: LoggingHarness,
) -> None:
    async def invalid_state(*_: object) -> None:
        raise OAuthFailure("invalid_state") from ValueError(SENSITIVE_MESSAGE)

    diagnostic.consume.side_effect = invalid_state
    result = await diagnostic.service.callback(
        "google",
        SENTINELS["state"],
        SENTINELS["binding"],
        SENTINELS["code"],
        None,
        SENTINELS["access"],
    )
    assert result.location == "/login?oauth_error=invalid_state"
    diagnostic.exchange.assert_not_awaited()
    assert_safe_record(
        diagnostic,
        stage="state",
        code="invalid_state",
        error_type="ValueError",
        reason="invalid_state",
    )


@pytest.mark.parametrize("boundary", ["issuer", "denial"])
async def test_callback_boundary_log_never_discloses_issuer_or_raw_provider_error(
    diagnostic: LoggingHarness,
    boundary: str,
) -> None:
    result = await diagnostic.service.callback(
        "google",
        SENTINELS["state"],
        SENTINELS["binding"],
        SENTINELS["code"],
        SENTINELS["error"] if boundary == "denial" else None,
        SENTINELS["access"],
        issuer=SENTINELS["url"] if boundary == "issuer" else "https://accounts.google.com",
    )
    code = "invalid_identity" if boundary == "issuer" else "denied"
    assert result.location == f"/login?oauth_error={code}"
    diagnostic.consume.assert_awaited_once()
    diagnostic.exchange.assert_not_awaited()
    assert_safe_record(
        diagnostic,
        stage="callback",
        code=code,
        error_type="OAuthFailure",
        reason="callback_issuer" if boundary == "issuer" else "denied",
    )


@pytest.mark.parametrize("failure", ["timeout", "domain"])
async def test_operational_failure_logs_only_class_and_fixed_error(
    diagnostic: LoggingHarness,
    failure: str,
) -> None:
    if failure == "timeout":
        diagnostic.exchange.side_effect = TimeoutError(SENSITIVE_MESSAGE)
        stage, error_type = "provider_identity", "TimeoutError"
    else:
        diagnostic.complete.side_effect = DomainError(
            503, "sensitive-domain-code", SENSITIVE_MESSAGE
        )
        stage, error_type = "account", "DomainError"
    result = await diagnostic.service.callback(
        "google",
        SENTINELS["state"],
        SENTINELS["binding"],
        SENTINELS["code"],
        None,
        SENTINELS["access"],
    )
    assert result.location == "/login?oauth_error=provider_unavailable"
    assert "sensitive-domain-code" not in diagnostic.output.getvalue()
    assert_safe_record(diagnostic, stage=stage, code="provider_unavailable", error_type=error_type)
