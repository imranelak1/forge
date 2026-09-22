from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from forge.config import Settings
from forge.domain.analytics import AnalyticsCursor, github_url, window
from forge.domain.identity import DomainError
from forge.security.identity import TokenCodec
from forge.services.analytics import AnalyticsService

NOW = datetime(2026, 9, 22, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "start,end",
    [
        (NOW.replace(tzinfo=None), NOW),
        (NOW, NOW),
        (NOW, NOW - timedelta(seconds=1)),
        (NOW - timedelta(days=367), NOW),
    ],
)
def test_windows_require_explicit_timezones_positive_bounded_ranges(start, end):
    with pytest.raises(DomainError) as error:
        window(start, end, NOW)
    assert error.value.code == "invalid_window"


def test_window_default_and_offset_are_unambiguous():
    result = window(None, None, NOW)
    assert result.start == NOW - timedelta(days=90) and result.end == NOW
    offset = datetime.fromisoformat("2026-09-22T13:00:00+01:00")
    assert window(offset - timedelta(days=1), offset, NOW).end == NOW


@pytest.mark.parametrize(
    "end",
    [
        datetime.min.replace(tzinfo=UTC),
        datetime.fromisoformat("9999-12-31T23:59:59-01:00"),
    ],
)
def test_out_of_range_window_conversion_is_validation_error(end):
    with pytest.raises(DomainError) as error:
        window(None, end, NOW)
    assert error.value.code == "invalid_window"


def test_cursor_preserves_window_and_rejects_scope_change_or_tampering():
    tokens = TokenCodec(
        Settings(database_password="unit-password-long-enough", auth_secret="a" * 64)
    )
    org, repository = uuid4(), uuid4()
    scope = {"org": org, "repository": repository, "author": "reviewer", "limit": 30}
    codec = AnalyticsCursor(tokens, scope)
    identifier = uuid4()
    effective = window(None, None, NOW)
    token = codec.encode({"id": identifier, "sort_at": NOW}, effective)
    parsed = codec.decode(token)
    assert parsed == {"id": identifier, "at": NOW, "window": effective}
    for changed in (
        {**scope, "org": uuid4()},
        {**scope, "repository": uuid4()},
        {**scope, "author": "someone-else"},
        {**scope, "limit": 100},
    ):
        with pytest.raises(DomainError):
            AnalyticsCursor(tokens, changed).decode(token)
    with pytest.raises(DomainError):
        codec.decode("a" + token[1:])


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://github.com.evil.test/repo",
        "http://github.com/repo",
        "https://user:secret@github.com/repo",
        "https://github.com:9000/repo",
        "",
        None,
    ],
)
def test_source_links_are_only_actual_https_github_urls(url):
    assert github_url(url) is None


def test_synthetic_files_never_invent_source_urls():
    row = {
        "id": uuid4(),
        "filename": "source.py",
        "previous_filename": None,
        "status": "modified",
        "additions": 3,
        "deletions": 1,
        "changes": 4,
    }
    parent = {"html_url": "", "repository_name": "synthetic/repo", "sha": "a" * 40}
    assert AnalyticsService.child_summary(row, "files", parent)["blob_url"] is None


def test_review_flags_preserve_historical_approval_without_counting_bot_or_self():
    row = {
        "id": uuid4(),
        "provider_id": 1,
        "reviewer_login": "reviewer",
        "reviewer_type": "User",
        "state": "DISMISSED",
        "original_state": "APPROVED",
        "submitted_at": NOW,
        "approved_at": NOW,
        "dismissed_at": NOW + timedelta(hours=1),
        "html_url": "https://github.com/example/repo/pull/1#pullrequestreview-1",
    }
    parent = {"author_login": "author"}
    known = AnalyticsService.child_summary(row, "reviews", parent)
    assert known["qualifies"] and known["approval_known"]
    unknown = AnalyticsService.child_summary(
        {**row, "original_state": None, "approved_at": None}, "reviews", parent
    )
    assert not unknown["qualifies"] and not unknown["approval_known"]
    for changed in (
        {"reviewer_type": "Bot"},
        {"reviewer_login": "AuThOr"},
        {"reviewer_login": "automation[bot]"},
    ):
        assert not AnalyticsService.child_summary({**row, **changed}, "reviews", parent)[
            "qualifies"
        ]
