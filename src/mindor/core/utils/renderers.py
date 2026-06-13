from typing import Callable, Dict, List, Optional, Union, Awaitable, Any
from collections.abc import AsyncIterator
from pydantic import BaseModel
from .streaming import StreamResource, UploadFileStreamResource, Base64StreamResource, EventStreamResource, StreamFormat
from .streaming import encode_stream_to_base64, save_stream_to_temporary_file, BytesStreamResource
from .http_client import create_stream_with_url
from .url import UrlStreamResource, parse_data_uri
from .image import load_image_from_stream, ImageStreamResource
from .audio import PcmStreamResource, WavStreamResource, AudioStreamResource, create_audio_source
from .video import VideoStreamResource, create_video_source
from .media import MediaSource
from .streaming import FileStreamResource
from .resolvers import FieldResolver
from .size import parse_size
from starlette.datastructures import UploadFile
from PIL import Image as PILImage
from urllib.parse import unquote_to_bytes
import re, json, base64, aiofiles

_STREAM_FORMAT_MAP = {
    "sse-text": StreamFormat.TEXT,
    "sse-json": StreamFormat.JSON,
}

class VariableRenderer:
    def __init__(self, source_resolver: Callable[[str, Optional[int], Optional[str]], Awaitable[Any]]):
        self.source_resolver: Callable[[str, Optional[int], Optional[str]], Awaitable[Any]] = source_resolver
        self.field_resolver: FieldResolver = FieldResolver()
        self.patterns: Dict[str, re.Pattern] = {
            "variable": re.compile(
                r"""\$\{                                                                                                # ${
                    (?:\s*([a-zA-Z_][^.\[\s]*(?:\[\])?))(?:\[(-?[0-9]+)\])?                                             # key: input, result[], result[0], result[-1], etc.
                    (?:\.([^\s|}]+))?                                                                                   # path: key, key.path[0], etc.
                    (?:\s*as\s*([^\s/;\[}]+)(\[\])?(?:/([^\s;\[}]+)(?:\[((?:\$\{[^}]*\}|[^\]])*)\])?)?(?:;([^\s}]+))?)? # type[]/subtype[attrs];format (attrs may contain nested ${...})
                    (?:\s*\|\s*((?:\$\{[^}]+\}|\\[$@{}]|(?!\s*(?:@\(|\$\{)).)+))?                                       # default value after `|`
                    (?:\s*(@\(\s*[\w]+\s+(?:\\[$@{}]|(?!\s*\$\{).)+\)))?                                                # annotations
                \s*\}""",                                                                                               # }
                re.VERBOSE,
            ),
            "spread": re.compile(r"^\.\.\.\$\{[^}]+\}$"),
        }

    async def render(self, value: Any, scope: Optional[str] = None, skip_decode: bool = False) -> Any:
        return await self._render_element(value, scope, skip_decode)

    def contains_reference(self, key: str, value: Any) -> bool:
        return self._contains_reference(key, value)

    async def _render_element(self, element: Any, scope: Optional[str], skip_decode: bool) -> Any:
        if isinstance(element, str):
            return await self._render_text(element, scope, skip_decode)

        if isinstance(element, BaseModel):
            return await self._render_element(element.model_dump(by_alias=True), scope, skip_decode)

        if isinstance(element, dict):
            return await self._render_dict(element, scope, skip_decode)

        if isinstance(element, (list, tuple)):
            return await self._render_list(element, scope, skip_decode)

        return element

    async def _render_dict(self, element: dict, scope: Optional[str], skip_decode: bool) -> dict:
        values = {}
        for key, value in element.items():
            if key == "...":
                value = await self._render_element(value, scope, skip_decode)
                if isinstance(value, dict) or value is None:
                    values.update(value or {})
                else:
                    raise TypeError(f"Spread in dict must resolve to a dict, got {type(value).__name__}")
            else:
                values[key] = await self._render_element(value, scope, skip_decode)
        return values

    async def _render_list(self, element: list, scope: Optional[str], skip_decode: bool) -> list:
        values = []
        for item in element:
            if isinstance(item, str) and self._is_spread_expression(item):
                value = await self._render_text(item[3:], scope, skip_decode)
                if isinstance(value, (list, tuple)) or value is None:
                    values.extend(value or [])
                else:
                    raise TypeError(f"Spread in list must resolve to a list, got {type(value).__name__}: {item}")
            else:
                values.append(await self._render_element(item, scope, skip_decode))
        return values

    async def _render_text(self, text: str, scope: Optional[str], skip_decode: bool) -> Any:
        matches = list(self.patterns["variable"].finditer(text))

        for m in reversed(matches):
            key, index, path, type, is_list, subtype, attrs, format, default = m.group(1, 2, 3, 4, 5, 6, 7, 8, 9)
            index = int(index) if index else None
            is_list = bool(is_list)

            if attrs:
                attrs = await self._render_attrs(attrs, scope)

            try:
                value = self.field_resolver.resolve(await self.source_resolver(key, index, scope), path)
            except Exception:
                value = None

            if value is None and default is not None:
                value = await self._render_element(default, scope, skip_decode)

            if type and value is not None:
                value = await self._convert_value_to_type(value, type, is_list, subtype, attrs, format, skip_decode)

            start, end = m.span()

            if start == 0 and end == len(text):
                return value

            text = text[:start] + (str(value) if value is not None else "") + text[end:]

        return text

    async def _convert_value_to_type(
        self,
        value: Any,
        type: str,
        is_list: bool,
        subtype: Optional[str],
        attrs: Optional[Dict[str, Any]],
        format: Optional[str],
        skip_decode: bool = False,
    ) -> Any:
        if is_list:
            if type in [ "sse-text", "sse-json" ]:
                raise ValueError(f"`{type}[]` is not allowed: SSE is a single stream by nature")
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"`{type}[]` requires a list/tuple input, got {value.__class__.__name__}")
            return [ await self._convert_value_to_type(v, type, False, subtype, attrs, format, skip_decode) for v in value ]

        if skip_decode and format in [ "base64", "url", "data-uri" ]:
            if not isinstance(value, str):
                raise TypeError(f"`{format}` format requires a string value, got {value.__class__.__name__}")
            return value

        if value is None:
            return None

        if type in [ "string", "text", "integer", "number", "boolean", "list", "object", "json", "base64", "markdown" ]:
            if format in [ "path", "url", "data-uri", "base64" ] and isinstance(value, str):
                value = await self._load_bytes_from_format(value, format)

        if type in [ "json", "object", "list" ] and isinstance(value, (str, bytes)):
            value = json.loads(value)

        if type in [ "string", "text", "markdown" ]:
            if isinstance(value, bytes):
                return value.decode("utf-8")
            return value if isinstance(value, str) else str(value)

        if type == "number":
            return float(value)

        if type == "integer":
            return int(value)

        if type == "boolean":
            if isinstance(value, bytes):
                return value.lower() in [ b"true", b"1" ]
            return str(value).lower() in [ "true", "1" ]

        if type == "list":
            if not isinstance(value, list):
                raise ValueError(f"`list` requires a list input, got {value.__class__.__name__}")
            return value

        if type == "object":
            if not isinstance(value, dict):
                raise ValueError(f"`object` requires a dict input, got {value.__class__.__name__}")
            if subtype:
                paths = [ ( path, path.split(".")[-1] ) for path in subtype.split(",") ]
                return { key: self.field_resolver.resolve(value, path) for path, key in paths }
            return value

        if type == "base64":
            if isinstance(value, PILImage.Image):
                return await encode_stream_to_base64(ImageStreamResource(value))
            if isinstance(value, UploadFile):
                return await encode_stream_to_base64(UploadFileStreamResource(value))
            if isinstance(value, StreamResource):
                return await encode_stream_to_base64(value)
            if isinstance(value, str):
                return base64.b64encode(value.encode("utf-8")).decode("ascii")
            return base64.b64encode(value).decode("ascii")

        if type in [ "image", "audio", "video", "file" ]:
            if isinstance(value, AsyncIterator) and not isinstance(value, StreamResource):
                return value

            if format in [ "path", "url", "data-uri", "base64" ] and isinstance(value, str):
                value = await self._load_stream_from_format(value, format)

            if isinstance(value, UploadFile):
                value = UploadFileStreamResource(value)

            if type == "image":
                if not isinstance(value, (StreamResource, PILImage.Image)):
                    raise TypeError(f"`image` requires an image or raw image bytes, got {value.__class__.__name__}")
                if isinstance(value, StreamResource):
                    value = await load_image_from_stream(value)
                if subtype:
                    value = ImageStreamResource(value, subtype)
                return value

            if type == "audio":
                if not isinstance(value, (StreamResource, bytes)):
                    raise TypeError(f"`audio` requires raw audio bytes, got {value.__class__.__name__}")
                if subtype == "pcm":
                    return PcmStreamResource(value, attrs)
                if subtype == "wav":
                    return WavStreamResource(value)
                return AudioStreamResource(value, subtype, attrs)

            if type == "video":
                if not isinstance(value, (StreamResource, bytes)):
                    raise TypeError(f"`video` requires raw video input, got {value.__class__.__name__}")
                return VideoStreamResource(value, subtype, attrs)

            if type == "file":
                if not isinstance(value, (StreamResource, bytes)):
                    raise TypeError(f"`file` requires a binary input, got {value.__class__.__name__}")
                if isinstance(value, bytes):
                    value = BytesStreamResource(value)
                return value

        if type in [ "sse-text", "sse-json" ]:
            if isinstance(value, (StreamResource, AsyncIterator)):
                return EventStreamResource(value, _STREAM_FORMAT_MAP[type])
            async def _stream_output_generator():
                yield value
            return EventStreamResource(_stream_output_generator(), _STREAM_FORMAT_MAP[type])

        return value

    async def _load_bytes_from_format(self, value: str, format: str) -> bytes:
        if format == "url":
            stream = await create_stream_with_url(value)
            chunks: List[bytes] = []
            async with stream:
                async for chunk in stream:
                    chunks.append(chunk)
            return b"".join(chunks)

        if format == "path":
            async with aiofiles.open(value, "rb") as file:
                return await file.read()

        if format == "base64":
            return base64.b64decode(value)

        if format == "data-uri":
            _, meta, data = parse_data_uri(value)
            if "base64" in meta.split(";"):
                return base64.b64decode(data)
            return unquote_to_bytes(data)

        raise ValueError(f"Unknown format: {format}")

    async def _load_stream_from_format(self, value: str, format: str) -> StreamResource:
        if format == "url":
            return UrlStreamResource(value)

        if format == "path":
            return FileStreamResource(value)

        if format == "base64":
            return Base64StreamResource(value)

        if format == "data-uri":
            _, meta, data = parse_data_uri(value)
            if "base64" in meta.split(";"):
                return Base64StreamResource(data)
            return BytesStreamResource(unquote_to_bytes(data))

        raise ValueError(f"Unknown format: {format}")

    async def _render_attrs(self, value: str, scope: Optional[str]) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}

        for pair in self._split_attrs(value):
            pair = pair.strip()
            if "=" in pair:
                k, _, v = pair.partition("=")
                attrs[k.strip()] = await self._render_text(v.strip(), scope, skip_decode=False)

        return attrs

    def _split_attrs(self, value: str) -> List[str]:
        parts: List[str] = []
        start, depth = 0, 0
        index, length = 0, len(value)

        while index < length:
            ch = value[index]
            if ch == "$" and index + 1 < length and value[index + 1] == "{":
                depth += 1
                index += 2
                continue
            if ch == "}" and depth > 0:
                depth -= 1
                index += 1
                continue
            if ch == "," and depth == 0:
                parts.append(value[start:index])
                start = index + 1
                index += 1
                continue
            index += 1

        parts.append(value[start:])

        return parts

    def _is_spread_expression(self, text: str) -> bool:
        return self.patterns["spread"].fullmatch(text) is not None

    def _contains_reference(self, key: str, element: Any) -> bool:
        if isinstance(element, str):
            return any(key == m.group(1) for m in self.patterns["variable"].finditer(element))
        
        if isinstance(element, dict):
            return any([ self._contains_reference(key, value) for value in element.values() ])
        
        if isinstance(element, (list, tuple)):
            return any([ self._contains_reference(key, item) for item in element ])
        
        return False

class ImageValueRenderer:
    async def render(self, value: Any) -> Optional[Union[PILImage.Image, AsyncIterator, List[Union[PILImage.Image, AsyncIterator]]]]:
        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element(self, element: Any) -> Optional[Union[PILImage.Image, AsyncIterator]]:
        if isinstance(element, (PILImage.Image, AsyncIterator)):
            return element

        if isinstance(element, ImageStreamResource):
            return element.image

        if isinstance(element, StreamResource):
            return await load_image_from_stream(element)

        return None

class AudioValueRenderer:
    async def render(self, value: Any) -> Union[MediaSource, List[MediaSource]]:
        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element(self, element: Any) -> MediaSource:
        return create_audio_source(element)

class VideoValueRenderer:
    async def render(self, value: Any) -> Union[MediaSource, List[MediaSource]]:
        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element(self, element: Any) -> MediaSource:
        return create_video_source(element)

class FileValueRenderer:
    async def render(self, value: Any) -> Optional[Union[str, List[Optional[str]]]]:
        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element(self, element: Any) -> Optional[str]:
        if isinstance(element, FileStreamResource):
            return element.path

        if isinstance(element, StreamResource):
            return await save_stream_to_temporary_file(element, None)

        return None

class SizeValueRenderer:
    async def render(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        if isinstance(value, (str, int, float)):
            return parse_size(value)

        return default
