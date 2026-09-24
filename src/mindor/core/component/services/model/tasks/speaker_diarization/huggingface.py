from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceSpeakerDiarizationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.package.torch import torch_requirements
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskDriver
from .common import SpeakerDiarizationTaskAction

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    import numpy as np
    import torch

class HuggingfaceSpeakerDiarizationTaskAction(SpeakerDiarizationTaskAction):
    def __init__(
        self,
        config: HuggingfaceSpeakerDiarizationModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device,
    ):
        super().__init__(config, device)

        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        streaming_latency = await context.render_variable(self.config.streaming_latency)

        params.update({
            "streaming_latency": streaming_latency,
        })

        return params

    async def _diarize_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[Dict[str, Any]], List[AsyncIterator[Dict[str, Any]]]]:
        waveforms = await self._preprocess_audio(audios)

        def _diarize() -> List[List[Dict[str, Any]]]:
            results: List[List[Dict[str, Any]]] = []

            for waveform in waveforms:
                results.append(self._diarize(waveform, params, cancellation_token))

            return results

        results = await self._run_in_executor(_diarize)

        if streaming:
            # Nemotron diarization needs the full audio; fake streaming by re-emitting segments.
            streams: List[AsyncIterator[Dict[str, Any]]] = []

            for segments in results:
                async def _stream_chunk_generator(segments=segments):
                    for segment in segments:
                        yield { "type": "segment", **segment }

                streams.append(_stream_chunk_generator())

            return streams

        return [ { "segments": segments } for segments in results ]

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        sampling_rate = self.processor.feature_extractor.sampling_rate
        waveforms: List[np.ndarray] = []

        for audio in audios:
            audio = await AudioBufferStreamer(audio, sample_rate=sampling_rate, channel="mono").collect()
            waveforms.append(audio.waveform)

        return waveforms

    def _diarize(
        self,
        waveform: np.ndarray,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        import torch

        if params.get("streaming_latency"):
            # Set streaming mode on the processor before feature extraction so it
            # emits chunked inputs matched to the requested latency budget.
            self.processor.set_streaming_mode(f"{params['streaming_latency']}_latency")

        sampling_rate = self.processor.feature_extractor.sampling_rate
        inputs = self.processor(
            waveform,
            sampling_rate=sampling_rate,
            return_tensors="pt",
        ).to(self.device, dtype=self.model.dtype)

        with torch.inference_mode():
            outputs = self.model(**inputs)

        attention_mask = getattr(inputs, "attention_mask", None)
        turns = self.processor.extract_speaker_dict(outputs.logits, attention_mask)[0]

        segments: List[Dict[str, Any]] = []

        for turn in turns:
            segments.append({
                "speaker":    f"speaker_{turn['Speaker']}",
                "start_time": float(turn["Start"]),
                "end_time":   float(turn["End"]),
                "confidence": 1.0,
            })

        segments = self._merge_segments(segments, float(params["merge_gap"] or 0.0))
        segments = [ segment for segment in segments if (segment["end_time"] - segment["start_time"]) >= float(params["min_segment_duration"] or 0.0) ]
        segments.sort(key=lambda segment: segment["start_time"])

        return segments

    def _merge_segments(self, segments: List[Dict[str, Any]], merge_gap: float) -> List[Dict[str, Any]]:
        if merge_gap > 0.0 and segments:
            segments = sorted(segments, key=lambda segment: (segment["speaker"], segment["start_time"]))
            merged: List[Dict[str, Any]] = []

            for segment in segments:
                if merged and merged[-1]["speaker"] == segment["speaker"] and segment["start_time"] - merged[-1]["end_time"] <= merge_gap:
                    merged[-1]["end_time"] = max(merged[-1]["end_time"], segment["end_time"])
                else:
                    merged.append(dict(segment))

            merged.sort(key=lambda segment: segment["start_time"])
            return merged

        return segments

@register_model_task_driver(ModelTaskType.SPEAKER_DIARIZATION, ModelDriverType.HUGGINGFACE)
class HuggingfaceSpeakerDiarizationTaskDriver(HuggingfaceMultimodalModelTaskDriver):
    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchaudio"),
            "transformers>=4.52.0",
            "accelerate",
            "soxr",
        ]

    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import AutoModelForAudioFrameClassification
        return AutoModelForAudioFrameClassification

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        from transformers import AutoProcessor
        return AutoProcessor

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceSpeakerDiarizationTaskAction(action, self.model, self.processor, self.device).run(context)
