"""Tests for the ffmpeg-style filename formatter used by video-frame-extractor."""

from __future__ import annotations

import pytest

from mindor.core.component.services.video_frame_extractor.filename import format_filename


class TestFormatFilename:
    def test_plain_index(self):
        assert format_filename("frame-%d.png", 1) == "frame-1.png"
        assert format_filename("frame-%d.png", 42) == "frame-42.png"

    def test_zero_padded(self):
        assert format_filename("frame-%04d.png", 1) == "frame-0001.png"
        assert format_filename("frame-%04d.png", 1234) == "frame-1234.png"
        assert format_filename("frame-%04d.png", 12345) == "frame-12345.png"

    def test_wide_padding(self):
        assert format_filename("shot-%09d.jpg", 7) == "shot-000000007.jpg"

    def test_literal_percent(self):
        assert format_filename("%%d-%04d.png", 3) == "%d-0003.png"

    def test_no_specifier_returns_literal(self):
        assert format_filename("frame.png", 5) == "frame.png"

    def test_multiple_specifiers(self):
        assert format_filename("%d-%04d.png", 9) == "9-0009.png"

    def test_unsupported_specifier_raises(self):
        with pytest.raises(ValueError, match="Unsupported specifier"):
            format_filename("frame-%s.png", 1)

    def test_bare_percent_raises(self):
        with pytest.raises(ValueError, match="Unsupported specifier"):
            format_filename("frame-%.png", 1)

    def test_non_zero_padded_width_is_rejected(self):
        # Only %d and %0Nd are supported; %4d (space-padded) is not meaningful for filenames.
        with pytest.raises(ValueError, match="Unsupported specifier"):
            format_filename("frame-%4d.png", 1)
