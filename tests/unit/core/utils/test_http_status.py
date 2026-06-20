"""Unit tests for ``mindor.core.utils.http_status``."""

import pytest

from mindor.core.utils.http_status import is_status_code_matched


class TestExactMatches:
    def test_int_exact_match(self):
        assert is_status_code_matched(200, [200]) is True

    def test_string_digit_exact_match(self):
        assert is_status_code_matched(200, ["200"]) is True

    def test_int_no_match(self):
        assert is_status_code_matched(404, [200, 201]) is False

    def test_empty_conditions(self):
        assert is_status_code_matched(200, []) is False


class TestWildcardClassMatches:
    @pytest.mark.parametrize("code", [200, 201, 204, 299])
    def test_2xx_class_matches_2xx_codes(self, code):
        assert is_status_code_matched(code, ["2xx"]) is True

    @pytest.mark.parametrize("code", [199, 300, 404, 500])
    def test_2xx_class_does_not_match_other_codes(self, code):
        assert is_status_code_matched(code, ["2xx"]) is False

    def test_4xx_class(self):
        assert is_status_code_matched(404, ["4xx"]) is True
        assert is_status_code_matched(399, ["4xx"]) is False
        assert is_status_code_matched(500, ["4xx"]) is False

    def test_5xx_class(self):
        assert is_status_code_matched(503, ["5xx"]) is True


class TestMultipleConditions:
    def test_matches_any_condition(self):
        assert is_status_code_matched(404, [200, "4xx"]) is True

    def test_matches_first_class(self):
        assert is_status_code_matched(201, ["2xx", "3xx"]) is True

    def test_no_condition_matches(self):
        assert is_status_code_matched(500, [200, "4xx"]) is False
