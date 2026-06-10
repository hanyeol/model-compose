from typing import Optional, Dict, Any
from mindor.core.utils.renderers import VariableRenderer, ImageValueRenderer, AudioValueRenderer, VideoValueRenderer
from mindor.core.workflow.context import WorkflowContext

class JobContext:
    def __init__(self, workflow: WorkflowContext, job_id: str):
        self.workflow: WorkflowContext = workflow
        self.job_id: str = job_id
        self._sources: Dict[str, Dict[str, Any]] = { "__global__": {} }
        self.renderer: VariableRenderer = VariableRenderer(self._resolve_source)

    def register_source(self, run_id: Optional[str], key: str, source: Any) -> None:
        self._sources.setdefault(run_id or "__global__", {})[key] = source

    async def render_variable(self, run_id: Optional[str], value: Any) -> Any:
        return await self.renderer.render(value, run_id)

    async def render_image(self, run_id: Optional[str], value: Any) -> Any:
        return await ImageValueRenderer().render(await self.render_variable(run_id, value))

    async def render_audio(self, run_id: Optional[str], value: Any) -> Any:
        return await AudioValueRenderer().render(await self.render_variable(run_id, value))

    async def render_video(self, run_id: Optional[str], value: Any) -> Any:
        return await VideoValueRenderer().render(await self.render_variable(run_id, value))

    async def _resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        sources = self._sources.get(scope or "__global__", {})

        if key in sources:
            return sources[key][index] if index is not None else sources[key]

        return await self.workflow.resolve_source(key, index)
