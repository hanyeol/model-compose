from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, DemucsMusicSourceSeparationModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, MusicSourceSeparationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource, AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import MusicSourceSeparationTaskAction

if TYPE_CHECKING:
    import numpy as np
    import torch

class DemucsMusicSourceSeparationTaskAction(MusicSourceSeparationTaskAction):
    def __init__(
        self,
        config: MusicSourceSeparationModelActionConfig,
        model: Any,
        model_sample_rate: int,
        model_sources: List[str],
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model: Any = model
        self.model_sample_rate: int = model_sample_rate
        self.model_sources: List[str] = model_sources

    async def _separate_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        # Demucs models expect stereo audio at their native sample rate.
        waveforms = await self._preprocess_audio(audios)

        def _separate() -> List[Any]:
            return [ self._separate(waveform, params) for waveform in waveforms ]

        return await self._run_in_executor(_separate)

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            # channel=None keeps the original layout so stereo mixes stay stereo;
            # mono comes back as (samples,) and is expanded in _separate below.
            audio = await AudioBufferStreamer(audio, sample_rate=self.model_sample_rate).collect()
            waveforms.append(audio.waveform)

        return waveforms

    def _separate(self, waveform: np.ndarray, params: Dict[str, Any]) -> Any:
        import numpy as np
        import torch
        from demucs.apply import apply_model

        # AudioBufferStreamer.collect() returns (samples,) for mono and
        # (channels, samples) otherwise. Demucs expects stereo, so mono is
        # duplicated to both channels.
        tensor = torch.from_numpy(np.ascontiguousarray(waveform, dtype=np.float32))
        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0).repeat(2, 1)
        elif tensor.shape[0] == 1:
            tensor = tensor.repeat(2, 1)

        tensor = tensor.unsqueeze(0)  # (1, channels, samples)

        if self.device is not None:
            tensor = tensor.to(self.device)

        apply_params: Dict[str, Any] = { "device": self.device }
        if params["overlap"] is not None:
            apply_params["overlap"] = params["overlap"]
        if params["shifts"] is not None:
            apply_params["shifts"] = params["shifts"]

        with torch.no_grad():
            estimates = apply_model(self.model, tensor, **apply_params)

        # estimates shape: (batch=1, sources, channels, samples)
        estimates = estimates.squeeze(0).cpu()

        stems = self._resolve_selected_stems(params["stems"])
        sample_rate = params["sample_rate"] or self.model_sample_rate

        return self._build_separation_result(estimates, stems, sample_rate)

    def _resolve_selected_stems(self, wanted_stems: Optional[List[str]]) -> List[Tuple[str, int]]:
        stem_indices: Dict[str, int] = { name: index for index, name in enumerate(self.model_sources) }

        if not wanted_stems:
            return list(stem_indices.items())

        stems: List[Tuple[str, int]] = []

        for name in wanted_stems:
            if name not in stem_indices:
                raise ValueError(f"Stem '{name}' is not produced by this Demucs model. Available: {self.model_sources}")
            stems.append((name, stem_indices[name]))

        return stems

    def _build_separation_result(self, estimates: Any, stems: List[Tuple[str, int]], sample_rate: int) -> Any:
        result: Dict[str, PcmStreamResource] = {}

        for name, index in stems:
            waveform = estimates[index].numpy()
            frames, channels = encode_waveform_to_pcm(waveform)
            result[name] = PcmStreamResource(frames, {
                "sample_rate": str(sample_rate),
                "channels":    str(channels),
                "bit_depth":   "16",
            })

        if len(result) == 1:
            return next(iter(result.values()))

        return result

class DemucsMusicSourceSeparationTaskService(ModelTaskService):
    config: DemucsMusicSourceSeparationModelComponentConfig

    def __init__(self, id: str, config: DemucsMusicSourceSeparationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.model_sample_rate: int = 44100
        self.model_sources: List[str] = []
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "demucs", "torch", "torchaudio", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.model, self.model_sample_rate, self.model_sources, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.model_sources = []
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[Any, int, List[str], torch.device]:
        from demucs.pretrained import get_model

        device = self._resolve_device(self.config.device)
        model = get_model(self.config.model.name)

        if model is None:
            raise RuntimeError(f"Failed to load Demucs model '{self.config.model.name}'.")

        model.to(device)
        model.eval()

        sample_rate = int(getattr(model, "samplerate", 44100))
        sources = list(getattr(model, "sources", [ "drums", "bass", "other", "vocals" ]))

        return model, sample_rate, sources, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await DemucsMusicSourceSeparationTaskAction(
            action,
            self.model,
            self.model_sample_rate,
            self.model_sources,
            self.device,
        ).run(context)
