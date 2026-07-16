from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Tuple, Iterator, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VoiceActivityDetectionModelActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.streamer import SyncGeneratorStreamer
from mindor.core.foundation.variable.time import parse_duration
from ...base import ModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import torch

class VoiceSegmenter:
    """Online frame-by-frame VAD state machine with hysteresis and duration
    filtering. Feed frame-level speech probabilities via :meth:`feed`; call
    :meth:`flush` at end of stream to drain any trailing unconfirmed segment.

    Common to all VAD backends (Silero, WebRTC, pyannote, ...) that expose
    per-frame speech probabilities: a segment starts when `prob >= threshold`,
    ends after `min_silence_samples` of `prob < neg_threshold`, and is emitted
    only if it exceeds `min_speech_samples`.
    """
    def __init__(
        self,
        threshold: float,
        neg_threshold: float,
        min_speech_samples: int,
        min_silence_samples: int,
        speech_pad_samples: int,
    ):
        self.threshold = threshold
        self.neg_threshold = neg_threshold
        self.min_speech_samples = min_speech_samples
        self.min_silence_samples = min_silence_samples
        self.speech_pad_samples = speech_pad_samples

        self.triggered: bool = False
        self.speech_start: Optional[int] = None
        self.temp_end: int = 0
        self.probs_in_segment: List[float] = []

    def feed(self, prob: float, offset: int) -> Optional[Tuple[int, int, List[float]]]:
        """Return (speech_start, speech_end, probs) if a segment was just confirmed."""
        # Speech resumed inside a candidate silence: cancel the pending end.
        if prob >= self.threshold and self.temp_end:
            self.temp_end = 0

        # Start of speech.
        if prob >= self.threshold and not self.triggered:
            self.triggered = True
            self.speech_start = offset
            self.probs_in_segment = [prob]
            return None

        if not self.triggered:
            return None

        self.probs_in_segment.append(prob)

        # Silence while in speech: arm a candidate end, confirm once it grows past min_silence.
        if prob >= self.neg_threshold:
            return None

        if not self.temp_end:
            self.temp_end = offset
            return None

        if offset - self.temp_end < self.min_silence_samples:
            return None

        segment: Optional[Tuple[int, int, List[float]]] = None
        speech_end = self.temp_end

        if speech_end - self.speech_start > self.min_speech_samples:
            segment = (self.speech_start, speech_end, self.probs_in_segment)

        self.triggered = False
        self.speech_start = None
        self.temp_end = 0
        self.probs_in_segment = []

        return segment

    def flush(self, audio_length: int) -> Optional[Tuple[int, int, List[float]]]:
        """At end-of-stream, return the trailing unconfirmed segment if any."""
        if not (self.triggered and self.speech_start is not None):
            return None

        if audio_length - self.speech_start <= self.min_speech_samples:
            return None

        return (self.speech_start, audio_length, self.probs_in_segment)

class VoiceActivityDetectionTaskAction:
    def __init__(self, config: VoiceActivityDetectionModelActionConfig, device: Optional[torch.device]):
        self.config: VoiceActivityDetectionModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._detect(batch_audios, params, streaming, loop)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(generator=result, scope=f"stream:{id(result)}"):
                                iterator = generator if isinstance(generator, AsyncIterator) else SyncGeneratorStreamer(generator, loop)
                                async for chunk in iterator:
                                    if chunk:
                                        context.register_source("result[]", chunk, scope=scope)
                                        yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._detect(batch_audios, params, streaming, loop)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(generator=result, scope=f"stream:{id(result)}"):
                            iterator = generator if isinstance(generator, AsyncIterator) else SyncGeneratorStreamer(generator, loop)
                            async for chunk in iterator:
                                if chunk:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        sample_rate          = await context.render_variable(self.config.sample_rate)
        threshold            = await context.render_variable(self.config.params.threshold)
        min_speech_duration  = parse_duration(await context.render_variable(self.config.params.min_speech_duration))
        min_silence_duration = parse_duration(await context.render_variable(self.config.params.min_silence_duration))
        speech_padding_time  = parse_duration(await context.render_variable(self.config.params.speech_padding_time))

        return {
            "sample_rate":          sample_rate,
            "threshold":            threshold,
            "min_speech_duration":  min_speech_duration,
            "min_silence_duration": min_silence_duration,
            "speech_padding_time":  speech_padding_time,
        }

    @abstractmethod
    async def _detect(self, audios: List[MediaSource], params: Dict[str, Any], streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[List[Dict[str, Any]]], List[Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]]]:
        pass

class VoiceActivityDetectionTaskService(ModelTaskService):
    pass
