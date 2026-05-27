"""Tests for parse_size: suffix matching and validation."""

import pytest

from mindor.core.utils.size import parse_size


class TestParseSize:

    def test_int_passthrough(self):
        assert parse_size(1048576) == 1048576

    def test_float_truncates(self):
        assert parse_size(1024.5) == 1024

    def test_suffix(self):
        assert parse_size("500B") == 500
        assert parse_size("512K") == 512 * 1024
        assert parse_size("50M") == 50 * 1024 ** 2
        assert parse_size("2G") == 2 * 1024 ** 3

    def test_kb_mb_gb_suffix(self):
        assert parse_size("2.5KB") == int(2.5 * 1024)
        assert parse_size("3.5MB") == int(3.5 * 1024 ** 2)
        assert parse_size("1.5GB") == int(1.5 * 1024 ** 3)


class TestParseSizeErrors:

    @pytest.mark.parametrize("bad", ["abc", "", "50X", "M50", "1048576", "50m", "  50M  "])
    def test_malformed(self, bad):
        with pytest.raises(ValueError):
            parse_size(bad)
