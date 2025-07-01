from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from .http_request import build_request_body, parse_options_header
from .streaming import StreamResource
from requests.structures import CaseInsensitiveDict
import aiohttp

class HttpStreamResource(StreamResource):
    def __init__(
        self, 
        session: aiohttp.ClientSession, 
        stream: aiohttp.StreamReader, 
        content_type: Optional[str] = None, 
        filename: Optional[str] = None
    ):
        super().__init__(content_type, filename)

        self.session: aiohttp.ClientSession = session
        self.stream: aiohttp.StreamReader = stream

    async def close(self):
        await self.session.close()
        self.session = None
        self.stream  = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        _, buffer_size = self.stream.get_read_buffer_limits()
        chunk_size = buffer_size or 65536

        while not self.stream.at_eof():
            chunk = await self.stream.read(chunk_size)
            if not chunk:
                break
            yield chunk

class HttpClient:
    async def request(
        self,
        url: str,
        method: Optional[str] = "GET",
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Any:
        session = aiohttp.ClientSession()
        try:
            response = await self._request_with_session(session, url, method, params, body, headers)
            content, _ = await self._parse_response_content(session, response)

            if response.status >= 400:
                raise ValueError(f"Request failed with status {response.status}: {content}")

            if not isinstance(content, HttpStreamResource):
                await session.close()

            return content
        except:
            await session.close()
            raise

    async def _request_with_session(
        self,
        session: aiohttp.ClientSession,
        url: str,
        method: str,
        params: Optional[Dict[str, Any]],
        body: Optional[Any],
        headers: Optional[Dict[str, str]]
    ) -> aiohttp.ClientResponse:
        data, content_type = self._build_request_body(body, headers)
 
        if content_type == "multipart/form-data":
            headers = CaseInsensitiveDict(headers)
            headers.pop("Content-Type", None)

        return await session.request(method, url, params=params, data=data, headers=headers)

    def _build_request_body(self, body: Optional[Any], headers: Optional[Dict[str, str]]) -> Tuple[Any, str]:
        content_type, _ = parse_options_header(headers, "Content-Type")

        if content_type and body is not None:
            return (build_request_body(body, content_type), content_type)

        return (body, content_type)

    async def _parse_response_content(self, session: aiohttp.ClientSession, response: aiohttp.ClientResponse) -> Tuple[Any, str]:
        content_type, _ = parse_options_header(response.headers, "Content-Type")

        if content_type == "application/json":
            return (await response.json(), content_type)

        if content_type.startswith("text/"):
            return (await response.text(), content_type)

        _, disposition = parse_options_header(response.headers, "Content-Disposition")
        filename = disposition.get("filename")

        return (HttpStreamResource(session, response.content, content_type, filename), content_type)
