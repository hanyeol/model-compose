from typing import Callable, Dict, List, Optional, Awaitable, Any
from .streaming import StreamResource, UploadFileStreamResource, Base64StreamResource
from .streaming import encode_stream_to_base64, save_stream_to_temporary_file
from .http_request import create_upload_file
from .http_client import create_stream_with_url
from .image import load_image_from_stream
from .resolvers import FieldResolver
from starlette.datastructures import UploadFile
from PIL import Image as PILImage
import re, json, base64

class VariableRenderer:
    def __init__(self, source_resolver: Callable[[str, Optional[int]], Awaitable[Any]]):
        self.source_resolver: Callable[[str, Optional[int]], Awaitable[Any]] = source_resolver
        self.field_resolver: FieldResolver = FieldResolver()
        self.patterns: Dict[str, re.Pattern] = {
            "variable": re.compile(
                r"""\$\{                                                          # ${ 
                    (?:\s*([a-zA-Z_][^.\[\s]*(?:\[\])?))(?:\[([0-9]+)\])?         # key: input, result[], result[0], etc.
                    (?:\.([^\s|}]+))?                                             # path: key, key.path[0], etc.
                    (?:\s*as\s*([^\s/;}]+)(?:/([^\s;}]+))?(?:;([^\s}]+))?)?       # type/subtype;format
                    (?:\s*\|\s*((?:\$\{[^}]+\}|\\[$@{}]|(?!\s*(?:@\(|\$\{)).)+))? # default value after `|`
                    (?:\s*(@\(\s*[\w]+\s+(?:\\[$@{}]|(?!\s*\$\{).)+\)))?          # annotations
                \s*\}""",                                                         # }
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
        
        if isinstance(element, dict):
            return { key: await self._render_element(value, ignore_files) for key, value in element.items() }
        
        if isinstance(element, (list, tuple)):
            return [ await self._render_element(item, ignore_files) for item in element ]
        
        return element

    async def _render_text(self, text: str, ignore_files: bool) -> Any:
        matches = list(self.patterns["variable"].finditer(text))

        for m in reversed(matches):
            key, index, path, type, subtype, format, default = m.group(1, 2, 3, 4, 5, 6, 7)
            index = int(index) if index else None

            try:
                value = self.field_resolver.resolve(await self.source_resolver(key, index), path)
            except Exception:
                value = None

            if value is None and default is not None:
                value = await self._render_text(default, ignore_files)

            if type and value is not None:
                value = await self._convert_value_to_type(value, type, subtype, format, ignore_files)

            start, end = m.span()

            if start == 0 and end == len(text):
                return value

            text = text[:start] + str(value) + text[end:]

        return text

    async def _convert_value_to_type(self, value: Any, type: str, subtype: str, format: Optional[str], ignore_files: bool) -> Any:
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
            if isinstance(value, UploadFile):
                return await encode_stream_to_base64(UploadFileStreamResource(value))
            if isinstance(value, StreamResource):
                return await encode_stream_to_base64(value)
            return base64.b64encode(value)

        if type in [ "image", "audio", "video", "file" ]:
            if not ignore_files and not isinstance(value, UploadFile):
                if format != "path":
                    value = await self._save_value_to_temporary_file(value, subtype, format)
                return create_upload_file(value, type, subtype)
            return value

        return value

    async def _save_value_to_temporary_file(self, value: Any, subtype: Optional[str], format: Optional[str]) -> Optional[str]:
        if format == "base64" and isinstance(value, str):
            return await save_stream_to_temporary_file(Base64StreamResource(value), subtype)

        if format == "url" and isinstance(value, str):
            return await save_stream_to_temporary_file(await create_stream_with_url(value), subtype)

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, subtype)

        return None

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
