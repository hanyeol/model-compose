from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Type, Union, Any
from mindor.dsl.schema.component import (
    BsRoFormerMusicSourceSeparationModelComponentConfig,
    MelBandRoFormerMusicSourceSeparationModelComponentConfig,
)
from mindor.dsl.schema.action import (
    ModelActionConfig,
    BsRoFormerMusicSourceSeparationModelActionConfig,
    MelBandRoFormerMusicSourceSeparationModelActionConfig,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource, AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.utils.audio import encode_waveform_to_pcm
from .......base import ComponentActionContext
from .....base import ModelTaskDriver
from ...common import MusicSourceSeparationTaskAction

if TYPE_CHECKING:
    import numpy as np
    import torch

# lucidrains BSRoformer / MelBandRoformer both default to a receptive field of
# ~8 seconds; the wrapper falls back to this when the user doesn't override
# chunk_duration.
_DEFAULT_CHUNK_DURATION_SECONDS = 8.0

RoFormerModelComponentConfig = Union[
    BsRoFormerMusicSourceSeparationModelComponentConfig,
    MelBandRoFormerMusicSourceSeparationModelComponentConfig,
]

RoFormerModelActionConfig = Union[
    BsRoFormerMusicSourceSeparationModelActionConfig,
    MelBandRoFormerMusicSourceSeparationModelActionConfig,
]

class RoFormerMusicSourceSeparationTaskAction(MusicSourceSeparationTaskAction):
    """Shared preprocessing/inference/postprocessing for BSRoformer + MelBandRoformer.

    Both architectures share the exact same input contract (stereo/mono
    `(batch, channels, samples)` tensors) and output shape
    (`(batch, channels, samples)` when num_stems=1, else `(batch, stems, channels, samples)`),
    so the only per-driver difference is the model class it was instantiated from.
    """
    def __init__(
        self,
        config: RoFormerModelActionConfig,
        model: torch.nn.Module,
        sample_rate: int,
        stereo: bool,
        stem_names: List[str],
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model: torch.nn.Module = model
        self.sample_rate: int = sample_rate
        self.stereo: bool = stereo
        self.stem_names: List[str] = stem_names

    async def _separate_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        waveforms = await self._preprocess_audio(audios)

        def _separate() -> List[Any]:
            return [ self._separate(waveform, params) for waveform in waveforms ]

        return await self._run_in_executor(_separate)

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            # channel=None preserves the original layout; mono returns (samples,)
            # and _to_model_tensor below expands it to match self.stereo.
            audio = await AudioBufferStreamer(audio, sample_rate=self.sample_rate).collect()
            waveforms.append(audio.waveform)

        return waveforms

    def _separate(self, waveform: np.ndarray, params: Dict[str, Any]) -> Any:
        tensor = self._to_model_tensor(waveform)

        chunk_duration = params.get("chunk_duration") or _DEFAULT_CHUNK_DURATION_SECONDS
        chunk_samples = max(1, int(round(chunk_duration * self.sample_rate)))
        overlap_ratio = params["overlap"] if params["overlap"] is not None else 0.25
        overlap_ratio = min(max(overlap_ratio, 0.0), 0.99)
        hop_samples = max(1, chunk_samples - int(round(chunk_samples * overlap_ratio)))

        estimates = self._run_chunked(tensor, chunk_samples, hop_samples)
        # estimates: (num_stems, channels, samples)

        stems = self._resolve_selected_stems(params["stems"], estimates.shape[0])
        sample_rate = params["sample_rate"] or self.sample_rate

        return self._build_separation_result(estimates, stems, sample_rate)

    def _to_model_tensor(self, waveform: np.ndarray) -> torch.Tensor:
        import numpy as np
        import torch

        array = np.ascontiguousarray(waveform, dtype=np.float32)
        tensor = torch.from_numpy(array)

        # AudioBufferStreamer.collect() returns (samples,) for mono and
        # (channels, samples) otherwise; normalize both to (channels, samples)
        # matching whatever `self.stereo` was configured with.
        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0)
        if self.stereo:
            if tensor.shape[0] == 1:
                tensor = tensor.repeat(2, 1)
            else:
                tensor = tensor[:2]
        else:
            if tensor.shape[0] > 1:
                tensor = tensor.mean(dim=0, keepdim=True)

        tensor = tensor.unsqueeze(0)  # (1, channels, samples)

        if self.device is not None:
            tensor = tensor.to(self.device)

        return tensor

    def _run_chunked(self, mix: torch.Tensor, chunk_samples: int, hop_samples: int) -> np.ndarray:
        """Sliding-window inference with Hann-window cross-fade at the overlap seams."""
        import torch

        _, channels, total_samples = mix.shape

        # Pad the tail so the last chunk is full-length; the padding is trimmed
        # off the reconstruction at the end.
        pad = 0
        if total_samples < chunk_samples:
            pad = chunk_samples - total_samples
        else:
            remainder = (total_samples - chunk_samples) % hop_samples
            if remainder != 0:
                pad = hop_samples - remainder

        if pad > 0:
            mix = torch.nn.functional.pad(mix, (0, pad))

        padded_samples = mix.shape[-1]
        hann = torch.hann_window(chunk_samples, device=mix.device)

        num_stems_ref: Optional[int] = None
        output: Optional[torch.Tensor] = None
        norm: Optional[torch.Tensor] = None

        start = 0
        with torch.no_grad():
            while start < padded_samples:
                end = min(start + chunk_samples, padded_samples)
                chunk = mix[:, :, start:end]

                if chunk.shape[-1] < chunk_samples:
                    chunk = torch.nn.functional.pad(chunk, (0, chunk_samples - chunk.shape[-1]))

                estimate = self.model(chunk)

                # Normalize output shape to (num_stems, channels, samples).
                if estimate.dim() == 3:      # (batch, channels, samples), num_stems=1
                    estimate = estimate.unsqueeze(1)
                # Now estimate: (batch, num_stems, channels, samples)
                estimate = estimate[0]        # drop batch → (num_stems, channels, samples)

                if num_stems_ref is None:
                    num_stems_ref = estimate.shape[0]
                    output = torch.zeros((num_stems_ref, channels, padded_samples), device=mix.device)
                    norm = torch.zeros(padded_samples, device=mix.device)

                output[:, :, start:start + chunk_samples] += estimate * hann
                norm[start:start + chunk_samples] += hann

                if end >= padded_samples:
                    break
                start += hop_samples

        assert output is not None and norm is not None

        norm = torch.where(norm == 0, torch.ones_like(norm), norm)
        output = output / norm

        # Trim off the tail padding to line up with the original mix length.
        output = output[:, :, :total_samples]

        return output.cpu().numpy()

    def _resolve_selected_stems(self, wanted_stems: Optional[List[str]], produced_stems: int) -> List[Tuple[str, int]]:
        available_names = list(self.stem_names)

        if len(available_names) < produced_stems:
            available_names = available_names + [ f"stem_{i}" for i in range(len(available_names), produced_stems) ]
        elif len(available_names) > produced_stems:
            available_names = available_names[:produced_stems]

        stem_indices: Dict[str, int] = { name: index for index, name in enumerate(available_names) }

        if not wanted_stems:
            return list(stem_indices.items())

        stems: List[Tuple[str, int]] = []

        for name in wanted_stems:
            if name not in stem_indices:
                raise ValueError(f"Stem '{name}' is not produced by this RoFormer checkpoint. Available: {available_names}")
            stems.append((name, stem_indices[name]))

        return stems

    def _build_separation_result(self, estimates: np.ndarray, stems: List[Tuple[str, int]], sample_rate: int) -> Any:
        result: Dict[str, PcmStreamResource] = {}

        for name, index in stems:
            waveform = estimates[index]
            frames, channels = encode_waveform_to_pcm(waveform)
            result[name] = PcmStreamResource(frames, {
                "sample_rate": str(sample_rate),
                "channels":    str(channels),
                "bit_depth":   "16",
            })

        if len(result) == 1:
            return next(iter(result.values()))

        return result

class RoFormerMusicSourceSeparationTaskDriver(ModelTaskDriver):
    """Shared loading/unloading/dispatch for BS-RoFormer and Mel-Band RoFormer.

    Subclasses provide the concrete model class via `_get_model_class` and the
    audio sample rate to feed the model via `_get_sample_rate`.
    """
    config: RoFormerModelComponentConfig

    def __init__(self, id: str, config: RoFormerModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[torch.nn.Module] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchaudio"),
            "bs-roformer",
            "einops",
            "rotary-embedding-torch",
            "librosa",
            "numpy",
            "soxr",
            "safetensors"
        ]

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[torch.nn.Module, torch.device]:
        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        # exclude_none keeps lucidrains' own defaults for optional fields the
        # user didn't set (e.g. BS-RoFormer's `freqs_per_bands`).
        model_params: Dict[str, Any] = self.config.params.model_dump(exclude_none=True)
        model_class = self._get_model_class()

        def _load() -> torch.nn.Module:
            model = model_class(**model_params)

            self._load_checkpoint(model, model_path)

            model.to(device)
            model.eval()

            return model

        model = await self._run_in_executor(_load)

        return model, device

    def _load_checkpoint(self, model: torch.nn.Module, model_path: str) -> None:
        """Load a .ckpt/.pt/.safetensors state dict into the roformer module.

        Uses the framework's `_load_model_checkpoint` for standard `.pt`/`.ckpt`
        files (which handles the `params` / `state_dict` wrapping conventions)
        and falls back to safetensors when the file has that extension.
        """
        if model_path.endswith(".safetensors"):
            from safetensors.torch import load_file
            state_dict = load_file(model_path, device="cpu")
            model.load_state_dict(state_dict, strict=True)
        else:
            self._load_model_checkpoint(model, model_path)

    def _get_model_class(self) -> Type[torch.nn.Module]:
        raise NotImplementedError

    def _get_sample_rate(self) -> int:
        raise NotImplementedError

    def _get_stem_names(self) -> List[str]:
        if self.config.stems:
            return list(self.config.stems)

        return [ f"stem_{index}" for index in range(self.config.params.num_stems) ]

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await RoFormerMusicSourceSeparationTaskAction(
            action,
            self.model,
            self._get_sample_rate(),
            self.config.params.stereo,
            self._get_stem_names(),
            self.device,
        ).run(context)
