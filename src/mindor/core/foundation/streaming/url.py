from typing import Any, Optional, Dict
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import unquote_to_bytes
from .resources import StreamResource, save_stream_to_file
from .base64 import Base64StreamResource
from .bytes import BytesStreamResource
from mindor.core.utils.files import create_temporary_file
from mindor.core.utils.transport.http_client import create_stream_with_url
from mindor.core.utils.url import parse_data_uri
import os

class UrlStreamResource(StreamResource):
    def __init__(
        self,
        url: str,
        content_type: Optional[str] = None,
        filename: Optional[str] = None,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
        timeout: Optional[float] = None,
    ):
        super().__init__(content_type, filename)

        self.url: str = url
        self.method: str = method
        self.headers: Optional[Dict[str, str]] = headers
        self.body: Optional[Any] = body
        self.timeout: Optional[float] = timeout

        self._stream: Optional[StreamResource] = None
        self._has_own_content_type = bool(content_type)

    async def close(self) -> None:
        if self._stream:
            await self._stream.close()
            self._stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self._stream:
            self._stream = await create_stream_with_url(
                self.url,
                method=self.method,
                headers=self.headers,
                body=self.body,
                timeout=self.timeout,
            )

            if not self._has_own_content_type and self._stream.content_type:
                self.content_type = self._stream.content_type

            if not self.filename and self._stream.filename:
                self.filename = self._stream.filename

        async for chunk in self._stream:
            yield chunk

class DataUriStreamResource(StreamResource):
    def __init__(self, uri: str, filename: Optional[str] = None):
        super().__init__(None, filename)

        self.uri: str = uri
        self._stream: Optional[StreamResource] = None

    async def close(self) -> None:
        if self._stream:
            await self._stream.close()
            self._stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self._stream:
            mime, meta, data = parse_data_uri(self.uri)

            if "base64" in meta.split(";"):
                self._stream = Base64StreamResource(data, content_type=mime or None)
            else:
                self._stream = BytesStreamResource(unquote_to_bytes(data), content_type=mime or None)

            if self._stream.content_type:
                self.content_type = self._stream.content_type

            self.size = self._stream.size

        async for chunk in self._stream:
            yield chunk

async def download_to_file(
    url: str,
    path: Path,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    timeout: Optional[float] = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = create_temporary_file(dir=str(path.parent))

    try:
        stream = UrlStreamResource(
            url,
            method=method,
            headers=headers,
            body=body,
            timeout=timeout
        )
        await save_stream_to_file(stream, temp_path)

        # If the server advertised a Content-Length, ensure the download wasn't
        # truncated mid-stream. Chunked/compressed responses leave size=None.
        file_size = os.path.getsize(temp_path)
        if stream.size is not None and stream.size != file_size:
            raise IOError(f"Incomplete download from {url}: expected {stream.size} bytes, got {file_size}")

        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
