from typing import Tuple
from urllib.parse import quote, urlparse, urlsplit, urlunsplit, parse_qsl, urlencode
import re

_DATA_URI_PATTERN = re.compile(r"^data:([^,;]*(?:;[^,;]+)*),(.*)$", re.DOTALL)

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
