"""Machine report ingestion limits and safe outward metadata."""

import base64
import hashlib
import hmac
import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet

from forge.domain.identity import DomainError

MAX_REPORT_BYTES = 10 * 1024 * 1024
REPORT_PATH = re.compile(
    r"^/api/v1/organizations/[0-9a-fA-F-]{36}/repositories/[0-9a-fA-F-]{36}/test-reports$"
)
DEFAULT_POLICY: dict[str, Any] = {
    "version": 1,
    "window_days": 14,
    "min_executions": 10,
    "failure_rate_low": 0.05,
    "failure_rate_high": 0.95,
    "min_transitions": 2,
    "excluded_branches": [],
    "updated_at": None,
}
TOKEN_FIELDS = (
    "id",
    "repository_id",
    "name",
    "token_prefix",
    "scope",
    "created_at",
    "expires_at",
    "revoked_at",
    "last_used_at",
)
RECEIPT_FIELDS = (
    "id",
    "repository_id",
    "workflow_run_id",
    "status",
    "received_at",
    "processed_at",
    "error_code",
    "supersedes_id",
    "superseded_by_id",
)


def invalid_token() -> DomainError:
    return DomainError(401, "invalid_service_token", "A valid repository upload token is required.")


def parse_credential(header: str | None) -> tuple[UUID, str]:
    match = re.fullmatch(r"Bearer (forge_ci_([0-9a-f]{32})\.([A-Za-z0-9_-]{43}))", header or "")
    if match is None:
        raise invalid_token()
    return UUID(hex=match[2]), match[1]


def payload_cipher(secret: str) -> Fernet:
    key = hmac.new(secret.encode(), b"forge:junit-payload:v1", hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def token_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in TOKEN_FIELDS}


def receipt(row: Mapping[str, Any], duplicate: bool = False) -> dict[str, Any]:
    return {key: row[key] for key in RECEIPT_FIELDS} | {"duplicate": duplicate}


def policy_summary(row: Mapping[str, Any] | None, repository: UUID) -> dict[str, Any]:
    return {
        "repository_id": repository,
        **{key: row[key] if row else value for key, value in DEFAULT_POLICY.items()},
    }
