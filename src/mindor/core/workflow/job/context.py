from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.foundation.variable.image import ImageValueRenderer
from mindor.core.foundation.variable.audio import AudioValueRenderer
from mindor.core.foundation.variable.video import VideoValueRenderer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.workflow.context import WorkflowContext
from PIL import Image as PILImage

class JobContext:
    def __init__(self, workflow: WorkflowContext, job_id: str, is_terminal: bool = False):
        self.workflow: WorkflowContext = workflow
        self.job_id: str = job_id
        self.is_terminal: bool = is_terminal

        self._sources: Dict[str, Dict[str, Any]] = { "__global__": {} }
        self._renderer: VariableRenderer = VariableRenderer(self.resolve_source)

    @property
    def cancellation_token(self) -> Optional[CancellationToken]:
        return self.workflow.cancellation_token if self.workflow else None

    def register_source(self, run_id: Optional[str], key: str, source: Any) -> None:
        self._sources.setdefault(run_id or "__global__", {})[key] = source

    async def render_variable(
        self,
        run_id: Optional[str],
        value: Any,
        skip_decode: bool = False
    ) -> Any:
        if value is not None:
            return await self._renderer.render(value, run_id, skip_decode=skip_decode)

        return None

    async def render_image(
        self,
        run_id: Optional[str],
        value: Any
    ) -> Optional[Union[PILImage.Image, List[Optional[PILImage.Image]], AsyncIterator[Optional[PILImage.Image]]]]:
        return await ImageValueRenderer().render(await self.render_variable(run_id, value))

    async def render_audio(
        self,
        run_id: Optional[str],
        value: Any
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        return await AudioValueRenderer().render(await self.render_variable(run_id, value))

    async def render_video(
        self,
        run_id: Optional[str],
        value: Any
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        return await VideoValueRenderer().render(await self.render_variable(run_id, value))

    async def resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        sources = self._sources.get(scope or "__global__", {})

        if key in sources:
            return sources[key][index] if index is not None else sources[key]

        return await self.workflow.resolve_source(key, index, None)
