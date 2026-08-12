from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, CrisperWhisperSpeechToTextModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, CrisperWhisperSpeechToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.logger import logging
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import SpeechToTextTaskAction

if TYPE_CHECKING:
    from crisperwhisper import CrisperWhisperModel
    import numpy as np
    import torch

# Model shorthand accepted by CrisperWhisperModel(...). Passed through verbatim
# so users can also give a full HuggingFace id like "nyralabs/CrisperWhisper2.0_large".
_MODEL_SHORTHANDS = {
    "large", "turbo", "medium", "small", "large_pro", "turbo_pro", "medium_pro", "small_pro",
}

class CrisperWhisperSpeechToTextTaskAction(SpeechToTextTaskAction):
    def __init__(
        self,
        config: CrisperWhisperSpeechToTextModelActionConfig,
        model: CrisperWhisperModel,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model: CrisperWhisperModel = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        transcribe_params: Dict[str, Any] = await self._resolve_transcribe_params(context)

        # CrisperWhisper's transcribe() requires a language; default to English
        # when the user did not specify one (matches the package's own default).
        transcribe_params["language"] = params["language"] or "en"

        # word_timestamps is required whenever the caller asked for timestamps
        # at any level (the package returns a per-word list; segment-level is
        # derived from it here).
        transcribe_params["word_timestamps"] = bool(params["return_timestamps"])

        params["transcribe"] = transcribe_params

        return params

    async def _resolve_transcribe_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        mode                     = await context.render_variable(self.config.mode)
        hotwords                 = await context.render_variable(self.config.hotwords)
        longform_strategy        = await context.render_variable(self.config.longform_strategy)
        speculative_decoding     = await context.render_scalar(self.config.speculative_decoding, bool)
        speculative_mode         = await context.render_variable(self.config.speculative_mode)
        hallucination_mitigation = await context.render_scalar(self.config.hallucination_mitigation, bool)
        temperature_fallback     = await context.render_scalar(self.config.temperature_fallback, bool)

        params: Dict[str, Any] = {
            "hallucination_mitigation": hallucination_mitigation,
            "temperature_fallback":     temperature_fallback,
            "speculative_decoding":     speculative_decoding,
        }

        params.update(await self._resolve_generation_params(context))

        if mode is not None:
            params["mode"] = mode
        if hotwords:
            params["hotwords"] = list(hotwords)
        if longform_strategy is not None:
            params["longform_strategy"] = longform_strategy
        if speculative_mode is not None:
            params["speculative_mode"] = speculative_mode

        return params

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        chunk_duration    = await context.render_scalar(self.config.params.chunk_duration, float)
        stride            = await context.render_scalar(self.config.params.stride, float)
        context_words     = await context.render_scalar(self.config.params.context_words, int)
        drop_words        = await context.render_scalar(self.config.params.drop_words, int)
        max_output_length = await context.render_scalar(self.config.params.max_output_length, int)

        params: Dict[str, Any] = {}

        if chunk_duration is not None:
            params["chunk_duration"] = chunk_duration
        if stride is not None:
            params["stride"] = stride
        if context_words is not None:
            params["context_words"] = context_words
        if drop_words is not None:
            params["drop_words"] = drop_words
        if max_output_length is not None:
            params["max_new_tokens"] = max_output_length

        return params

    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]], List[List[Dict[str, Any]]], List[AsyncIterator[Dict[str, Any]]]]:
        waveforms = await self._preprocess_audio(audios)

        return_timestamps = params["return_timestamps"]
        timestamp_level   = params["timestamp_level"]
        transcribe_params = params["transcribe"]

        def _transcribe() -> Union[List[str], List[List[Dict[str, Any]]]]:
            # CrisperWhisper decodes one waveform per call — the package has no
            # batched transcribe() entry point.
            results: List[Any] = []

            for waveform in waveforms:
                result = self.model.transcribe(waveform, sr=16000, **transcribe_params)

                if return_timestamps:
                    results.append(self._build_segments(result, timestamp_level))
                else:
                    results.append(result.text)

            return results

        results = await self._run_in_executor(_transcribe)

        # CrisperWhisper has no token-level streaming; re-emit each collected
        # result as an async iterator so the caller can consume it via `async for`.
        if streaming:
            streams: List[AsyncIterator[Any]] = []
            for result in results:
                async def _stream_chunk_generator(result=result):
                    if isinstance(result, list):
                        for segment in result:
                            yield segment
                    else:
                        yield result
                streams.append(_stream_chunk_generator())
            return streams

        return results

    def _build_segments(self, result: Any, timestamp_level: str) -> List[Dict[str, Any]]:
        # result.chunks is populated on longform (>30s) transcriptions; on
        # short-form it is None and we fall back to a single segment covering
        # the whole utterance.
        chunks = result.chunks or []
        words  = result.words or []

        if not chunks:
            return [ self._build_segment(
                text=result.text,
                start_time=float(words[0].start) if words else 0.0,
                end_time=float(words[-1].end) if words else float(result.duration or 0.0),
                words=words if timestamp_level == "word" else None,
            ) ]

        segments: List[Dict[str, Any]] = []
        word_cursor = 0
        for chunk in chunks:
            chunk_start = float(chunk.start_sec)
            chunk_end   = float(chunk.end_sec)

            chunk_words: Optional[List[Any]] = None
            if timestamp_level == "word":
                # Words come back as a flat list with global timestamps; partition
                # them onto chunks by walking in order — cheaper than repeated
                # scanning and preserves ordering when chunk boundaries fall
                # mid-word (the word is assigned to the chunk it started in).
                chunk_words = []
                while word_cursor < len(words) and float(words[word_cursor].start) < chunk_end:
                    chunk_words.append(words[word_cursor])
                    word_cursor += 1

            segments.append(self._build_segment(
                text=chunk.text,
                start_time=chunk_start,
                end_time=chunk_end,
                words=chunk_words,
            ))

        return segments

    @staticmethod
    def _build_segment(
        text: str,
        start_time: float,
        end_time: float,
        words: Optional[List[Any]],
    ) -> Dict[str, Any]:
        segment: Dict[str, Any] = {
            "text":       text,
            "start_time": start_time,
            "end_time":   end_time,
        }

        if words is not None:
            segment["words"] = [
                {
                    "text":       word.word,
                    "start_time": float(word.start),
                    "end_time":   float(word.end),
                }
                for word in words
            ]

        return segment

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            audio = await AudioBufferStreamer(audio, sample_rate=16000, channel="mono").collect()
            waveforms.append(audio.waveform)

        return waveforms


class CrisperWhisperSpeechToTextTaskService(ModelTaskService):
    config: CrisperWhisperSpeechToTextModelComponentConfig

    def __init__(self, id: str, config: CrisperWhisperSpeechToTextModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[CrisperWhisperModel] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        # `crisperwhisper[transformers]` covers the portable pure-torch backend;
        # users who want the ct2 (Linux NVIDIA) fast path can install
        # crisperwhisper[ct2] separately.
        return [ "crisperwhisper[transformers]", "torchaudio", "soxr" ]

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[CrisperWhisperModel, torch.device]:
        from crisperwhisper import CrisperWhisperModel

        if isinstance(self.config.model, HuggingfaceModelConfig) and self.config.model.repository in _MODEL_SHORTHANDS:
            # CrisperWhisperModel resolves shorthands ("large", "turbo", ...) to
            # nyralabs/CrisperWhisper2.0_<size> itself, so skip our provisioner.
            model_path = self.config.model.repository
        else:
            model_path = await self._provision_model(self.config.model, prefetch=True)

        device = self._resolve_device(self.config.device)
        backend = self._resolve_backend()

        model = CrisperWhisperModel(
            model_path,
            backend=backend,
            compute_type=self._resolve_compute_type(device, backend),
            device=device.type,
            device_index=device.index if device.index is not None else 0,
            draft_model=self.config.draft_model,
        )

        return model, device

    def _resolve_backend(self) -> str:
        # The 'ct2' backend requires the ctranslate2-crisperwhisper fork
        # (Linux x86_64 NVIDIA wheels only); upstream ctranslate2 lacks the
        # CrisperWhisper APIs and fails at model construction. When the user
        # asked for 'auto' we probe for those APIs and silently fall back to
        # 'transformers' so macOS/Windows/upstream setups still work.
        if self.config.backend != "auto":
            return self.config.backend

        if self._has_ct2_fork():
            return "ct2"

        logging.info(
            f"Component '{self.id}': ctranslate2-crisperwhisper fork not found; "
            "falling back to the 'transformers' backend."
        )
        return "transformers"

    def _resolve_compute_type(self, device: torch.device, backend: str) -> str:
        # CTranslate2 rejects float16 on CPU; float16 is the recommended type on
        # cuda/mps GPUs. Let users override by setting compute_type to anything
        # other than "auto".
        if self.config.compute_type != "auto":
            return self.config.compute_type

        if backend == "ct2":
            return "float16" if device.type == "cuda" else "int8"

        # transformers backend accepts torch dtype names; float16 works on
        # cuda/mps, cpu wants float32.
        return "float16" if device.type in ("cuda", "mps") else "float32"

    @staticmethod
    def _has_ct2_fork() -> bool:
        # The ctranslate2-crisperwhisper fork adds several APIs to Whisper as a
        # set (prefill, forward_step, set_alignment_heads,
        # generate_greedy_with_attention). Probing one fork-only API is enough
        # to tell fork from upstream — crisperwhisper itself will hard-fail
        # inside CT2Engine if a partial install ever slips through.
        try:
            from ctranslate2.models import Whisper
        except ImportError:
            return False

        return hasattr(Whisper, "generate_greedy_with_attention")

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await CrisperWhisperSpeechToTextTaskAction(action, self.model, self.device).run(context)
