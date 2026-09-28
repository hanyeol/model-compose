from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Mapping, Optional, List, Tuple, Type, Union, Any
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
        stft_hop_length: int,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model: torch.nn.Module = model
        self.sample_rate: int = sample_rate
        self.stereo: bool = stereo
        self.stem_names: List[str] = stem_names
        self.stft_hop_length: int = stft_hop_length

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        chunk_duration = await context.render_scalar(self.config.params.chunk_duration, float)

        params.update({
            "chunk_duration": chunk_duration,
        })

        return params

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

        chunk_duration = params["chunk_duration"] or _DEFAULT_CHUNK_DURATION_SECONDS
        # RoFormer's internal iSTFT calls torch.istft without `length=`, so its
        # output rounds down to a multiple of stft_hop_length. Align the request
        # to that grid up-front — otherwise the overlap-add stitch below hits a
        # shape mismatch of up to stft_hop_length - 1 samples.
        chunk_samples = max(1, int(round(chunk_duration * self.sample_rate)))
        chunk_samples = max(self.stft_hop_length, chunk_samples // self.stft_hop_length * self.stft_hop_length)
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

                # Defensive: some roformer versions return slightly short output
                # when the iSTFT length isn't perfectly aligned. Force the length
                # to match `chunk_samples` so the overlap-add stitch doesn't
                # trip on a shape mismatch.
                length = estimate.shape[-1]

                if length > chunk_samples:
                    estimate = estimate[..., :chunk_samples]
                elif length < chunk_samples:
                    estimate = torch.nn.functional.pad(estimate, (0, chunk_samples - length))

                if num_stems_ref is None:
                    num_stems_ref = estimate.shape[0]
                    output = torch.zeros((num_stems_ref, channels, padded_samples), device=mix.device)
                    norm = torch.zeros(padded_samples, device=mix.device)

                output[:, :, start:start + chunk_samples] += estimate * hann
                norm[start:start + chunk_samples] += hann

                if end >= padded_samples:
                    break

                start += hop_samples

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
        import inspect

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        # exclude_none keeps lucidrains' own defaults for optional fields the
        # user didn't set (e.g. BS-RoFormer's `freqs_per_bands`).
        model_class = self._get_model_class()
        model_params: Dict[str, Any] = self.config.params.model_dump(exclude_none=True)
        accepts_streams = "num_residual_streams" in inspect.signature(model_class).parameters

        def _load() -> torch.nn.Module:
            state_dict = self._load_checkpoint_state_dict(model_path)
            # bs-roformer 0.6+ wraps each transformer block with hyper-connections,
            # inserting a `.branch.` submodule in the state-dict keys. Older
            # community checkpoints (0.4.x) predate this and have no `.branch.`
            # keys — detecting one tells us we're loading a legacy checkpoint on
            # a newer model class.
            legacy = not any(".branch." in key for key in state_dict)

            if legacy and accepts_streams:
                # Collapse hyper-connections to a single residual stream so the
                # module tree matches what the legacy checkpoint expects (aside
                # from the `.branch.` prefix, which the key rewrite below fixes).
                model_params.setdefault("num_residual_streams", 1)

            model = model_class(**model_params)

            if legacy:
                state_dict = self._adapt_legacy_state_dict(model, state_dict)

            model.load_state_dict(state_dict, strict=True)

            model.to(device)
            model.eval()

            return model

        model = await self._run_in_executor(_load)

        return model, device

    def _load_checkpoint_state_dict(self, model_path: str) -> Mapping[str, Any]:
        import torch

        if model_path.endswith(".safetensors"):
            from safetensors.torch import load_file

            return load_file(model_path, device="cpu")

        checkpoint = torch.load(model_path, map_location="cpu")

        return self._get_state_dict_from_checkpoint(checkpoint)

    def _adapt_legacy_state_dict(self, model: torch.nn.Module, state_dict: Mapping[str, Any]) -> Dict[str, Any]:
        """Rewrite a pre-0.6 RoFormer state dict to load on the current architecture.

        Two adjustments are needed:

        1. Insert `.branch.` into transformer-block keys so they match the
           hyper-connections wrapper (kept even at num_residual_streams=1).
        2. Fill in the value-residual mix parameters that pre-0.6 checkpoints
           don't carry. Initializing weight=0, bias=-1e4 makes sigmoid(...) ≈ 0,
           which turns the mix into a no-op (the constructor exposes no flag
           to disable it).
        """
        import torch
        import re

        block_pattern = re.compile(r"^(layers\.\d+\.\d+\.layers\.\d+\.\d+)\.(.+)$")
        expected = model.state_dict()

        # Step 1: insert `.branch.` where the model expects it.
        adapted: Dict[str, Any] = {}

        for key, tensor in state_dict.items():
            if key not in expected:
                match = block_pattern.match(key)

                if match:
                    candidate = f"{match.group(1)}.branch.{match.group(2)}"

                    if candidate in expected:
                        key = candidate

            adapted[key] = tensor

        # Step 2: value-residual mix — BS uses `.to_value_residual_mix.{weight,bias}`;
        # Mel-Band uses `.learned_value_residual_mix.0.{weight,bias}`. Only fill
        # keys the model expects but the legacy checkpoint doesn't provide.
        value_mix_markers = (".to_value_residual_mix.", ".learned_value_residual_mix.0.")

        for key, reference in expected.items():
            if key in adapted or not any(marker in key for marker in value_mix_markers):
                continue

            if key.endswith(".weight"):
                adapted[key] = torch.zeros_like(reference)
            elif key.endswith(".bias"):
                adapted[key] = torch.full_like(reference, -1e4)

        return adapted

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
            self.config.params.stft_hop_length,
            self.device,
        ).run(context)
