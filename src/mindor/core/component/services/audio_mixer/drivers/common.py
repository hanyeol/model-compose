from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator, Iterator
from abc import abstractmethod
from mindor.dsl.schema.action import (
    AudioMixerActionConfig,
    AudioMixerActionMethod,
    AudioMixerOverlayDurationMode,
    AudioOverlayPlacement,
)
from mindor.core.foundation.media.encoding import AudioEncoderParams
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.audio import AudioArrayValue
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ....action.media import VideoAudioEncodingResolver
from ..base import ComponentActionContext
import asyncio

class AudioMixerAction(ComponentAction):
    def __init__(self, config: AudioMixerActionConfig):
        self.config: AudioMixerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_scalar(self.config.streaming, bool, False)

        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(self.config.method, batch_inputs, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[AudioStreamResource] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_results = await self._process_batch(self.config.method, batch_inputs, params, streaming, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: AudioMixerActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        if method == AudioMixerActionMethod.CONCAT:
            audios = await context.render_audio_array(self.config.audios)

            is_single_input    = isinstance(audios, AudioArrayValue)
            is_streaming_input = isinstance(audios, (StreamIterator, AsyncIterator))

            return audios, is_single_input, is_streaming_input

        if method == AudioMixerActionMethod.OVERLAY:
            audio     = await context.render_audio(self.config.audio)
            overlay   = await context.render_audio_array(self.config.overlay, single_as_array=True)
            placement = await self._render_overlay_placement(context)

            is_single_input    = not isinstance(audio, (list, StreamIterator, AsyncIterator))
            is_streaming_input = isinstance(audio, (StreamIterator, AsyncIterator))

            return (audio, overlay, placement), is_single_input, is_streaming_input

        raise ValueError(f"Unsupported audio mixer action method: {method}")

    async def _resolve_params(
        self,
        method: AudioMixerActionMethod,
        context: ComponentActionContext,
    ) -> Dict[str, Any]:
        if method == AudioMixerActionMethod.CONCAT:
            format    = await context.render_scalar(self.config.format, str)
            encoding  = await VideoAudioEncodingResolver().resolve_audio(context, self.config.encoding) if self.config.encoding else AudioEncoderParams()
            crossfade = await context.render_scalar(self.config.crossfade, "time")

            return {
                "format":    format,
                "encoding":  encoding,
                "crossfade": crossfade,
            }

        if method == AudioMixerActionMethod.OVERLAY:
            format        = await context.render_scalar(self.config.format, str)
            encoding      = await VideoAudioEncodingResolver().resolve_audio(context, self.config.encoding) if self.config.encoding else AudioEncoderParams()
            duration_mode = await context.render_variable(self.config.duration_mode)

            try:
                duration_mode = AudioMixerOverlayDurationMode(duration_mode)
            except ValueError:
                raise ValueError(f"Invalid duration_mode: {duration_mode}")

            return {
                "format":        format,
                "encoding":      encoding,
                "duration_mode": duration_mode,
            }

        raise ValueError(f"Unsupported audio mixer action method: {method}")

    async def _process_batch(
        self,
        method: AudioMixerActionMethod,
        inputs: Any,
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[AudioStreamResource]:
        if method in (AudioMixerActionMethod.OVERLAY, ):
            inputs = list(zip(*inputs))

        return await asyncio.gather(*[
            self._process(method, input, params, streaming, cancellation_token) for input in inputs
        ])

    async def _process(
        self,
        method: AudioMixerActionMethod,
        input: Any,
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AudioStreamResource:
        if method == AudioMixerActionMethod.CONCAT:
            audios = await input.collect()

            if len(audios) < 2:
                raise ValueError("concat requires at least two audios.")

            return await self._concat(audios, params, streaming, cancellation_token)

        if method == AudioMixerActionMethod.OVERLAY:
            audio, overlays, placements = input
            overlays, placements = await asyncio.gather(overlays.collect(), placements.collect())

            # Broadcast a single placement across all overlays; otherwise pair by position.
            if len(placements) == 1 and len(overlays) > 1:
                placements = [ placements[0] ] * len(overlays)

            if len(placements) != len(overlays):
                raise ValueError(
                    f"overlay/placement cardinality mismatch: {len(overlays)} overlays vs {len(placements)} placements."
                )

            return await self._overlay(
                audio,
                overlays,
                placements,
                params,
                streaming,
                cancellation_token,
            )

        raise ValueError(f"Unsupported audio mixer action method: {method}")

    async def _render_overlay_placement(self, context: ComponentActionContext) -> ArrayValue:
        """Resolve the overlay `placement` field into an `ArrayValue` of placements paired with overlays.

        `self.config.placement` may be a single `AudioOverlayPlacement`, a
        list of placements, a template string, or a list of template strings.
        `render_array` with `single_as_array=True` renders any template refs
        and normalizes single values into a one-element `ArrayValue`, so
        downstream always sees an iterable of placement entries. `ArrayValue`
        isn't seen as iterable by `BatchSourceIterator`, so the placements
        travel as a single unit alongside the base audio instead of being
        consumed element-by-element.
        """
        placement = await context.render_array(self.config.placement, single_as_array=True)

        if placement is None:
            return ArrayValue([ AudioOverlayPlacement() ])

        return ArrayValue([ self._as_overlay_placement(item) async for item in placement ])

    @staticmethod
    def _as_overlay_placement(value: Any) -> AudioOverlayPlacement:
        if isinstance(value, AudioOverlayPlacement):
            return value

        if isinstance(value, dict):
            return AudioOverlayPlacement.model_validate(value)

        raise ValueError(f"'placement' entry must be a placement object or dict, got {type(value).__name__}")

    @abstractmethod
    async def _concat(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AudioStreamResource:
        pass

    @abstractmethod
    async def _overlay(
        self,
        audio: MediaSource,
        overlays: List[MediaSource],
        placements: List[AudioOverlayPlacement],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AudioStreamResource:
        pass
