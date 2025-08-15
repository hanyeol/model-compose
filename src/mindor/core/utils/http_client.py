from typing import Union, Optional, Dict, Tuple, AsyncIterator, Any
from .http_request import build_request_body, parse_options_header
from .streaming import StreamResource
from requests.structures import CaseInsensitiveDict
import aiohttp

class HttpStreamResource(StreamResource):
    def __init__(
        self, 
        response: aiohttp.ClientResponse,
        content_type: Optional[str] = None, 
        filename: Optional[str] = None
    ):
        super().__init__(content_type, filename)

        self.response: aiohttp.ClientResponse = response
        self.stream: aiohttp.StreamReader = response.content

    async def close(self) -> None:
        self.response.close()
        self.response = None
        self.stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        _, buffer_size = self.stream.get_read_buffer_limits()
        chunk_size = buffer_size or 65536

        while not self.stream.at_eof():
            chunk = await self.stream.read(chunk_size)
            if not chunk:
                break
            yield chunk

class HttpEventStreamResource(StreamResource):
    def __init__(
        self,
        response: aiohttp.ClientResponse
    ):
        super().__init__("text/event-stream", None)

        self.response: aiohttp.ClientResponse = response
        self.stream: aiohttp.StreamReader = response.content
        self._buffer: bytearray = bytearray()

    async def close(self) -> None:
        self.response.close()
        self.response = None
        self.stream = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.stream:
            self._buffer += chunk.replace(b"\r\n", b"\n")

            while True:
                pos = self._buffer.find(b"\n\n")
                if pos < 0:
                    break

                block, self._buffer = self._buffer[:pos], self._buffer[pos + 2:]
                parts = []

                for line in block.split(b"\n"):
                    if line.startswith(b"data:"):
                        parts.append(line[6:] if line[5:6] == b" " else line[5:])
                        continue
                    if line == b"data":
                        parts.append(b"")
                        continue
                    if line.startswith(b":"): # comment
                        continue

                if parts:
                    yield b"\n".join(parts)

class HttpClient:
    shared_instance: Optional["HttpClient"] = None

    def __init__(self, base_url: Optional[str] = None, headers: Optional[Dict[str, str]] = None):
        self.base_url: Optional[str] = base_url
        self.headers: Optional[Dict[str, str]] = headers
        self.session: aiohttp.ClientSession = self._create_session(self.base_url)

    async def __aenter__(self):
        if not self.session:
            self.session = self._create_session(self.base_url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def request(
        self,
        url_or_path: str,
        method: Optional[str] = "GET",
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        raise_on_error: bool = True
    ) -> Union[Any, Tuple[Any, int]]:
        response: aiohttp.ClientResponse = None
        try:
            response = await self._request_with_session(self.session, url_or_path, method, params, body, { **(self.headers or {}), **(headers or {})})
            content, _ = await self._parse_response_content(response)

            if raise_on_error and response.status >= 400:
                raise ValueError(f"Request failed with status {response.status}: {content}")

            if not isinstance(content, StreamResource):
                response.close()

            return content if raise_on_error else (content, response.status)
        except Exception as e:
            if response:
                response.close()
            raise e

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    @classmethod
    def get_shared_instance(cls) -> "HttpClient":
        if not cls.shared_instance:
            cls.shared_instance = HttpClient()
        return cls.shared_instance
    
    @classmethod
    async def request_once(cls, *args, **kwargs):
        instance = cls()
        try:
            return await instance.request(*args, **kwargs)
        finally:
            await instance.close()

    def _create_session(self, base_url: Optional[str]) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(base_url.rstrip("/") + "/" if base_url else None)

    async def _request_with_session(
        self,
        session: aiohttp.ClientSession,
        url_or_path: str,
        method: str,
        params: Optional[Dict[str, Any]],
        body: Optional[Any],
        headers: Optional[Dict[str, str]]
    ) -> aiohttp.ClientResponse:
        data, content_type = self._build_request_body(body, headers)
 
        if content_type == "multipart/form-data":
            headers = CaseInsensitiveDict(headers)
            headers.pop("Content-Type", None)

        return await session.request(method, url_or_path.lstrip("/"), params=params, data=data, headers=headers)

    def _build_request_body(self, body: Optional[Any], headers: Optional[Dict[str, str]]) -> Tuple[Any, str]:
        content_type, _ = parse_options_header(headers, "Content-Type")

        if content_type and body is not None:
            return (build_request_body(body, content_type), content_type)

        return (body, content_type)

    async def _parse_response_content(self, response: aiohttp.ClientResponse) -> Tuple[Any, str]:
        content_type, _ = parse_options_header(response.headers, "Content-Type")

        if content_type == "application/json":
            return (await response.json(), content_type)

        if content_type == "text/event-stream":
            return (HttpEventStreamResource(response), content_type)

        if content_type.startswith("text/"):
            return (await response.text(), content_type)

        _, disposition = parse_options_header(response.headers, "Content-Disposition")
        filename = disposition.get("filename")

        return (HttpStreamResource(response, content_type, filename), content_type)

async def create_stream_with_url(url: str) -> HttpStreamResource:
    return await HttpClient.get_shared_instance().request(url)
