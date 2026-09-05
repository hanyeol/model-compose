from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, MdxNetMusicSourceSeparationModelComponentConfig
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
    import onnxruntime as ort
    import torch

# MDX-Net standard hyperparameters shared by the UVR-MDX-NET voice models.
_MDX_SAMPLE_RATE = 44100
_MDX_N_FFT = 6144
_MDX_HOP_LENGTH = 1024
_MDX_DIM_F = 3072
_MDX_DIM_T = 8      # 2**8 = 256 spectrogram frames per chunk
_MDX_STEM_NAME = "vocals"
_MDX_INSTRUMENTAL_STEM_NAME = "instrumental"
_MDX_DEFAULT_STEMS = [ _MDX_STEM_NAME, _MDX_INSTRUMENTAL_STEM_NAME ]

class MdxNetMusicSourceSeparationTaskAction(MusicSourceSeparationTaskAction):
    def __init__(
        self,
        config: MusicSourceSeparationModelActionConfig,
        session: Any,
        input_name: str,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.session: Any = session
        self.input_name: str = input_name

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
            # channel=None keeps the original layout; mono comes back as (samples,)
            # and _ensure_stereo_waveform below duplicates it to both channels.
            audio = await AudioBufferStreamer(audio, sample_rate=_MDX_SAMPLE_RATE).collect()
            waveforms.append(audio.waveform)

        return waveforms

    def _separate(self, waveform: np.ndarray, params: Dict[str, Any]) -> Any:
        import numpy as np

        stereo = self._ensure_stereo_waveform(waveform)
        vocals = self._run_mdx(stereo)

        stems = list(params["stems"]) if params["stems"] else list(_MDX_DEFAULT_STEMS)
        sample_rate = params["sample_rate"] or _MDX_SAMPLE_RATE

        result: Dict[str, PcmStreamResource] = {}

        for name in stems:
            if name == _MDX_STEM_NAME:
                waveform = vocals
            elif name in (_MDX_INSTRUMENTAL_STEM_NAME, "accompaniment", "other"):
                waveform = stereo - vocals
            else:
                raise ValueError(f"Stem '{name}' is not supported by MDX-Net vocal models. Available: {_MDX_DEFAULT_STEMS}")

            frames, channels = encode_waveform_to_pcm(waveform)
            result[name] = PcmStreamResource(frames, {
                "sample_rate": str(sample_rate),
                "channels":    str(channels),
                "bit_depth":   "16",
            })

        if len(result) == 1:
            return next(iter(result.values()))

        return result

    def _ensure_stereo_waveform(self, waveform: np.ndarray) -> np.ndarray:
        import numpy as np

        array = np.asarray(waveform, dtype=np.float32)

        if array.ndim == 1:
            return np.stack([ array, array ], axis=0)

        if array.shape[0] == 1:
            array = np.repeat(array, 2, axis=0)

        return array[:2]

    def _run_mdx(self, mix: np.ndarray) -> np.ndarray:
        """Run MDX-Net over the full mix by chunking the STFT into fixed-size windows.

        The UVR MDX-Net ONNX takes a spectrogram tensor of shape (1, 4, dim_f, dim_t) —
        real+imag for two channels — and returns the same shape masked to the target stem.
        We slide over the input with 50% overlap to avoid edge artifacts.
        """
        import numpy as np

        chunk_samples = _MDX_HOP_LENGTH * (2 ** _MDX_DIM_T)  # samples per model chunk
        step = chunk_samples // 2  # 50% overlap

        pad = chunk_samples - (mix.shape[1] % chunk_samples)
        padded = np.pad(mix, ((0, 0), (0, pad)), mode="constant")

        output = np.zeros_like(padded)
        window = np.zeros((padded.shape[1],), dtype=np.float32)
        hann = np.hanning(chunk_samples).astype(np.float32)

        start = 0
        while start < padded.shape[1]:
            end = start + chunk_samples
            if end > padded.shape[1]:
                break

            chunk = padded[:, start:end]
            estimate = self._infer_chunk(chunk)
            output[:, start:end] += estimate * hann
            window[start:end] += hann

            start += step

        window = np.where(window == 0, 1.0, window)
        output = output / window

        return output[:, : mix.shape[1]]

    def _infer_chunk(self, chunk: np.ndarray) -> np.ndarray:
        import numpy as np

        spec = self._stft(chunk)
        result = self.session.run(None, { self.input_name: spec })[0]
        return self._istft(result, chunk.shape[1])

    def _stft(self, waveform: np.ndarray) -> np.ndarray:
        import numpy as np

        window = np.hanning(_MDX_N_FFT).astype(np.float32)
        frames: List[np.ndarray] = []

        for channel in waveform:
            padded = np.pad(channel, (_MDX_N_FFT // 2, _MDX_N_FFT // 2), mode="reflect")
            n_frames = 1 + (padded.shape[0] - _MDX_N_FFT) // _MDX_HOP_LENGTH
            stft = np.empty((_MDX_N_FFT // 2 + 1, n_frames), dtype=np.complex64)

            for frame in range(n_frames):
                start = frame * _MDX_HOP_LENGTH
                segment = padded[start : start + _MDX_N_FFT] * window
                stft[:, frame] = np.fft.rfft(segment).astype(np.complex64)

            frames.append(stft[: _MDX_DIM_F])

        stacked = np.stack(frames, axis=0)  # (2, dim_f, dim_t+1)
        stacked = stacked[:, :, : 2 ** _MDX_DIM_T]

        real = stacked.real
        imag = stacked.imag
        spec = np.stack([ real[0], imag[0], real[1], imag[1] ], axis=0)  # (4, dim_f, dim_t)
        return spec[np.newaxis, :].astype(np.float32)

    def _istft(self, spec: np.ndarray, target_length: int) -> np.ndarray:
        import numpy as np

        spec = spec[0]  # (4, dim_f, dim_t)
        real_l, imag_l, real_r, imag_r = spec[0], spec[1], spec[2], spec[3]

        left = real_l + 1j * imag_l
        right = real_r + 1j * imag_r

        # Pad frequency axis back to n_fft // 2 + 1
        full_bins = _MDX_N_FFT // 2 + 1
        pad_f = full_bins - left.shape[0]
        if pad_f > 0:
            left = np.pad(left, ((0, pad_f), (0, 0)), mode="constant")
            right = np.pad(right, ((0, pad_f), (0, 0)), mode="constant")

        window = np.hanning(_MDX_N_FFT).astype(np.float32)
        channels: List[np.ndarray] = []

        for spec_channel in (left, right):
            n_frames = spec_channel.shape[1]
            samples = (n_frames - 1) * _MDX_HOP_LENGTH + _MDX_N_FFT
            waveform = np.zeros(samples, dtype=np.float32)
            norm = np.zeros(samples, dtype=np.float32)

            for frame in range(n_frames):
                start = frame * _MDX_HOP_LENGTH
                segment = np.fft.irfft(spec_channel[:, frame]).astype(np.float32) * window
                waveform[start : start + _MDX_N_FFT] += segment
                norm[start : start + _MDX_N_FFT] += window * window

            norm = np.where(norm == 0, 1.0, norm)
            waveform = waveform / norm

            waveform = waveform[_MDX_N_FFT // 2 : _MDX_N_FFT // 2 + target_length]
            channels.append(waveform)

        return np.stack(channels, axis=0)

class MdxNetMusicSourceSeparationTaskService(ModelTaskService):
    config: MdxNetMusicSourceSeparationModelComponentConfig

    def __init__(self, id: str, config: MdxNetMusicSourceSeparationModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.session: Optional[Any] = None
        self.input_name: str = ""
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "onnxruntime", "torch", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.session, self.input_name, self.device = await self._load_onnx_session()

    async def _unload_model(self) -> None:
        self.session = None
        self.input_name = ""
        self.device = None

    async def _load_onnx_session(self) -> Tuple[Any, str, torch.device]:
        import onnxruntime as ort

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        providers: List[str] = []

        if device.type == "cuda":
            providers.append("CUDAExecutionProvider")

        providers.append("CPUExecutionProvider")

        session = ort.InferenceSession(model_path, providers=providers)
        input_name = session.get_inputs()[0].name

        return session, input_name, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await MdxNetMusicSourceSeparationTaskAction(
            action,
            self.session,
            self.input_name,
            self.device,
        ).run(context)
