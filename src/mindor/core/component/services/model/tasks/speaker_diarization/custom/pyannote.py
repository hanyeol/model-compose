from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Iterator, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, PyannoteSpeakerDiarizationModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, SpeakerDiarizationModelActionConfig
from mindor.core.foundation.streaming.audio import load_audio_array
from mindor.core.foundation.streaming.media import MediaSource
from ......base import ComponentActionContext
from ..common import SpeakerDiarizationTaskService, SpeakerDiarizationTaskAction
import asyncio

if TYPE_CHECKING:
    import numpy as np
    import torch

_DEFAULT_PYANNOTE_REPO = "pyannote/speaker-diarization-3.1"

class PipelineCancelled(Exception):
    pass

class PyannoteSpeakerDiarizationTaskAction(SpeakerDiarizationTaskAction):
    def __init__(
        self,
        config: SpeakerDiarizationModelActionConfig,
        pipeline: Any,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.pipeline: Any = pipeline

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        params["pipeline"] = self._resolve_pipeline_params(params)

        return params

    def _resolve_pipeline_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_params: Dict[str, Any] = {}

        if params["num_speakers"] is not None:
            pipeline_params["num_speakers"] = int(params["num_speakers"])
        else:
            if params["min_speakers"] is not None:
                pipeline_params["min_speakers"] = int(params["min_speakers"])
            if params["max_speakers"] is not None:
                pipeline_params["max_speakers"] = int(params["max_speakers"])

        return pipeline_params

    async def _diarize(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[List[List[Dict[str, Any]]], List[Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]]]:
        sample_rate = int(params["sample_rate"])
        waveforms = await self._preprocess_audio(audios, sample_rate)
        results = []

        for waveform in waveforms:
            segments = self._collect_segments(waveform, sample_rate, params)
            if streaming:
                async def _stream_chunk_generator(segments=segments):
                    for segment in segments:
                        yield segment
                results.append(_stream_chunk_generator())
            else:
                results.append(segments)

        return results

    async def _preprocess_audio(self, audios: List[MediaSource], sample_rate: int) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            waveform, _ = await load_audio_array(audio, sample_rate=sample_rate)
            waveforms.append(waveform)

        return waveforms

    def _collect_segments(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        import torch

        tensor = torch.from_numpy(waveform).unsqueeze(0)

        if self.device is not None:
            tensor = tensor.to(self.device)

        pipeline_kwargs = params["pipeline"]
        cancellation_token = params.get("cancellation_token")

        if cancellation_token is not None:
            def _abort_if_cancelled(_step_name, _step_artifact, file=None, total=None, completed=None):
                if cancellation_token.is_cancelled():
                    raise PipelineCancelled()
            pipeline_kwargs = { **pipeline_kwargs, "hook": _abort_if_cancelled }

        try:
            with torch.no_grad():
                output = self.pipeline({ "waveform": tensor, "sample_rate": sample_rate }, **pipeline_kwargs)
        except PipelineCancelled:
            raise asyncio.CancelledError()

        annotation = getattr(output, "speaker_diarization", output)
        segments: List[Dict[str, Any]] = []

        for turn, _, speaker in annotation.itertracks(yield_label=True):
            segments.append({
                "speaker":    str(speaker),
                "start":      float(turn.start),
                "end":        float(turn.end),
                "confidence": 1.0,
            })

        segments = self._merge_segments(segments, float(params["merge_gap"] or 0.0))
        segments = [ segment for segment in segments if (segment["end"] - segment["start"]) >= float(params["min_segment_duration"] or 0.0) ]
        segments.sort(key=lambda segment: segment["start"])

        return segments

    def _merge_segments(self, segments: List[Dict[str, Any]], merge_gap: float) -> List[Dict[str, Any]]:
        if merge_gap > 0.0 and segments:
            segments = sorted(segments, key=lambda segment: (segment["speaker"], segment["start"]))
            merged: List[Dict[str, Any]] = []

            for segment in segments:
                if merged and merged[-1]["speaker"] == segment["speaker"] and segment["start"] - merged[-1]["end"] <= merge_gap:
                    merged[-1]["end"] = max(merged[-1]["end"], segment["end"])
                else:
                    merged.append(dict(segment))

            return merged

        return segments

class PyannoteSpeakerDiarizationTaskService(SpeakerDiarizationTaskService):
    config: PyannoteSpeakerDiarizationModelComponentConfig

    def __init__(self, id: str, config: PyannoteSpeakerDiarizationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pyannote.audio", "torch", "torchaudio", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.pipeline, self.device = self._load_pretrained_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    def _load_pretrained_pipeline(self) -> Tuple[Any, torch.device]:
        from pyannote.audio import Pipeline
        import torch

        device = self._resolve_device(self.config.device)
        source, token = self._resolve_source_and_token()
        pipeline = Pipeline.from_pretrained(source, token=token)

        if pipeline is None:
            raise RuntimeError(f"Failed to load pyannote pipeline '{source}'. Verify the HuggingFace token has access to the gated model.")

        pipeline.to(device)

        return pipeline, device

    def _resolve_source_and_token(self) -> Tuple[str, Optional[str]]:
        model = self.config.model

        if isinstance(model, HuggingfaceModelConfig):
            return model.repository, model.token

        if isinstance(model, str):
            return model, None

        return _DEFAULT_PYANNOTE_REPO, None

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        return await PyannoteSpeakerDiarizationTaskAction(action, self.pipeline, self.device).run(context, loop)
