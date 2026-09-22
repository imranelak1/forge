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
        "author_type": string(
            object_value(author).get("type") if author is not None else None, 30, optional=True
        ),
        "merge_commit_sha": sha(value["merge_commit_sha"])
        if value.get("merged_at") and value.get("merge_commit_sha")
        else None,
        "provider_commit_count": count(value.get("commits")),
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


def count(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value < 2**31:
        raise ValueError("invalid_count")
    return value


def actor(value: object) -> tuple[str | None, str | None]:
    data = object_value(value) if value is not None else {}
    return string(data.get("login"), 100, optional=True), string(
        data.get("type"), 30, optional=True
    )


def review(value: Mapping[str, Any], full_name: str, number: int) -> dict[str, Any]:
    state = value.get("state")
    if state not in {"PENDING", "COMMENTED", "APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
        raise ValueError("invalid_review_state")
    identifier = positive_id(value.get("id"))
    login, kind = actor(value.get("user"))
    submitted = timestamp(value.get("submitted_at"), optional=True)
    return {
        "provider_id": identifier,
        "reviewer_login": login,
        "reviewer_type": kind,
        "state": state,
        "original_state": state if state not in {"PENDING", "DISMISSED"} else None,
        "submitted_at": submitted,
        "approved_at": submitted if state == "APPROVED" else None,
        "html_url": f"https://github.com/{full_name}/pull/{number}#pullrequestreview-{identifier}",
    }


def transition(value: Mapping[str, Any], full_name: str, number: int) -> dict[str, Any] | None:
    kind = value.get("event")
    if kind not in {
        "closed",
        "reopened",
        "merged",
        "convert_to_draft",
        "ready_for_review",
        "review_dismissed",
    }:
        return None
    identifier = positive_id(value.get("id"))
    login, actor_type = actor(value.get("actor"))
    result = {
        "provider_id": identifier,
        "source_key": f"timeline:{identifier}",
        "kind": "converted_to_draft" if kind == "convert_to_draft" else kind,
        "occurred_at": timestamp(value.get("created_at")),
        "actor_login": login,
        "actor_type": actor_type,
        "html_url": f"https://github.com/{full_name}/pull/{number}",
    }
    if kind == "review_dismissed":
        dismissed = object_value(value.get("dismissed_review"))
        review_id = dismissed.get("review_id")
        if isinstance(review_id, str) and review_id.isdecimal() and len(review_id) <= 19:
            review_id = int(review_id)
        state = str(dismissed.get("state", "")).upper()
        if state not in {"APPROVED", "COMMENTED", "CHANGES_REQUESTED"}:
            raise ValueError("invalid_dismissed_review")
        result["dismissed_review_id"] = positive_id(review_id)
        result["dismissed_state"] = state
    return result


def commit_file(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("status") not in {
        "added",
        "removed",
        "modified",
        "renamed",
        "copied",
        "changed",
        "unchanged",
    }:
        raise ValueError("invalid_file_status")
    return {
        "filename": string(value.get("filename"), 4096),
        "previous_filename": string(value.get("previous_filename"), 4096, optional=True),
        "status": value["status"],
        "additions": count(value.get("additions")),
        "deletions": count(value.get("deletions")),
        "changes": count(value.get("changes")),
    }


def issue(value: Mapping[str, Any], full_name: str) -> dict[str, Any]:
    number = positive_id(value.get("number"))
    if number >= 2**31 or value.get("state") not in {"open", "closed"} or "pull_request" in value:
        raise ValueError("invalid_issue")
    login, kind = actor(value.get("user"))
    return {
        "provider_id": positive_id(value.get("id")),
        "number": number,
        "title": string(value.get("title"), 10000),
        "state": value["state"],
        "author_login": login,
        "author_type": kind,
        "opened_at": timestamp(value.get("created_at")),
        "updated_at": timestamp(value.get("updated_at")),
        "closed_at": timestamp(value.get("closed_at"), optional=True),
        "html_url": f"https://github.com/{full_name}/issues/{number}",
    }


def issue_reference(value: Mapping[str, Any], full_name: str) -> dict[str, Any] | None:
    if value.get("event") != "cross-referenced":
        return None
    source = object_value(value.get("source"))
    if source.get("type") != "issue":
        return None
    item = object_value(source.get("issue"))
    number = positive_id(item.get("number"))
    # Validate the explicit provider URL against this repository; never follow arbitrary URLs.
    is_pr = isinstance(item.get("pull_request"), Mapping)
    path = "pull" if is_pr else "issues"
    expected = f"https://github.com/{full_name}/{path}/{number}"
    if item.get("html_url") != expected:
        return {"outside_repository": True}
    occurred = timestamp(value.get("created_at"))
    assert occurred
    return {
        "number": number,
        "is_pr": is_pr,
        "occurred_at": occurred,
        "source_key": f"reference:{path}:{number}:{occurred.isoformat()}",
        "html_url": expected,
    }
