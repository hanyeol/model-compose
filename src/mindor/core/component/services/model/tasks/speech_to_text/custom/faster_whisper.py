from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Iterator, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, FasterWhisperSpeechToTextModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, FasterWhisperSpeechToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.streamer import SyncGeneratorStreamer
from ......base import ComponentActionContext
from ..common import SpeechToTextTaskService, SpeechToTextTaskAction
import asyncio

if TYPE_CHECKING:
    from faster_whisper import WhisperModel
    import numpy as np
    import torch

class FasterWhisperSpeechToTextTaskAction(SpeechToTextTaskAction):
    def __init__(
        self,
        config: FasterWhisperSpeechToTextModelActionConfig,
        model: WhisperModel,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.model: WhisperModel = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        task         = await context.render_variable(self.config.task) if self.config.task is not None else None
        chunk_length = await context.render_variable(self.config.chunk_length) if self.config.chunk_length is not None else None

        transcribe_params: Dict[str, Any] = await self._resolve_transcribe_params(context)
        transcribe_params["return_timestamps"] = params["return_timestamps"]

        if params["language"] is not None:
            transcribe_params["language"] = params["language"]

        if task is not None:
            transcribe_params["task"] = task

        if chunk_length is not None:
            transcribe_params["chunk_length"] = int(chunk_length)

        # faster-whisper always emits segment start/end; only word-level alignment needs a flag.
        if params["return_timestamps"] and params["timestamp_level"] == "word":
            transcribe_params["word_timestamps"] = True

        params["transcribe"] = transcribe_params

        return params

    async def _resolve_transcribe_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_beams                   = await context.render_variable(self.config.params.num_beams)
        temperature                 = await context.render_variable(self.config.params.temperature)
        compression_ratio_threshold = await context.render_variable(self.config.params.compression_ratio_threshold)
        logprob_threshold           = await context.render_variable(self.config.params.logprob_threshold)
        no_speech_threshold         = await context.render_variable(self.config.params.no_speech_threshold)

        params: Dict[str, Any] = {
            "beam_size": num_beams,
        }

        if temperature is not None:
            params["temperature"] = temperature

        if compression_ratio_threshold is not None:
            params["compression_ratio_threshold"] = compression_ratio_threshold
        if logprob_threshold is not None:
            params["log_prob_threshold"] = logprob_threshold
        if no_speech_threshold is not None:
            params["no_speech_threshold"] = no_speech_threshold

        return params

    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]], List[List[Dict[str, Any]]], List[AsyncIterator[Dict[str, Any]]]]:
        loop = asyncio.get_running_loop()

        waveforms = await self._preprocess_audio(audios)

        transcribe_params = dict(params["transcribe"])
        return_timestamps = transcribe_params.pop("return_timestamps", False)

        if streaming:
            # faster_whisper yields segments synchronously; wrap each iterator so
            # the caller can consume it via ``async for``.
            return [
                SyncGeneratorStreamer(self._transcribe_stream(waveform, transcribe_params, return_timestamps), loop)
                for waveform in waveforms
            ]

        def _transcribe() -> Union[List[str], List[List[Dict[str, Any]]]]:
            return [ self._transcribe_full(waveform, transcribe_params, return_timestamps) for waveform in waveforms ]

        return await self._run_in_executor(_transcribe)

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            waveform, _ = await AudioBufferStreamer(audio, sample_rate=16000, channel="mono").collect()
            waveforms.append(waveform)

        return waveforms

    def _transcribe_full(
        self,
        waveform: np.ndarray,
        params: Dict[str, Any],
        return_timestamps: Union[bool, str],
    ) -> Union[str, List[Dict[str, Any]]]:
        segments, _ = self.model.transcribe(waveform, **params)
        if return_timestamps:
            return [ self._to_transcript_segment(segment) for segment in segments ]
        return "".join(segment.text for segment in segments)

    def _transcribe_stream(
        self,
        waveform: np.ndarray,
        params: Dict[str, Any],
        return_timestamps: Union[bool, str],
    ) -> Iterator[Union[str, Dict[str, Any]]]:
        segments, _ = self.model.transcribe(waveform, **params)
        for segment in segments:
            yield self._to_transcript_segment(segment) if return_timestamps else segment.text

    def _to_transcript_segment(self, segment: Any) -> Dict[str, Any]:
        words = getattr(segment, "words", None)
        return {
            "text":       segment.text,
            "start_time": float(segment.start),
            "end_time":   float(segment.end),
            "words": [
                {
                    "text":        word.word,
                    "start_time":  float(word.start),
                    "end_time":    float(word.end),
                    "probability": float(word.probability) if word.probability is not None else None,
                }
                for word in words
            ] if words else None,
        }

class FasterWhisperSpeechToTextTaskService(SpeechToTextTaskService):
    config: FasterWhisperSpeechToTextModelComponentConfig

    def __init__(self, id: str, config: FasterWhisperSpeechToTextModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[WhisperModel] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "faster-whisper", "torch", "torchaudio", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[WhisperModel, torch.device]:
        from faster_whisper import WhisperModel

        device = self._resolve_device(self.config.device)
        model_path = self._get_model_path()
        model = WhisperModel(model_path, device=str(device.type), compute_type=self.config.compute_type)

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await FasterWhisperSpeechToTextTaskAction(action, self.model, self.device).run(context)
