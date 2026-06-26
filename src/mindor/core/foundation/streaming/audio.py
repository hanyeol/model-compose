from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Tuple, Dict, Any
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

async def load_audio_array(source: MediaSource) -> Tuple[np.ndarray, int]:
    import torchaudio, io
    import numpy as np

    data = await read_stream_to_bytes(source.stream)

    if source.format in _PCM_FORMAT_NUMPY_DTYPE_MAP:
        sample_rate = int(source.attrs.get("sample_rate", 16000))
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

        return waveform, sample_rate

    waveform, sample_rate = torchaudio.load(io.BytesIO(data))
    return waveform.numpy(), int(sample_rate)
