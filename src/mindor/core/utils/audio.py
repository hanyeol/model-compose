from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, Set

if TYPE_CHECKING:
    import numpy as np
    import torch

_PCM_FORMATS: Set[str] = {
    "u8", "s16le", "s24le", "s32le", "f32le", "f64le",
}

_PCM_BIT_DEPTH_FORMAT_MAP: Dict[int, str] = {
     8: "u8",
    16: "s16le",
    24: "s24le",
    32: "s32le",
}

_PCM_FORMAT_NUMPY_DTYPE_MAP: Dict[str, str] = {
    "u8":    "uint8",
    "s16le": "<i2",
    "s24le": "<i4",  # 24-bit handled specially by callers
    "s32le": "<i4",
    "f32le": "<f4",
    "f64le": "<f8",
}

# Audio container formats whose headers sit at the front of the stream, so
# ffmpeg can decode them straight off pipe:0 without needing to seek. Formats
# like m4a/mp4 keep the moov atom at the end and must be spooled to a file.
_STREAMABLE_AUDIO_FORMATS: Set[str] = {
    "mp3", "wav", "flac", "ogg", "opus", "aac",
}

# Container formats that carry only an audio stream (no video track). Includes
# m4a on top of the streamable set — m4a needs seeking to decode but is still
# audio-only from the container's perspective.
_AUDIO_ONLY_FORMATS: Set[str] = {
    "mp3", "wav", "flac", "ogg", "opus", "aac", "m4a",
}

class AudioBuffer:
    def __init__(self, waveform: np.ndarray, sample_rate: int):
        self.waveform: np.ndarray = waveform
        self.sample_rate: int = sample_rate

    @property
    def channels(self) -> int:
        if self.waveform.ndim == 2:
            if self.waveform.shape[0] <= 8 and self.waveform.shape[0] < self.waveform.shape[1]:
                return int(self.waveform.shape[0])
            return int(self.waveform.shape[1])

        if self.waveform.ndim == 1:
            return 1

        raise ValueError(f"Expected 1-D or 2-D waveform, got shape {self.waveform.shape}")

def encode_waveform_to_pcm(
    waveform: Union[torch.Tensor, np.typing.ArrayLike],
    format: str = "s16le",
) -> Tuple[bytes, int]:
    """Encode a mono or stereo waveform to raw PCM bytes. Returns (pcm_bytes, channels).

    2-D input with `channels <= 8 and channels < samples` is auto-transposed to
    (samples, channels). Floats are clipped to [-1, 1] and scaled by 2^(bits-1).
    Inverse of :func:`decode_pcm_to_waveform`.
    """
    import numpy as np

    if hasattr(waveform, "detach"):
        waveform = waveform.detach()
    if hasattr(waveform, "cpu"):
        waveform = waveform.cpu()
    if hasattr(waveform, "numpy"):
        waveform = waveform.numpy()

    waveform = np.asarray(waveform)
    if waveform.ndim == 1:
        channels = 1
    elif waveform.ndim == 2:
        if waveform.shape[0] <= 8 and waveform.shape[0] < waveform.shape[1]:
            waveform = waveform.T
        channels = int(waveform.shape[1])
    else:
        raise ValueError(f"Expected 1-D or 2-D waveform, got shape {waveform.shape}")

    if format == "s24le":
        # s24le encode would require int32→3-byte repacking; not supported yet.
        raise NotImplementedError("encode to s24le is not supported")

    dtype = get_pcm_dtype(format)

    if np.issubdtype(waveform.dtype, np.floating):
        waveform = np.clip(waveform, -1.0, 1.0)
        if np.issubdtype(dtype, np.integer):
            # Standard signed-PCM scale: 2^(bits-1). Clamp to the dtype's max so
            # +1.0 doesn't overflow (e.g. 1.0 * 32768 → wraps to -32768 as int16).
            peak = float(2 ** (dtype.itemsize * 8 - 1))
            scaled = waveform * peak
            np.clip(scaled, np.iinfo(dtype).min, np.iinfo(dtype).max, out=scaled)
            waveform = scaled.astype(dtype)
        else:
            waveform = waveform.astype(dtype)
    elif waveform.dtype != dtype:
        waveform = waveform.astype(dtype)

    return waveform.tobytes(), channels

def decode_pcm_to_waveform(data: bytes, format: str) -> np.ndarray:
    """Decode raw PCM bytes into a 1-D numpy sample array.

    Handles the 24-bit (s24le) special case internally (numpy has no native 24-bit
    integer dtype); other formats reduce to a plain `np.frombuffer` view.
    Multi-channel bytes are returned interleaved — reshape by channel at the caller.

    Inverse of :func:`encode_waveform_to_pcm`.
    """
    import numpy as np

    if format == "s24le":
        raw = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
        padded = np.zeros((raw.shape[0], 4), dtype=np.uint8)
        padded[:, 1:] = raw
        return padded.view("<i4").reshape(-1) >> 8

    return np.frombuffer(data, dtype=get_pcm_dtype(format))

def normalize_pcm_to_float32(waveform: np.ndarray, format: Optional[str] = None) -> np.ndarray:
    """Convert a PCM waveform to float32 normalized to [-1.0, 1.0].

    Float inputs are just cast. Integer inputs are scaled by 2^(bits-1) — the
    standard signed-PCM peak (e.g. 32768 for s16le, not iinfo.max=32767). Pass
    `format` so `s24le` (packed in int32 storage but only 24 significant bits)
    is scaled correctly; other integer formats infer bit-depth from the dtype.
    """
    import numpy as np

    if not np.issubdtype(waveform.dtype, np.integer):
        return waveform.astype(np.float32)

    bits = 24 if format == "s24le" else waveform.dtype.itemsize * 8
    return waveform.astype(np.float32) / float(2 ** (bits - 1))

def is_streamable_audio_format(format: Optional[str]) -> bool:
    """True if the audio format can be fed to ffmpeg's pipe:0 without seeking."""
    return format in _STREAMABLE_AUDIO_FORMATS or format in _PCM_FORMATS

def is_audio_only_format(format: Optional[str]) -> bool:
    """True if the container carries only an audio stream (no video track)."""
    return format in _AUDIO_ONLY_FORMATS

def is_pcm_format(format: str) -> bool:
    """True if `format` names a raw sample layout that np.frombuffer can decode directly."""
    return format in _PCM_FORMATS

def get_pcm_format(bit_depth: int, default: str = "s16le") -> str:
    """Raw PCM format identifier for a given bit depth. Returns `default` if unknown."""
    return _PCM_BIT_DEPTH_FORMAT_MAP.get(int(bit_depth), default)

def get_pcm_dtype(format: str) -> np.dtype:
    """Numpy dtype for a raw PCM format identifier. Raises ValueError if unsupported."""
    import numpy as np

    if format not in _PCM_FORMAT_NUMPY_DTYPE_MAP:
        raise ValueError(f"Unsupported PCM format: {format!r}")

    return np.dtype(_PCM_FORMAT_NUMPY_DTYPE_MAP[format])
