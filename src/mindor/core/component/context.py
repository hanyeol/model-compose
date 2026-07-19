from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.foundation.variable.image import ImageValueRenderer
from mindor.core.foundation.variable.audio import AudioValueRenderer
from mindor.core.foundation.variable.video import VideoValueRenderer
from mindor.core.foundation.variable.media import MediaValueRenderer
from mindor.core.foundation.variable.file import FileValueRenderer
from mindor.core.foundation.variable.text import TextValueRenderer
from mindor.core.foundation.variable.size import SizeValueRenderer
from mindor.core.foundation.variable.color import ColorValueRenderer, Color
from mindor.core.foundation.variable.array import ArrayValueRenderer, ArrayValue
from mindor.core.foundation.variable.vector import VectorValueRenderer, VectorValue
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.gateway import find_gateway_by_port
from PIL import Image as PILImage

if TYPE_CHECKING:
    from mindor.core.workflow.context import WorkflowContext
    from mindor.core.workflow.notifiers import ComponentEventNotifier

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
        self.sources: Dict[str, Dict[str, Any]] = { "__global__": {} }
        self.renderer: VariableRenderer = VariableRenderer(self.resolve_source)
        self.event_notifier: ComponentActionEventNotifier = self._build_event_notifier()

    @property
    def cancellation_token(self) -> Optional[CancellationToken]:
        return self.workflow.cancellation_token if self.workflow else None

    def register_source(self, key: str, source: Any, scope: Optional[str] = None) -> None:
        self.sources.setdefault(scope or "__global__", {})[key] = source

    async def render_variable(self, value: Any, scope: Optional[str] = None, skip_decode: bool = False) -> Any:
        return await self.renderer.render(value, scope, skip_decode=skip_decode)

    async def render_text(self, value: Any) -> Optional[Union[str, List[Optional[str]], AsyncIterator[Optional[str]]]]:
        return await TextValueRenderer().render(await self.render_variable(value))

    async def render_image(self, value: Any) -> Union[PILImage.Image, List[PILImage.Image], AsyncIterator[PILImage.Image]]:
        return await ImageValueRenderer().render(await self.render_variable(value))

    async def render_image_array(self, value: Any) -> Union[List[List[PILImage.Image]], AsyncIterator[List[PILImage.Image]]]:
        return await ImageValueRenderer().render_array(await self.render_variable(value))

    async def render_audio(self, value: Any) -> Union[MediaSource, List[MediaSource]]:
        return await AudioValueRenderer().render(await self.render_variable(value))

    async def render_video(self, value: Any) -> Union[MediaSource, List[MediaSource]]:
        return await VideoValueRenderer().render(await self.render_variable(value))

    async def render_media(self, value: Any) -> Union[MediaSource, List[MediaSource]]:
        return await MediaValueRenderer().render(await self.render_variable(value))

    async def render_file(self, value: Any) -> Any:
        return await FileValueRenderer().render(await self.render_variable(value))

    async def render_vector(self, value: Any) -> Union[VectorValue, List[VectorValue], AsyncIterator[VectorValue]]:
        return await VectorValueRenderer().render(await self.render_variable(value))

    async def render_vector_list(self, value: Any) -> Union[List[VectorValue], AsyncIterator[List[VectorValue]]]:
        return await VectorValueRenderer().render_list(await self.render_variable(value))

    async def render_array(self, value: Any) -> Union[ArrayValue, List[ArrayValue], AsyncIterator[ArrayValue]]:
        return await ArrayValueRenderer().render(await self.render_variable(value))

    async def render_size(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        return await SizeValueRenderer().render(await self.render_variable(value), default)

    async def render_color(self, value: Any, default: Optional[Color] = None) -> Optional[Color]:
        return await ColorValueRenderer().render(await self.render_variable(value), default)

    async def resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        sources = self.sources.get(scope or "__global__", {})

        if key in sources:
            return sources[key][index] if index is not None else sources[key]

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
