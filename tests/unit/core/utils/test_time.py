"""Unit tests for ``mindor.core.utils.time``."""

from datetime import datetime, timedelta, timezone

from mindor.core.utils.time import (
    TimeTracker,
    TimezoneFormat,
    format_datetime_iso_string,
    format_timecode,
)


class TestFormatTimecode:
    def test_zero(self):
        assert format_timecode(0) == "00:00:00.000"

    def test_under_one_hour(self):
        assert format_timecode(3661.5) == "01:01:01.500"

    def test_seconds_only(self):
        assert format_timecode(45.25) == "00:00:45.250"


class TestFormatDatetimeIsoString:
    def test_zulu_format_for_utc(self):
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        assert format_datetime_iso_string(dt) == "2024-01-15T10:30:45Z"

    def test_offset_format_keeps_plus_zero(self):
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        assert format_datetime_iso_string(dt, tz_format=TimezoneFormat.OFFSET) == "2024-01-15T10:30:45+00:00"

    def test_naive_datetime_treated_as_utc(self):
        dt = datetime(2024, 1, 15, 10, 30, 45)
        assert format_datetime_iso_string(dt) == "2024-01-15T10:30:45Z"

    def test_unix_timestamp_int(self):
        # 2024-01-15T00:00:00Z = 1705276800
        result = format_datetime_iso_string(1705276800)
        assert result == "2024-01-15T00:00:00Z"

    def test_non_utc_timezone_converted_to_utc(self):
        kst = timezone(timedelta(hours=9))
        dt = datetime(2024, 1, 15, 19, 30, 0, tzinfo=kst)
        assert format_datetime_iso_string(dt) == "2024-01-15T10:30:00Z"


class TestTimeTracker:
    def test_elapsed_increases_monotonically(self):
        import time

        t = TimeTracker()
        first = t.elapsed()
        time.sleep(0.01)
        second = t.elapsed()
        assert second > first

    def test_reset_brings_elapsed_back_to_near_zero(self):
        import time

        t = TimeTracker()
        time.sleep(0.01)
        assert t.elapsed() > 0
        t.reset()
        assert t.elapsed() < 0.01
