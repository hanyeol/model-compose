from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.core.utils.template import TemplateRenderer

class WorkflowContext:
    def __init__(self, task_id: str, input: Dict[str, Any], env: Dict[str, str]):
        self.task_id: str = task_id
        self.input: Dict[str, Any] = input
        self.env: Dict[str, str] = env
        self.context: Dict[str, Any] = { "task_id": task_id }
        self.sources: Dict[str, Any] = { "jobs": {} }
        self.renderer = TemplateRenderer(self._resolve_source)

    def complete_job(self, job_id: str, output: Any) -> None:
        self.sources["jobs"][job_id] = { "output": output }

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
        raise KeyError(f"Unknown source: {key}")
