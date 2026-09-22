"""Analytics windows, evidence DTOs and bounded, filter-bound pagination."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from forge.domain.identity import DomainError
from forge.security.identity import TokenCodec

Metric = Literal["cycle_time", "review_wait", "approval_to_merge"]
METRICS: tuple[Metric, ...] = ("cycle_time", "review_wait", "approval_to_merge")
FORMULA_VERSION = "pr-flow-v1"


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def summary(self) -> dict[str, datetime]:
        return {"from": self.start, "to": self.end}


def window(start: datetime | None, end: datetime | None, as_of: datetime) -> Window:
    end = end or as_of
    if end.tzinfo is None or (start is not None and start.tzinfo is None):
        raise DomainError(422, "invalid_window", "Use timezone-aware from and to timestamps.")
    try:
        end = end.astimezone(UTC)
        start = start.astimezone(UTC) if start is not None else end - timedelta(days=90)
    except (OverflowError, ValueError) as exc:
        raise DomainError(
            422, "invalid_window", "Choose timestamps within the supported range."
        ) from exc
    if not timedelta(0) < end - start <= timedelta(days=366):
        raise DomainError(422, "invalid_window", "Choose a positive window of at most 366 days.")
    return Window(start, end)


def github_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme == "https"
            and parsed.hostname == "github.com"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in {None, 443}
            and not any(ord(char) < 32 for char in value)
        ):
            return value
    except ValueError:
        pass
    return None


def evidence_coverage(row: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    return {
        "status": row[f"{prefix}_status"],
        "observed_at": row.get(f"{prefix}_synced_at"),
        "error_code": row.get(f"{prefix}_error"),
    }


def empty_distribution() -> dict[str, Any]:
    return {
        "sample_count": 0,
        "excluded_count": 0,
        "mean_seconds": None,
        "median_seconds": None,
        "p75_seconds": None,
        "p95_seconds": None,
        "exclusions": {},
    }


class AnalyticsCursor:
    """Carries the initial default window so later pages do not drift with the clock."""

    def __init__(self, tokens: TokenCodec, scope: Mapping[str, Any]) -> None:
        self.tokens = tokens
        self.scope = hashlib.sha256(
            json.dumps(dict(scope), sort_keys=True, default=str, separators=(",", ":")).encode()
        ).hexdigest()

    def decode(self, token: str | None) -> dict[str, Any] | None:
        if token is None:
            return None
        try:
            if len(token) > 4096:
                raise ValueError("length")
            data = self.tokens.decode(token, "analytics_cursor")
            if data["scope"] != self.scope:
                raise ValueError("scope")
            boundary = UUID(data["id"])
            stamp = datetime.fromisoformat(data["at"]) if data.get("at") else None
            if stamp is not None and stamp.tzinfo is None:
                raise ValueError("timestamp")
            effective = None
            if data.get("from") or data.get("to"):
                effective = window(
                    datetime.fromisoformat(data["from"]),
                    datetime.fromisoformat(data["to"]),
                    datetime.now(UTC),
                )
            return {"id": boundary, "at": stamp, "window": effective}
        except (ValueError, KeyError, TypeError, DomainError) as exc:
            raise DomainError(422, "invalid_cursor", "The pagination cursor is invalid.") from exc

    def encode(self, row: Mapping[str, Any], effective: Window | None = None) -> str:
        return self.tokens.encode(
            {
                "scope": self.scope,
                "id": str(row["id"]),
                "at": row["sort_at"].isoformat() if row.get("sort_at") else None,
                "from": effective.start.isoformat() if effective else None,
                "to": effective.end.isoformat() if effective else None,
            },
            3600,
            "analytics_cursor",
        )
