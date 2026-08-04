"""Non-blocking behaviour tests for the async audio streaming utilities.

The functions under test offload CPU-bound decode/resample work into
``asyncio.to_thread`` closures. These tests complement the contract-oriented
suite in ``test_audio.py`` by ensuring the offloading actually keeps the event
loop responsive under realistic (multi-hundred-KB) payloads.
"""

from __future__ import annotations

import asyncio
import io
import time
import wave

import numpy as np
import pytest

from mindor.core.foundation.streaming.audio import (
    AudioBufferStreamer,
    PcmStreamResource,
)
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.audio import AudioBuffer

from tests.async_helpers import assert_does_not_block, collect_async


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

class ChunkedStreamResource(StreamResource):
    """Async stream resource that yields fixed-size chunks from a byte buffer.

    Copied locally rather than imported cross-test-file to keep this suite
    self-contained.
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


def _build_stereo_pcm_source(
    seconds: float = 4.0,
    sample_rate: int = 48000,
    chunk_size: int = 16384,
) -> MediaSource:
    """Build an s16le stereo PCM MediaSource of ``seconds`` duration.

    4 seconds @ 48kHz stereo s16le = ~1.5 MB — large enough that decode +
    channel-mean + resample take well over 50 ms of wall time.
    """
    n = int(seconds * sample_rate)
    t = np.arange(n) / sample_rate
    left = (np.sin(2 * np.pi * 440.0 * t) * 20000).astype(np.int16)
    right = (np.sin(2 * np.pi * 660.0 * t) * 20000).astype(np.int16)
    interleaved = np.empty(n * 2, dtype=np.int16)
    interleaved[0::2] = left
    interleaved[1::2] = right
    attrs = {"sample_rate": sample_rate, "channels": 2, "bit_depth": 16}
    pcm = PcmStreamResource(
        ChunkedStreamResource(interleaved.tobytes(), chunk_size),
        attrs=attrs,
    )
    return MediaSource(pcm, format=pcm.format, attrs=attrs)


def _build_wav_source(seconds: float = 4.0, sample_rate: int = 48000) -> MediaSource:
    """Build a WAV-container MediaSource that must go through torchaudio."""
    n = int(seconds * sample_rate)
    t = np.arange(n) / sample_rate
    samples = (np.sin(2 * np.pi * 440.0 * t) * 20000).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(samples.tobytes())

    return MediaSource(BytesStreamResource(buf.getvalue()), format="wav")


# ---- AudioBufferStreamer.collect(): non-blocking ----

class TestCollectDoesNotBlock:
    @pytest.mark.anyio
    async def test_large_pcm_decode_and_resample_does_not_block(self):
        src = _build_stereo_pcm_source(seconds=4.0, sample_rate=48000)

        result = await assert_does_not_block(
            AudioBufferStreamer(src, sample_rate=16000, channel="mono").collect(),
        )

        assert isinstance(result, AudioBuffer)
        assert result.sample_rate == 16000
        assert result.waveform.dtype == np.float32
        # Downmix to mono => 1-D array. 4s @ 16k ~= 64_000 samples (with soxr tail tolerance).
        assert result.waveform.ndim == 1
        assert 63_000 <= result.waveform.shape[0] <= 65_000

    @pytest.mark.anyio
    async def test_wav_container_decode_does_not_block(self):
        src = _build_wav_source(seconds=4.0, sample_rate=48000)

        result = await assert_does_not_block(
            AudioBufferStreamer(src, sample_rate=16000, channel="mono").collect(),
        )

        assert isinstance(result, AudioBuffer)
        assert result.sample_rate == 16000
        assert result.waveform.dtype == np.float32
        # 4s @ 16k mono ~= 64_000 samples after decode + resample.
        total = result.waveform.shape[-1]
        assert 63_000 <= total <= 65_000

    @pytest.mark.anyio
    async def test_concurrent_sleep_is_not_blocked_by_decode(self):
        """A concurrent short sleep should finish in ~its own duration, not wait for decode."""
        src = _build_stereo_pcm_source(seconds=4.0, sample_rate=48000)

        sleep_duration_s = 0.05
        sleep_finished_at: list[float] = []

        async def timed_sleep() -> None:
            await asyncio.sleep(sleep_duration_s)
            sleep_finished_at.append(time.monotonic())

        start = time.monotonic()
        decode_task = asyncio.create_task(
            AudioBufferStreamer(src, sample_rate=16000, channel="mono").collect()
        )
        sleep_task = asyncio.create_task(timed_sleep())

        await sleep_task
        sleep_elapsed = sleep_finished_at[0] - start

        # If decode were blocking the event loop, sleep would only wake up after
        # decode returned (many hundreds of ms). Allow generous headroom for
        # thread scheduling; the essential contract is that sleep completes
        # before the decode finishes.
        assert sleep_elapsed < 0.5, (
            f"Concurrent sleep took {sleep_elapsed:.3f}s — decode is blocking the loop."
        )

        result = await decode_task
        assert isinstance(result, AudioBuffer)
        assert result.sample_rate == 16000


# ---- AudioBufferStreamer: non-blocking ----

class TestStreamAudioArrayDoesNotBlock:
    @pytest.mark.anyio
    async def test_streaming_large_pcm_does_not_block(self):
        # ~1 MB of stereo PCM, streamed in 4KB chunks, resampled to a different rate.
        # Many per-chunk _process_chunk offloads + a final _flush_tail offload.
        src = _build_stereo_pcm_source(seconds=3.0, sample_rate=48000, chunk_size=4096)
        frame_size = 1024

        frames = await assert_does_not_block(
            collect_async(
                AudioBufferStreamer(src, frame_size=frame_size, sample_rate=16000),
            ),
        )

        # 3s @ 16k ~= 48_000 samples across frames of 1024 => ~47 frames plus a padded tail.
        # Stereo source with default channel handling preserves both channels per frame.
        assert len(frames) >= 40
        for f in frames:
            assert f.waveform.shape == (2, frame_size)
            assert f.waveform.dtype == np.float32
            assert f.sample_rate == 16000

        # Sanity: total samples close to expected 16k * 3s.
        total = sum(f.waveform.shape[-1] for f in frames)
        # frames are all frame_size (padded), so total is a multiple of frame_size >= 48000.
        assert total >= 48_000
        # Should not have wildly over-produced either.
        assert total <= 48_000 + frame_size * 2

    @pytest.mark.anyio
    async def test_streaming_native_rate_frame_count_matches(self):
        # No resample: exact frame math should hold and non-blocking still expected.
        seconds = 2.0
        sample_rate = 48000
        n = int(seconds * sample_rate)
        # Mono s16le so frame math is trivial (n samples => ceil(n / frame_size) frames).
        samples = np.arange(n, dtype=np.int16)
        attrs = {"sample_rate": sample_rate, "channels": 1, "bit_depth": 16}
        pcm = PcmStreamResource(ChunkedStreamResource(samples.tobytes(), 4096), attrs=attrs)
        src = MediaSource(pcm, format=pcm.format, attrs=attrs)
        frame_size = 1024

        frames = await assert_does_not_block(
            collect_async(
                AudioBufferStreamer(src, frame_size=frame_size, sample_rate=sample_rate),
            ),
        )

        # n=96_000, frame_size=1024 => 93 full frames + 1 padded tail (96_000 % 1024 = 768).
        expected_full = n // frame_size
        tail = n % frame_size
        expected = expected_full + (1 if tail else 0)
        assert len(frames) == expected
        for f in frames:
            assert f.waveform.shape == (frame_size,)
            assert f.waveform.dtype == np.float32
            assert f.sample_rate == sample_rate
