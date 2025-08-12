from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.core.utils.renderers import VariableRenderer, ImageValueRenderer
from mindor.core.gateway import find_gateway_by_port

class ComponentActionContext:
    def __init__(self, run_id: str, input: Dict[str, Any]):
        self.run_id: str = run_id
        self.input: Dict[str, Any] = input
        self.context: Dict[str, Any] = { "run_id": run_id }
        self.sources: Dict[str, Any] = {}
        self.renderer: VariableRenderer = VariableRenderer(self._resolve_source)

    def register_source(self, key: str, source: Any) -> None:
        self.sources[key] = source

    async def render_variable(self, value: Any, ignore_files: bool = False) -> Any:
        return await self.renderer.render(value, ignore_files)

    async def render_image(self, value: Any) -> Any:
        return await ImageValueRenderer().render(await self.render_variable(value))

    def contains_variable_reference(self, key: str, value: Any) -> bool:
        return self.renderer.contains_reference(key, value)

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
