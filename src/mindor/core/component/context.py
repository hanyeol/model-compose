from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, TypeVar, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Awaitable, Callable, Any
from collections.abc import AsyncIterator
from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.foundation.variable.image import ImageValueRenderer, ImageArrayValue
from mindor.core.foundation.variable.audio import AudioValueRenderer, AudioBufferValueRenderer, AudioBufferArrayValue
from mindor.core.utils.audio import AudioBuffer
from mindor.core.foundation.variable.video import VideoValueRenderer
from mindor.core.foundation.variable.media import MediaValueRenderer
from mindor.core.foundation.variable.file import FileValueRenderer
from mindor.core.foundation.variable.text import TextValueRenderer
from mindor.core.foundation.variable.size import parse_size
from mindor.core.foundation.variable.time import TimeValueRenderer, parse_time
from mindor.core.foundation.variable.decimal import parse_decimal
from mindor.core.foundation.variable.color import parse_color, Color
from mindor.core.foundation.variable.array import ArrayValueRenderer, ArrayValue
from mindor.core.foundation.variable.vector import VectorValueRenderer, VectorValue, VectorArrayValue
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.gateway import find_gateway_by_port
from PIL import Image as PILImage

if TYPE_CHECKING:
    from mindor.core.workflow.context import WorkflowContext
    from mindor.core.workflow.notifiers import ComponentEventNotifier

ScalarT = TypeVar("ScalarT")

_SCALAR_PARSERS: Dict[str, Callable[[Any], Any]] = {
    "time":     parse_time,
    "size":     parse_size,
    "decimal":  parse_decimal,
    "color":    parse_color,
}

ComponentEventPayload = Dict[str, Any]
ComponentEventCallback = Callable[[ComponentEventPayload], Awaitable[None]]

class ComponentActionEventNotifier:
    def __init__(
        self,
        notifier: Optional[ComponentEventNotifier],
        component_id: Optional[str],
        component_type: Optional[str],
        job_id: Optional[str],
        run_id: Optional[str],
        on_event: Optional[ComponentEventCallback] = None,
    ):
        self.notifier: Optional[ComponentEventNotifier] = notifier
        self.component_id: Optional[str] = component_id
        self.component_type: Optional[str] = component_type
        self.job_id: Optional[str] = job_id
        self.run_id: Optional[str] = run_id
        self.on_event: Optional[ComponentEventCallback] = on_event

    async def notify(
        self,
        event: Literal[ "started", "completed", "cancelled", "failed", "internal" ],
        kind: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        if self.notifier is not None:
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
        if self.on_event is not None:
            await self.on_event({
                "event": event,
                "kind": kind,
                "input": input,
                "output": output,
                "error": error,
            })

class ComponentActionContext:
    def __init__(
        self,
        run_id: str,
        input: Dict[str, Any],
        workflow: Optional[WorkflowContext] = None,
        component_id: Optional[str] = None,
        component_type: Optional[str] = None,
        job_id: Optional[str] = None,
        on_event: Optional[ComponentEventCallback] = None,
    ):
        self.run_id: str = run_id
        self.input: Dict[str, Any] = input
        self.workflow: Optional[WorkflowContext] = workflow
        self.component_id: Optional[str] = component_id
        self.component_type: Optional[str] = component_type
        self.job_id: Optional[str] = job_id
        self.on_event: Optional[ComponentEventCallback] = on_event
        self.context: Dict[str, Any] = { "run_id": run_id }
        self.sources: Dict[str, Dict[str, Any]] = { "__global__": {} }
        self.renderer: VariableRenderer = VariableRenderer(self.resolve_source)
        self.event_notifier: ComponentActionEventNotifier = self._build_event_notifier()

    @property
    def cancellation_token(self) -> Optional[CancellationToken]:
        return self.workflow.cancellation_token if self.workflow else None

    def register_source(self, key: str, source: Any, scope: Optional[str] = None) -> None:
        self.sources.setdefault(scope or "__global__", {})[key] = source

    async def render_variable(
        self,
        value: Any,
        scope: Optional[str] = None,
        skip_decode: bool = False
    ) -> Any:
        if value is not None:
            return await self.renderer.render(value, scope, skip_decode=skip_decode)

        return None

    async def render_text(
        self,
        value: Any,
        collect: bool = True
    ) -> Optional[Union[str, List[Optional[str]], AsyncIterator[Optional[str]]]]:
        return await TextValueRenderer().render(await self.render_variable(value), collect=collect)

    async def render_image(
        self,
        value: Any
    ) -> Optional[Union[PILImage.Image, List[Optional[PILImage.Image]], AsyncIterator[Optional[PILImage.Image]]]]:
        return await ImageValueRenderer().render(await self.render_variable(value))

    async def render_image_array(
        self,
        value: Any
    ) -> Optional[Union[ImageArrayValue, List[Optional[ImageArrayValue]], AsyncIterator[Optional[ImageArrayValue]]]]:
        return await ImageValueRenderer().render_array(await self.render_variable(value))

    async def render_audio(
        self,
        value: Any
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        return await AudioValueRenderer().render(await self.render_variable(value))

    async def render_audio_buffer(
        self,
        value: Any,
        sample_rate: Optional[int] = None,
        channel: Optional[Union[int, Literal["mono"]]] = None
    ) -> Optional[Union[AudioBuffer, List[Optional[AudioBuffer]], AsyncIterator[Optional[AudioBuffer]]]]:
        return await AudioBufferValueRenderer(sample_rate, channel).render(await self.render_variable(value))

    async def render_audio_buffer_array(
        self,
        value: Any,
        sample_rate: Optional[int] = None,
        channel: Optional[Union[int, Literal["mono"]]] = None
    ) -> Optional[Union[AudioBufferArrayValue, List[Optional[AudioBufferArrayValue]], AsyncIterator[Optional[AudioBufferArrayValue]]]]:
        return await AudioBufferValueRenderer(sample_rate, channel).render_array(await self.render_variable(value))

    async def render_video(
        self,
        value: Any
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        return await VideoValueRenderer().render(await self.render_variable(value))

    async def render_media(
        self,
        value: Any
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        return await MediaValueRenderer().render(await self.render_variable(value))

    async def render_file(
        self,
        value: Any
    ) -> Optional[Union[str, List[Optional[str]], AsyncIterator[Optional[str]]]]:
        return await FileValueRenderer().render(await self.render_variable(value))

    async def render_vector(
        self,
        value: Any
    ) -> Optional[Union[VectorValue, List[Optional[VectorValue]], AsyncIterator[Optional[VectorValue]]]]:
        return await VectorValueRenderer().render(await self.render_variable(value))

    async def render_vector_array(
        self,
        value: Any
    ) -> Optional[Union[VectorArrayValue, List[Optional[VectorArrayValue]], AsyncIterator[Optional[VectorArrayValue]]]]:
        return await VectorValueRenderer().render_array(await self.render_variable(value))

    async def render_array(
        self,
        value: Any
    ) -> Optional[Union[ArrayValue, List[Optional[ArrayValue]], AsyncIterator[Optional[ArrayValue]]]]:
        return await ArrayValueRenderer().render(await self.render_variable(value))

    async def render_time(
        self,
        value: Any,
        default: Optional[float] = None
    ) -> Optional[Union[float, List[Optional[float]], AsyncIterator[Optional[float]]]]:
        return await TimeValueRenderer().render(await self.render_variable(value), default)

    async def render_scalar(
        self,
        value: Any,
        caster: Union[Callable[[Any], ScalarT], Literal["time", "size", "decimal", "color"]],
        default: Optional[Union[ScalarT, float, int, Color]] = None
    ) -> Optional[Union[ScalarT, float, int, Color]]:
        value = await self.render_variable(value) if value is not None else None

        if value is not None:
            if isinstance(caster, str):
                return _SCALAR_PARSERS[caster](value)
            return caster(value)

        return default

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
            self.run_id,
            on_event=self.on_event,
        )
