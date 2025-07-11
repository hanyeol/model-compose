from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.core.utils.renderer import VariableRenderer
from mindor.core.gateway import find_gateway_by_port

class ComponentActionContext:
    def __init__(self, call_id: str, input: Dict[str, Any]):
        self.call_id: str = call_id
        self.input: Dict[str, Any] = input
        self.context: Dict[str, Any] = { "call_id": call_id }
        self.sources: Dict[str, Any] = {}
        self.renderer: VariableRenderer = VariableRenderer(self._resolve_source)

    def register_source(self, key: str, source: Any) -> None:
        self.sources[key] = source

    async def render_variable(self, data: Dict[str, Any], ignore_files: bool = False) -> Any:
        return await self.renderer.render(data, ignore_files)

    async def _resolve_source(self, key: str, index: Optional[int]) -> Any:
        if key in self.sources:
            return self.sources[key][index] if index is not None else self.sources[key]
        if key == "input":
            return self.input
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
