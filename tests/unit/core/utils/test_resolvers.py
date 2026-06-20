"""Tests for FieldResolver: keypath parsing and value resolution."""

import pytest

from mindor.core.utils.resolvers import FieldResolver


@pytest.fixture
def resolver():
    return FieldResolver()


@pytest.fixture
def data():
    return {
        "user": {
            "name": "Hanyeol",
            "age": 30,
            "tags": ["admin", "dev", "owner"],
            "addresses": [
                {"city": "Seoul", "zip": "12345"},
                {"city": "Busan", "zip": "67890"},
            ],
            "matrix": [[1, 2], [3, 4]],
            "profile": {
                "social": {
                    "github": "hanyeol",
                },
            },
        },
        "items-list": [10, 20, 30],
        "with_underscore": "u",
        "empty_list": [],
        "empty_dict": {},
        "none_value": None,
        "false_value": False,
        "zero": 0,
    }


class TestDictAccess:

    def test_top_level_key(self, resolver, data):
        assert resolver.resolve(data, "user") == data["user"]

    def test_nested_key(self, resolver, data):
        assert resolver.resolve(data, "user.name") == "Hanyeol"

    def test_deeply_nested_key(self, resolver, data):
        assert resolver.resolve(data, "user.profile.social.github") == "hanyeol"

    def test_hyphen_in_key(self, resolver, data):
        assert resolver.resolve(data, "items-list") == [10, 20, 30]

    def test_underscore_in_key(self, resolver, data):
        assert resolver.resolve(data, "with_underscore") == "u"

    def test_integer_value(self, resolver, data):
        assert resolver.resolve(data, "user.age") == 30

    def test_falsy_values_returned_as_is(self, resolver, data):
        assert resolver.resolve(data, "false_value") is False
        assert resolver.resolve(data, "zero") == 0
        assert resolver.resolve(data, "none_value") is None
        assert resolver.resolve(data, "empty_list") == []
        assert resolver.resolve(data, "empty_dict") == {}


class TestListAccess:

    def test_positive_index(self, resolver, data):
        assert resolver.resolve(data, "user.tags[0]") == "admin"
        assert resolver.resolve(data, "user.tags[1]") == "dev"

    def test_negative_index(self, resolver, data):
        assert resolver.resolve(data, "user.tags[-1]") == "owner"
        assert resolver.resolve(data, "user.tags[-3]") == "admin"

    def test_dict_inside_list(self, resolver, data):
        assert resolver.resolve(data, "user.addresses[0].city") == "Seoul"
        assert resolver.resolve(data, "user.addresses[1].zip") == "67890"

    def test_index_on_top_level_list(self, resolver, data):
        assert resolver.resolve(data, "items-list[2]") == 30


class TestWildcard:

    def test_wildcard_collects_field(self, resolver, data):
        assert resolver.resolve(data, "user.addresses[*].city") == ["Seoul", "Busan"]

    def test_wildcard_collects_other_field(self, resolver, data):
        assert resolver.resolve(data, "user.addresses[*].zip") == ["12345", "67890"]

    def test_wildcard_at_end(self, resolver, data):
        assert resolver.resolve(data, "user.tags[*]") == ["admin", "dev", "owner"]

    def test_wildcard_on_empty_list(self, resolver, data):
        assert resolver.resolve(data, "empty_list[*]") == []

    def test_nested_wildcards(self, resolver, data):
        assert resolver.resolve(data, "user.matrix[*][*]") == [[1, 2], [3, 4]]

    def test_wildcard_with_missing_field_uses_default(self, resolver, data):
        assert resolver.resolve(data, "user.addresses[*].missing", default="X") == ["X", "X"]


class TestDefault:

    def test_missing_top_level_key(self, resolver, data):
        assert resolver.resolve(data, "missing", default="D") == "D"

    def test_missing_nested_key(self, resolver, data):
        assert resolver.resolve(data, "user.missing", default="D") == "D"

    def test_missing_deep_key(self, resolver, data):
        assert resolver.resolve(data, "user.missing.deep", default="D") == "D"

    def test_index_out_of_range(self, resolver, data):
        assert resolver.resolve(data, "user.tags[99]", default="D") == "D"

    def test_negative_index_out_of_range(self, resolver, data):
        assert resolver.resolve(data, "user.tags[-99]", default="D") == "D"

    def test_default_is_none_by_default(self, resolver, data):
        assert resolver.resolve(data, "missing") is None

    def test_default_can_be_any_type(self, resolver, data):
        assert resolver.resolve(data, "missing", default=42) == 42
        assert resolver.resolve(data, "missing", default=[]) == []
        assert resolver.resolve(data, "missing", default={"k": "v"}) == {"k": "v"}


class TestTypeMismatch:

    def test_index_on_dict_returns_default(self, resolver, data):
        assert resolver.resolve(data, "user[0]", default="D") == "D"

    def test_key_on_list_returns_default(self, resolver, data):
        assert resolver.resolve(data, "user.tags.foo", default="D") == "D"

    def test_descend_into_scalar_returns_default(self, resolver, data):
        assert resolver.resolve(data, "user.name.foo", default="D") == "D"

    def test_wildcard_on_dict_returns_default(self, resolver, data):
        assert resolver.resolve(data, "user[*]", default="D") == "D"

    def test_wildcard_on_scalar_returns_default(self, resolver, data):
        assert resolver.resolve(data, "user.name[*]", default="D") == "D"


class TestEmptyPath:

    def test_empty_string_returns_object(self, resolver, data):
        assert resolver.resolve(data, "") == data

    def test_empty_path_with_scalar_object(self, resolver):
        assert resolver.resolve("hello", "") == "hello"

    def test_empty_path_with_none_object(self, resolver):
        assert resolver.resolve(None, "") is None


class TestSeparators:

    def test_dot_separator(self, resolver, data):
        assert resolver.resolve(data, "user.name") == "Hanyeol"

    def test_brackets_need_no_separator(self, resolver, data):
        assert resolver.resolve(data, "user.tags[0]") == "admin"

    def test_unknown_chars_are_ignored(self, resolver, data):
        # Current parser is lenient and ignores any non-token characters.
        assert resolver.resolve(data, "user>name") == "Hanyeol"
        assert resolver.resolve(data, "user@@name") == "Hanyeol"
        assert resolver.resolve(data, "user/name") == "Hanyeol"


class TestRootTypes:

    def test_resolve_from_list_root(self, resolver):
        assert resolver.resolve([10, 20, 30], "[1]") == 20

    def test_resolve_from_list_root_wildcard(self, resolver):
        assert resolver.resolve([{"k": 1}, {"k": 2}], "[*].k") == [1, 2]

    def test_resolve_from_scalar_root_returns_default(self, resolver):
        assert resolver.resolve("hello", "foo", default="D") == "D"

    def test_resolve_from_none_root_returns_default(self, resolver):
        assert resolver.resolve(None, "foo", default="D") == "D"
