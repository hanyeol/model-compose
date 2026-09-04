from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Iterator, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, VibeVoiceSpeechToTextModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, VibeVoiceSpeechToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.streamer import SyncGeneratorStreamer
from mindor.core.utils.time import parse_timecode
from mindor.core.logger import logging
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import SpeechToTextTaskAction
import asyncio

if TYPE_CHECKING:
    import numpy as np
    import torch

_SAMPLE_RATE = 24000
_DEFAULT_MAX_TOKENS_PER_CHUNK = 256
_DEFAULT_MAX_TOTAL_TOKENS = 32768

class VibeVoiceSpeechToTextTaskAction(SpeechToTextTaskAction):
    def __init__(
        self,
        config: VibeVoiceSpeechToTextModelActionConfig,
        model: Any,
        processor: Any,
        streaming_info: Optional[Dict[str, float]],
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model: Any = model
        self.processor: Any = processor
        self.streaming_info: Optional[Dict[str, float]] = streaming_info

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        context_info      = await context.render_scalar(self.config.context_info, str)
        max_output_length = await context.render_scalar(self.config.max_output_length, int)
        temperature       = await context.render_scalar(self.config.temperature, float)
        top_p             = await context.render_scalar(self.config.top_p, float)
        num_beams         = await context.render_scalar(self.config.num_beams, int)

        # VibeVoice ASR has no `language` argument — the model auto-detects
        # across its 10 supported languages. Warn instead of silently ignoring.
        if params["language"] is not None:
            logging.warning(
                "VibeVoice ASR does not accept a `language` argument; "
                f"ignoring language={params['language']!r}."
            )

        if self.streaming_info is not None and params["return_timestamps"]:
            logging.warning(
                "VibeVoice-ASR-Streaming does not emit timestamps; "
                "`return_timestamps=true` has no effect on this checkpoint."
            )

        params["generation"] = {
            "context_info":      context_info,
            "max_output_length": max_output_length,
            "temperature":       temperature,
            "top_p":             top_p,
            "num_beams":         num_beams,
        }

        return params

    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]], List[List[Dict[str, Any]]], List[AsyncIterator[Dict[str, Any]]]]:
        waveforms = await self._preprocess_audio(audios)

        if self.streaming_info is not None:
            return await self._transcribe_with_streaming_model(waveforms, params, streaming)

        return await self._transcribe_with_offline_model(waveforms, params, streaming)

    async def _transcribe_with_offline_model(
        self,
        waveforms: List[np.ndarray],
        params: Dict[str, Any],
        streaming: bool,
    ) -> Union[List[str], List[List[Dict[str, Any]]], List[AsyncIterator[Any]]]:
        def _transcribe() -> Union[List[str], List[List[Dict[str, Any]]]]:
            import torch

            # Waveforms are already resampled to _SAMPLE_RATE by AudioBufferStreamer;
            # the processor's numpy path uses target_sample_rate as-is (no resample).
            inputs = self.processor(
                audio=list(waveforms),
                return_tensors="pt",
                padding=True,
                add_generation_prompt=True,
                context_info=params["generation"]["context_info"],
            )
            inputs = { key: value.to(self.device) if isinstance(value, torch.Tensor) else value for key, value in inputs.items() }

            with torch.inference_mode():
                output_ids = self.model.generate(**inputs, **self._resolve_generate_kwargs(params["generation"]))

            input_length = inputs["input_ids"].shape[1]
            eos_id = self.processor.tokenizer.eos_token_id

            results: List[Any] = []

            for index in range(output_ids.shape[0]):
                # Strip the prompt prefix, then cut at the first eos so we don't
                # decode padding into the transcript.
                generated_ids = output_ids[index, input_length:]
                eos_positions = (generated_ids == eos_id).nonzero(as_tuple=True)[0]

                if len(eos_positions) > 0:
                    generated_ids = generated_ids[: eos_positions[0] + 1]

                text = self.processor.decode(generated_ids, skip_special_tokens=True)

                if params["return_timestamps"]:
                    results.append(self._build_segments(text))
                else:
                    # VibeVoice-ASR emits structured JSON even without timestamps
                    # asked for; concatenate the transcribed content so callers
                    # that just want plain text get plain text.
                    segments = self.processor.post_process_transcription(text)
                    results.append(" ".join(segment.get("text", "") for segment in segments) if segments else text)

            return results

        results = await self._run_in_executor(_transcribe)

        if streaming:
            # Offline checkpoints have no token-level stream; fake it by re-emitting segments,
            # or the full transcript as one chunk.
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

    async def _transcribe_with_streaming_model(
        self,
        waveforms: List[np.ndarray],
        params: Dict[str, Any],
        streaming: bool,
    ) -> Union[List[str], List[AsyncIterator[str]]]:
        def _transcribe(waveform: np.ndarray) -> Iterator[str]:
            import torch

            audio_tensor = torch.from_numpy(waveform)
            max_new_tokens = params["generation"]["max_output_length"] or _DEFAULT_MAX_TOKENS_PER_CHUNK

            for _, _, chunk_text in self.model.streaming_generate(
                audio_tensor=audio_tensor,
                tokenizer=self.processor.tokenizer,
                chunk_duration=self.streaming_info["chunk_duration"],
                text_audio_delay=self.streaming_info["text_audio_delay"],
                sample_rate=_SAMPLE_RATE,
                max_new_tokens_per_chunk=max_new_tokens,
                temperature=params["generation"]["temperature"],
                context_info=params["generation"]["context_info"],
            ):
                if chunk_text:
                    yield chunk_text

        # streaming_generate yields per-chunk text as the model consumes the audio;
        # wrap it so callers can consume via `async for`.
        if streaming:
            return [ SyncGeneratorStreamer(_transcribe(waveform), asyncio.get_running_loop()) for waveform in waveforms ]

        def _collect() -> List[str]:
            return [ "".join(_transcribe(waveform)) for waveform in waveforms ]

        return await self._run_in_executor(_collect)

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        # VibeVoice checkpoints expect 24 kHz mono; the acoustic tokenizer
        # frame rate (~7.5 Hz) is derived from that sample rate.
        waveforms: List[np.ndarray] = []

        for audio in audios:
            audio = await AudioBufferStreamer(audio, sample_rate=_SAMPLE_RATE, channel="mono").collect()
            waveforms.append(audio.waveform)

        return waveforms

    def _resolve_generate_kwargs(self, generation: Dict[str, Any]) -> Dict[str, Any]:
        max_new_tokens = generation["max_output_length"] or _DEFAULT_MAX_TOTAL_TOKENS
        temperature    = generation["temperature"]
        num_beams      = generation["num_beams"] or 1

        kwargs: Dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id":   self.processor.pad_id,
            "eos_token_id":   self.processor.tokenizer.eos_token_id,
        }

        if num_beams > 1:
            # Beam search rejects sampling kwargs; keep the two branches disjoint.
            kwargs["num_beams"] = num_beams
            kwargs["do_sample"] = False
        else:
            kwargs["do_sample"] = temperature > 0

            if temperature > 0:
                kwargs["temperature"] = temperature
                kwargs["top_p"]       = generation["top_p"]

        return kwargs

    def _build_segments(self, text: str) -> List[Dict[str, Any]]:
        segments: List[Dict[str, Any]] = []

        for segment in self.processor.post_process_transcription(text):
            text       = segment.get("text", "")
            start_time = parse_timecode(segment["start_time"])
            end_time   = parse_timecode(segment["end_time"])
            speaker_id = segment.get("speaker_id")

            segments.append(self._build_segment(
                text=text,
                start_time=start_time,
                end_time=end_time,
                speaker_id=speaker_id,
            ))

        return segments

    @staticmethod
    def _build_segment(
        text: str,
        start_time: float,
        end_time: float,
        speaker_id: Optional[str],
    ) -> Dict[str, Any]:
        segment: Dict[str, Any] = {
            "text":       text,
            "start_time": start_time,
            "end_time":   end_time,
        }

        if speaker_id is not None:
            segment["speaker_id"] = speaker_id

        return segment

class VibeVoiceSpeechToTextTaskService(ModelTaskService):
    config: VibeVoiceSpeechToTextModelComponentConfig

    def __init__(self, id: str, config: VibeVoiceSpeechToTextModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.processor: Optional[Any] = None
        self.streaming_info: Optional[Dict[str, float]] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        # PyPI's `vibevoice 0.0.1` is the earlier TTS release and does not ship
        # the ASR modules; install from GitHub for the real classes.
        # `transformers==4.51.3` matches the checkpoints' `transformers_version`.
        return [
            "transformers==4.51.3",
            "torch",
            "torchaudio",
            "soxr",
            "vibevoice@git+https://github.com/microsoft/VibeVoice.git",
        ]

    async def _load_model(self) -> None:
        self.model, self.processor, self.streaming_info, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.processor = None
        self.streaming_info = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[Any, Any, Optional[Dict[str, float]], torch.device]:
        from vibevoice.modular.modeling_vibevoice_asr import VibeVoiceASRForConditionalGeneration
        from vibevoice.processor.vibevoice_asr_processor import VibeVoiceASRProcessor

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        processor = VibeVoiceASRProcessor.from_pretrained(model_path)
        streaming_info = self._load_streaming_info(model_path)
        dtype = self._resolve_torch_dtype(device)

        model = VibeVoiceASRForConditionalGeneration.from_pretrained(
            model_path,
            dtype=dtype,
            attn_implementation=self.config.attn_implementation,
        ).to(device).eval()

        return model, processor, streaming_info, device

    def _load_streaming_info(self, model_path: str) -> Optional[Dict[str, float]]:
        # Streaming checkpoints ship chunk/lookahead sizes in
        # preprocessor_config.json; non-streaming checkpoints don't ship this
        # file at all. Absence is the signal for "non-streaming checkpoint".
        import json
        import os

        config_path = os.path.join(model_path, "preprocessor_config.json")
        if not os.path.exists(config_path):
            return None

        with open(config_path) as f:
            config = json.load(f)

        # A preprocessor_config.json without chunk_frames is still a
        # non-streaming preprocessor; treat it the same as absent.
        if "chunk_frames" not in config:
            return None

        frame_seconds = config["speech_tok_compress_ratio"] / config["target_sample_rate"]

        return {
            "chunk_duration":   config["chunk_frames"] * frame_seconds,
            "text_audio_delay": config["lookahead_frames"] * frame_seconds,
        }

    def _resolve_torch_dtype(self, device: torch.device) -> torch.dtype:
        import torch

        if self.config.compute_type != "auto":
            dtype = getattr(torch, self.config.compute_type, None)
            if not isinstance(dtype, torch.dtype):
                raise ValueError(f"Unknown compute_type: {self.config.compute_type!r}")
            return dtype

        # VibeVoice ships and is validated at bfloat16 on CUDA; the demo falls
        # back to float32 elsewhere because bfloat16 support is uneven on
        # mps/cpu.
        return torch.bfloat16 if device.type == "cuda" else torch.float32

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await VibeVoiceSpeechToTextTaskAction(action, self.model, self.processor, self.streaming_info, self.device).run(context)
