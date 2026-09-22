from datetime import UTC, datetime, timedelta

import pytest

from forge.domain.analytics import Window
from forge.domain.delivery import dates, day_is_full, full_days, seconds
from forge.services.delivery import ci_bucket, coverage


def test_partial_calendar_days_do_not_enter_frequency_denominator():
    effective = Window(datetime(2026, 1, 1, 12, tzinfo=UTC), datetime(2026, 1, 4, 1, tzinfo=UTC))
    assert full_days(effective) == (
        datetime(2026, 1, 2, tzinfo=UTC),
        datetime(2026, 1, 4, tzinfo=UTC),
        2,
    )
    assert dates(effective) == ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    assert [day for day in dates(effective) if day_is_full(day, effective)] == [
        "2026-01-02",
        "2026-01-03",
    ]


def test_maximum_date_and_subday_window_have_no_invented_full_days():
    end = datetime.max.replace(tzinfo=UTC)
    effective = Window(end - timedelta(hours=1), end)
    assert full_days(effective)[2] == 0
    assert dates(effective) == ["9999-12-31"]
    assert not day_is_full("9999-12-31", effective)


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (None, datetime(2026, 1, 1, tzinfo=UTC), None),
        (datetime(2026, 1, 1, tzinfo=UTC), None, None),
        (datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC), None),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC), 0),
    ],
)
def test_missing_or_invalid_job_timing_stays_unknown(start, end, expected):
    assert seconds(start, end) == expected


def test_empty_attempt_denominator_is_unknown_and_distributions_do_not_share_exclusions():
    first, second = ci_bucket(), ci_bucket()
    assert first["success_fraction"] is first["failure_fraction"] is None
    assert first["duration"]["mean_seconds"] is None
    first["queue"]["exclusions"]["queue_unknown"] = 1
    assert second["queue"]["exclusions"] == first["duration"]["exclusions"] == {}


def test_completion_provenance_disclosed_and_unknown_timing_downgrades_coverage():
    source = dict(
        repository_count=1,
        repositories_complete=1,
        repositories_unavailable=0,
        source_incomplete=0,
        history_window_partial=0,
        sources_unavailable=0,
        input_watermark=None,
    )
    proxy = coverage(source, {"completion_proxy_count": 3})
    assert proxy["status"] == "complete" and proxy["limitations"] == ["job_completion_proxy"]
    unknown = coverage(source, {"completion_unknown_count": 1})
    assert unknown["status"] == "partial" and "completion_unknown" in unknown["limitations"]
    unavailable = coverage({**source, "repositories_unavailable": 1, "source_incomplete": 1})
    assert unavailable["status"] == "unavailable"
