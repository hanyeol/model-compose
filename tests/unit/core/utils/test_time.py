"""Unit tests for ``mindor.core.utils.time``."""

from datetime import datetime, timedelta, timezone

import pytest

from mindor.core.utils.time import (
    TimeTracker,
    TimezoneFormat,
    format_datetime_iso_string,
    format_timecode,
    parse_datetime,
    parse_duration,
    parse_timecode,
)


class TestParseDuration:
    def test_numeric_passthrough(self):
        assert parse_duration(30) == 30.0
        assert parse_duration(1.5) == 1.5

    def test_milliseconds(self):
        assert parse_duration("250ms") == 0.25

    def test_seconds(self):
        assert parse_duration("30s") == 30.0

    def test_minutes(self):
        assert parse_duration("5m") == 300.0

    def test_hours(self):
        assert parse_duration("2h") == 7200.0

    def test_days(self):
        assert parse_duration("1d") == 86400.0

    def test_unsupported_format_raises(self):
        with pytest.raises(ValueError, match="Unsupported duration format"):
            parse_duration("1y")

    def test_unitless_string_raises(self):
        with pytest.raises(ValueError):
            parse_duration("30")


class TestParseTimecode:
    def test_hh_mm_ss(self):
        assert parse_timecode("01:30:45") == 5445.0

    def test_hh_mm_ss_with_fractional_seconds(self):
        assert parse_timecode("00:00:01.500") == 1.5

    def test_mm_ss(self):
        assert parse_timecode("02:30") == 150.0

    def test_falls_back_to_duration_parser_for_no_colon(self):
        assert parse_timecode("30s") == 30.0
        assert parse_timecode(60) == 60.0

    def test_too_many_parts_raises(self):
        with pytest.raises(ValueError, match="Unsupported timecode format"):
            parse_timecode("01:02:03:04")


class TestFormatTimecode:
    def test_zero(self):
        assert format_timecode(0) == "00:00:00.000"

    def test_under_one_hour(self):
        assert format_timecode(3661.5) == "01:01:01.500"

    def test_seconds_only(self):
        assert format_timecode(45.25) == "00:00:45.250"


class TestParseDatetime:
    def test_iso_string_with_timezone(self):
        dt = parse_datetime("2024-01-15T10:30:00+09:00", timezone=None)
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=9)

    def test_naive_string_with_timezone_applies_zone(self):
        dt = parse_datetime("2024-01-15T10:30:00", timezone="UTC")
        assert dt.tzinfo is not None

    def test_naive_string_without_timezone_stays_naive(self):
        dt = parse_datetime("2024-01-15T10:30:00", timezone=None)
        assert dt.tzinfo is None

    def test_aware_datetime_passes_through(self):
        original = datetime(2024, 1, 15, tzinfo=timezone.utc)
        assert parse_datetime(original, timezone=None) is original


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
