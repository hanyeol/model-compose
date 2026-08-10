from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Awaitable, Any
from collections.abc import AsyncIterator
from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.foundation.variable.image import ImageValueRenderer
from mindor.core.foundation.variable.audio import AudioValueRenderer
from mindor.core.foundation.variable.video import VideoValueRenderer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from .interrupt import InterruptHandler
from PIL import Image as PILImage

if TYPE_CHECKING:
    from .notifiers import JobEventNotifier, ComponentEventNotifier

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
        cancellation_token: Optional[CancellationToken] = None,
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
        self.renderer = VariableRenderer(self.resolve_source)
        self.interrupt_handler: InterruptHandler = interrupt_handler
        self.workflow_delegate: WorkflowDelegate = workflow_delegate
        self.job_event_notifier: JobEventNotifier = job_event_notifier
        self.component_event_notifier: ComponentEventNotifier = component_event_notifier
        self.cancellation_token: Optional[CancellationToken] = cancellation_token
        self.job_run_ids: Dict[str, List[str]] = {}

    def register_source(self, key: str, source: Any) -> None:
        self.sources[key] = source

    def complete_job(self, job_id: str, output: Any) -> None:
        self.sources["jobs"][job_id] = { "output": output }

    def record_run_id(self, job_id: str, run_id: str) -> None:
        self.job_run_ids.setdefault(job_id, []).append(run_id)

    async def render_variable(
        self,
        value: Any,
        skip_decode: bool = False
    ) -> Any:
        if value is not None:
            return await self.renderer.render(value, skip_decode=skip_decode)

        return None

    async def render_image(
        self,
        value: Any
    ) -> Optional[Union[PILImage.Image, List[Optional[PILImage.Image]], AsyncIterator[Optional[PILImage.Image]]]]:
        return await ImageValueRenderer().render(await self.render_variable(value))

    async def render_audio(
        self,
        value: Any
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        return await AudioValueRenderer().render(await self.render_variable(value))

    async def render_video(
        self,
        value: Any
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        return await VideoValueRenderer().render(await self.render_variable(value))

    async def resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        if key in self.sources:
            return self.sources[key][index] if index is not None else self.sources[key]

        if key == "input":
            return self.input

        if key == "context":
            return self.context

        raise KeyError(f"Unknown source: {key}")
