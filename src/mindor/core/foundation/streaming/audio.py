from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Literal, Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from .resources import StreamResource, AsyncIterableStreamResource, read_stream_to_bytes
from .bytes import BytesStreamResource
from .file import FileStreamResource, UploadFileStreamResource
from .media import MediaSource
from .iterators import StreamChunkIterator
from ...utils.audio import (
    AudioBuffer,
    is_pcm_format,
    get_pcm_dtype,
    get_pcm_format,
    decode_pcm_to_waveform,
    encode_waveform_to_pcm,
    parse_wav_header,
)
from ...utils.shell import stream_subprocess
from ...logger import logging
from starlette.datastructures import UploadFile
import asyncio, struct, shutil

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
        samples: Union[StreamResource, AudioBufferStreamIterator, bytes],
        attrs: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ):
        super().__init__("audio/pcm", filename)

        if isinstance(samples, AudioBufferStreamIterator):
            attrs = dict(attrs) if attrs else {}
            attrs.setdefault("sample_rate", samples.sample_rate)
            attrs.setdefault("channels", samples.channels)
            attrs.setdefault("bit_depth", 16)

        self.samples: Union[StreamResource, AudioBufferStreamIterator] = self._resolve_samples(samples)
        self.attrs: Dict[str, Any] = attrs or {}

    @property
    def format(self) -> str:
        return self.attrs.get("format") or get_pcm_format(int(self.attrs.get("bit_depth", 16)))

    async def close(self) -> None:
        if isinstance(self.samples, StreamResource):
            await self.samples.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if isinstance(self.samples, AudioBufferStreamIterator):
            async for audio in self.samples:
                async for chunk in BytesStreamResource(audio.as_pcm_bytes(self.format)):
                    yield chunk
            return

        async for chunk in self.samples:
            yield chunk

    @staticmethod
    def _resolve_samples(
        samples: Union[StreamResource, AudioBufferStreamIterator, bytes],
    ) -> Union[StreamResource, AudioBufferStreamIterator]:
        if isinstance(samples, bytes):
            return BytesStreamResource(samples)

        return samples

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
            is_raw_samples = True
        else:
            is_raw_samples = attrs is not None

        self.source: StreamResource = self._resolve_source(source)
        self.attrs: Dict[str, Any] = attrs or {}

        self._is_raw_samples = is_raw_samples

    def as_pcm_stream(self) -> Optional[PcmStreamResource]:
        if self._is_raw_samples:
            return PcmStreamResource(self.source, attrs=self.attrs)

        return None

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if self._is_raw_samples:
            yield self._build_header()

        async for chunk in self.source:
            yield chunk

    @staticmethod
    def _resolve_source(source: Union[StreamResource, bytes]) -> StreamResource:
        if isinstance(source, bytes):
            return BytesStreamResource(source)

        return source

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

        self.source: StreamResource = self._resolve_source(source)
        self.format: str = format
        self.attrs: Dict[str, Any] = attrs or {}

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.source:
            yield chunk

    @staticmethod
    def _resolve_source(source: Union[StreamResource, bytes]) -> StreamResource:
        if isinstance(source, bytes):
            return BytesStreamResource(source)

        return source

    @staticmethod
    def _resolve_content_type(format: Optional[str]) -> str:
        if format:
            return _AUDIO_CONTENT_TYPE_MAP.get(format.lower(), "application/octet-stream")

        return "application/octet-stream"

    @staticmethod
    def _resolve_size(source: Union[StreamResource, bytes]) -> Optional[int]:
        return source.size if isinstance(source, StreamResource) else len(source)

class AudioBufferStreamIterator(StreamChunkIterator):
    def __init__(
        self,
        source: AsyncIterator[AudioBuffer],
        sample_rate: int,
        channels: int,
    ):
        super().__init__(source, is_fragmented=True)

        self.sample_rate: int = sample_rate
        self.channels: int    = channels

    def matches(
        self,
        sample_rate: Optional[int] = None,
        channel: Optional[Union[int, Literal["mono"]]] = None,
    ) -> bool:
        if sample_rate is not None and sample_rate != self.sample_rate:
            return False

        # channel="mono"/int only take effect on multi-channel input, so a mono
        # iterator already matches any channel request.
        if channel is not None and self.channels > 1:
            return False

        return True

    async def collect(self) -> AudioBuffer:
        import numpy as np

        frames: list = []
        async for chunk in self:
            frames.append(chunk.waveform)

        waveform = frames[0] if len(frames) == 1 else np.concatenate(frames, axis=-1)
        return AudioBuffer(waveform=waveform, sample_rate=self.sample_rate)

    @classmethod
    def from_single(cls, buffer: AudioBuffer) -> AudioBufferStreamIterator:
        async def _stream() -> AsyncIterator[AudioBuffer]:
            yield buffer

        return cls(
            source=_stream(),
            sample_rate=buffer.sample_rate,
            channels=buffer.channels,
        )

class AudioDecodingStreamer:
    """Decode any audio ``MediaSource`` into an s16le PCM byte stream.

    Consume either as raw bytes (``async for chunk in streamer``) or wrap into
    a ``PcmStreamResource`` via ``as_pcm_stream()``.

    Dispatch order:
      1. Source is already raw PCM matching the requested layout — reuse its
         bytes without re-decoding.
      2. ``ffmpeg`` binary available — spawn ``ffmpeg -f s16le pipe:1`` and
         stream its stdout (bounded memory, backpressure via pipe).
      3. ``torchaudio`` importable — decode the whole source into memory and
         re-encode as s16le (non-streaming fallback; logs a debug line on
         each decode).
      4. Otherwise — raise ``RuntimeError`` asking the user to install one.

    ``sample_rate`` / ``channels`` optionally resample / downmix at decode
    time, avoiding a second pass in downstream consumers like
    ``AudioBufferStreamer``. When ``None`` the source layout is preserved.
    Requesting a layout that differs from a raw-PCM source bypasses the
    passthrough shortcut and routes through the ffmpeg / torchaudio path.
    """
    def __init__(
        self,
        source: MediaSource,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
    ):
        self._source = source
        self._sample_rate = sample_rate
        self._channels = channels

    def __aiter__(self) -> AsyncIterator[bytes]:
        iterator, _ = self._decode_to_stream(self._source)

        return iterator

    def as_pcm_stream(self) -> PcmStreamResource:
        iterator, attrs = self._decode_to_stream(self._source)

        return PcmStreamResource(
            samples=AsyncIterableStreamResource(iterator),
            attrs=attrs,
        )

    def _decode_to_stream(self, source: MediaSource) -> Tuple[AsyncIterator[bytes], Dict[str, Any]]:
        """Choose a decode path and return ``(byte iterator, resolved pcm attrs)``.

        The iterator yields raw ``s16le`` PCM bytes; ``attrs`` describes the
        layout (``sample_rate`` / ``channels`` / ``bit_depth``) so callers can
        wrap the pair in a ``PcmStreamResource`` or consume the bytes directly.
        """
        if isinstance(source.stream, (PcmStreamResource, WavStreamResource)):
            stream = self._get_passthrough_stream(source.stream)

            if stream is not None:
                return stream

        if shutil.which("ffmpeg") is not None:
            return self._decode_with_ffmpeg(source)

        if self._is_torchaudio_available():
            logging.debug("ffmpeg not found; falling back to torchaudio (non-streaming decode)")
            return self._decode_with_torchaudio(source)

        raise RuntimeError("No audio decoder available: install ffmpeg or torchaudio.")

    def _decode_with_ffmpeg(self, source: MediaSource) -> Tuple[AsyncIterator[bytes], Dict[str, Any]]:
        sample_rate = self._sample_rate or int(source.attrs.get("sample_rate") or 0) or None
        channels = self._channels or int(source.attrs.get("channels") or 0) or None

        command: list = [ "ffmpeg", "-hide_banner", "-loglevel", "error" ]
        input_path: Optional[str] = None

        if isinstance(source.stream, FileStreamResource):
            input_path = source.stream.path
        
        if source.format and input_path is None:
            command.extend([ "-f", source.format ])

            if is_pcm_format(source.format):
                if source.attrs.get("sample_rate"):
                    command.extend([ "-ar", str(source.attrs["sample_rate"]) ])
                else:
                    raise ValueError(f"Raw PCM source {source.format!r} requires 'sample_rate' in attrs")
                if source.attrs.get("channels"):
                    command.extend([ "-ac", str(source.attrs["channels"]) ])
                else:
                    raise ValueError(f"Raw PCM source {source.format!r} requires 'channels' in attrs")

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])
        # Use WAV container instead of raw s16le so ffmpeg emits a 44-byte RIFF
        # header carrying the actual sr/channels. Lets us populate ``attrs``
        # without a pre-scan when the caller didn't specify a layout.
        command.extend([ "-vn", "-f", "wav", "-acodec", "pcm_s16le" ])
        if sample_rate:
            command.extend([ "-ar", str(sample_rate) ])
        if channels:
            command.extend([ "-ac", str(channels) ])
        command.append("pipe:1")

        stdin_source = source.stream if input_path is None else None

        # Shared with ``_stream``: sr/channels/bit_depth get filled in-place once
        # the WAV header is parsed. Consumers must start iterating before reading
        # these keys — see ``AudioBufferStreamer._iterate`` which pre-consumes
        # the first chunk.
        attrs: Dict[str, Any] = { "bit_depth": 16 }

        if sample_rate:
            attrs["sample_rate"] = sample_rate

        if channels:
            attrs["channels"] = channels

        async def _handle_stdout(reader: asyncio.StreamReader) -> AsyncIterator[bytes]:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                yield chunk

        async def _handle_stderr(reader: asyncio.StreamReader) -> bytes:
            lines: list = []
            while True:
                line = await reader.readline()
                if not line:
                    break
                lines.append(line)
            return b"".join(lines)

        async def _stream() -> AsyncIterator[bytes]:
            async with stream_subprocess(
                command,
                source=stdin_source,
                stdout_handler=_handle_stdout,
                stderr_handler=_handle_stderr,
            ) as (process, chunks, error):
                header_buffer = bytearray()
                header_stripped = False

                async for chunk in chunks:
                    if not header_stripped:
                        header_buffer.extend(chunk)

                        # RIFF header is 44 bytes for a canonical PCM WAV. If the
                        # source has extra chunks (e.g. LIST/INFO), the ``data``
                        # marker still appears near the front — scan for it.
                        if len(header_buffer) < 44:
                            continue

                        header = parse_wav_header(bytes(header_buffer))

                        if header is None:
                            # Not enough bytes yet to locate the ``data`` chunk;
                            # keep buffering.
                            continue

                        header_size, header_attrs = header
                        attrs.update(header_attrs)

                        pcm_bytes = bytes(header_buffer[header_size:])
                        header_buffer.clear()
                        header_stripped = True

                        if pcm_bytes:
                            yield pcm_bytes
                    else:
                        yield chunk

                # stdout EOF doesn't imply the process has reaped yet; wait so
                # returncode is populated before we decide success/failure.
                await process.wait()

                if process.returncode != 0:
                    error_bytes: bytes = b""
                    if error is not None:
                        try:
                            error_bytes = await error
                        except Exception:
                            error_bytes = b""
                    error_message = error_bytes.decode("utf-8", errors="replace") if error_bytes else ""
                    raise RuntimeError(f"ffmpeg audio decoding failed (exit code {process.returncode}): {error_message}")

        return _stream(), attrs

    def _decode_with_torchaudio(self, source: MediaSource) -> Tuple[AsyncIterator[bytes], Dict[str, Any]]:
        sample_rate = self._sample_rate or int(source.attrs.get("sample_rate") or 0) or None
        channels = self._channels or int(source.attrs.get("channels") or 0) or None

        # Shared with ``_stream``: sr/channels get filled in-place once the
        # source has actually been decoded and we know the resolved layout.
        # Consumers must start iterating before reading these keys.
        attrs: Dict[str, Any] = { "bit_depth": 16 }

        async def _stream() -> AsyncIterator[bytes]:
            data = await read_stream_to_bytes(source.stream)

            def _decode() -> Tuple[bytes, int, int]:
                import torchaudio, io

                waveform, source_sample_rate = torchaudio.load(io.BytesIO(data))
                waveform = waveform.numpy()  # (channels, samples), float32
                source_sample_rate = int(source_sample_rate)
                source_channels = int(waveform.shape[0])

                target_sample_rate = sample_rate if sample_rate is not None else source_sample_rate

                if target_sample_rate != source_sample_rate:
                    import soxr
                    # soxr expects (samples, channels) interleaved; round-trip via transpose.
                    waveform = soxr.resample(waveform.T, source_sample_rate, target_sample_rate).T

                target_channels = channels if channels is not None else source_channels

                if target_channels != source_channels:
                    if target_channels == 1:
                        waveform = waveform.mean(axis=0, keepdims=True)
                    else:
                        raise ValueError(f"torchaudio fallback: cannot upmix from {source_channels} to {target_channels} channels")

                pcm_bytes, _ = encode_waveform_to_pcm(waveform, format="s16le")

                return pcm_bytes, target_sample_rate, target_channels

            pcm_bytes, resolved_sample_rate, resolved_channels = await asyncio.to_thread(_decode)
            attrs["sample_rate"] = resolved_sample_rate
            attrs["channels"]    = resolved_channels

            # Emit in reasonable chunks so downstream consumers see streaming-like
            # behavior even though decode was one-shot.
            chunk_size = 65536
            for index in range(0, len(pcm_bytes), chunk_size):
                yield pcm_bytes[index:index + chunk_size]

        return _stream(), attrs

    def _get_passthrough_stream(
        self,
        stream: Union[PcmStreamResource, WavStreamResource],
    ) -> Optional[Tuple[AsyncIterator[bytes], Dict[str, Any]]]:
        """Return ``(iterator, attrs)`` if the source PCM already matches the
        requested layout, else ``None`` so the caller falls through to decode.

        A ``WavStreamResource`` is first unwrapped via ``as_pcm_stream()``;
        WAV containers without a known raw-samples layout return ``None``.
        """
        if isinstance(stream, WavStreamResource):
            stream = stream.as_pcm_stream()

            if stream is None:
                return None

        source_sample_rate = int(stream.attrs.get("sample_rate", 16000))
        source_channels = int(stream.attrs.get("channels", 1))

        if self._sample_rate is not None and self._sample_rate != source_sample_rate:
            return None

        if self._channels is not None and self._channels != source_channels:
            return None

        async def _stream() -> AsyncIterator[bytes]:
            async for chunk in stream:
                yield chunk

        return _stream(), stream.attrs

    @staticmethod
    def _is_torchaudio_available() -> bool:
        try:
            import torchaudio
        except ImportError:
            return False
        return True

class AudioBufferStreamer:
    """Frame-by-frame async iterator over an audio source.

    Each `__aiter__` re-decodes the source, so repeated iteration requires a
    re-consumable `MediaSource` (file-backed); one-shot streams yield nothing
    on the second pass.

    `channel`: `None` keeps original layout as `(channels, samples)` (mono stays
    1D); `"mono"` downmixes; `int` picks that channel index (1D).
    `sample_rate` resamples on the fly.
    `frame_size` is in target-rate samples; `None` yields the entire waveform
    as one frame (fast path for `.collect()`, skips framing/padding).
    `hop_size < frame_size` produces overlap. `pad_final` zero-pads the trailing
    partial frame. Both ignored when `frame_size is None`.
    """
    @dataclass
    class StreamContext:
        source: PcmStreamResource
        source_format: str
        source_channels: int
        source_block_align: int
        source_sample_rate: int
        channels: int
        keep_channels: bool
        sample_rate: int
        resampler: Optional[Any]
        frame_buffer: np.ndarray
        frame_size: Optional[int]
        hop_size: Optional[int]
        pad_final: bool
        input_buffer: bytearray = field(default_factory=bytearray)

    def __init__(
        self,
        source: MediaSource,
        frame_size: Optional[int] = None,
        channel: Optional[Union[int, Literal["mono"]]] = None,
        sample_rate: Optional[int] = None,
        hop_size: Optional[int] = None,
        pad_final: bool = True,
    ):
        if frame_size is not None:
            if hop_size is None:
                hop_size = frame_size

            if hop_size <= 0 or hop_size > frame_size:
                raise ValueError(f"hop_size must satisfy 0 < hop_size <= frame_size; got hop_size={hop_size}, frame_size={frame_size}")

        self._source      = source
        self._channel     = channel
        self._sample_rate = sample_rate  # None means "match source"; resolved per iteration
        self._frame_size  = frame_size   # None means "yield the whole waveform as one frame"
        self._hop_size    = hop_size
        self._pad_final   = pad_final

    async def stream(self, chunk_size: int, overlap_size: int = 0) -> AsyncIterator[Tuple[AudioBuffer, bool]]:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive; got {chunk_size}")

        if not 0 <= overlap_size < chunk_size:
            raise ValueError(f"overlap_size must satisfy 0 <= overlap < chunk; got {overlap_size} / {chunk_size}")

        hop_size = chunk_size - overlap_size
        pending: Optional[AudioBuffer] = None

        async for chunk in self._iterate(chunk_size, hop_size, pad_final=True):
            if pending is not None:
                yield pending, False
            pending = chunk

        if pending is not None:
            yield pending, True

    async def collect(self) -> AudioBuffer:
        import numpy as np

        frames: list = []
        sample_rate: Optional[int] = None

        async for chunk in self._iterate(self._frame_size, self._hop_size, self._pad_final):
            frames.append(chunk.waveform)
            sample_rate = chunk.sample_rate

        waveform = frames[0] if len(frames) == 1 else np.concatenate(frames, axis=-1)
        return AudioBuffer(waveform=waveform, sample_rate=sample_rate)

    async def as_iterator(self) -> AudioBufferStreamIterator:
        iterator = self._iterate(self._frame_size, self._hop_size, self._pad_final)

        try:
            first_chunk = await anext(iterator)
        except StopAsyncIteration:
            raise ValueError("Cannot build AudioBufferStreamIterator from an empty audio source")

        async def _stream() -> AsyncIterator[AudioBuffer]:
            yield first_chunk
            async for chunk in iterator:
                yield chunk

        return AudioBufferStreamIterator(
            source=_stream(),
            sample_rate=first_chunk.sample_rate,
            channels=first_chunk.channels,
        )

    def __aiter__(self) -> AsyncIterator[AudioBuffer]:
        return self._iterate(self._frame_size, self._hop_size, self._pad_final)

    async def _iterate(
        self,
        frame_size: Optional[int],
        hop_size: Optional[int],
        pad_final: bool,
    ) -> AsyncIterator[AudioBuffer]:
        # Push resample / mono downmix into ffmpeg; `channel=int` still needs
        # the original channels since ffmpeg -ac can only downmix.
        sample_rate, channels = self._sample_rate, 1 if self._channel == "mono" else None
        source = AudioDecodingStreamer(self._source, sample_rate, channels).as_pcm_stream()

        # ``AudioDecodingStreamer`` populates ``source.attrs`` from the WAV
        # header (or the torchaudio decode result) as its first chunks stream
        # in. Prime the iterator so the layout is resolved before
        # ``_create_stream_context`` reads sr/channels.
        source_iterator = aiter(source)
        prefetched_chunks: List[bytes] = []

        try:
            while "sample_rate" not in source.attrs:
                prefetched_chunks.append(await anext(source_iterator))
        except StopAsyncIteration:
            pass

        context = self._create_stream_context(source, frame_size, hop_size, pad_final)

        async def _remaining_chunks() -> AsyncIterator[bytes]:
            for chunk in prefetched_chunks:
                yield chunk
            async for chunk in source_iterator:
                yield chunk

        async for chunk in _remaining_chunks():
            if not chunk:
                continue

            # Assemble whole interleaved samples (one per channel) from possibly-split bytes.
            context.input_buffer.extend(chunk)

            aligned_len = (len(context.input_buffer) // context.source_block_align) * context.source_block_align

            if aligned_len == 0:
                continue

            chunk = bytes(context.input_buffer[:aligned_len])
            del context.input_buffer[:aligned_len]

            for waveform in await asyncio.to_thread(self._process_chunk, context, chunk):
                yield AudioBuffer(waveform=waveform, sample_rate=context.sample_rate)

        for waveform in await asyncio.to_thread(self._process_final, context):
            yield AudioBuffer(waveform=waveform, sample_rate=context.sample_rate)

    def _create_stream_context(
        self,
        source: PcmStreamResource,
        frame_size: Optional[int],
        hop_size: Optional[int],
        pad_final: bool,
    ) -> AudioBufferStreamer.StreamContext:
        source_format = source.format
        source_channels = int(source.attrs.get("channels", 1))
        source_block_align = get_pcm_dtype(source_format).itemsize * source_channels
        source_sample_rate = int(source.attrs.get("sample_rate", 16000))

        if source_channels > 1 and isinstance(self._channel, int) and (self._channel < 0 or self._channel >= source_channels):
            raise ValueError(f"channel must satisfy 0 <= channel < channels; got channel={self._channel}, channels={source_channels}")

        # Output shape decision: keep 2D iff source is multi-channel AND caller asked to
        # preserve channels. Everything else collapses to 1D.
        keep_channels = source_channels > 1 and self._channel is None
        channels = source_channels if keep_channels else 1
        sample_rate = self._sample_rate if self._sample_rate is not None else source_sample_rate
        resampler = None

        if sample_rate != source_sample_rate:
            import soxr

            resampler = soxr.ResampleStream(source_sample_rate, sample_rate, num_channels=channels, dtype="float32")

        return AudioBufferStreamer.StreamContext(
            source=source,
            source_format=source_format,
            source_channels=source_channels,
            source_block_align=source_block_align,
            source_sample_rate=source_sample_rate,
            channels=channels,
            keep_channels=keep_channels,
            sample_rate=sample_rate,
            resampler=resampler,
            frame_buffer=self._empty_frame_buffer(channels, keep_channels),
            frame_size=frame_size,
            hop_size=hop_size,
            pad_final=pad_final,
        )

    def _process_chunk(self, context: AudioBufferStreamer.StreamContext, chunk: bytes) -> list:
        samples = self._decode_to_samples(context, chunk)

        if context.resampler is not None:
            samples = self._resample(context, samples)

        self._push_samples(context, samples)

        return list(self._drain_frames(context, final=False))

    def _process_final(self, context: AudioBufferStreamer.StreamContext) -> list:
        if context.resampler is not None:
            tail = self._resample(context, self._empty_frame_buffer(context.channels, context.keep_channels), last=True)
            self._push_samples(context, tail)

        return list(self._drain_frames(context, final=True))

    def _decode_to_samples(self, context: AudioBufferStreamer.StreamContext, chunk: bytes) -> np.ndarray:
        samples = decode_pcm_to_waveform(chunk, context.source_format, dtype="float32", channels=context.source_channels)

        if context.source_channels > 1:
            # samples shape: (channels, frames)
            if self._channel == "mono":
                samples = samples.mean(axis=0)
            elif isinstance(self._channel, int):
                samples = samples[self._channel]

        return samples

    def _resample(self, context: AudioBufferStreamer.StreamContext, samples: np.ndarray, last: bool = False) -> np.ndarray:
        # soxr expects (samples, channels) interleaved for multi-channel; single-channel
        # accepts either 1D or 2D. Round-trip via transpose for our (channels, samples) layout.
        if context.keep_channels:
            return context.resampler.resample_chunk(samples.T, last=last).T

        return context.resampler.resample_chunk(samples, last=last)

    def _push_samples(self, context: AudioBufferStreamer.StreamContext, samples: np.ndarray) -> None:
        import numpy as np

        if samples.shape[-1] == 0:
            return

        context.frame_buffer = np.concatenate([ context.frame_buffer, samples ], axis=-1) if context.frame_buffer.shape[-1] > 0 else samples

    def _drain_frames(self, context: AudioBufferStreamer.StreamContext, final: bool):
        # Collect mode: hold everything until EOF, then yield one whole-waveform frame.
        if context.frame_size is None:
            if final:
                frame = context.frame_buffer
                context.frame_buffer = self._empty_frame_buffer(context.channels, context.keep_channels)
                yield frame
            return

        while context.frame_buffer.shape[-1] >= context.frame_size:
            frame = context.frame_buffer[..., :context.frame_size]
            context.frame_buffer = context.frame_buffer[..., context.hop_size:]
            yield frame

        if final and context.pad_final and context.frame_buffer.shape[-1] > 0:
            frame = self._pad_frame(context.frame_buffer, context.frame_size)
            context.frame_buffer = self._empty_frame_buffer(context.channels, context.keep_channels)
            yield frame

    def _pad_frame(self, samples: np.ndarray, pad_to: int) -> np.ndarray:
        import numpy as np

        if samples.shape[-1] < pad_to:
            pad_width = [ (0, 0) ] * (samples.ndim - 1) + [ (0, pad_to - samples.shape[-1]) ]
            samples = np.pad(samples, pad_width)

        return samples

    def _empty_frame_buffer(self, channels: int, keep_channels: bool) -> np.ndarray:
        import numpy as np

        return np.zeros((channels, 0), dtype=np.float32) if keep_channels else np.zeros(0, dtype=np.float32)

def create_audio_source(value: Any) -> MediaSource:
    if isinstance(value, PcmStreamResource):
        return MediaSource(value, value.format, value.attrs)

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

def is_audio_streamable(source: MediaSource) -> bool:
    if not is_pcm_format(source.format):
        return False

    if source.attrs.get("sample_rate") is None:
        return False

    return True
