from __future__ import annotations

from typing import Union, Optional, Dict, Tuple, Any
from .http_request import build_request_body, parse_options_header
from mindor.core.foundation.streaming.http import HttpStreamResource, HttpEventStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.url import encode_url
from requests.structures import CaseInsensitiveDict
from urllib.parse import urlparse, unquote
from urllib.request import url2pathname
import aiohttp, asyncio, json, platform

_DEFAULT_USER_AGENTS = {
    "Darwin":  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
               "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Linux":   "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
}

class HttpClient:
    _shared_instance: Optional[HttpClient] = None

    def __init__(
        self,
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        shared: bool = False
    ):
        self.base_url: Optional[str] = base_url
        self.headers: Optional[Dict[str, str]] = headers
        self.timeout: Optional[float] = timeout
        self.shared: bool = shared

        self._sessions: Dict[int, aiohttp.ClientSession] = {}

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self.shared:
            await self.close()

    async def request(
        self,
        url_or_path: str,
        method: Optional[str] = "GET",
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        raise_on_error: bool = True,
        streaming: bool = False
    ) -> Union[Any, Tuple[Any, int]]:
        response: aiohttp.ClientResponse = None
        try:
            merged_headers = { **(self.headers or {}), **(headers or {}) }

            if not CaseInsensitiveDict(merged_headers).get("User-Agent"):
                merged_headers["User-Agent"] = self._default_user_agent()

            response = await self._request_with_session(
                session=await self._get_session(),
                url_or_path=url_or_path,
                method=method,
                params={ k: v for k, v in params.items() if v is not None } if params else None,
                body=body,
                headers={ k: v for k, v in merged_headers.items() if v is not None },
                timeout=timeout or self.timeout
            )

            if raise_on_error and response.status >= 400:
                error = await self._parse_response_error(response)
                raise ValueError(f"Request failed with status {response.status}\nURL: {url_or_path}\nResponse: {error}")

            content, _ = await self._parse_response_content(response, streaming)

            if not isinstance(content, StreamResource):
                response.close()

            return content if raise_on_error else (content, response.status)
        except Exception as e:
            if response:
                response.close()
            raise e

    async def close(self) -> None:
        sessions, self._sessions = self._sessions, {}
        for session in sessions.values():
            try:
                await session.close()
            except Exception:
                pass

    @classmethod
    def get_shared_instance(cls) -> HttpClient:
        if not cls._shared_instance:
            cls._shared_instance = HttpClient(shared=True)
        return cls._shared_instance

    async def _get_session(self) -> aiohttp.ClientSession:
        key = id(asyncio.get_running_loop())
        session = self._sessions.get(key)

        if session and not session.closed:
            return session

        session = self._create_session(self.base_url)
        self._sessions[key] = session

        return session

    def _create_session(self, base_url: Optional[str]) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(base_url.rstrip("/") + "/" if base_url else None)

    async def _request_with_session(
        self,
        session: aiohttp.ClientSession,
        url_or_path: str,
        method: str,
        params: Optional[Dict[str, Any]],
        body: Optional[Any],
        headers: Optional[Dict[str, str]],
        timeout: Optional[float] = None
    ) -> aiohttp.ClientResponse:
        data, content_type = self._build_request_body(body, headers)
 
        if content_type == "multipart/form-data":
            headers = CaseInsensitiveDict(headers)
            headers.pop("Content-Type", None)

        return await session.request(
            method=method,
            url=encode_url(url_or_path.lstrip("/")),
            params=params,
            data=data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout) if timeout is not None else None
        )

    def _build_request_body(self, body: Optional[Any], headers: Optional[Dict[str, str]]) -> Tuple[Any, str]:
        content_type, _ = parse_options_header(headers, "Content-Type")

        if content_type and body is not None:
            return (build_request_body(body, content_type), content_type)

        return (body, content_type)

    async def _parse_response_content(self, response: aiohttp.ClientResponse, streaming: bool = False) -> Tuple[Any, str]:
        content_type, _ = parse_options_header(response.headers, "Content-Type")

        if content_type == "text/event-stream":
            return (HttpEventStreamResource(response), content_type)

        if streaming:
            return (HttpStreamResource(response, content_type), content_type)

        if content_type == "application/json":
            return (await response.json(), content_type)

        if content_type.startswith("text/"):
            return (await response.text(), content_type)

        _, disposition = parse_options_header(response.headers, "Content-Disposition")
        filename = disposition.get("filename")

        return (HttpStreamResource(response, content_type, filename), content_type)

    async def _parse_response_error(self, response: aiohttp.ClientResponse) -> str:
        body = await response.text()
        try:
            return json.dumps(json.loads(body), indent=2)
        except (ValueError, json.JSONDecodeError):
            return body

    @staticmethod
    def _default_user_agent() -> str:
        return _DEFAULT_USER_AGENTS.get(platform.system(), _DEFAULT_USER_AGENTS["Linux"])

async def create_stream_with_url(url: str) -> StreamResource:
    parsed = urlparse(url)

    if parsed.scheme == "file":
        from mindor.core.foundation.streaming.file import FileStreamResource
        path = url2pathname(parsed.path)
        return FileStreamResource(path)

    return await HttpClient.get_shared_instance().request(url)
