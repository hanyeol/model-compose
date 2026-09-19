from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, Mdx23cMusicSourceSeparationModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, Mdx23cMusicSourceSeparationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource, AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.utils.audio import encode_waveform_to_pcm
from ......base import ComponentActionContext
from ....base import ModelTaskDriver
from ..common import MusicSourceSeparationTaskAction

if TYPE_CHECKING:
    import numpy as np
    import torch

# MDX23C models are trained on 44.1 kHz stereo mixes; the STFT window that lives
# inside the network is baked in at construction time.
_MDX23C_SAMPLE_RATE = 44100
_MDX23C_DEFAULT_CHUNK_SIZE = 130560
_MDX23C_DEFAULT_NUM_OVERLAP = 4

class Mdx23cMusicSourceSeparationTaskAction(MusicSourceSeparationTaskAction):
    config: Mdx23cMusicSourceSeparationModelActionConfig

    def __init__(
        self,
        config: Mdx23cMusicSourceSeparationModelActionConfig,
        model: Any,
        instruments: List[str],
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model: Any = model
        self.instruments: List[str] = instruments

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        chunk_size  = await context.render_scalar(self.config.params.chunk_size, int)
        num_overlap = await context.render_scalar(self.config.params.num_overlap, int)

        params.update({
            "chunk_size":  chunk_size,
            "num_overlap": num_overlap,
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
            audio = await AudioBufferStreamer(audio, sample_rate=_MDX23C_SAMPLE_RATE).collect()
            waveforms.append(audio.waveform)

        return waveforms

    def _separate(self, waveform: np.ndarray, params: Dict[str, Any]) -> Any:
        import numpy as np
        import torch

        chunk_size  = params["chunk_size"]  or _MDX23C_DEFAULT_CHUNK_SIZE
        num_overlap = params["num_overlap"] or _MDX23C_DEFAULT_NUM_OVERLAP

        stereo = self._ensure_stereo_waveform(waveform)
        tensor = torch.from_numpy(stereo)  # (2, samples)
        estimates = self._run_chunked(tensor, chunk_size, num_overlap)

        stems = self._resolve_selected_stems(params["stems"])
        sample_rate = params["sample_rate"] or _MDX23C_SAMPLE_RATE

        return self._build_separation_result(estimates, stems, sample_rate)

    def _ensure_stereo_waveform(self, waveform: np.ndarray) -> np.ndarray:
        import numpy as np

        array = np.asarray(waveform, dtype=np.float32)

        if array.ndim == 1:
            return np.stack([ array, array ], axis=0)

        if array.shape[0] == 1:
            array = np.repeat(array, 2, axis=0)

        return array[:2]

    def _run_chunked(self, mix: torch.Tensor, chunk_size: int, num_overlap: int) -> torch.Tensor:
        """Run the full-track mix through the network in fixed-size chunks and
        stitch predictions with a Hann-windowed overlap-add.

        MDX23C's STFT lives inside the model, so the network only needs a raw
        waveform tensor of shape (batch, channels, chunk_size)."""
        import torch

        num_instruments = len(self.instruments)
        channels, samples = mix.shape
        step = max(1, chunk_size // num_overlap)

        # Pad both ends so every output sample is covered by full-length chunks.
        pad = chunk_size
        padded = torch.nn.functional.pad(mix, (pad, pad + chunk_size))
        padded_length = padded.shape[-1]

        window = torch.hann_window(chunk_size, periodic=True, dtype=torch.float32)

        output = torch.zeros((num_instruments, channels, padded_length), dtype=torch.float32)
        weight = torch.zeros(padded_length, dtype=torch.float32)

        start = 0
        with torch.no_grad():
            while start + chunk_size <= padded_length:
                chunk = padded[:, start : start + chunk_size].unsqueeze(0)  # (1, C, T)

                if self.device is not None:
                    chunk = chunk.to(self.device)

                estimate = self.model(chunk)  # (1, num_instruments, C, T)
                estimate = estimate.squeeze(0).cpu()

                output[..., start : start + chunk_size] += estimate * window
                weight[start : start + chunk_size] += window

                start += step

        # Guard against divide-by-zero at the padded tails.
        weight = torch.where(weight == 0, torch.ones_like(weight), weight)
        output = output / weight

        return output[..., pad : pad + samples]

    def _resolve_selected_stems(self, wanted_stems: Optional[List[str]]) -> List[Tuple[str, int]]:
        stem_indices: Dict[str, int] = { name: index for index, name in enumerate(self.instruments) }

        if not wanted_stems:
            return list(stem_indices.items())

        stems: List[Tuple[str, int]] = []

        for name in wanted_stems:
            if name not in stem_indices:
                raise ValueError(f"Stem '{name}' is not produced by this MDX23C model. Available: {self.instruments}")
            stems.append((name, stem_indices[name]))

        return stems

    def _build_separation_result(self, estimates: torch.Tensor, stems: List[Tuple[str, int]], sample_rate: int) -> Any:
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

class Mdx23cMusicSourceSeparationTaskDriver(ModelTaskDriver):
    config: Mdx23cMusicSourceSeparationModelComponentConfig

    def __init__(self, id: str, config: Mdx23cMusicSourceSeparationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.instruments: List[str] = []
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch"),
            "mindor-mdx23c@git+https://github.com/hanyeol/mindor-mdx23c.git",
            "numpy",
            "soxr",
        ]

    async def _load_model(self) -> None:
        self.model, self.instruments, self.device = await self._load_checkpoint()

    async def _unload_model(self) -> None:
        self.model = None
        self.instruments = []
        self.device = None

    async def _load_checkpoint(self) -> Tuple[Any, List[str], torch.device]:
        import torch
        from mdx23c import TFC_TDF_net, load_config

        checkpoint_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        # Build the config dict the model expects from the flat DSL fields.
        # `audio.num_channels`, `model.act/norm/scale` are the MDX23C invariants
        # and stay hard-coded here; everything else comes from the component.
        config_dict = {
            "audio": {
                "n_fft":        self.config.n_fft,
                "hop_length":   self.config.hop_length,
                "dim_f":        self.config.dim_f,
                "num_channels": 2,
            },
            "model": {
                "act":                  "gelu",
                "norm":                 "InstanceNorm",
                "scale":                [2, 2],
                "num_subbands":         self.config.num_subbands,
                "num_scales":           self.config.num_scales,
                "num_blocks_per_scale": self.config.num_blocks_per_scale,
                "num_channels":         self.config.num_channels,
                "growth":               self.config.growth,
                "bottleneck_factor":    self.config.bottleneck_factor,
            },
            "training": {
                "instruments":       list(self.config.instruments),
                "target_instrument": self.config.target_instrument,
            },
        }

        def _load() -> Tuple[Any, List[str]]:
            config = load_config(config_dict)
            model = TFC_TDF_net(config)

            state_dict = torch.load(checkpoint_path, map_location="cpu")
            # Community MDX23C checkpoints sometimes wrap the state dict in
            # `{"state_dict": {...}}` (PyTorch Lightning) and prefix keys with
            # `module.` (nn.DataParallel). Peel both off before loading.
            if isinstance(state_dict, dict) and "state_dict" in state_dict:
                state_dict = state_dict["state_dict"]
            state_dict = { k.removeprefix("module."): v for k, v in state_dict.items() }

            model.load_state_dict(state_dict)
            model.to(device)
            model.eval()

            from mdx23c import prefer_target_instrument
            instruments = prefer_target_instrument(config)

            return model, instruments

        model, instruments = await self._run_in_executor(_load)

        return model, instruments, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Mdx23cMusicSourceSeparationTaskAction(
            action,
            self.model,
            self.instruments,
            self.device,
        ).run(context)
