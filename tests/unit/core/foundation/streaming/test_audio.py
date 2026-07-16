"""Unit tests for ``mindor.core.foundation.streaming.audio``.

Covers:
- ``is_audio_streamable``: dispatch predicate for PCM streaming eligibility.
- ``load_audio_array``: MediaSource -> full waveform (with optional resample / channel).
- ``stream_audio_array``: MediaSource -> per-frame async iterator of float32 arrays.
"""

from __future__ import annotations

import io
import wave

import numpy as np
import pytest

from mindor.core.foundation.streaming.audio import (
    is_audio_streamable,
    load_audio_array,
    stream_audio_array,
)
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import StreamResource


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

class ChunkedStreamResource(StreamResource):
    """Async stream resource that yields fixed-size chunks from a byte buffer.

    Used to simulate different chunk arrival patterns (small/large/misaligned)
    without relying on real network/file IO.
    """
    def __init__(self, data: bytes, chunk_size: int):
        super().__init__("audio/pcm", None)
        self._data = data
        self._chunk_size = chunk_size

    async def close(self) -> None:
        pass

    async def _iterate_stream(self):
        for i in range(0, len(self._data), self._chunk_size):
            yield self._data[i:i + self._chunk_size]


def pcm_mono_source(samples: np.ndarray, sample_rate: int = 16000, chunk_size: int = 8000) -> MediaSource:
    """Wrap an int16 mono sample array as an s16le PCM MediaSource."""
    return MediaSource(
        ChunkedStreamResource(samples.astype("<i2").tobytes(), chunk_size),
        format="s16le",
        attrs={"sample_rate": sample_rate, "channels": 1},
    )


def pcm_stereo_source(left: np.ndarray, right: np.ndarray, sample_rate: int = 16000, chunk_size: int = 8000) -> MediaSource:
    """Wrap two int16 channel arrays as an interleaved s16le stereo MediaSource."""
    assert left.shape == right.shape
    interleaved = np.empty(left.size * 2, dtype=np.int16)
    interleaved[0::2] = left.astype(np.int16)
    interleaved[1::2] = right.astype(np.int16)
    return MediaSource(
        ChunkedStreamResource(interleaved.tobytes(), chunk_size),
        format="s16le",
        attrs={"sample_rate": sample_rate, "channels": 2},
    )


def build_wav_bytes(samples: np.ndarray, sample_rate: int, channels: int = 1, bit_depth: int = 16) -> bytes:
    """Build a minimal WAV container from int16 samples for compressed-path tests."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(bit_depth // 8)
        w.setframerate(sample_rate)
        if channels > 1 and samples.ndim == 2:
            # Interleave (channels, samples) -> (samples * channels,)
            samples = samples.T.reshape(-1)
        w.writeframes(samples.astype("<i2").tobytes())
    return buf.getvalue()


async def collect_frames(gen) -> list:
    return [frame async for frame in gen]


# ---- is_audio_streamable ----

class TestIsAudioStreamable:
    def test_pcm_s16le_with_sample_rate(self):
        src = MediaSource(BytesStreamResource(b""), format="s16le", attrs={"sample_rate": 16000, "channels": 1})
        assert is_audio_streamable(src) is True

    def test_pcm_f32le_with_sample_rate(self):
        src = MediaSource(BytesStreamResource(b""), format="f32le", attrs={"sample_rate": 44100, "channels": 2})
        assert is_audio_streamable(src) is True

    def test_pcm_all_supported_formats(self):
        for fmt in ("u8", "s16le", "s24le", "s32le", "f32le", "f64le"):
            src = MediaSource(BytesStreamResource(b""), format=fmt, attrs={"sample_rate": 16000})
            assert is_audio_streamable(src) is True, f"{fmt} should be streamable"

    def test_multichannel_is_streamable(self):
        src = MediaSource(BytesStreamResource(b""), format="s16le", attrs={"sample_rate": 48000, "channels": 8})
        assert is_audio_streamable(src) is True

    def test_missing_sample_rate_is_not_streamable(self):
        src = MediaSource(BytesStreamResource(b""), format="s16le", attrs={"channels": 1})
        assert is_audio_streamable(src) is False

    def test_mp3_is_not_streamable(self):
        src = MediaSource(BytesStreamResource(b""), format="mp3", attrs={"sample_rate": 16000})
        assert is_audio_streamable(src) is False

    def test_none_format_is_not_streamable(self):
        src = MediaSource(BytesStreamResource(b""), attrs={"sample_rate": 16000})
        assert is_audio_streamable(src) is False

    def test_wav_container_is_not_streamable(self):
        # WAV container format is not raw PCM (needs header parsing)
        src = MediaSource(BytesStreamResource(b""), format="wav", attrs={"sample_rate": 16000})
        assert is_audio_streamable(src) is False


# ---- load_audio_array ----

class TestLoadAudioArrayPcm:
    @pytest.mark.anyio
    async def test_pcm_s16le_mono_default(self):
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples)
        waveform, sr = await load_audio_array(src)
        assert waveform.dtype == np.int16
        assert waveform.shape == (1000,)
        assert sr == 16000
        assert np.array_equal(waveform, samples)

    @pytest.mark.anyio
    async def test_pcm_s16le_stereo_default_is_downmix(self):
        # Multi-channel default reduces to mono via mean downmix.
        left = np.full(500, 1000, dtype=np.int16)
        right = np.full(500, 3000, dtype=np.int16)
        src = pcm_stereo_source(left, right)
        waveform, sr = await load_audio_array(src)
        assert waveform.shape == (500,)
        assert waveform.dtype == np.float32
        assert sr == 16000
        assert np.allclose(waveform, 2000.0)

    @pytest.mark.anyio
    async def test_pcm_stereo_mean_downmix(self):
        left = np.full(500, 1000, dtype=np.int16)
        right = np.full(500, 3000, dtype=np.int16)
        src = pcm_stereo_source(left, right)
        waveform, sr = await load_audio_array(src, channel=None)
        assert waveform.shape == (500,)
        assert waveform.dtype == np.float32
        # Mean of (1000, 3000) = 2000
        assert np.allclose(waveform, 2000.0)

    @pytest.mark.anyio
    async def test_pcm_stereo_select_left(self):
        left = np.arange(500, dtype=np.int16)
        right = np.arange(500, dtype=np.int16) + 1000
        src = pcm_stereo_source(left, right)
        waveform, sr = await load_audio_array(src, channel=0)
        assert waveform.shape == (500,)
        assert np.array_equal(waveform, left)

    @pytest.mark.anyio
    async def test_pcm_stereo_select_right(self):
        left = np.arange(500, dtype=np.int16)
        right = np.arange(500, dtype=np.int16) + 1000
        src = pcm_stereo_source(left, right)
        waveform, sr = await load_audio_array(src, channel=1)
        assert np.array_equal(waveform, right)

    @pytest.mark.anyio
    async def test_pcm_channel_out_of_range_raises(self):
        left = np.zeros(100, dtype=np.int16)
        right = np.zeros(100, dtype=np.int16)
        src = pcm_stereo_source(left, right)
        with pytest.raises(ValueError, match="channel must satisfy"):
            await load_audio_array(src, channel=5)

    @pytest.mark.anyio
    async def test_mono_source_ignores_out_of_range_channel(self):
        # Mono waveform is 1-D; channel is silently ignored.
        samples = np.arange(100, dtype=np.int16)
        src = pcm_mono_source(samples)
        waveform, _ = await load_audio_array(src, channel=5)
        assert np.array_equal(waveform, samples)

    @pytest.mark.anyio
    async def test_pcm_missing_sample_rate_defaults_to_16000(self):
        samples = np.arange(100, dtype=np.int16)
        src = MediaSource(
            ChunkedStreamResource(samples.tobytes(), 1000),
            format="s16le",
            attrs={"channels": 1},
        )
        _, sr = await load_audio_array(src)
        assert sr == 16000

    @pytest.mark.anyio
    async def test_pcm_resample_16k_to_8k(self):
        # Build a 1s sine at 16k, resample to 8k, check length halves.
        sr_in = 16000
        n = sr_in
        samples = (np.sin(2 * np.pi * 440 * np.arange(n) / sr_in) * 10000).astype(np.int16)
        src = pcm_mono_source(samples, sample_rate=sr_in, chunk_size=n * 2)
        waveform, sr_out = await load_audio_array(src, sample_rate=8000)
        assert sr_out == 8000
        assert waveform.dtype == np.float32
        # ~8000 samples with some soxr tail tolerance
        assert 7900 <= waveform.shape[0] <= 8100

    @pytest.mark.anyio
    async def test_pcm_resample_same_rate_is_noop(self):
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples, sample_rate=16000)
        waveform, sr = await load_audio_array(src, sample_rate=16000)
        assert sr == 16000
        # Should preserve int16 dtype (no resample = no cast)
        assert waveform.dtype == np.int16
        assert np.array_equal(waveform, samples)


class TestLoadAudioArrayCompressed:
    @pytest.mark.anyio
    async def test_wav_container_decoded_via_torchaudio(self):
        samples = np.arange(1600, dtype=np.int16)
        wav_bytes = build_wav_bytes(samples, sample_rate=16000, channels=1)
        src = MediaSource(BytesStreamResource(wav_bytes), format="wav")
        waveform, sr = await load_audio_array(src)
        assert sr == 16000
        # torchaudio yields (1, N) tensor for mono, our code preserves that shape
        # unless channel selection kicks in
        assert waveform.ndim in (1, 2)

    @pytest.mark.anyio
    async def test_wav_container_resample_and_downmix(self):
        samples = np.arange(3200, dtype=np.int16)
        wav_bytes = build_wav_bytes(samples, sample_rate=32000, channels=1)
        src = MediaSource(BytesStreamResource(wav_bytes), format="wav")
        waveform, sr = await load_audio_array(src, sample_rate=16000)
        assert sr == 16000
        assert waveform.dtype == np.float32
        # ~half length; allow tolerance for filter tail
        assert 1500 <= waveform.shape[-1] <= 1700


# ---- stream_audio_array ----

class TestStreamAudioArrayBasic:
    @pytest.mark.anyio
    async def test_mono_default_non_overlapping(self):
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(stream_audio_array(src, 512))
        # 2048 / 512 = 4 frames, no padding needed
        assert len(frames) == 4
        for f in frames:
            assert f.shape == (512,)
            assert f.dtype == np.float32

    @pytest.mark.anyio
    async def test_normalization_to_unit_range(self):
        # int16 max/min normalize to ~1.0 / ~-1.0
        samples = np.array([32767, -32768, 0, 16384] * 128, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=len(samples) * 2)
        frames = await collect_frames(stream_audio_array(src, 512))
        assert frames[0][0] == pytest.approx(32767 / 32768, rel=1e-3)
        assert frames[0][1] == pytest.approx(-32768 / 32768, rel=1e-3)
        assert frames[0][2] == 0.0
        assert frames[0][3] == pytest.approx(16384 / 32768, rel=1e-3)

    @pytest.mark.anyio
    async def test_final_frame_zero_padded_by_default(self):
        # 1500 samples = 2 full frames of 512 + 476 tail
        samples = np.arange(1500, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(stream_audio_array(src, 512))
        assert len(frames) == 3
        # Last frame's trailing samples should be zero-padded
        assert frames[-1].shape == (512,)
        assert np.all(frames[-1][476:] == 0.0)

    @pytest.mark.anyio
    async def test_pad_final_false_drops_tail(self):
        samples = np.arange(1500, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(stream_audio_array(src, 512, pad_final=False))
        # Tail dropped: only 2 full frames
        assert len(frames) == 2


class TestStreamAudioArrayOverlap:
    @pytest.mark.anyio
    async def test_hop_half_frame_produces_double_frames(self):
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(stream_audio_array(src, 512, hop_size=256))
        # (2048 - 512) / 256 + 1 = 7 full frames, +tail padded = 8
        assert len(frames) == 8

    @pytest.mark.anyio
    async def test_overlap_frames_share_data(self):
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(stream_audio_array(src, 512, hop_size=256))
        # Overlap: last 256 samples of frame[0] == first 256 samples of frame[1]
        assert np.allclose(frames[0][256:], frames[1][:256])

    @pytest.mark.anyio
    async def test_hop_size_zero_raises(self):
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples)
        with pytest.raises(ValueError, match="hop_size must satisfy"):
            async for _ in stream_audio_array(src, 512, hop_size=0):
                pass

    @pytest.mark.anyio
    async def test_hop_size_greater_than_frame_raises(self):
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples)
        with pytest.raises(ValueError, match="hop_size must satisfy"):
            async for _ in stream_audio_array(src, 512, hop_size=513):
                pass


class TestStreamAudioArrayChunkAlignment:
    @pytest.mark.anyio
    @pytest.mark.parametrize("chunk_size", [1, 3, 500, 999, 1024, 8192])
    async def test_chunk_size_independence_mono(self, chunk_size):
        # Result should not depend on how bytes are split across chunks.
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=chunk_size)
        frames = await collect_frames(stream_audio_array(src, 512))
        assert len(frames) == 4
        # Concatenated frames should reproduce the source (float32 normalized)
        concat = np.concatenate(frames)
        expected = samples.astype(np.float32) / 32768.0
        assert np.allclose(concat, expected)

    @pytest.mark.anyio
    async def test_stereo_odd_chunks_realign_correctly(self):
        left = np.arange(2048, dtype=np.int16)
        right = np.arange(2048, dtype=np.int16) + 1000
        # 333 bytes is NOT aligned to 4 (2 chan * 2 bytes/sample)
        src = pcm_stereo_source(left, right, chunk_size=333)
        frames_odd = await collect_frames(stream_audio_array(src, 512, channel=0))
        src = pcm_stereo_source(left, right, chunk_size=8000)
        frames_aligned = await collect_frames(stream_audio_array(src, 512, channel=0))
        assert len(frames_odd) == len(frames_aligned)
        for a, b in zip(frames_odd, frames_aligned):
            assert np.allclose(a, b)


class TestStreamAudioArrayChannel:
    @pytest.mark.anyio
    async def test_stereo_default_is_mean_downmix(self):
        left = np.full(2048, 1000, dtype=np.int16)
        right = np.full(2048, 3000, dtype=np.int16)
        src = pcm_stereo_source(left, right, chunk_size=500)
        frames = await collect_frames(stream_audio_array(src, 512))
        # Mean of (1000, 3000) = 2000; normalized = 2000/32768
        assert frames[0][0] == pytest.approx(2000 / 32768, rel=1e-3)

    @pytest.mark.anyio
    async def test_stereo_channel_selection(self):
        left = np.arange(2048, dtype=np.int16)
        right = np.arange(2048, dtype=np.int16) + 1000
        src = pcm_stereo_source(left, right, chunk_size=500)
        frames_l = await collect_frames(stream_audio_array(src, 512, channel=0))
        src = pcm_stereo_source(left, right, chunk_size=500)
        frames_r = await collect_frames(stream_audio_array(src, 512, channel=1))
        assert frames_l[0][0] == 0.0
        assert frames_r[0][0] == pytest.approx(1000 / 32768, rel=1e-3)

    @pytest.mark.anyio
    async def test_stereo_channel_out_of_range_raises(self):
        left = np.zeros(1000, dtype=np.int16)
        right = np.zeros(1000, dtype=np.int16)
        src = pcm_stereo_source(left, right)
        with pytest.raises(ValueError, match="channel must satisfy"):
            async for _ in stream_audio_array(src, 512, channel=5):
                pass

    @pytest.mark.anyio
    async def test_mono_ignores_invalid_channel(self):
        # Consistent with load_audio_array: mono sources silently ignore channel.
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples)
        frames = await collect_frames(stream_audio_array(src, 512, channel=5))
        assert len(frames) >= 1


class TestStreamAudioArrayResample:
    @pytest.mark.anyio
    async def test_native_rate_no_resampler(self):
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, sample_rate=16000, chunk_size=8000)
        frames = await collect_frames(stream_audio_array(src, 512, sample_rate=16000))
        # No resample = source samples preserved (up to normalization)
        assert len(frames) == 4
        concat = np.concatenate(frames)
        expected = samples.astype(np.float32) / 32768.0
        assert np.allclose(concat, expected)

    @pytest.mark.anyio
    async def test_resample_48k_to_16k_shrinks_output(self):
        # 1s of 48k input => ~1s of 16k output
        sr_in = 48000
        samples = (np.sin(2 * np.pi * 440 * np.arange(sr_in) / sr_in) * 10000).astype(np.int16)
        src = pcm_mono_source(samples, sample_rate=sr_in, chunk_size=8000)
        frames = await collect_frames(stream_audio_array(src, 512, sample_rate=16000))
        total = sum(f.shape[0] for f in frames)
        # ~16000 samples, allow filter tail tolerance
        assert 15500 <= total <= 16500

    @pytest.mark.anyio
    async def test_missing_sample_rate_defaults_to_16000(self):
        # No sample_rate in attrs but target is also 16000 => no resample
        samples = np.arange(2048, dtype=np.int16)
        src = MediaSource(
            ChunkedStreamResource(samples.tobytes(), 500),
            format="s16le",
            attrs={"channels": 1},
        )
        frames = await collect_frames(stream_audio_array(src, 512, sample_rate=16000))
        assert len(frames) == 4  # No resample path taken


class TestStreamAudioArrayValidation:
    @pytest.mark.anyio
    async def test_non_pcm_format_raises(self):
        src = MediaSource(BytesStreamResource(b""), format="mp3", attrs={"sample_rate": 16000})
        with pytest.raises(ValueError, match="raw PCM source"):
            async for _ in stream_audio_array(src, 512):
                pass

    @pytest.mark.anyio
    async def test_none_format_raises(self):
        src = MediaSource(BytesStreamResource(b""), attrs={"sample_rate": 16000})
        with pytest.raises(ValueError, match="raw PCM source"):
            async for _ in stream_audio_array(src, 512):
                pass


class TestStreamAudioArrayFloat32Source:
    @pytest.mark.anyio
    async def test_f32le_no_normalization_applied(self):
        # float32 PCM must not be rescaled; values pass through untouched.
        samples = np.array([0.5, -0.25, 0.0, 1.0] * 128, dtype=np.float32)
        src = MediaSource(
            ChunkedStreamResource(samples.tobytes(), 500),
            format="f32le",
            attrs={"sample_rate": 16000, "channels": 1},
        )
        frames = await collect_frames(stream_audio_array(src, 512))
        # First 4 samples preserved as-is
        assert frames[0][0] == 0.5
        assert frames[0][1] == -0.25
        assert frames[0][2] == 0.0
        assert frames[0][3] == 1.0
