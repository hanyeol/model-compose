from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from .http_request import serialize_request_body, parse_options_header
from .streaming import StreamResource
import aiohttp

class HttpStreamResource(StreamResource):
    def __init__(self, session: aiohttp.ClientSession, stream: aiohttp.StreamReader, content_type: Optional[str] = None, filename: Optional[str] = None):
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
    async def request(self, url: str, method: Optional[str] = "GET", params: Optional[Dict[str, Any]] = None, body: Optional[Any] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        session = aiohttp.ClientSession()
        try:
            response = await session.request(
                method,
                url,
                params=params,
                data=await self._serialize_request_body(body, headers),
                headers=headers
            )

            content = await self._parse_response_content(session, response)

            if response.status >= 400:
                raise ValueError(f"Request failed with status {response.status}: {content}")

            if not isinstance(content, HttpStreamResource):
                await session.close()

            return content
        except:
            await session.close()
            raise

    async def _serialize_request_body(self, body: Optional[Any], headers: Optional[Dict[str, str]]) -> Any:
        content_type, _ = parse_options_header(headers, "Content-Type")

        if content_type and body:
            return await serialize_request_body(body, content_type)

        return body

    async def _parse_response_content(self, session: aiohttp.ClientSession, response: aiohttp.ClientResponse) -> Any:
        content_type, _ = parse_options_header(response.headers, "Content-Type")

        if content_type == "application/json":
            return await response.json()

        if content_type.startswith("text/"):
            return await response.text()

        _, disposition = parse_options_header(response.headers, "Content-Disposition")
        filename = disposition.get("filename")

        return HttpStreamResource(session, response.content, content_type, filename)
