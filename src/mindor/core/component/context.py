from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.core.utils.renderers import VariableRenderer, ImageValueRenderer, AudioValueRenderer, VideoValueRenderer, FileValueRenderer, SizeValueRenderer
from mindor.core.gateway import find_gateway_by_port
from PIL import Image as PILImage

if TYPE_CHECKING:
    from mindor.core.workflow.context import WorkflowContext
    from mindor.core.workflow.workflow import ComponentEventNotifier

class ComponentActionEventNotifier:
    def __init__(self, notifier: Optional[ComponentEventNotifier], component_id: Optional[str], component_type: Optional[str], job_id: Optional[str], run_id: Optional[str]):
        self.notifier: Optional[ComponentEventNotifier] = notifier
        self.component_id: Optional[str] = component_id
        self.component_type: Optional[str] = component_type
        self.job_id: Optional[str] = job_id
        self.run_id: Optional[str] = run_id

    async def notify(
        self,
        event: Literal[ "started", "completed", "failed", "internal" ],
        kind: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        if self.notifier is None:
            return
        await self.notifier.notify(
            event=event,
            job_id=self.job_id,
            component_id=self.component_id,
            component_type=self.component_type,
            run_id=self.run_id,
            kind=kind,
            input=input,
            output=output,
            error=error,
        )

class ComponentActionContext:
    def __init__(
        self,
        run_id: str,
        input: Dict[str, Any],
        workflow: Optional[WorkflowContext] = None,
        component_id: Optional[str] = None,
        component_type: Optional[str] = None,
        job_id: Optional[str] = None,
    ):
        self.run_id: str = run_id
        self.input: Dict[str, Any] = input
        self.workflow: Optional[WorkflowContext] = workflow
        self.component_id: Optional[str] = component_id
        self.component_type: Optional[str] = component_type
        self.job_id: Optional[str] = job_id
        self.context: Dict[str, Any] = { "run_id": run_id }
        self.sources: Dict[str, Any] = {}
        self.renderer: VariableRenderer = VariableRenderer(self.resolve_source)
        self.event_notifier: ComponentActionEventNotifier = self._build_event_notifier()

    def register_source(self, key: str, source: Any) -> None:
        self.sources[key] = source

    async def render_variable(self, value: Any) -> Any:
        return await self.renderer.render(value)

    async def render_image(self, value: Any) -> Any:
        return await ImageValueRenderer().render(await self.render_variable(value))

    async def render_audio(self, value: Any) -> Any:
        return await AudioValueRenderer().render(await self.render_variable(value))

    async def render_video(self, value: Any) -> Any:
        return await VideoValueRenderer().render(await self.render_variable(value))

    async def render_file(self, value: Any) -> Any:
        return await FileValueRenderer().render(await self.render_variable(value))

    async def render_size(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        return await SizeValueRenderer().render(await self.render_variable(value), default)

    def contains_variable_reference(self, key: str, value: Any) -> bool:
        return self.renderer.contains_reference(key, value)

    async def resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
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
            return gateway.get_context(int(port))

        return None

    def _build_event_notifier(self) -> ComponentActionEventNotifier:
        return ComponentActionEventNotifier(
            self.workflow.component_event_notifier if self.workflow else None,
            self.component_id,
            self.component_type,
            self.job_id,
            self.run_id
        )
