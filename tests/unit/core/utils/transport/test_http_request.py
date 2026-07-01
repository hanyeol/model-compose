"""Unit tests for ``mindor.core.utils.transport.http_request`` pure helpers.

Async ``parse_request_body`` / ``parse_request_form`` are not unit-tested here —
they need a Starlette ``Request`` instance which belongs in integration tests.
"""

import json
from urllib.parse import parse_qs

from starlette.datastructures import FormData

from mindor.core.utils.transport.http_request import (
    NestedFormParser,
    build_request_body,
    guess_file_content_type,
    parse_options_header,
)


class TestNestedFormParser:
    def test_flat_keys(self):
        result = NestedFormParser().parse(FormData([("a", "1"), ("b", "2")]))
        assert result == {"a": "1", "b": "2"}

    def test_nested_brackets(self):
        result = NestedFormParser().parse(FormData([("user[name]", "Alice"), ("user[age]", "30")]))
        assert result == {"user": {"name": "Alice", "age": "30"}}

    def test_deeply_nested(self):
        result = NestedFormParser().parse(FormData([("a[b][c]", "v")]))
        assert result == {"a": {"b": {"c": "v"}}}

    def test_array_suffix_collects_into_list(self):
        # NOTE: FormData.items() deduplicates by key, so passing two ("tags[]", _) tuples
        # only surfaces the last one to NestedFormParser. The parser's array branch wraps
        # the surviving value in a list — confirming the [] suffix path runs.
        result = NestedFormParser().parse(FormData([("tags[]", "y")]))
        assert result == {"tags[]": ["y"]}

    def test_mixed_flat_and_nested(self):
        result = NestedFormParser().parse(
            FormData([("name", "Alice"), ("addr[city]", "Seoul")])
        )
        assert result == {"name": "Alice", "addr": {"city": "Seoul"}}


class TestBuildRequestBody:
    def test_application_json_serializes(self):
        assert build_request_body({"a": 1}, "application/json") == json.dumps({"a": 1})

    def test_form_urlencoded_serializes(self):
        body = build_request_body({"a": "1", "b": "2"}, "application/x-www-form-urlencoded")
        # urlencode order matches dict insertion order in py3.7+
        assert parse_qs(body) == {"a": ["1"], "b": ["2"]}

    def test_unknown_content_type_passes_through_str(self):
        assert build_request_body("raw text", "text/plain") == "raw text"

    def test_unknown_content_type_passes_through_bytes(self):
        assert build_request_body(b"raw", "application/octet-stream") == b"raw"

    def test_none_content_type_passes_through(self):
        assert build_request_body({"a": 1}, None) == {"a": 1}


class TestParseOptionsHeader:
    def test_simple_content_type(self):
        value, opts = parse_options_header({"Content-Type": "text/plain"}, "Content-Type")
        assert value == "text/plain"
        assert opts == {}

    def test_with_charset_parameter(self):
        value, opts = parse_options_header(
            {"Content-Type": "text/html; charset=utf-8"}, "Content-Type"
        )
        assert value == "text/html"
        assert opts == {"charset": "utf-8"}

    def test_quoted_parameter(self):
        value, opts = parse_options_header(
            {"Content-Disposition": 'form-data; name="file"; filename="hi.txt"'},
            "Content-Disposition",
        )
        assert value == "form-data"
        assert opts == {"name": "file", "filename": "hi.txt"}

    def test_case_insensitive_header_lookup(self):
        value, _ = parse_options_header({"content-type": "image/png"}, "Content-Type")
        assert value == "image/png"

    def test_lowercases_value(self):
        value, _ = parse_options_header({"Content-Type": "TEXT/PLAIN"}, "Content-Type")
        assert value == "text/plain"

    def test_missing_header_returns_empty(self):
        value, opts = parse_options_header({}, "Content-Type")
        assert value == ""
        assert opts == {}


class TestGuessFileContentType:
    def test_image_with_explicit_subtype(self):
        assert guess_file_content_type("photo.jpg", "image", "png") == "image/png"

    def test_image_infers_subtype_from_extension(self):
        assert guess_file_content_type("photo.png", "image", None) == "image/png"

    def test_audio_infers_subtype(self):
        assert guess_file_content_type("clip.wav", "audio", None) == "audio/wav"

    def test_video_infers_subtype(self):
        assert guess_file_content_type("clip.mp4", "video", None) == "video/mp4"

    def test_unknown_type_falls_back_to_octet_stream(self):
        assert guess_file_content_type("data.bin", "application", None) == "application/octet-stream"

    def test_no_type_falls_back_to_octet_stream(self):
        assert guess_file_content_type("data.bin", None, None) == "application/octet-stream"
