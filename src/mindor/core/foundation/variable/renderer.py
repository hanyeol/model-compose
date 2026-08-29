from typing import Callable, Dict, List, Optional, Union, Awaitable, Any
from collections.abc import AsyncIterator, AsyncIterable
from pydantic import BaseModel
from ..streaming.resources import StreamResource
from ..streaming.file import UploadFileStreamResource, FileStreamResource
from ..streaming.base64 import Base64StreamResource, encode_value_to_base64, decode_base64_value
from ..streaming.json import decode_json_value, encode_value_to_json
from ..streaming.bytes import BytesStreamResource
from ..streaming.iterators import StreamEncodingFormat, StreamEncodingIterator, StreamIterator, StreamChunkIterator
from ..streaming.image import load_image_from_stream, ImageStreamResource
from ..streaming.audio import PcmStreamResource, WavStreamResource, AudioStreamResource
from ..streaming.video import VideoStreamResource
from ..streaming.url import UrlStreamResource, DataUriStreamResource
from mindor.core.utils.transport.http_client import create_stream_with_url
from mindor.core.utils.url import parse_data_uri
from mindor.core.foundation.condition import evaluate_condition, evaluate_where
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from starlette.datastructures import UploadFile
from PIL import Image as PILImage
from urllib.parse import unquote_to_bytes
import re, aiofiles, os, asyncio

class FieldResolver:
    def __init__(self):
        self.patterns: Dict[str, re.Pattern] = {
            "keypath": re.compile(r"[-_\w]+|\[-?\d*:-?\d*\]|\[-?\d+\]|\[\*\]"),
        }

    def resolve(self, object: Any, path: Optional[str], default: Any = None) -> Any:
        if path is not None:
            return self._resolve_value(object, self.patterns["keypath"].findall(path), default)

        return object

    def _resolve_value(self, object: Any, segments: List[str], default: Any) -> Any:
        value = object
        for index, segment in enumerate(segments):
            if segment == "[*]":
                if not isinstance(value, list):
                    return default
                return [ self._resolve_value(item, segments[index + 1:], default) for item in value ]

            if segment.startswith("["):
                if not isinstance(value, list):
                    return default
                inner = segment[1:-1]
                if ":" in inner:
                    start_str, stop_str = inner.split(":", 1)
                    start = int(start_str) if start_str else None
                    stop = int(stop_str) if stop_str else None
                    value = value[start:stop]
                else:
                    i = int(inner)
                    if not -len(value) <= i < len(value):
                        return default
                    value = value[i]
            else:
                if not isinstance(value, dict):
                    return default
                if segment not in value:
                    return default
                value = value[segment]

        return value

class VariableRenderer:
    def __init__(self, source_resolver: Callable[[str, Optional[Union[int, slice]], Optional[str]], Awaitable[Any]]):
        self.source_resolver: Callable[[str, Optional[Union[int, slice]], Optional[str]], Awaitable[Any]] = source_resolver
        self.field_resolver: FieldResolver = FieldResolver()
        self.patterns: Dict[str, re.Pattern] = {
            "variable": re.compile(
                r"""\$\{                                                                                                # ${
                    (?:\s*([a-zA-Z_][^.\[\s]*(?:\[\])?))(?:\[(-?\d*:-?\d*|-?\d+)\])?                                    # key: input, result[], result[0], result[-1], result[1:], result[:5], result[1:5], etc.
                    (?:\.([^\s|}]+))?                                                                                   # path: key, key.path[0], etc.
                    (?:\s*as\s*([^\s/;\[}]+)(\[\])?(?:/([^\s;\[}]+)(?:\[((?:\$\{[^}]*\}|[^\]])*)\])?)?(?:;([^\s}]+))?)? # type[]/subtype[attrs];format (attrs may contain nested ${...})
                    (?:\s*\|\s*((?:\$\{[^}]+\}|\\[$@{}]|(?!\s*(?:@\(|\$\{)).)+))?                                       # default value after `|`
                    (?:\s*(@\(\s*[\w]+\s+(?:\\[$@{}]|(?!\s*\$\{).)+\)))?                                                # annotations
                \s*\}""",                                                                                               # }
                re.VERBOSE,
            ),
            "spread": re.compile(r"^\.\.\.\$\{[^}]+\}$"),
        }

        self._item_stack: List[Any] = []
        self._index_stack: List[int] = []

    async def render(self, value: Any, scope: Optional[str] = None, skip_decode: bool = False) -> Any:
        return await self._render_element(value, scope, skip_decode)

    async def _render_element(self, value: Any, scope: Optional[str], skip_decode: bool) -> Any:
        if isinstance(value, str):
            return await self._render_text(value, scope, skip_decode)

        if isinstance(value, BaseModel):
            return await self._render_element(value.model_dump(by_alias=True), scope, skip_decode)

        if isinstance(value, dict):
            if "?" in value and len(value) == 1:
                return await self._render_conditional(value["?"], scope, skip_decode)
            if "+" in value and len(value) == 1:
                return await self._render_join(value["+"], scope, skip_decode)
            if "*" in value:
                return await self._render_map(value, scope, skip_decode)
            if "|" in value:
                return await self._render_split(value, scope, skip_decode)
            return await self._render_dict(value, scope, skip_decode)

        if isinstance(value, (list, tuple)):
            return await self._render_list(value, scope, skip_decode)

        return value

    async def _render_dict(self, entries: dict, scope: Optional[str], skip_decode: bool) -> Dict[str, Any]:
        values = {}

        for key, value in entries.items():
            if key == "...":
                value = await self._render_element(value, scope, skip_decode)
                if isinstance(value, dict) or value is None:
                    values.update(value or {})
                else:
                    raise TypeError(f"Spread in dict must resolve to a dict, got {type(value).__name__}")
            elif key == "?":
                result = await self._render_conditional(value, scope, skip_decode)
                if result is None:
                    continue
                if not isinstance(result, dict):
                    raise TypeError(f"Conditional `?` as a sibling key must resolve to a dict, got {type(result).__name__}")
                values.update(result)
            else:
                values[key] = await self._render_element(value, scope, skip_decode)

        return values

    async def _render_list(self, entries: list, scope: Optional[str], skip_decode: bool) -> list:
        values = []

        for item in entries:
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
            index = self._parse_index(index) if index else None
            is_list = bool(is_list)

            if attrs:
                attrs = await self._render_attrs(attrs, scope)

            try:
                value = self.field_resolver.resolve(await self._resolve_source(key, index, scope), path)
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

    async def _render_conditional(self, entries: Any, scope: Optional[str], skip_decode: bool) -> Any:
        conditions = entries if isinstance(entries, list) else [entries]

        for condition in conditions:
            if not isinstance(condition, dict):
                raise TypeError(f"Conditional `?` entry must be a dict, got {type(condition).__name__}")

            input = await self._render_element(condition.get("input"), scope, skip_decode)
            value = await self._render_element(condition.get("value"), scope, skip_decode)
            operator = ConditionOperator(condition.get("operator", ConditionOperator.EQ.value))

            if evaluate_condition(operator, input, value):
                return await self._render_element(condition.get("if_true"), scope, skip_decode)

            if "if_false" in condition:
                return await self._render_element(condition["if_false"], scope, skip_decode)

        return None

    async def _render_map(self, entries: dict, scope: Optional[str], skip_decode: bool) -> Any:
        source, where = None, None
        value = entries["*"]

        if isinstance(value, dict):
            source = await self._render_element(value.get("input"), scope, skip_decode)
            where = value.get("where")
        else:
            source = await self._render_element(value, scope, skip_decode)

        if source is None:
            return []

        template = { key: value for key, value in entries.items() if key != "*" }

        if isinstance(source, (list, tuple)):
            if not template and where is None:
                return list(source)

            values: List[Any] = []

            for index, item in enumerate(source):
                self._item_stack.append(item)
                self._index_stack.append(index)
                try:
                    if where is not None and not await self._matches_where(where, scope, skip_decode):
                        continue
                    if template:
                        values.append(await self._render_dict(template, scope, skip_decode))
                    else:
                        values.append(item)
                finally:
                    self._item_stack.pop()
                    self._index_stack.pop()

            return values

        if isinstance(source, (StreamIterator, AsyncIterable)):
            if not template and where is None:
                return source

            async def _iterate() -> AsyncIterator[Any]:
                index = 0
                async for item in source:
                    self._item_stack.append(item)
                    self._index_stack.append(index)
                    try:
                        if where is not None and not await self._matches_where(where, scope, skip_decode):
                            continue
                        if template:
                            yield await self._render_dict(template, scope, skip_decode)
                        else:
                            yield item
                    finally:
                        self._item_stack.pop()
                        self._index_stack.pop()
                        index += 1

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(source, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=source.is_fragmented)

            return _iterate()

        raise TypeError(f"Map source (`*`) must resolve to a list or iterator, got {type(source).__name__}")

    async def _render_join(self, entries: Any, scope: Optional[str], skip_decode: bool) -> Any:
        parts = await self._render_element(entries, scope, skip_decode)

        if parts is None:
            return None

        # Promote a list whose elements contain a stream to a lazy stream so
        # the stream branch below handles per-chunk unrolling uniformly.
        if isinstance(parts, (list, tuple)) and any(isinstance(part, (StreamIterator, AsyncIterable)) for part in parts):
            async def _stream_from_parts(parts=parts):
                for part in parts:
                    if part is not None:
                        yield part
            parts = StreamChunkIterator(_stream_from_parts(), is_fragmented=True)

        if isinstance(parts, (list, tuple)):
            parts = [ part for part in parts if part is not None ]

            if not parts:
                return None

            if isinstance(parts[0], (list, tuple)):
                value: List[Any] = []
                for part in parts:
                    value.extend(part)
                return value

            if isinstance(parts[0], dict):
                value: Dict[str, Any] = {}
                for part in parts:
                    value.update(part)
                return value

            if isinstance(parts[0], str):
                return "".join(parts)

            raise TypeError(f"Join `+` cannot combine values of type {type(parts[0]).__name__}")

        if isinstance(parts, (StreamIterator, AsyncIterable)):
            async def _iterate() -> AsyncIterator[Any]:
                async for chunk in parts:
                    if isinstance(chunk, (list, tuple)):
                        for item in chunk:
                            yield item
                        continue

                    if isinstance(chunk, (StreamIterator, AsyncIterable)):
                        async for item in chunk:
                            yield item
                        continue

                    if chunk is not None:
                        yield chunk
                        continue

            # `+` collapses its inputs into one logical value, so the result
            # is always a fragmented stream — an array delivered in pieces.
            return StreamChunkIterator(_iterate(), is_fragmented=True)

        raise TypeError(f"Join `+` source must resolve to a list or iterator, got {type(parts).__name__}")

    async def _render_split(self, entries: dict, scope: Optional[str], skip_decode: bool) -> Any:
        source = await self._render_element(entries["|"], scope, skip_decode)
        template = { key: value for key, value in entries.items() if key != "|" }

        if not template:
            raise ValueError("Split `|` requires a template with at least one output field.")

        if source is None:
            return { key: [] for key in template }

        if isinstance(source, (list, tuple)):
            value: Dict[str, List[Any]] = { key: [] for key in template }

            for index, item in enumerate(source):
                self._item_stack.append(item)
                self._index_stack.append(index)
                try:
                    for key in template:
                        value[key].append(await self._render_element(template[key], scope, skip_decode))
                finally:
                    self._item_stack.pop()
                    self._index_stack.pop()

            return value

        if isinstance(source, (StreamIterator, AsyncIterable)):
            source_iterator = source.__aiter__()
            buffers: Dict[str, List[Any]] = { key: [] for key in template }
            error: Optional[BaseException] = None
            advance_lock = asyncio.Lock()
            exhausted = False
            index = 0

            async def _advance_for(key: str) -> bool:
                nonlocal exhausted, error, index

                async with advance_lock:
                    if buffers[key]:
                        return True
                    if exhausted:
                        return False
                    if error is not None:
                        raise error

                    try:
                        item = await source_iterator.__anext__()
                    except StopAsyncIteration:
                        exhausted = True
                        return False
                    except BaseException as e:
                        error = e
                        raise

                    self._item_stack.append(item)
                    self._index_stack.append(index)
                    try:
                        for key in template:
                            buffers[key].append(await self._render_element(template[key], scope, skip_decode))
                    finally:
                        self._item_stack.pop()
                        self._index_stack.pop()
                        index += 1

                    return True

            def _iterate_for(key: str) -> AsyncIterator[Any]:
                async def _iterate() -> AsyncIterator[Any]:
                    while True:
                        if not buffers[key]:
                            if not await _advance_for(key):
                                return
                        yield buffers[key].pop(0)
                return _iterate()

            is_fragmented = source.is_fragmented if isinstance(source, StreamChunkIterator) else True

            return { key: StreamChunkIterator(_iterate_for(key), is_fragmented=is_fragmented) for key in template }

        raise TypeError(f"Split `|` source must resolve to a list or iterator, got {type(source).__name__}")

    async def _matches_where(self, where: Any, scope: Optional[str], skip_decode: bool) -> bool:
        if not isinstance(where, dict):
            raise TypeError(f"Map `where` must be a dict, got {type(where).__name__}")

        async def _evaluate_condition(condition: Any) -> bool:
            input = await self._render_element(condition.get("input"), scope, skip_decode)
            value = await self._render_element(condition.get("value"), scope, skip_decode)
            operator = ConditionOperator(condition.get("operator", ConditionOperator.EQ.value))
            return evaluate_condition(operator, input, value)

        return await evaluate_where(where, _evaluate_condition)

    async def _resolve_source(self, key: str, index: Optional[Union[int, slice]], scope: Optional[str]) -> Any:
        if key == "item" and self._item_stack:
            value = self._item_stack[-1]
            if index is not None and isinstance(value, list):
                return value[index]
            return value

        if key == "index" and self._index_stack:
            return self._index_stack[-1]

        return await self.source_resolver(key, index, scope)

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
            if isinstance(value, (StreamIterator, AsyncIterator)):
                async def _iterate():
                    async for item in value:
                        yield await self._convert_value_to_type(item, type, False, subtype, attrs, format, skip_decode)
                return _iterate()

            if not isinstance(value, (list, tuple)):
                raise ValueError(f"`{type}[]` requires a list/tuple or stream input, got {value.__class__.__name__}")

            return [ await self._convert_value_to_type(v, type, False, subtype, attrs, format, skip_decode) for v in value ]

        # `path` is intentionally excluded: it refers to a local filesystem location and is not
        # self-contained, so it cannot be passed through to consumers as-is. It must be loaded
        # into a StreamResource below so adapters can stream the actual bytes.
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
            value = await decode_json_value(value)

        if type in [ "string", "text" ] and isinstance(value, (dict, list, tuple)):
            value = await encode_value_to_json(value)

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
            return await encode_value_to_base64(value)

        if type in [ "image", "audio", "video", "file" ]:
            if isinstance(value, (StreamIterator, AsyncIterator)) and not isinstance(value, StreamResource):
                return value

            if format in [ "base64", "path", "url", "data-uri" ] and isinstance(value, str):
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
                    return value if isinstance(value, PcmStreamResource) else PcmStreamResource(value, attrs)
                if subtype == "wav":
                    return value if isinstance(value, WavStreamResource) else WavStreamResource(value)
                if subtype is None and isinstance(value, (PcmStreamResource, WavStreamResource, AudioStreamResource)):
                    return value
                return AudioStreamResource(value, subtype, attrs)

            if type == "video":
                if not isinstance(value, (StreamResource, bytes)):
                    raise TypeError(f"`video` requires raw video input, got {value.__class__.__name__}")
                if subtype is None and isinstance(value, VideoStreamResource):
                    return value
                return VideoStreamResource(value, subtype, attrs)

            if type == "file":
                if not isinstance(value, (StreamResource, bytes)):
                    raise TypeError(f"`file` requires a binary input, got {value.__class__.__name__}")
                if isinstance(value, bytes):
                    value = BytesStreamResource(value)
                return value

        if type == "stream":
            format = StreamEncodingFormat(subtype) if subtype else StreamEncodingFormat.TEXT
            if isinstance(value, (StreamResource, StreamIterator, AsyncIterator)):
                if isinstance(value, StreamEncodingIterator) and value.format == format:
                    return value
                return StreamEncodingIterator(value, format)
            async def _stream_output_generator():
                yield value
            return StreamEncodingIterator(_stream_output_generator(), format)

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
            async with aiofiles.open(os.path.expanduser(value), "rb") as f:
                return await f.read()

        if format == "base64":
            return await decode_base64_value(value)

        if format == "data-uri":
            _, meta, data = parse_data_uri(value)
            if "base64" in meta.split(";"):
                return await decode_base64_value(data)
            return unquote_to_bytes(data)

        raise ValueError(f"Unknown format: {format}")

    async def _load_stream_from_format(self, value: str, format: str) -> StreamResource:
        if format == "base64":
            return Base64StreamResource(value)

        if format == "url":
            return UrlStreamResource(value)

        if format == "path":
            return FileStreamResource(os.path.expanduser(value))

        if format == "data-uri":
            return DataUriStreamResource(value)

        raise ValueError(f"Unknown format: {format}")

    async def _render_attrs(self, value: str, scope: Optional[str]) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}

        for pair in self._split_attrs(value):
            pair = pair.strip()
            if "=" in pair:
                k, _, v = pair.partition("=")
                attrs[k.strip()] = await self._render_text(v.strip(), scope, skip_decode=False)

        return attrs

    @staticmethod
    def _split_attrs(value: str) -> List[str]:
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

    @staticmethod
    def _parse_index(expression: str) -> Union[int, slice]:
        if ":" in expression:
            start, stop = expression.split(":", 1)
            start = int(start) if start else None
            stop  = int(stop) if stop else None

            return slice(start, stop)

        return int(expression)

    def _is_spread_expression(self, text: str) -> bool:
        return self.patterns["spread"].fullmatch(text) is not None
