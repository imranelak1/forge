from datetime import UTC, datetime

import pytest

from forge.domain import github
from forge.workers.github import retry_delay


@pytest.mark.parametrize("value", [True, 0, -1, 2**63, "123", None])
def test_provider_identity_is_a_bounded_integer(value: object) -> None:
    with pytest.raises(ValueError):
        github.positive_id(value)


@pytest.mark.parametrize("value", ["../team", ".", "..", "team/repo", "repo?token=secret"])
def test_repository_paths_cannot_escape_fixed_provider_routes(value: str) -> None:
    with pytest.raises(ValueError):
        github.segment(value)


def test_provider_timestamps_require_timezone_and_normalize_to_utc() -> None:
    assert github.timestamp("2026-01-02T12:00:00+02:00") == datetime(2026, 1, 2, 10, tzinfo=UTC)
    assert github.timestamp(None, optional=True) is None
    with pytest.raises(ValueError):
        github.timestamp("2026-01-02T12:00:00")


def test_provider_links_are_reconstructed_from_validated_repository_identity() -> None:
    result = github.repository(
        {
            "id": 3,
            "owner": {"login": "team"},
            "name": "api",
            "private": True,
            "archived": False,
            "default_branch": "main",
            "html_url": "javascript:alert(1)",
        }
    )
    assert result["html_url"] == "https://github.com/team/api"
    assert result["full_name"] == "team/api"
    assert result["pushed_at"] is None


def test_backoff_is_bounded_and_respects_retry_after() -> None:
    for attempt in range(1, 20):
        assert 2 <= retry_delay(attempt) <= 4500
        assert retry_delay(attempt, 6000) == 6000
    assert retry_delay(1, 999999) == 86400
