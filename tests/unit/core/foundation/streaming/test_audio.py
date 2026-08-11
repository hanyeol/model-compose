"""Unit tests for ``mindor.core.foundation.streaming.audio``.

Covers:
- ``is_audio_streamable``: dispatch predicate for PCM streaming eligibility.
- ``AudioBufferStreamer``: MediaSource -> per-frame async iterator of float32
  arrays, or single-buffer ``.collect()`` for the load-all case.
"""

from __future__ import annotations

import io
import wave

import numpy as np
import pytest

from mindor.core.foundation.streaming.audio import (
    is_audio_streamable,
    AudioBufferStreamer,
    PcmStreamResource,
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
    attrs = {"sample_rate": sample_rate, "channels": 1, "bit_depth": 16}
    pcm = PcmStreamResource(
        ChunkedStreamResource(samples.astype("<i2").tobytes(), chunk_size),
        attrs=attrs,
    )
    return MediaSource(pcm, format=pcm.format, attrs=attrs)


def pcm_stereo_source(left: np.ndarray, right: np.ndarray, sample_rate: int = 16000, chunk_size: int = 8000) -> MediaSource:
    """Wrap two int16 channel arrays as an interleaved s16le stereo MediaSource."""
    assert left.shape == right.shape
    interleaved = np.empty(left.size * 2, dtype=np.int16)
    interleaved[0::2] = left.astype(np.int16)
    interleaved[1::2] = right.astype(np.int16)
    attrs = {"sample_rate": sample_rate, "channels": 2, "bit_depth": 16}
    pcm = PcmStreamResource(
        ChunkedStreamResource(interleaved.tobytes(), chunk_size),
        attrs=attrs,
    )
    return MediaSource(pcm, format=pcm.format, attrs=attrs)


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
    # AudioBufferStreamer yields AudioBuffer; existing frame-array assertions
    # keep working by unwrapping .waveform here.
    return [buffer.waveform async for buffer in gen]


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


# ---- AudioBufferStreamer.collect() — load-all cases ----

class TestCollectPcm:
    @pytest.mark.anyio
    async def test_pcm_s16le_mono_default(self):
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples)
        waveform, sr = await AudioBufferStreamer(src).collect()
        assert waveform.dtype == np.float32
        assert waveform.shape == (1000,)
        assert sr == 16000
        assert np.allclose(waveform, samples.astype(np.float32) / 32768.0)

    @pytest.mark.anyio
    async def test_pcm_s16le_stereo_default_preserves_channels(self):
        # Multi-channel default keeps the (channels, samples) layout.
        left = np.full(500, 1000, dtype=np.int16)
        right = np.full(500, 3000, dtype=np.int16)
        src = pcm_stereo_source(left, right)
        waveform, sr = await AudioBufferStreamer(src).collect()
        assert waveform.shape == (2, 500)
        assert waveform.dtype == np.float32
        assert sr == 16000
        assert np.allclose(waveform[0], 1000.0 / 32768.0)
        assert np.allclose(waveform[1], 3000.0 / 32768.0)

    @pytest.mark.anyio
    async def test_pcm_stereo_mean_downmix(self):
        left = np.full(500, 1000, dtype=np.int16)
        right = np.full(500, 3000, dtype=np.int16)
        src = pcm_stereo_source(left, right)
        waveform, sr = await AudioBufferStreamer(src, channel="mono").collect()
        assert waveform.shape == (500,)
        assert waveform.dtype == np.float32
        # Mean of (1000, 3000) = 2000, normalized to float32 by /32768.
        assert np.allclose(waveform, 2000.0 / 32768.0)

    @pytest.mark.anyio
    async def test_pcm_stereo_select_left(self):
        left = np.arange(500, dtype=np.int16)
        right = np.arange(500, dtype=np.int16) + 1000
        src = pcm_stereo_source(left, right)
        waveform, sr = await AudioBufferStreamer(src, channel=0).collect()
        assert waveform.shape == (500,)
        assert waveform.dtype == np.float32
        assert np.allclose(waveform, left.astype(np.float32) / 32768.0)

    @pytest.mark.anyio
    async def test_pcm_stereo_select_right(self):
        left = np.arange(500, dtype=np.int16)
        right = np.arange(500, dtype=np.int16) + 1000
        src = pcm_stereo_source(left, right)
        waveform, sr = await AudioBufferStreamer(src, channel=1).collect()
        assert waveform.dtype == np.float32
        assert np.allclose(waveform, right.astype(np.float32) / 32768.0)

    @pytest.mark.anyio
    async def test_pcm_channel_out_of_range_raises(self):
        left = np.zeros(100, dtype=np.int16)
        right = np.zeros(100, dtype=np.int16)
        src = pcm_stereo_source(left, right)
        with pytest.raises(ValueError, match="channel must satisfy"):
            await AudioBufferStreamer(src, channel=5).collect()

    @pytest.mark.anyio
    async def test_mono_source_ignores_out_of_range_channel(self):
        # Mono waveform is 1-D; channel is silently ignored.
        samples = np.arange(100, dtype=np.int16)
        src = pcm_mono_source(samples)
        waveform, _ = await AudioBufferStreamer(src, channel=5).collect()
        assert waveform.dtype == np.float32
        assert np.allclose(waveform, samples.astype(np.float32) / 32768.0)

    @pytest.mark.anyio
    async def test_pcm_missing_sample_rate_raises(self):
        samples = np.arange(100, dtype=np.int16)
        src = MediaSource(
            ChunkedStreamResource(samples.tobytes(), 1000),
            format="s16le",
            attrs={"channels": 1},
        )
        with pytest.raises(ValueError, match="requires 'sample_rate'"):
            await AudioBufferStreamer(src).collect()

    @pytest.mark.anyio
    async def test_pcm_resample_16k_to_8k(self):
        # Build a 1s sine at 16k, resample to 8k, check length halves.
        sr_in = 16000
        n = sr_in
        samples = (np.sin(2 * np.pi * 440 * np.arange(n) / sr_in) * 10000).astype(np.int16)
        src = pcm_mono_source(samples, sample_rate=sr_in, chunk_size=n * 2)
        waveform, sr_out = await AudioBufferStreamer(src, sample_rate=8000).collect()
        assert sr_out == 8000
        assert waveform.dtype == np.float32
        # ~8000 samples with some soxr tail tolerance
        assert 7900 <= waveform.shape[0] <= 8100

    @pytest.mark.anyio
    async def test_pcm_resample_same_rate_is_noop(self):
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples, sample_rate=16000)
        waveform, sr = await AudioBufferStreamer(src, sample_rate=16000).collect()
        assert sr == 16000
        # Integer PCM is normalized to float32 in [-1, 1] even without resampling.
        assert waveform.dtype == np.float32
        assert np.allclose(waveform, samples.astype(np.float32) / 32768.0)


class TestCollectCompressed:
    @pytest.mark.anyio
    async def test_wav_container_decoded_via_torchaudio(self):
        samples = np.arange(1600, dtype=np.int16)
        wav_bytes = build_wav_bytes(samples, sample_rate=16000, channels=1)
        src = MediaSource(BytesStreamResource(wav_bytes), format="wav")
        waveform, sr = await AudioBufferStreamer(src).collect()
        assert sr == 16000
        # torchaudio yields (1, N) tensor for mono, our code preserves that shape
        # unless channel selection kicks in
        assert waveform.ndim in (1, 2)

    @pytest.mark.anyio
    async def test_wav_container_resample_and_downmix(self):
        samples = np.arange(3200, dtype=np.int16)
        wav_bytes = build_wav_bytes(samples, sample_rate=32000, channels=1)
        src = MediaSource(BytesStreamResource(wav_bytes), format="wav")
        waveform, sr = await AudioBufferStreamer(src, sample_rate=16000, channel="mono").collect()
        assert sr == 16000
        assert waveform.dtype == np.float32
        # ~half length; allow tolerance for filter tail
        assert 1500 <= waveform.shape[-1] <= 1700


# ---- AudioBufferStreamer ----

class TestStreamAudioArrayBasic:
    @pytest.mark.anyio
    async def test_mono_default_non_overlapping(self):
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(AudioBufferStreamer(src, 512))
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
        frames = await collect_frames(AudioBufferStreamer(src, 512))
        assert frames[0][0] == pytest.approx(32767 / 32768, rel=1e-3)
        assert frames[0][1] == pytest.approx(-32768 / 32768, rel=1e-3)
        assert frames[0][2] == 0.0
        assert frames[0][3] == pytest.approx(16384 / 32768, rel=1e-3)

    @pytest.mark.anyio
    async def test_final_frame_zero_padded_by_default(self):
        # 1500 samples = 2 full frames of 512 + 476 tail
        samples = np.arange(1500, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(AudioBufferStreamer(src, 512))
        assert len(frames) == 3
        # Last frame's trailing samples should be zero-padded
        assert frames[-1].shape == (512,)
        assert np.all(frames[-1][476:] == 0.0)

    @pytest.mark.anyio
    async def test_pad_final_false_drops_tail(self):
        samples = np.arange(1500, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(AudioBufferStreamer(src, 512, pad_final=False))
        # Tail dropped: only 2 full frames
        assert len(frames) == 2


class TestStreamAudioArrayOverlap:
    @pytest.mark.anyio
    async def test_hop_half_frame_produces_double_frames(self):
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(AudioBufferStreamer(src, 512, hop_size=256))
        # (2048 - 512) / 256 + 1 = 7 full frames, +tail padded = 8
        assert len(frames) == 8

    @pytest.mark.anyio
    async def test_overlap_frames_share_data(self):
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        frames = await collect_frames(AudioBufferStreamer(src, 512, hop_size=256))
        # Overlap: last 256 samples of frame[0] == first 256 samples of frame[1]
        assert np.allclose(frames[0][256:], frames[1][:256])

    @pytest.mark.anyio
    async def test_hop_size_zero_raises(self):
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples)
        with pytest.raises(ValueError, match="hop_size must satisfy"):
            async for _ in AudioBufferStreamer(src, 512, hop_size=0):
                pass

    @pytest.mark.anyio
    async def test_hop_size_greater_than_frame_raises(self):
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples)
        with pytest.raises(ValueError, match="hop_size must satisfy"):
            async for _ in AudioBufferStreamer(src, 512, hop_size=513):
                pass


class TestStreamAudioArrayChunkAlignment:
    @pytest.mark.anyio
    @pytest.mark.parametrize("chunk_size", [1, 3, 500, 999, 1024, 8192])
    async def test_chunk_size_independence_mono(self, chunk_size):
        # Result should not depend on how bytes are split across chunks.
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=chunk_size)
        frames = await collect_frames(AudioBufferStreamer(src, 512))
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
        frames_odd = await collect_frames(AudioBufferStreamer(src, 512, channel=0))
        src = pcm_stereo_source(left, right, chunk_size=8000)
        frames_aligned = await collect_frames(AudioBufferStreamer(src, 512, channel=0))
        assert len(frames_odd) == len(frames_aligned)
        for a, b in zip(frames_odd, frames_aligned):
            assert np.allclose(a, b)


class TestStreamAudioArrayChannel:
    @pytest.mark.anyio
    async def test_stereo_default_keeps_channels(self):
        # Consistent with .collect(): default preserves channels as (channels, samples).
        left = np.full(2048, 1000, dtype=np.int16)
        right = np.full(2048, 3000, dtype=np.int16)
        src = pcm_stereo_source(left, right, chunk_size=500)
        frames = await collect_frames(AudioBufferStreamer(src, 512))
        assert frames[0].shape == (2, 512)
        assert frames[0][0, 0] == pytest.approx(1000 / 32768, rel=1e-3)
        assert frames[0][1, 0] == pytest.approx(3000 / 32768, rel=1e-3)

    @pytest.mark.anyio
    async def test_stereo_mono_downmix(self):
        # `channel="mono"` averages all channels into a single (samples,) frame.
        left = np.full(2048, 1000, dtype=np.int16)
        right = np.full(2048, 3000, dtype=np.int16)
        src = pcm_stereo_source(left, right, chunk_size=500)
        frames = await collect_frames(AudioBufferStreamer(src, 512, channel="mono"))
        assert frames[0].shape == (512,)
        # Mean of (1000, 3000) = 2000; normalized = 2000/32768
        assert frames[0][0] == pytest.approx(2000 / 32768, rel=1e-3)

    @pytest.mark.anyio
    async def test_stereo_channel_selection(self):
        left = np.arange(2048, dtype=np.int16)
        right = np.arange(2048, dtype=np.int16) + 1000
        src = pcm_stereo_source(left, right, chunk_size=500)
        frames_l = await collect_frames(AudioBufferStreamer(src, 512, channel=0))
        src = pcm_stereo_source(left, right, chunk_size=500)
        frames_r = await collect_frames(AudioBufferStreamer(src, 512, channel=1))
        assert frames_l[0].shape == (512,)
        assert frames_l[0][0] == 0.0
        assert frames_r[0][0] == pytest.approx(1000 / 32768, rel=1e-3)

    @pytest.mark.anyio
    async def test_stereo_channel_out_of_range_raises(self):
        left = np.zeros(1000, dtype=np.int16)
        right = np.zeros(1000, dtype=np.int16)
        src = pcm_stereo_source(left, right)
        with pytest.raises(ValueError, match="channel must satisfy"):
            async for _ in AudioBufferStreamer(src, 512, channel=5):
                pass

    @pytest.mark.anyio
    async def test_mono_ignores_invalid_channel(self):
        # Consistent with .collect(): mono sources silently ignore channel.
        samples = np.arange(1000, dtype=np.int16)
        src = pcm_mono_source(samples)
        frames = await collect_frames(AudioBufferStreamer(src, 512, channel=5))
        assert len(frames) >= 1


class TestStreamAudioArrayResample:
    @pytest.mark.anyio
    async def test_native_rate_no_resampler(self):
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, sample_rate=16000, chunk_size=8000)
        frames = await collect_frames(AudioBufferStreamer(src, 512, sample_rate=16000))
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
        frames = await collect_frames(AudioBufferStreamer(src, 512, sample_rate=16000))
        total = sum(f.shape[0] for f in frames)
        # ~16000 samples, allow filter tail tolerance
        assert 15500 <= total <= 16500

    @pytest.mark.anyio
    async def test_missing_sample_rate_defaults_to_16000(self):
        # No sample_rate in attrs but target is also 16000 => no resample
        samples = np.arange(2048, dtype=np.int16)
        attrs = {"channels": 1, "bit_depth": 16}
        pcm = PcmStreamResource(ChunkedStreamResource(samples.tobytes(), 500), attrs=attrs)
        src = MediaSource(pcm, format=pcm.format, attrs=attrs)
        frames = await collect_frames(AudioBufferStreamer(src, 512, sample_rate=16000))
        assert len(frames) == 4  # No resample path taken


class TestStreamAudioArrayContainerDecode:
    """AudioBufferStreamer transparently decodes compressed containers via
    AudioDecodingStreamer, so a WAV MediaSource yields the same frames as
    the equivalent raw PCM source.
    """
    @pytest.mark.anyio
    async def test_wav_container_source_yields_frames(self):
        samples = np.arange(2048, dtype=np.int16)
        wav = build_wav_bytes(samples, sample_rate=16000, channels=1)
        src = MediaSource(BytesStreamResource(wav), format="wav")
        frames = await collect_frames(AudioBufferStreamer(src, 512))

        assert len(frames) == 4
        for frame in frames:
            assert frame.shape == (512,)
            assert frame.dtype == np.float32


class TestStreamAudioArrayStream:
    """``.stream(chunk_size, overlap_size)`` yields ``(buffer, is_last)`` in
    target-rate samples — the API used by chunked-forward pipelines (e.g.
    audio-text alignment).
    """
    @pytest.mark.anyio
    async def test_stream_yields_overlapping_windows_with_is_last_flag(self):
        # 32000 samples, chunk_size=16000 / overlap_size=4000 => stride=12000
        # windows start at 0, 12000, 24000; last window is zero-padded.
        samples = np.zeros(32000, dtype=np.int16)
        src = pcm_mono_source(samples, sample_rate=16000, chunk_size=4000)
        streamer = AudioBufferStreamer(src, channel="mono", sample_rate=16000)

        collected = [(buf.waveform.shape, is_last) async for buf, is_last in streamer.stream(16000, 4000)]

        # All chunks should be chunk_size (16000) samples wide.
        assert all(shape == (16000,) for shape, _ in collected)
        # is_last is only True for the final chunk.
        assert [is_last for _, is_last in collected] == [False] * (len(collected) - 1) + [True]
        assert len(collected) >= 2

    @pytest.mark.anyio
    async def test_stream_without_sample_rate_still_works(self):
        # Unlike the old seconds-based API, sample-unit stream() does not require
        # the streamer to know the target rate — sizes are already in samples.
        samples = np.zeros(4096, dtype=np.int16)
        src = pcm_mono_source(samples, sample_rate=16000, chunk_size=1024)
        streamer = AudioBufferStreamer(src, channel="mono")

        chunks = [buf.waveform.shape async for buf, _ in streamer.stream(1024)]
        assert all(shape == (1024,) for shape in chunks)

    @pytest.mark.anyio
    async def test_stream_rejects_non_positive_chunk_size(self):
        src = pcm_mono_source(np.arange(1000, dtype=np.int16))
        streamer = AudioBufferStreamer(src, channel="mono", sample_rate=16000)

        with pytest.raises(ValueError, match="chunk_size must be positive"):
            async for _ in streamer.stream(0):
                pass

    @pytest.mark.anyio
    async def test_stream_rejects_overlap_ge_chunk(self):
        src = pcm_mono_source(np.arange(1000, dtype=np.int16))
        streamer = AudioBufferStreamer(src, channel="mono", sample_rate=16000)

        with pytest.raises(ValueError, match="overlap_size must satisfy"):
            async for _ in streamer.stream(512, 512):
                pass


class TestStreamAudioArrayCollect:
    """``frame_size=None`` + ``.collect()`` is the "load-all" idiom that
    replaces the removed ``load_audio_buffer``.
    """
    @pytest.mark.anyio
    async def test_collect_returns_whole_waveform_as_single_buffer(self):
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        buffer = await AudioBufferStreamer(src).collect()

        assert buffer.sample_rate == 16000
        assert buffer.waveform.shape == (2048,)
        expected = samples.astype(np.float32) / 32768.0
        assert np.allclose(buffer.waveform, expected)

    @pytest.mark.anyio
    async def test_collect_with_channel_mono_downmix(self):
        left = np.full(1024, 1000, dtype=np.int16)
        right = np.full(1024, 3000, dtype=np.int16)
        src = pcm_stereo_source(left, right, chunk_size=500)
        buffer = await AudioBufferStreamer(src, channel="mono").collect()

        assert buffer.waveform.shape == (1024,)
        assert buffer.waveform[0] == pytest.approx(2000 / 32768, rel=1e-3)

    @pytest.mark.anyio
    async def test_collect_with_resample(self):
        sr_in = 48000
        samples = (np.sin(2 * np.pi * 440 * np.arange(sr_in) / sr_in) * 10000).astype(np.int16)
        src = pcm_mono_source(samples, sample_rate=sr_in, chunk_size=8000)
        buffer = await AudioBufferStreamer(src, sample_rate=16000).collect()

        assert buffer.sample_rate == 16000
        # ~16000 samples with soxr filter tail tolerance
        assert 15500 <= buffer.waveform.shape[0] <= 16500

    @pytest.mark.anyio
    async def test_collect_preserves_stereo_shape_by_default(self):
        left = np.full(1024, 1000, dtype=np.int16)
        right = np.full(1024, 3000, dtype=np.int16)
        src = pcm_stereo_source(left, right, chunk_size=500)
        buffer = await AudioBufferStreamer(src).collect()

        assert buffer.waveform.shape == (2, 1024)

    @pytest.mark.anyio
    async def test_collect_with_frame_size_concatenates_frames(self):
        # collect() also works with a set frame_size — frames are re-joined.
        samples = np.arange(2048, dtype=np.int16)
        src = pcm_mono_source(samples, chunk_size=500)
        buffer = await AudioBufferStreamer(src, frame_size=512).collect()

        assert buffer.waveform.shape == (2048,)
        expected = samples.astype(np.float32) / 32768.0
        assert np.allclose(buffer.waveform, expected)


class TestStreamAudioArrayValidation:
    @pytest.mark.anyio
    async def test_non_pcm_format_decodes_via_ffmpeg(self):
        # Non-PCM containers are now routed through AudioDecodingStreamer;
        # an empty mp3 blob fails inside ffmpeg with a RuntimeError, not a
        # ValueError at the frontend.
        src = MediaSource(BytesStreamResource(b""), format="mp3", attrs={"sample_rate": 16000})
        with pytest.raises(RuntimeError, match="ffmpeg audio decoding failed"):
            async for _ in AudioBufferStreamer(src, 512):
                pass

    @pytest.mark.anyio
    async def test_none_format_decodes_via_ffmpeg(self):
        src = MediaSource(BytesStreamResource(b""), attrs={"sample_rate": 16000})
        with pytest.raises(RuntimeError, match="ffmpeg audio decoding failed"):
            async for _ in AudioBufferStreamer(src, 512):
                pass


class TestStreamAudioArrayFloat32Source:
    @pytest.mark.skip(reason="PcmStreamResource cannot express f32le yet (format derived from bit_depth only).")
    @pytest.mark.anyio
    async def test_f32le_no_normalization_applied(self):
        # float32 PCM must not be rescaled; values pass through untouched.
        samples = np.array([0.5, -0.25, 0.0, 1.0] * 128, dtype=np.float32)
        attrs = {"sample_rate": 16000, "channels": 1, "bit_depth": 32}
        pcm = PcmStreamResource(ChunkedStreamResource(samples.tobytes(), 500), attrs=attrs)
        src = MediaSource(pcm, format="f32le", attrs=attrs)
        frames = await collect_frames(AudioBufferStreamer(src, 512))
        # First 4 samples preserved as-is
        assert frames[0][0] == 0.5
        assert frames[0][1] == -0.25
        assert frames[0][2] == 0.0
        assert frames[0][3] == 1.0
