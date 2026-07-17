from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator
from .resources import StreamResource, read_stream_to_bytes
from .bytes import BytesStreamResource
from .file import UploadFileStreamResource
from .media import MediaSource
from starlette.datastructures import UploadFile
import struct

if TYPE_CHECKING:
    import numpy as np

_AUDIO_CONTENT_TYPE_MAP: Dict[str, str] = {
    "wav":  "audio/wav",
    "mp3":  "audio/mpeg",
    "aac":  "audio/aac",
    "m4a":  "audio/mp4",
    "mp4":  "audio/mp4",
    "flac": "audio/flac",
    "ogg":  "audio/ogg",
    "opus": "audio/opus",
    "webm": "audio/webm",
    "pcm":  "audio/pcm",
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
    "s24le": "<i4",  # 24-bit handled specially below
    "s32le": "<i4",
    "f32le": "<f4",
    "f64le": "<f8",
}

class PcmStreamResource(StreamResource):
    def __init__(
        self,
        samples: Union[StreamResource, bytes],
        attrs: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ):
        super().__init__("audio/pcm", filename)

        self.samples: StreamResource = samples if isinstance(samples, StreamResource) else BytesStreamResource(samples)
        self.attrs: Dict[str, Any] = attrs or {}

    @property
    def format(self) -> str:
        return _PCM_BIT_DEPTH_FORMAT_MAP.get(int(self.attrs.get("bit_depth", 16)), "s16le")

    async def close(self) -> None:
        await self.samples.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.samples:
            yield chunk

class WavStreamResource(StreamResource):
    def __init__(
        self,
        source: Union[StreamResource, bytes],
        attrs: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ):
        super().__init__("audio/wav", filename)

        if isinstance(source, PcmStreamResource):
            attrs = attrs if attrs is not None else source.attrs
            source = source.samples
            is_raw_samples = True
        else:
            is_raw_samples = attrs is not None

        self.source: StreamResource = source if isinstance(source, StreamResource) else BytesStreamResource(source)
        self.attrs: Dict[str, Any] = attrs or {}

        self._is_raw_samples = is_raw_samples

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if self._is_raw_samples:
            yield self._build_header()
        async for chunk in self.source:
            yield chunk

    def _build_header(self) -> bytes:
        sample_rate = int(self.attrs.get("sample_rate", 44100))
        channels    = int(self.attrs.get("channels", 1))
        bit_depth   = int(self.attrs.get("bit_depth", 16))
        byte_rate   = sample_rate * channels * bit_depth // 8
        block_align = channels * bit_depth // 8

        # Streaming WAV: use 0xFFFFFFFF (uint32 max) as the conventional unknown-size marker.
        # Decoders (ffmpeg/MediaFoundation/browsers) treat this as "read until EOF".
        return (
            b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVE"
            + b"fmt " + struct.pack("<I", 16)
            + struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bit_depth)
            + b"data" + struct.pack("<I", 0xFFFFFFFF)
        )

class AudioStreamResource(StreamResource):
    def __init__(
        self,
        source: Union[StreamResource, bytes],
        format: Optional[str] = None,
        attrs: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ):
        super().__init__(self._resolve_content_type(format), filename, size=self._resolve_size(source))

        self.source: StreamResource = source if isinstance(source, StreamResource) else BytesStreamResource(source)
        self.format: str = format
        self.attrs: Dict[str, Any] = attrs or {}

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.source:
            yield chunk

    @staticmethod
    def _resolve_content_type(format: Optional[str]) -> str:
        if format:
            return _AUDIO_CONTENT_TYPE_MAP.get(format.lower(), "application/octet-stream")

        return "application/octet-stream"

    @staticmethod
    def _resolve_size(source: Union[StreamResource, bytes]) -> Optional[int]:
        return source.size if isinstance(source, StreamResource) else len(source)

def create_audio_source(value: Any) -> MediaSource:
    if isinstance(value, PcmStreamResource):
        return MediaSource(value.samples, value.format, value.attrs)

    if isinstance(value, WavStreamResource):
        return MediaSource(value, "wav", value.attrs)

    if isinstance(value, AudioStreamResource):
        return MediaSource(value.source, value.format, value.attrs)

    if isinstance(value, StreamResource):
        return MediaSource(value)

    if isinstance(value, UploadFile):
        return MediaSource(UploadFileStreamResource(value))

    if isinstance(value, (bytes, bytearray)):
        return MediaSource(BytesStreamResource(bytes(value)))

    raise TypeError(f"Unsupported audio source: {value.__class__.__name__}")

async def load_audio_array(
    source: MediaSource,
    sample_rate: Optional[int] = None,
    channel: Optional[int] = None,
) -> Tuple[np.ndarray, int]:
    """Load a MediaSource into a mono numpy waveform array.

    The returned waveform is always `float32` normalized to `[-1.0, 1.0]` so
    downstream DSP code can operate on a uniform sample-value contract regardless
    of whether the source was integer PCM (s16le, s24le, ...) or a decoded
    float32 stream (torchaudio-decoded wav/mp3/...).

    Multi-channel inputs are always reduced to 1-D `(samples,)`.

    `channel` selects how to reduce multi-channel audio to mono. `None` (default)
    averages all channels; an int selects a specific channel index (must satisfy
    0 <= channel < channels). Mono sources ignore this parameter.

    `sample_rate` resamples the waveform to the given rate via soxr if it
    differs from the source's own sample rate. `None` (default) keeps the source
    rate unchanged.
    """
    import torchaudio, io
    import numpy as np
    import soxr

    data = await read_stream_to_bytes(source.stream)

    if source.format in _PCM_FORMAT_NUMPY_DTYPE_MAP:
        source_sample_rate = int(source.attrs.get("sample_rate", 16000))
        channels = int(source.attrs.get("channels", 1))

        if source.format == "s24le":
            raw = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
            padded = np.zeros((raw.shape[0], 4), dtype=np.uint8)
            padded[:, 1:] = raw
            waveform = padded.view("<i4").reshape(-1) >> 8
        else:
            dtype = _PCM_FORMAT_NUMPY_DTYPE_MAP[source.format]
            waveform = np.frombuffer(data, dtype=np.dtype(dtype))

        if channels > 1:
            waveform = waveform.reshape(-1, channels).T
    else:
        loaded, source_sample_rate = torchaudio.load(io.BytesIO(data))
        waveform = loaded.numpy()
        source_sample_rate = int(source_sample_rate)

    # Normalize integer PCM to [-1.0, 1.0] float32 before any downmix so channel
    # averaging happens in the normalized space. torchaudio-decoded waveforms are
    # already float32; this only pays a cast for them.
    if np.issubdtype(waveform.dtype, np.integer):
        waveform = waveform.astype(np.float32) / float(np.iinfo(waveform.dtype).max)
    else:
        waveform = waveform.astype(np.float32)

    # Channel selection / downmix
    if waveform.ndim > 1:
        source_channels = waveform.shape[0]
        if channel is None:
            waveform = waveform.mean(axis=0)
        else:
            if channel < 0 or channel >= source_channels:
                raise ValueError(f"channel must satisfy 0 <= channel < channels; got channel={channel}, channels={source_channels}")
            waveform = waveform[channel]

    # Resample
    if sample_rate is not None and sample_rate != source_sample_rate:
        waveform = soxr.resample(waveform, source_sample_rate, sample_rate)
        source_sample_rate = sample_rate

    return waveform, source_sample_rate

async def stream_audio_array(
    source: MediaSource,
    frame_size: int,
    channel: Optional[int] = None,
    sample_rate: Optional[int] = None,
    hop_size: Optional[int] = None,
    pad_final: bool = True,
) -> AsyncIterator[np.ndarray]:
    """Stream a PCM audio source frame by frame as normalized float32 arrays.

    Companion to :func:`load_audio_array`: instead of collating the whole audio
    into one buffer, this reads the source stream chunk by chunk, slices it into
    fixed-size sample frames, and yields each frame as it becomes available.

    Integer PCM formats are normalized to the [-1.0, 1.0] range.

    `channel` selects how to reduce multi-channel PCM (read from
    `source.attrs["channels"]`) to a mono stream. `None` (default) averages all
    channels; an int selects a specific channel index (must satisfy
    0 <= channel < channels). Mono sources ignore this parameter.

    When `sample_rate` is provided and differs from the source's own sample rate
    (read from `source.attrs["sample_rate"]`, defaulting to 16000 if absent),
    the stream is resampled on the fly via `soxr.ResampleStream`. In this case
    `frame_size` is interpreted in the target sample rate.

    `hop_size` controls the stride between consecutive frames. Defaults to
    `frame_size` (non-overlapping frames). Setting `hop_size < frame_size`
    produces overlapping frames (sliding window), as commonly used for feature
    extraction (mel-spectrogram, MFCC, etc.). Must satisfy `0 < hop_size <= frame_size`.

    `pad_final` controls what happens to the trailing samples that do not form a
    complete frame. `True` (default) zero-pads them to `frame_size` and yields
    one final frame. `False` drops them silently.

    Requires the source to be raw PCM (see `_PCM_FORMAT_NUMPY_DTYPE_MAP`).
    Compressed formats are not supported here and should be handled via
    `load_audio_array` instead.
    """
    import numpy as np
    import soxr

    if source.format not in _PCM_FORMAT_NUMPY_DTYPE_MAP:
        raise ValueError(f"Streaming requires a raw PCM source; got format={source.format!r}")

    channels = int(source.attrs.get("channels", 1))

    if channels > 1 and channel is not None and (channel < 0 or channel >= channels):
        raise ValueError(f"channel must satisfy 0 <= channel < channels; got channel={channel}, channels={channels}")

    if hop_size is None:
        hop_size = frame_size

    if hop_size <= 0 or hop_size > frame_size:
        raise ValueError(f"hop_size must satisfy 0 < hop_size <= frame_size; got hop_size={hop_size}, frame_size={frame_size}")

    dtype = np.dtype(_PCM_FORMAT_NUMPY_DTYPE_MAP[source.format])
    bytes_per_sample = dtype.itemsize
    frame_stride_bytes = bytes_per_sample * channels  # size of one interleaved sample across all channels
    is_integer_pcm = dtype.kind in ("i", "u")
    int_scale = float(2 ** (bytes_per_sample * 8 - 1)) if is_integer_pcm else 1.0
    source_sample_rate = int(source.attrs.get("sample_rate", 16000))
    frame_buffer: np.ndarray = np.zeros(0, dtype=np.float32)
    input_buffer = bytearray()
    resampler = None

    if sample_rate is not None and sample_rate != source_sample_rate:
        resampler = soxr.ResampleStream(source_sample_rate, sample_rate, num_channels=1, dtype="float32")

    def _bytes_to_float32(raw: bytes) -> np.ndarray:
        samples = np.frombuffer(raw, dtype=dtype).astype(np.float32)
        if is_integer_pcm:
            samples = samples / int_scale
        if channels > 1:
            reshaped = samples.reshape(-1, channels)
            samples = reshaped.mean(axis=1) if channel is None else reshaped[:, channel]
        return samples

    def _pad_frame(samples: np.ndarray, pad_to: int) -> np.ndarray:
        if samples.shape[-1] < pad_to:
            samples = np.pad(samples, (0, pad_to - samples.shape[-1]))
        return samples

    def _drain_frames(flush_final: bool):
        nonlocal frame_buffer

        while frame_buffer.size >= frame_size:
            frame = frame_buffer[:frame_size]
            frame_buffer = frame_buffer[hop_size:]
            yield frame

        if flush_final and pad_final and frame_buffer.size > 0:
            frame = _pad_frame(frame_buffer, frame_size)
            frame_buffer = np.zeros(0, dtype=np.float32)
            yield frame

    def _push_samples(samples: np.ndarray):
        nonlocal frame_buffer

        if samples.size == 0:
            return
        frame_buffer = np.concatenate([frame_buffer, samples]) if frame_buffer.size > 0 else samples

    async for chunk in source.stream:
        if not chunk:
            continue

        # Assemble whole interleaved samples (one per channel) from possibly-split bytes.
        input_buffer.extend(chunk)
        aligned_len = (len(input_buffer) // frame_stride_bytes) * frame_stride_bytes
        if aligned_len == 0:
            continue

        raw_chunk = bytes(input_buffer[:aligned_len])
        del input_buffer[:aligned_len]

        samples = _bytes_to_float32(raw_chunk)

        if resampler is not None:
            samples = resampler.resample_chunk(samples)

        _push_samples(samples)

        for frame in _drain_frames(flush_final=False):
            yield frame

    # Flush resampler tail (if any) at end of stream.
    if resampler is not None:
        tail = resampler.resample_chunk(np.zeros(0, dtype=np.float32), last=True)
        _push_samples(tail)

    for frame in _drain_frames(flush_final=True):
        yield frame

def is_audio_streamable(source: MediaSource) -> bool:
    if source.format not in _PCM_FORMAT_NUMPY_DTYPE_MAP:
        return False

    if source.attrs.get("sample_rate") is None:
        return False

    return True
