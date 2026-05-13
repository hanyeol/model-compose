from typing import Callable, Dict, List, Optional, Awaitable, Any
from collections.abc import AsyncIterator
from pydantic import BaseModel
from .streaming import StreamResource, UploadFileStreamResource, Base64StreamResource, EventIteratorStreamResource, StreamFormat
from .streaming import encode_stream_to_base64, save_stream_to_temporary_file, BytesStreamResource
from .http_request import create_upload_file
from .http_client import create_stream_with_url
from .image import load_image_from_stream, ImageStreamResource
from .resolvers import FieldResolver
from starlette.datastructures import UploadFile
from PIL import Image as PILImage
import os, re, json, base64

_STREAM_FORMAT_MAP = {
    "sse-text": StreamFormat.TEXT,
    "sse-json": StreamFormat.JSON,
}

class VariableRenderer:
    def __init__(self, source_resolver: Callable[[str, Optional[int]], Awaitable[Any]]):
        self.source_resolver: Callable[[str, Optional[int]], Awaitable[Any]] = source_resolver
        self.field_resolver: FieldResolver = FieldResolver()
        self.patterns: Dict[str, re.Pattern] = {
            "variable": re.compile(
                r"""\$\{                                                                       # ${
                    (?:\s*([a-zA-Z_][^.\[\s]*(?:\[\])?))(?:\[(-?[0-9]+)\])?                    # key: input, result[], result[0], result[-1], etc.
                    (?:\.([^\s|}]+))?                                                          # path: key, key.path[0], etc.
                    (?:\s*as\s*([^\s/;}]+)(?:/([^\s;\[}]+)(?:\[([^\]]*)\])?)?(?:;([^\s}]+))?)? # type/subtype[attrs];format
                    (?:\s*\|\s*((?:\$\{[^}]+\}|\\[$@{}]|(?!\s*(?:@\(|\$\{)).)+))?              # default value after `|`
                    (?:\s*(@\(\s*[\w]+\s+(?:\\[$@{}]|(?!\s*\$\{).)+\)))?                       # annotations
                \s*\}""",                                                                      # }
                re.VERBOSE,
            )
        }

    async def render(self, value: Any, ignore_files: bool = True) -> Any:
        return await self._render_element(value, ignore_files)

    def contains_reference(self, key: str, value: Any) -> bool:
        return self._contains_reference(key, value)

    async def _render_element(self, element: Any, ignore_files: bool) -> Any:
        if isinstance(element, str):
            return await self._render_text(element, ignore_files)
        
        if isinstance(element, BaseModel):
            return await self._render_element(element.model_dump(by_alias=True), ignore_files)

        if isinstance(element, dict):
            return { key: await self._render_element(value, ignore_files) for key, value in element.items() }

        if isinstance(element, (list, tuple)):
            return [ await self._render_element(item, ignore_files) for item in element ]

        return element

    async def _render_text(self, text: str, ignore_files: bool) -> Any:
        matches = list(self.patterns["variable"].finditer(text))

        for m in reversed(matches):
            key, index, path, type, subtype, attrs, format, default = m.group(1, 2, 3, 4, 5, 6, 7, 8)
            index = int(index) if index else None

            if attrs:
                attrs = self._parse_attrs(attrs)

            try:
                value = self.field_resolver.resolve(await self.source_resolver(key, index), path)
            except Exception:
                value = None

            if value is None and default is not None:
                value = await self._render_text(default, ignore_files)

            if type and value is not None:
                value = await self._convert_value_to_type(value, type, subtype, attrs, format, ignore_files)

            start, end = m.span()

            if start == 0 and end == len(text):
                return value

            text = text[:start] + str(value) + text[end:]

        return text

    async def _convert_value_to_type(self, value: Any, type: str, subtype: Optional[str], attrs: Optional[Dict[str, str]], format: Optional[str], ignore_files: bool) -> Any:
        if type == "number":
            return float(value)

        if type == "integer":
            return int(value)

        if type == "boolean":
            return str(value).lower() in [ "true", "1" ]

        if type == "json":
            if isinstance(value, str):
                return json.loads(value)
            return value

        if type == "object[]":
            if isinstance(value, list):
                objects = [ v for v in value if isinstance(v, dict) ]
                if subtype:
                    paths = [ ( path, path.split(".")[-1] ) for path in subtype.split(",") ]
                    return [ { key: self.field_resolver.resolve(object, path) for path, key in paths } for object in objects ]
                return objects
            return []

        if type == "base64":
            if isinstance(value, PILImage.Image):
                return await encode_stream_to_base64(ImageStreamResource(value, format))
            if isinstance(value, UploadFile):
                return await encode_stream_to_base64(UploadFileStreamResource(value))
            if isinstance(value, StreamResource):
                return await encode_stream_to_base64(value)
            if isinstance(value, str):
                return base64.b64encode(value.encode("utf-8")).decode("ascii")
            return base64.b64encode(value)

        if type in [ "image", "audio", "video", "file" ]:
            if isinstance(value, UploadFile) and format == "path":
                return await FileValueRenderer().render(value)
            if not ignore_files and not isinstance(value, UploadFile):
                if format != "path":
                    value = await self._save_value_to_temporary_file(value, subtype, attrs, format)
                return create_upload_file(value, type, subtype)
            return value

        if type in [ "sse-text", "sse-json" ]:
            if isinstance(value, (StreamResource, AsyncIterator)):
                return EventIteratorStreamResource(value, _STREAM_FORMAT_MAP[type])
            async def _stream_output_generator():
                yield value
            return EventIteratorStreamResource(_stream_output_generator(), _STREAM_FORMAT_MAP[type])

        return value

    async def _save_value_to_temporary_file(self, value: Any, subtype: Optional[str], attrs: Optional[Dict[str, str]], format: Optional[str]) -> Optional[str]:
        if format == "base64" and isinstance(value, str):
            return await save_stream_to_temporary_file(Base64StreamResource(value), subtype)

        if format == "url" and isinstance(value, str):
            return await save_stream_to_temporary_file(await create_stream_with_url(value), subtype)

        if isinstance(value, bytes):
            return await save_stream_to_temporary_file(BytesStreamResource(value), subtype)

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, subtype)

        return None

    def _parse_attrs(self, value: Optional[str]) -> Optional[Dict[str, str]]:
        attrs: Dict[str, str] = {}

        for pair in value.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, _, v = pair.partition("=")
                attrs[k.strip()] = v.strip()

        return attrs

    def _contains_reference(self, key: str, element: Any) -> bool:
        if isinstance(element, str):
            return any(key == m.group(1) for m in self.patterns["variable"].finditer(element))
        
        if isinstance(element, dict):
            return any([ self._contains_reference(key, value) for value in element.values() ])
        
        if isinstance(element, (list, tuple)):
            return any([ self._contains_reference(key, item) for item in element ])
        
        return False

class ImageValueRenderer:
    async def render(self, value: Any) -> Any:
        return await self._render_element(value)

    async def _render_element(self, element: Any) -> Any:
        if isinstance(element, UploadFile):
            return await load_image_from_stream(UploadFileStreamResource(element))
        
        if isinstance(element, dict):
            return { key: await self._render_element(value) for key, value in element.items() }

        if isinstance(element, (list, tuple)):
            return [ await self._render_element(item) for item in element ]
        
        return element if isinstance(element, PILImage.Image) else None

class FileValueRenderer:
    async def render(self, value: Any) -> Optional[str]:
        if isinstance(value, UploadFile):
            extension = os.path.splitext(value.filename)[1].lstrip(".") if value.filename else None
            return await save_stream_to_temporary_file(UploadFileStreamResource(value), extension)

        if isinstance(value, bytes):
            return await save_stream_to_temporary_file(BytesStreamResource(value), None)

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, None)

        if isinstance(value, str):
            if os.path.isfile(value):
                return value
            return await save_stream_to_temporary_file(Base64StreamResource(value), None)

        return value
