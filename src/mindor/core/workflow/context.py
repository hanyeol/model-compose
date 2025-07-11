from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.core.utils.renderer import VariableRenderer

class WorkflowContext:
    def __init__(self, task_id: str, input: Dict[str, Any]):
        self.task_id: str = task_id
        self.input: Dict[str, Any] = input
        self.context: Dict[str, Any] = { "task_id": task_id }
        self.sources: Dict[str, Any] = { "jobs": {} }
        self.renderer = VariableRenderer(self._resolve_source)

    def complete_job(self, job_id: str, output: Any) -> None:
        self.sources["jobs"][job_id] = { "output": output }

    def register_source(self, key: str, source: Any) -> None:
        self.sources[key] = source

    async def render_variable(self, data: Dict[str, Any], ignore_files: bool = True) -> Any:
        return await self.renderer.render(data, ignore_files)

    async def _resolve_source(self, key: str, index: Optional[int]) -> Any:
        if key in self.sources:
            return self.sources[key][index] if index is not None else self.sources[key]
        if key == "input":
            return self.input
        if key == "context":
            return self.context
        raise KeyError(f"Unknown source: {key}")
