from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.core.utils.template import TemplateRenderer
from mindor.core.gateway import find_gateway_by_port

class ComponentContext:
    def __init__(self, call_id: str, input: Dict[str, Any], env: Dict[str, str]):
        self.call_id: str = call_id
        self.input: Dict[str, Any] = input
        self.env: Dict[str, str] = env
        self.context: Dict[str, Any] = { "call_id": call_id }
        self.sources: Dict[str, Any] = {}
        self.renderer: TemplateRenderer = TemplateRenderer(self._resolve_source)

    def register_source(self, key: str, source: Any) -> None:
        self.sources[key] = source

    async def render_template(self, data: Dict[str, Any]) -> Any:
        return await self.renderer.render(data)

    async def _resolve_source(self, key: str) -> Any:
        if key in self.sources:
            return self.sources[key]
        if key == "input":
            return self.input
        if key == "env":
            return self.env
        if key == "context":
            return self.context
        if key.startswith("gateway:"):
            return self._resolve_gateway(key)
        raise KeyError(f"Unknown source: {key}")

    def _resolve_gateway(self, key: str) -> Any:
        _, port = key.split(":")
        gateway = find_gateway_by_port(int(port)) if port else None
        if gateway:
            return gateway.get_context()
        return None
