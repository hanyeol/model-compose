from __future__ import annotations

from typing import Callable, Optional, Tuple
from contextlib import AbstractAsyncContextManager
from urllib.parse import quote, urlparse, urlsplit, urlunsplit, parse_qsl, urlencode
import re

_DATA_URI_PATTERN = re.compile(r"^data:([^,;]*(?:;[^,;]+)*),(.*)$", re.DOTALL)
_HTTP_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)

class UrlResource(AbstractAsyncContextManager):
    """A resource identified by a URL, optionally backed by a temporary
    file that must be cleaned up after use.

    This is a handle, not a stream reader — it does not fetch or decode
    the URL. Consumers pass `url` to whatever component knows how to load
    it (browser, http client, ffmpeg, ...) and rely on `close()` (or the
    async context manager) to release any transient backing resource
    (e.g. a temp file created from inline content).
    """
    def __init__(self, url: str, cleanup: Optional[Callable[[], None]] = None):
        self.url: str = url

        self._cleanup: Optional[Callable[[], None]] = cleanup

    async def __aenter__(self) -> UrlResource:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        if self._cleanup is not None:
            try:
                self._cleanup()
            finally:
                self._cleanup = None

def parse_data_uri(uri: str) -> Tuple[str, str, str]:
    match = _DATA_URI_PATTERN.match(uri)

    if not match:
        raise ValueError(f"Invalid data URI: {uri[:32]}...")

    meta, data = match.group(1), match.group(2)
    mime = meta.split(";", 1)[0]

    return mime, meta, data

def encode_url(url_or_path: str) -> str:
    parsed_url = urlparse(url_or_path)

    if parsed_url.scheme and (parsed_url.netloc or parsed_url.path):
        return url_or_path.replace(parsed_url.path, quote(parsed_url.path, safe="/"))

    return quote(url_or_path, safe="/")

def normalize_url(url: str) -> str:
    """Canonicalize a URL so equivalent spellings map to the same string.

    - scheme/host lowercased
    - trailing slashes on the path removed
    - query parameters sorted
    - fragment discarded
    - port and userinfo (user:pass@) preserved as-is
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port

    netloc = f"{host}:{port}" if port else host
    if parts.username or parts.password:
        userinfo = parts.username or ""
        if parts.password:
            userinfo = f"{userinfo}:{parts.password}"
        netloc = f"{userinfo}@{netloc}"

    path = parts.path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))

    return urlunsplit((scheme, netloc, path, query, ""))

def is_http_url(value: str) -> bool:
    return bool(_HTTP_URL_PATTERN.match(value))
