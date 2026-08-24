from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Literal, Tuple, Optional, Dict, Set, Any
from collections.abc import AsyncIterable
from dataclasses import dataclass
import struct

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

@dataclass
class AudioStream:
    """A stream of audio bytes together with its container/codec format.

    Lightweight value object for passing (bytes, format) as one unit into
    utils that need both — decoding, demuxing, spooling, etc.
    """
    stream: AsyncIterable[bytes]
    format: Optional[str] = None

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

    def matches(
        self,
        sample_rate: Optional[int] = None,
        channel: Optional[Union[int, Literal["mono"]]] = None,
    ) -> bool:
        if sample_rate is not None and sample_rate != self.sample_rate:
            return False

        # channel="mono"/int only take effect on multi-channel input, so a mono
        # buffer already matches any channel request.
        if channel is not None and self.channels > 1:
            return False

        return True

    def as_pcm_bytes(self, format: str = "s16le") -> bytes:
        pcm_bytes, _ = encode_waveform_to_pcm(self.waveform, format=format)

        return pcm_bytes

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

def decode_pcm_to_waveform(
    data: bytes,
    format: str,
    dtype: Optional[Union[str, np.dtype]] = None,
    channels: int = 1,
) -> np.ndarray:
    """Decode raw PCM bytes into a numpy waveform.

    ``format`` names the input PCM layout. ``dtype`` selects the output dtype:
      - ``None`` (default): the format's native dtype (e.g. s16le → int16). No scaling.
      - Float dtype (``"float32"``/``"float64"``): integer PCM is scaled to
        ``[-1.0, 1.0]`` using ``2^(bits-1)`` (``s24le`` uses 24-bit scale despite
        int32 storage); float PCM is cast without scaling.
      - Integer dtype: raw cast, no scaling.

    Shape: ``(frames,)`` when ``channels == 1``, ``(channels, frames)`` otherwise
    (multi-channel bytes are interleaved on the wire and de-interleaved here).

    Handles the 24-bit (s24le) special case internally (numpy has no native
    24-bit integer dtype).

    Inverse of :func:`encode_waveform_to_pcm`.
    """
    import numpy as np

    if format == "s24le":
        data = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
        padded = np.zeros((data.shape[0], 4), dtype=np.uint8)
        padded[:, 1:] = data
        waveform = padded.view("<i4").reshape(-1) >> 8
    else:
        waveform = np.frombuffer(data, dtype=get_pcm_dtype(format))

    if dtype is not None:
        target_dtype = np.dtype(dtype)
        if np.issubdtype(waveform.dtype, np.integer) and np.issubdtype(target_dtype, np.floating):
            bits = 24 if format == "s24le" else waveform.dtype.itemsize * 8
            waveform = waveform.astype(target_dtype) / target_dtype.type(2 ** (bits - 1))
        elif waveform.dtype != target_dtype:
            waveform = waveform.astype(target_dtype)

    if channels > 1:
        waveform = waveform.reshape(-1, channels).T.copy()

    return waveform

def parse_wav_header(data: bytes) -> Optional[Tuple[int, Dict[str, Any]]]:
    """Parse a canonical RIFF/WAVE header from ``data``. Returns
    ``(header_size, {sample_rate, channels, bit_depth})`` or ``None`` if the
    buffer doesn't yet contain both the ``fmt `` and ``data`` chunks.
    """
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None

    format: Optional[Tuple[int, int, int]] = None  # (channels, sample_rate, bits_per_sample)
    offset = 12

    while offset + 8 <= len(data):
        chunk_id = data[offset:offset + 4]
        (chunk_size,) = struct.unpack_from("<I", data, offset + 4)
        body_offset = offset + 8

        if chunk_id == b"fmt ":
            if body_offset + 16 > len(data):
                return None
            _, channels, sample_rate, _, _, bits_per_sample = struct.unpack_from("<HHIIHH", data, body_offset)
            format = (int(channels), int(sample_rate), int(bits_per_sample))

        if chunk_id == b"data":
            if format is None:
                return None

            channels, sample_rate, bits_per_sample = format
            return body_offset, {
                "sample_rate": sample_rate,
                "channels":    channels,
                "bit_depth":   bits_per_sample,
            }

        offset = body_offset + chunk_size

    return None

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
