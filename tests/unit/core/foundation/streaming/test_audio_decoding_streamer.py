"""Unit tests for ``AudioDecodingStreamer``.

Verifies each dispatch branch:
- PCM pass-through
- ffmpeg subprocess decode (streaming)
- torchaudio fallback (non-streaming)
- error when no decoder is available
"""

from __future__ import annotations

import io
import wave

import numpy as np
import pytest

from mindor.core.foundation.streaming.audio import (
    AudioDecodingStreamer,
    PcmStreamResource,
    WavStreamResource,
)
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import StreamResource


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

class ChunkedStreamResource(StreamResource):
    def __init__(self, data: bytes, chunk_size: int):
        super().__init__("application/octet-stream", None)
        self._data = data
        self._chunk_size = chunk_size

    async def close(self) -> None:
        pass

    async def _iterate_stream(self):
        for i in range(0, len(self._data), self._chunk_size):
            yield self._data[i:i + self._chunk_size]


def make_sine_int16(freq: float, sample_rate: int, duration: float) -> np.ndarray:
    t = np.arange(int(sample_rate * duration)) / sample_rate
    return (np.sin(2 * np.pi * freq * t) * 0.5 * 32767).astype(np.int16)


def build_wav_bytes(samples: np.ndarray, sample_rate: int, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        if channels > 1 and samples.ndim == 2:
            samples = samples.T.reshape(-1)
        w.writeframes(samples.astype("<i2").tobytes())
    return buf.getvalue()


async def collect_bytes(stream: PcmStreamResource) -> bytes:
    chunks = []
    async with stream:
        async for chunk in stream:
            chunks.append(chunk)
    return b"".join(chunks)


# ---- Pass-through path ----

class TestPassThrough:
    @pytest.mark.anyio
    async def test_raw_pcm_passes_through(self):
        samples = make_sine_int16(440.0, 16000, 0.05)
        pcm_bytes = samples.tobytes()
        attrs = {"sample_rate": 16000, "channels": 1, "bit_depth": 16}
        pcm = PcmStreamResource(BytesStreamResource(pcm_bytes), attrs=attrs)
        source = MediaSource(pcm, format=pcm.format, attrs=attrs)

        out = AudioDecodingStreamer(source).as_pcm_stream()

        # Bytes untouched when the source already matches (no re-decode)
        assert out.attrs == attrs
        data = await collect_bytes(out)
        assert data == pcm_bytes

    @pytest.mark.anyio
    async def test_raw_pcm_with_matching_target_still_passes_through(self):
        samples = make_sine_int16(440.0, 16000, 0.05)
        pcm_bytes = samples.tobytes()
        attrs = {"sample_rate": 16000, "channels": 1, "bit_depth": 16}
        pcm = PcmStreamResource(BytesStreamResource(pcm_bytes), attrs=attrs)
        source = MediaSource(pcm, format=pcm.format, attrs=attrs)

        out = AudioDecodingStreamer(source, sample_rate=16000, channels=1).as_pcm_stream()
        assert out.attrs == attrs
        data = await collect_bytes(out)
        assert data == pcm_bytes


# ---- ffmpeg path ----

class TestFFmpegDecode:
    @pytest.mark.anyio
    async def test_decode_wav_to_pcm(self):
        samples = make_sine_int16(440.0, 16000, 0.1)
        wav = build_wav_bytes(samples, sample_rate=16000, channels=1)

        source = MediaSource(BytesStreamResource(wav), format="wav")
        out = AudioDecodingStreamer(source).as_pcm_stream()

        assert isinstance(out, PcmStreamResource)
        assert out.attrs.get("bit_depth") == 16

        pcm = await collect_bytes(out)
        decoded = np.frombuffer(pcm, dtype="<i2")

        # ffmpeg s16le round-trip should preserve length and rough amplitude.
        assert len(decoded) == len(samples)
        assert np.max(np.abs(decoded)) > 1000

    @pytest.mark.anyio
    async def test_decode_wav_with_resample(self):
        samples = make_sine_int16(440.0, 44100, 0.1)
        wav = build_wav_bytes(samples, sample_rate=44100, channels=1)

        source = MediaSource(BytesStreamResource(wav), format="wav")
        out = AudioDecodingStreamer(source, sample_rate=16000).as_pcm_stream()

        assert out.attrs["sample_rate"] == 16000
        pcm = await collect_bytes(out)
        decoded = np.frombuffer(pcm, dtype="<i2")

        expected_len = int(len(samples) * 16000 / 44100)
        # allow ±2% tolerance for resampler filter tail
        assert abs(len(decoded) - expected_len) < expected_len * 0.02

    @pytest.mark.anyio
    async def test_decode_stereo_wav_downmix_to_mono(self):
        left = make_sine_int16(440.0, 16000, 0.1)
        right = make_sine_int16(880.0, 16000, 0.1)
        stereo = np.stack([left, right], axis=0)  # (channels, samples)
        wav = build_wav_bytes(stereo, sample_rate=16000, channels=2)

        source = MediaSource(BytesStreamResource(wav), format="wav")
        out = AudioDecodingStreamer(source, channels=1).as_pcm_stream()

        assert out.attrs["channels"] == 1
        pcm = await collect_bytes(out)
        decoded = np.frombuffer(pcm, dtype="<i2")
        assert len(decoded) == left.size  # mono output

    @pytest.mark.anyio
    async def test_ffmpeg_invalid_input_raises(self):
        source = MediaSource(BytesStreamResource(b"not audio data"), format="wav")
        out = AudioDecodingStreamer(source).as_pcm_stream()

        with pytest.raises(RuntimeError, match="ffmpeg audio decoding failed"):
            await collect_bytes(out)

    @pytest.mark.anyio
    async def test_raw_pcm_source_reencoded_when_target_differs(self):
        # Even though input is raw PCM, requesting a different sample rate
        # forces a re-decode path.
        samples = make_sine_int16(440.0, 44100, 0.1)
        attrs = {"sample_rate": 44100, "channels": 1, "bit_depth": 16}
        pcm = PcmStreamResource(BytesStreamResource(samples.tobytes()), attrs=attrs)
        source = MediaSource(pcm, format=pcm.format, attrs=attrs)

        out = AudioDecodingStreamer(source, sample_rate=16000).as_pcm_stream()

        assert out is not pcm
        assert out.attrs["sample_rate"] == 16000
        data = await collect_bytes(out)
        assert len(data) > 0


# ---- WavStreamResource passthrough ----

class TestWavPassThrough:
    @pytest.mark.anyio
    async def test_wav_wrapping_raw_pcm_unwraps_for_passthrough(self):
        # WavStreamResource(PcmStreamResource(...)) should skip ffmpeg entirely.
        samples = make_sine_int16(440.0, 16000, 0.05)
        pcm_bytes = samples.tobytes()
        attrs = {"sample_rate": 16000, "channels": 1, "bit_depth": 16}
        pcm = PcmStreamResource(BytesStreamResource(pcm_bytes), attrs=attrs)
        wav = WavStreamResource(pcm)

        source = MediaSource(wav, format="wav", attrs=attrs)
        out = AudioDecodingStreamer(source).as_pcm_stream()

        assert out.attrs == attrs
        # Bytes untouched — same raw PCM, no ffmpeg round-trip / WAV header.
        assert await collect_bytes(out) == pcm_bytes

    @pytest.mark.anyio
    async def test_wav_container_without_raw_samples_falls_back_to_decode(self):
        # A pre-encoded WAV blob (no PcmStreamResource inner + no attrs) has
        # `_is_raw_samples=False`, so as_pcm_stream() returns None and the
        # dispatcher routes through ffmpeg.
        samples = make_sine_int16(440.0, 16000, 0.05)
        wav_bytes = build_wav_bytes(samples, sample_rate=16000, channels=1)
        wav = WavStreamResource(wav_bytes)  # no attrs → treated as opaque WAV

        source = MediaSource(wav, format="wav")
        out = AudioDecodingStreamer(source).as_pcm_stream()

        pcm = await collect_bytes(out)
        decoded = np.frombuffer(pcm, dtype="<i2")
        assert len(decoded) == len(samples)


# ---- Direct async iteration ----

class TestAsyncIteration:
    @pytest.mark.anyio
    async def test_async_for_yields_pcm_bytes(self):
        samples = make_sine_int16(440.0, 16000, 0.1)
        wav = build_wav_bytes(samples, sample_rate=16000, channels=1)

        source = MediaSource(BytesStreamResource(wav), format="wav")
        chunks = []
        async for chunk in AudioDecodingStreamer(source):
            chunks.append(chunk)

        pcm = b"".join(chunks)
        decoded = np.frombuffer(pcm, dtype="<i2")
        assert len(decoded) == len(samples)

    @pytest.mark.anyio
    async def test_async_for_on_passthrough_source(self):
        samples = make_sine_int16(440.0, 16000, 0.05)
        pcm_bytes = samples.tobytes()
        attrs = {"sample_rate": 16000, "channels": 1, "bit_depth": 16}
        pcm = PcmStreamResource(BytesStreamResource(pcm_bytes), attrs=attrs)
        source = MediaSource(pcm, format=pcm.format, attrs=attrs)

        chunks = []
        async for chunk in AudioDecodingStreamer(source):
            chunks.append(chunk)

        assert b"".join(chunks) == pcm_bytes


# ---- torchaudio fallback ----

class TestTorchaudioFallback:
    @pytest.mark.anyio
    async def test_decode_wav_via_torchaudio(self, monkeypatch):
        # Force torchaudio path by pretending ffmpeg is missing.
        import mindor.core.foundation.streaming.audio as audio_module
        monkeypatch.setattr(audio_module.shutil, "which", lambda name: None)

        samples = make_sine_int16(440.0, 16000, 0.1)
        wav = build_wav_bytes(samples, sample_rate=16000, channels=1)

        source = MediaSource(BytesStreamResource(wav), format="wav")
        out = AudioDecodingStreamer(source).as_pcm_stream()

        assert isinstance(out, PcmStreamResource)
        pcm = await collect_bytes(out)
        decoded = np.frombuffer(pcm, dtype="<i2")

        assert len(decoded) == len(samples)
        assert np.max(np.abs(decoded)) > 1000

    @pytest.mark.anyio
    async def test_no_decoder_raises(self, monkeypatch):
        import mindor.core.foundation.streaming.audio as audio_module
        monkeypatch.setattr(audio_module.shutil, "which", lambda name: None)
        monkeypatch.setattr(
            AudioDecodingStreamer, "_is_torchaudio_available", staticmethod(lambda: False)
        )

        source = MediaSource(BytesStreamResource(b"whatever"), format="wav")
        with pytest.raises(RuntimeError, match="No audio decoder available"):
            AudioDecodingStreamer(source).as_pcm_stream()
