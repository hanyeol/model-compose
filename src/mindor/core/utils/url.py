from typing import Optional, Tuple
from collections.abc import AsyncIterator
from urllib.parse import quote, urlparse, urlunparse
from .streaming import StreamResource
import re

_DATA_URI_PATTERN = re.compile(r"^data:([^,;]*(?:;[^,;]+)*),(.*)$", re.DOTALL)

class UrlStreamResource(StreamResource):
    def __init__(self, url: str, content_type: Optional[str] = None, filename: Optional[str] = None):
        super().__init__(content_type, filename)

        self.url: str = url
        self._stream: Optional[StreamResource] = None
        self._has_own_content_type = bool(content_type)

    async def close(self) -> None:
        if self._stream:
            await self._stream.close()
            self._stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        from .http_client import create_stream_with_url

        if not self._stream:
            self._stream = await create_stream_with_url(self.url)
            if not self._has_own_content_type and self._stream.content_type:
                self.content_type = self._stream.content_type
            if not self.filename and self._stream.filename:
                self.filename = self._stream.filename

        async for chunk in self._stream:
            yield chunk

def parse_data_uri(uri: str) -> Tuple[str, str, str]:
    match = _DATA_URI_PATTERN.match(uri)
    if not match:
        raise ValueError(f"Invalid data URI: {uri[:32]}...")

    meta, data = match.group(1), match.group(2)
    mime = meta.split(";", 1)[0]

    return mime, meta, data

def encode_url(url_or_path: str) -> str:
    parsed_url = urlparse(url_or_path)

    if parsed_url.scheme and parsed_url.netloc:
        return url_or_path.replace(parsed_url.path, quote(parsed_url.path, safe="/"))
    
    return quote(url_or_path, safe="/")
