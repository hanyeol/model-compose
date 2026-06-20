"""Unit tests for ``mindor.core.utils.url``."""

import base64
from urllib.parse import unquote_to_bytes

import pytest

from mindor.core.utils.url import encode_url, parse_data_uri


class TestParseDataUri:
    def test_plain_text_data_uri(self):
        mime, meta, data = parse_data_uri("data:text/plain,hello")
        assert mime == "text/plain"
        assert meta == "text/plain"
        assert data == "hello"

    def test_base64_data_uri(self):
        payload = base64.b64encode(b"hello").decode()
        mime, meta, data = parse_data_uri(f"data:application/octet-stream;base64,{payload}")
        assert mime == "application/octet-stream"
        assert meta == "application/octet-stream;base64"
        assert data == payload
        assert base64.b64decode(data) == b"hello"

    def test_default_mediatype_empty_meta(self):
        mime, meta, data = parse_data_uri("data:,hello")
        assert mime == ""
        assert meta == ""
        assert data == "hello"

    def test_percent_encoded_payload(self):
        mime, _meta, data = parse_data_uri("data:text/plain,hello%20world")
        assert mime == "text/plain"
        assert unquote_to_bytes(data) == b"hello world"

    def test_multiple_parameters(self):
        mime, meta, _data = parse_data_uri("data:text/plain;charset=utf-8;base64,abc")
        assert mime == "text/plain"
        assert "charset=utf-8" in meta
        assert "base64" in meta

    def test_invalid_uri_raises(self):
        with pytest.raises(ValueError, match="Invalid data URI"):
            parse_data_uri("not-a-data-uri")

    def test_missing_comma_raises(self):
        with pytest.raises(ValueError, match="Invalid data URI"):
            parse_data_uri("data:text/plain")


class TestEncodeUrl:
    def test_full_url_encodes_path_only(self):
        result = encode_url("http://example.com/path with spaces")
        assert result == "http://example.com/path%20with%20spaces"

    def test_full_url_preserves_query_string_untouched(self):
        # The implementation only re-encodes the path component.
        result = encode_url("http://example.com/a b?q=foo bar")
        assert result.startswith("http://example.com/a%20b?")

    def test_path_segments_preserved(self):
        assert encode_url("http://x.com/a/b/c") == "http://x.com/a/b/c"

    def test_bare_path_quoted(self):
        # No scheme/netloc -> quote everything except "/"
        assert encode_url("/some path/file name.txt") == "/some%20path/file%20name.txt"

    def test_already_encoded_path_double_encodes_percent(self):
        # `quote` re-encodes literal '%' as '%25' — caller is expected to give an unencoded path.
        assert encode_url("/a%20b") == "/a%2520b"
