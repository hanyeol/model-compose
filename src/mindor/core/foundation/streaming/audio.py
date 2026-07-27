from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, Any
from collections.abc import AsyncIterator
from .resources import StreamResource, read_stream_to_bytes
from .bytes import BytesStreamResource
from .file import UploadFileStreamResource
from .media import MediaSource
from ...utils.audio import (
    AudioBuffer,
    is_raw_pcm_format,
    get_pcm_dtype,
    get_pcm_format,
    decode_pcm_to_waveform,
    normalize_pcm_to_float32,
)
from starlette.datastructures import UploadFile
import asyncio, struct

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
        return get_pcm_format(int(self.attrs.get("bit_depth", 16)))

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

async def load_audio_buffer(
    source: MediaSource,
    sample_rate: Optional[int] = None,
    channel: Optional[int] = None,
) -> AudioBuffer:
    """Load a MediaSource into a mono float32 waveform normalized to [-1.0, 1.0].

    Multi-channel is downmixed to mono: `channel=None` averages, an int picks that channel.
    `sample_rate` resamples via soxr when it differs from the source rate.
    """
    data = await read_stream_to_bytes(source.stream)
    source_format = source.format
    source_attrs = source.attrs

    def _decode() -> AudioBuffer:
        if is_raw_pcm_format(source_format):
            source_sample_rate = int(source_attrs.get("sample_rate", 16000))
            channels = int(source_attrs.get("channels", 1))

            waveform = decode_pcm_to_waveform(data, source_format)

            if channels > 1:
                waveform = waveform.reshape(-1, channels).T
        else:
            import torchaudio, io

            loaded, source_sample_rate = torchaudio.load(io.BytesIO(data))
            waveform = loaded.numpy()
            source_sample_rate = int(source_sample_rate)

        # Normalize to [-1.0, 1.0] float32 before any downmix so channel averaging
        # happens in the normalized space. Torchaudio-decoded waveforms are already
        # float32 (just a cast); PCM ones use format-aware scaling (see s24le note).
        waveform = normalize_pcm_to_float32(waveform, format=source_format if is_raw_pcm_format(source_format) else None)

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
            import soxr

            waveform = soxr.resample(waveform, source_sample_rate, sample_rate)
            source_sample_rate = sample_rate

        return AudioBuffer(waveform=waveform, sample_rate=source_sample_rate)

    return await asyncio.to_thread(_decode)

async def stream_audio_buffer(
    source: MediaSource,
    frame_size: int,
    channel: Optional[int] = None,
    sample_rate: Optional[int] = None,
    hop_size: Optional[int] = None,
    pad_final: bool = True,
) -> AsyncIterator[AudioBuffer]:
    """Streaming counterpart to :func:`load_audio_buffer`: yield frames as they arrive.

    Raw PCM only (compressed formats must go through `load_audio_buffer`).
    `sample_rate` resamples on the fly; `frame_size` is in target-rate samples.
    `hop_size < frame_size` produces overlapping frames.
    `pad_final` zero-pads the trailing partial frame; set False to drop it.
    """
    import numpy as np

    if not is_raw_pcm_format(source.format):
        raise ValueError(f"Streaming requires a raw PCM source; got format={source.format!r}")

    channels = int(source.attrs.get("channels", 1))

    if channels > 1 and channel is not None and (channel < 0 or channel >= channels):
        raise ValueError(f"channel must satisfy 0 <= channel < channels; got channel={channel}, channels={channels}")

    if hop_size is None:
        hop_size = frame_size

    if hop_size <= 0 or hop_size > frame_size:
        raise ValueError(f"hop_size must satisfy 0 < hop_size <= frame_size; got hop_size={hop_size}, frame_size={frame_size}")

    bytes_per_sample = get_pcm_dtype(source.format).itemsize
    frame_stride_bytes = bytes_per_sample * channels  # size of one interleaved sample across all channels
    source_sample_rate = int(source.attrs.get("sample_rate", 16000))
    target_sample_rate = sample_rate if sample_rate is not None else source_sample_rate
    frame_buffer: np.ndarray = np.zeros(0, dtype=np.float32)
    input_buffer = bytearray()
    resampler = None

    if sample_rate is not None and sample_rate != source_sample_rate:
        import soxr

        resampler = soxr.ResampleStream(source_sample_rate, sample_rate, num_channels=1, dtype="float32")

    def _bytes_to_float32(raw: bytes) -> np.ndarray:
        samples = normalize_pcm_to_float32(decode_pcm_to_waveform(raw, source.format), format=source.format)

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

    def _process_chunk(raw_chunk: bytes) -> list:
        samples = _bytes_to_float32(raw_chunk)

        if resampler is not None:
            samples = resampler.resample_chunk(samples)

        _push_samples(samples)

        return list(_drain_frames(flush_final=False))

    def _flush_tail() -> list:
        if resampler is not None:
            tail = resampler.resample_chunk(np.zeros(0, dtype=np.float32), last=True)
            _push_samples(tail)

        return list(_drain_frames(flush_final=True))

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

        for waveform in await asyncio.to_thread(_process_chunk, raw_chunk):
            yield AudioBuffer(waveform=waveform, sample_rate=target_sample_rate)

    for waveform in await asyncio.to_thread(_flush_tail):
        yield AudioBuffer(waveform=waveform, sample_rate=target_sample_rate)

def is_audio_streamable(source: MediaSource) -> bool:
    if not is_raw_pcm_format(source.format):
        return False

    if source.attrs.get("sample_rate") is None:
        return False

    return True
