from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Dict, Optional, List, Iterator, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, FasterWhisperSpeechToTextModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, FasterWhisperSpeechToTextModelActionConfig
from mindor.dsl.schema.action.impl.model.tasks.speech_to_text.impl.custom.faster_whisper import FasterWhisperVadParametersConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.streamer import SyncGeneratorStreamer
from ......base import ComponentActionContext
from ....base import ModelTaskDriver
from ..common import SpeechToTextTaskAction
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

        task         = await context.render_variable(self.config.task)
        chunk_length = await context.render_scalar(self.config.chunk_length, int)

        transcribe_params: Dict[str, Any] = await self._resolve_transcribe_params(context)

        if params["language"] is not None:
            transcribe_params["language"] = params["language"]

        if task is not None:
            transcribe_params["task"] = task

        if chunk_length is not None:
            transcribe_params["chunk_length"] = chunk_length

        if params["span"] is not None:
            transcribe_params["clip_timestamps"] = self._build_clip_timestamps(params["span"])

        # faster-whisper always emits segment start/end; only word-level alignment needs a flag.
        if params["return_timestamps"] and params["timestamp_level"] == "word":
            transcribe_params["word_timestamps"] = True

        params["transcribe"] = transcribe_params

        return params

    async def _resolve_transcribe_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_beams                   = await context.render_variable(self.config.params.num_beams)
        temperature                 = await context.render_variable(self.config.params.temperature)
        compression_ratio_threshold = await context.render_variable(self.config.params.compression_ratio_threshold)
        log_prob_threshold          = await context.render_variable(self.config.params.log_prob_threshold)
        no_speech_threshold         = await context.render_variable(self.config.params.no_speech_threshold)
        vad_filter                  = await context.render_scalar(self.config.params.vad_filter, bool)
        vad_parameters              = await self._resolve_vad_parameters(self.config.params.vad_parameters, context) if self.config.params.vad_parameters is not None else None
        condition_on_previous_text  = await context.render_scalar(self.config.params.condition_on_previous_text, bool)

        params: Dict[str, Any] = {
            "beam_size": num_beams,
        }

        if temperature is not None:
            params["temperature"] = temperature

        if compression_ratio_threshold is not None:
            params["compression_ratio_threshold"] = compression_ratio_threshold

        if log_prob_threshold is not None:
            params["log_prob_threshold"] = log_prob_threshold

        if no_speech_threshold is not None:
            params["no_speech_threshold"] = no_speech_threshold

        if vad_filter is not None:
            params["vad_filter"] = vad_filter

        if vad_parameters is not None:
            params["vad_parameters"] = vad_parameters

        if condition_on_previous_text is not None:
            params["condition_on_previous_text"] = condition_on_previous_text

        return params

    async def _resolve_vad_parameters(self, config: FasterWhisperVadParametersConfig, context: ComponentActionContext) -> Optional[Dict[str, Any]]:
        threshold               = await context.render_scalar(config.threshold, float)
        neg_threshold           = await context.render_scalar(config.neg_threshold, float)
        min_speech_duration_ms  = await context.render_scalar(config.min_speech_duration_ms, int)
        max_speech_duration_s   = await context.render_scalar(config.max_speech_duration_s, float)
        min_silence_duration_ms = await context.render_scalar(config.min_silence_duration_ms, int)
        speech_pad_ms           = await context.render_scalar(config.speech_pad_ms, int)

        params: Dict[str, Any] = {}

        if threshold is not None:
            params["threshold"] = threshold

        if neg_threshold is not None:
            params["neg_threshold"] = neg_threshold

        if min_speech_duration_ms is not None:
            params["min_speech_duration_ms"] = min_speech_duration_ms

        if max_speech_duration_s is not None:
            params["max_speech_duration_s"] = max_speech_duration_s

        if min_silence_duration_ms is not None:
            params["min_silence_duration_ms"] = min_silence_duration_ms

        if speech_pad_ms is not None:
            params["speech_pad_ms"] = speech_pad_ms

        return params or None

    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]], List[List[Dict[str, Any]]], List[AsyncIterator[Dict[str, Any]]]]:
        waveforms = await self._preprocess_audio(audios)

        transcribe_params = params["transcribe"]
        return_timestamps = params["return_timestamps"]

        if streaming:
            # faster_whisper yields segments synchronously; wrap each iterator so
            # the caller can consume it via ``async for``.
            return [
                SyncGeneratorStreamer(self._transcribe_stream(waveform, transcribe_params, return_timestamps), asyncio.get_running_loop())
                for waveform in waveforms
            ]

        def _transcribe() -> Union[List[str], List[List[Dict[str, Any]]]]:
            return [ self._transcribe_full(waveform, transcribe_params, return_timestamps) for waveform in waveforms ]

        return await self._run_in_executor(_transcribe)

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            audio = await AudioBufferStreamer(audio, sample_rate=16000, channel="mono").collect()
            waveforms.append(audio.waveform)

        return waveforms

    def _transcribe_full(
        self,
        waveform: np.ndarray,
        params: Dict[str, Any],
        return_timestamps: Union[bool, str],
    ) -> Union[str, List[Dict[str, Any]]]:
        segments, _ = self.model.transcribe(waveform, **params)

        if return_timestamps:
            return [ self._build_segment(segment) for segment in segments ]

        return "".join(segment.text for segment in segments)

    def _transcribe_stream(
        self,
        waveform: np.ndarray,
        params: Dict[str, Any],
        return_timestamps: Union[bool, str],
    ) -> Iterator[Union[str, Dict[str, Any]]]:
        segments, _ = self.model.transcribe(waveform, **params)

        for segment in segments:
            yield { "type": "segment", **self._build_segment(segment) } if return_timestamps else segment.text

    def _build_segment(self, segment: Any) -> Dict[str, Any]:
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

    def _build_clip_timestamps(self, span: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[float]:
        spans = span if isinstance(span, list) else [ span ]
        timestamps: List[float] = []

        for span in spans:
            timestamps.append(parse_time(span["start_time"]))
            timestamps.append(parse_time(span["end_time"]))

        return timestamps

class FasterWhisperSpeechToTextTaskDriver(ModelTaskDriver):
    config: FasterWhisperSpeechToTextModelComponentConfig

    def __init__(self, id: str, config: FasterWhisperSpeechToTextModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[WhisperModel] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ *torch_requirements("torch", "torchaudio"), "faster-whisper", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[WhisperModel, torch.device]:
        from faster_whisper import WhisperModel

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        def _load() -> WhisperModel:
            return WhisperModel(
                model_path,
                device=str(device.type),
                compute_type=self.config.compute_type
            )

        model = await self._run_in_executor(_load)

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await FasterWhisperSpeechToTextTaskAction(action, self.model, self.device).run(context)
