from typing import Callable, Dict, List, Optional, Awaitable, Any
from .streaming import StreamResource, encode_stream_to_base64
import re, json, base64

class TemplateRenderer:
    def __init__(self, source_resolver: Callable[[str], Awaitable[Any]]):
        self.source_resolver: Callable[[str], Awaitable[Any]] = source_resolver
        self.patterns: Dict[str, re.Pattern] = {
            "variable": re.compile(
                r"""\$\{                                                             # ${ 
                    ([a-zA-Z_][^.\s]*)                                               # key: input, env, etc.
                    (?:\.([^\s\|\}]+))?                                              # path: key, key.path[0], etc.
                    (?:\s*as\s*([^\s\|\}/;]+)(?:/([^\s\|\};]+))?(?:;([^\s\|\}]+))?)? # type/subtype;format
                    (?:\s*\|\s*([^\}]+))?                                            # default value after `|`
                \}""",                                                               # }
                re.VERBOSE,
            ),
            "keypath": re.compile(r"[-_\w]+|\[\d+\]"),
        }

    async def render(self, data: Any) -> Any:
        return await self._render_element(data)

    async def _render_element(self, element: Any) -> Any:
        if isinstance(element, str):
            return await self._render_text(element)
        
        if isinstance(element, dict):
            return { key: await self._render_element(value) for key, value in element.items() }
        
        if isinstance(element, list):
            return [ await self._render_element(item) for item in element ]
        
        return element

    async def _render_text(self, text: str) -> Any:
        while True:
            match = self.patterns["variable"].search(text)
            
            if not match:
                break

            key, path, type, subtype, format, default, variable = (*match.group(1, 2, 3, 4, 5, 6), match.group(0))
            try:
                value = self._resolve_by_path(await self.source_resolver(key), path)
            except Exception:
                value = None

            value = default if value is None else value

            if type and value is not None:
                value = await self._convert_type(value, type, subtype, format)

            if variable == text:
                return value

            text = text.replace(variable, str(value))

        return text

    def _resolve_by_path(self, source: Any, path: Optional[str]) -> Any:
        parts: List[str] = self.patterns["keypath"].findall(path) if path else []
        current = source

        for part in parts:
            if isinstance(current, dict) and not part.startswith("["):
                if part in current:
                    current = current[part]
                else:
                    return None
            elif isinstance(current, list) and part.startswith("["):
                index = int(part[1:-1])
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None
        
        return current

    async def _convert_type(self, value: Any, type: str, subtype: str, format: Optional[str]) -> Any:
        if type == "number":
            return float(value)

        if type == "integer":
            return int(value)

        if type == "json":
            return json.loads(value)
        
        if type == "boolean":
            return str(value).lower() in [ "true", "1" ]
        
        if type == "base64":
            if isinstance(value, StreamResource):
                return await encode_stream_to_base64(value)
            return base64.b64encode(value)

        return value
