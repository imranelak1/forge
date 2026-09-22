"""Strict, provider-independent records accepted at the GitHub ingestion boundary."""

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_SEGMENT = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
_SHA = re.compile(r"[0-9a-fA-F]{40}\Z")


def timestamp(value: object, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or len(value) > 50:
        raise ValueError("invalid_timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("invalid_timestamp")
    return parsed.astimezone(UTC)


def positive_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < 2**63:
        raise ValueError("invalid_provider_id")
    return value


def segment(value: object) -> str:
    if not isinstance(value, str) or not _SEGMENT.fullmatch(value) or value in {".", ".."}:
        raise ValueError("invalid_repository_name")
    return value


def string(value: object, limit: int, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or len(value) > limit or "\x00" in value:
        raise ValueError("invalid_provider_text")
    return value


def sha(value: object) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("invalid_commit_sha")
    return value.lower()


def object_value(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("invalid_provider_object")
    return value


def repository(value: Mapping[str, Any]) -> dict[str, Any]:
    owner = segment(object_value(value.get("owner")).get("login"))
    name = segment(value.get("name"))
    if not isinstance(value.get("private"), bool) or not isinstance(value.get("archived"), bool):
        raise ValueError("invalid_repository_flags")
    return {
        "provider_id": positive_id(value.get("id")),
        "owner": owner,
        "name": name,
        "full_name": f"{owner}/{name}",
        "html_url": f"https://github.com/{owner}/{name}",
        "description": string(value.get("description"), 10000, optional=True),
        "language": string(value.get("language"), 100, optional=True),
        "default_branch": string(value.get("default_branch"), 255),
        "is_private": value["private"],
        "archived": value["archived"],
        "pushed_at": timestamp(value.get("pushed_at"), optional=True),
    }


def pull_request(value: Mapping[str, Any], full_name: str) -> dict[str, Any]:
    number = positive_id(value.get("number"))
    if number >= 2**31 or value.get("state") not in {"open", "closed"}:
        raise ValueError("invalid_pull_request")
    if not isinstance(value.get("draft", False), bool):
        raise ValueError("invalid_pull_request")
    author = value.get("user")
    return {
        "provider_id": positive_id(value.get("id")),
        "number": number,
        "title": string(value.get("title"), 10000),
        "state": value["state"],
        "draft": value.get("draft", False),
        "author_login": string(
            object_value(author).get("login") if author is not None else None, 100, optional=True
        ),
        "head_sha": sha(object_value(value.get("head")).get("sha")),
        "base_ref": string(object_value(value.get("base")).get("ref"), 255),
        "opened_at": timestamp(value.get("created_at")),
        "updated_at": timestamp(value.get("updated_at")),
        "closed_at": timestamp(value.get("closed_at"), optional=True),
        "merged_at": timestamp(value.get("merged_at"), optional=True),
        "html_url": f"https://github.com/{full_name}/pull/{number}",
    }


def commit(value: Mapping[str, Any], full_name: str, *, webhook: bool = False) -> dict[str, Any]:
    identifier = sha(value.get("id" if webhook else "sha"))
    if webhook:
        author = object_value(value.get("author"))
        authored = timestamp(value.get("timestamp"))
        committed = authored
        message = value.get("message")
        login = author.get("username")
    else:
        detail = object_value(value.get("commit"))
        authored = timestamp(object_value(detail.get("author")).get("date"), optional=True)
        committed = timestamp(object_value(detail.get("committer")).get("date"))
        message = detail.get("message")
        author = object_value(value["author"]) if value.get("author") else {}
        login = author.get("login")
    return {
        "sha": identifier,
        "message": string(message, 1_000_000),
        "author_login": string(login, 100, optional=True),
        "authored_at": authored,
        "committed_at": committed,
        "html_url": f"https://github.com/{full_name}/commit/{identifier}",
    }
