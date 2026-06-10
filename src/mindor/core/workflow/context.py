from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Awaitable, Any
from mindor.core.utils.renderers import VariableRenderer, ImageValueRenderer, AudioValueRenderer, VideoValueRenderer
from mindor.core.workflow.interrupt import InterruptHandler

if TYPE_CHECKING:
    from mindor.core.workflow.workflow import JobEventNotifier, ComponentEventNotifier

WorkflowDelegate = Callable[[str, Dict[str, Any], InterruptHandler], Awaitable[Any]]

class WorkflowContext:
    def __init__(
        self,
        task_id: str,
        workflow_id: str,
        input: Dict[str, Any],
        interrupt_handler: InterruptHandler,
        workflow_delegate: WorkflowDelegate,
        job_event_notifier: JobEventNotifier,
        component_event_notifier: ComponentEventNotifier,
        session_id: Optional[str] = None,
        metadata: Optional[Any] = None,
    ):
        self.task_id: str = task_id
        self.workflow_id: str = workflow_id
        self.input: Dict[str, Any] = input
        self.context: Dict[str, Any] = {
            "task_id": task_id,
            **({"session_id": session_id} if session_id else {}),
            **({"metadata": metadata} if metadata else {})
        }
        self.sources: Dict[str, Any] = { "jobs": {} }
        self.renderer = VariableRenderer(self._resolve_source)
        self.interrupt_handler: InterruptHandler = interrupt_handler
        self.workflow_delegate: WorkflowDelegate = workflow_delegate
        self.job_event_notifier: JobEventNotifier = job_event_notifier
        self.component_event_notifier: ComponentEventNotifier = component_event_notifier
        self.job_run_ids: Dict[str, List[str]] = {}

    def complete_job(self, job_id: str, output: Any) -> None:
        self.sources["jobs"][job_id] = { "output": output }

    def register_source(self, key: str, source: Any) -> None:
        self.sources[key] = source

    async def resolve_source(self, key: str, index: Optional[int]) -> Any:
        return await self._resolve_source(key, index, None)

    async def render_variable(self, value: Any) -> Any:
        return await self.renderer.render(value)

    async def render_image(self, value: Any) -> Any:
        return await ImageValueRenderer().render(await self.render_variable(value))

    async def render_audio(self, value: Any) -> Any:
        return await AudioValueRenderer().render(await self.render_variable(value))

    async def render_video(self, value: Any) -> Any:
        return await VideoValueRenderer().render(await self.render_variable(value))

    def record_run_id(self, job_id: str, run_id: str) -> None:
        self.job_run_ids.setdefault(job_id, []).append(run_id)

    async def _resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        if key in self.sources:
            return self.sources[key][index] if index is not None else self.sources[key]

        if key == "input":
            return self.input

        if key == "context":
            return self.context

        raise KeyError(f"Unknown source: {key}")
