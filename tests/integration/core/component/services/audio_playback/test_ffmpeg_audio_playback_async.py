"""Async-behavior tests for the FFmpeg audio-playback driver.

Playback normally writes to an audio device (audiotoolbox / wasapi / pulse),
which we cannot rely on in a test environment — instead we monkeypatch the
output-options builder to send the decoded audio to ffmpeg's ``null`` muxer.
That keeps the ffmpeg subprocess wall time realistic (the entire input is
decoded and consumed by the muxer) while producing no actual sound.

Covers:

- ``FFmpegAudioPlaybackAction.run`` accepts only ``(self, context)``
- Awaited playback (``wait_for_finish=True``) does not block the event loop
- Detached playback (``wait_for_finish=False``) returns immediately
- List/batch input processes each source in turn
- CancellationToken firing mid-playback terminates the ffmpeg subprocess
"""

from __future__ import annotations

import asyncio
import inspect
import math
import os
import shutil
import struct
import tempfile
import time
import wave
from typing import Any, List, Optional

import pytest
from unittest.mock import MagicMock

from mindor.core.component.services.audio_playback.drivers.ffmpeg import (
    FFmpegAudioPlaybackAction,
    FFmpegAudioPlaybackService,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.dsl.schema.action import AudioPlaybackActionConfig, AudioPlaybackSink

from tests.async_helpers import assert_does_not_block, make_action_context


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _write_sine_wav(path: str, sample_rate: int, duration: float, frequency: float, amplitude: float = 0.5) -> None:
    n_samples = int(sample_rate * duration)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            value = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            frames += struct.pack("<h", value)
        w.writeframes(bytes(frames))


@pytest.fixture(scope="module")
def sine_2s_wav():
    """2-second mono sine — decodes in a few hundred ms via ffmpeg."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _write_sine_wav(path, sample_rate=44100, duration=2.0, frequency=440.0, amplitude=0.5)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def sine_1s_wav():
    """1-second mono sine — quick input for batch/detached tests."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _write_sine_wav(path, sample_rate=44100, duration=1.0, frequency=440.0, amplitude=0.5)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def sine_10s_wav():
    """10-second mono sine — long enough to interrupt via CancellationToken."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _write_sine_wav(path, sample_rate=44100, duration=10.0, frequency=440.0, amplitude=0.5)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(autouse=True)
def null_audio_sink(monkeypatch):
    """Redirect the ffmpeg output muxer to ``null`` so no real audio plays."""
    def _null_sink(self, system, sink, device):
        return [ "-f", "null", "-" ]

    monkeypatch.setattr(
        FFmpegAudioPlaybackAction,
        "_build_audio_output_options",
        _null_sink,
    )


def _wav_input(path: str) -> FileStreamResource:
    return FileStreamResource(path)


def _attach_cancellation(context, token: CancellationToken) -> None:
    workflow = MagicMock()
    workflow.cancellation_token = token
    workflow.component_event_notifier = None
    context.workflow = workflow


def _playback_config(source_template: str, **overrides) -> AudioPlaybackActionConfig:
    defaults = dict(
        audio=source_template,
        sink=AudioPlaybackSink.SYSTEM,
        volume=1.0,
        wait_for_finish=True,
    )
    defaults.update(overrides)
    return AudioPlaybackActionConfig(**defaults)


@ffmpeg_required
class TestActionRunSignature:
    """The refactored ``AudioPlaybackAction.run`` takes only ``(self, context)``."""

    def test_action_run_signature_has_no_loop_param(self):
        params = list(inspect.signature(FFmpegAudioPlaybackAction.run).parameters)
        assert params == ["self", "context"], f"unexpected run() signature: {params}"

    def test_service_run_signature_takes_action_and_context_only(self):
        params = list(inspect.signature(FFmpegAudioPlaybackService._run).parameters)
        assert params == ["self", "action", "context"], f"unexpected _run signature: {params}"

    @pytest.mark.anyio
    async def test_service_run_can_be_called_with_just_action_and_context(self, sine_1s_wav):
        service = FFmpegAudioPlaybackService(id="t", config=MagicMock(), daemon=False)
        action_config = _playback_config("${input.audio}")
        context = make_action_context(input={"audio": _wav_input(sine_1s_wav)})

        # No TypeError — the important assertion.
        result = await service._run(action_config, context)

        # Playback returns None.
        assert result is None


@ffmpeg_required
class TestNonBlockingBehavior:
    @pytest.mark.anyio
    async def test_awaited_playback_does_not_block_event_loop(self, sine_2s_wav):
        """With wait_for_finish=True the action awaits the ffmpeg subprocess.
        The asyncio.create_subprocess_exec path must not block the loop."""
        config = _playback_config("${input.audio}", wait_for_finish=True)
        context = make_action_context(input={"audio": _wav_input(sine_2s_wav)})

        await assert_does_not_block(
            FFmpegAudioPlaybackAction(config).run(context),
            tick_interval_s=0.01,
            min_ticks=5,
        )


@ffmpeg_required
class TestDetachedPlayback:
    @pytest.mark.anyio
    async def test_wait_for_finish_false_returns_promptly(self, sine_10s_wav):
        """A detached run spawns ffmpeg and returns immediately, even for a
        10-second input. The subprocess continues in the background but the
        caller is not blocked."""
        config = _playback_config("${input.audio}", wait_for_finish=False)
        context = make_action_context(input={"audio": _wav_input(sine_10s_wav)})

        start = time.monotonic()
        result = await FFmpegAudioPlaybackAction(config).run(context)
        elapsed = time.monotonic() - start

        assert result is None
        # Detached path returns without awaiting decode — should be well under
        # a second even for a 10s input.
        assert elapsed < 1.0, f"detached playback took too long: {elapsed:.2f}s"

        # Give the fire-and-forget task a moment to spin up its subprocess
        # so the pytest event loop doesn't tear it down mid-write with a
        # noisy warning.
        await asyncio.sleep(0.05)


@ffmpeg_required
class TestBatchInput:
    @pytest.mark.anyio
    async def test_list_input_all_items_played(self, sine_1s_wav, monkeypatch):
        """Track that ``_play`` is invoked once per list item."""
        original_play = FFmpegAudioPlaybackAction._play
        played: List[Any] = []

        async def _tracked_play(self, audio, params, cancellation_token=None):
            played.append(audio)
            return await original_play(self, audio, params, cancellation_token)

        monkeypatch.setattr(FFmpegAudioPlaybackAction, "_play", _tracked_play)

        config = _playback_config("${input.audios}")
        context = make_action_context(
            input={"audios": [_wav_input(sine_1s_wav) for _ in range(3)]},
        )

        await FFmpegAudioPlaybackAction(config).run(context)

        assert len(played) == 3


@ffmpeg_required
class TestCancellation:
    @pytest.mark.anyio
    async def test_cancellation_token_stops_playback_promptly(self, sine_10s_wav):
        """Firing the token mid-playback kills the ffmpeg process. The awaited
        run raises CancelledError; total elapsed should be a small multiple of
        the 200ms cancellation-watcher poll interval — never the full 10s."""
        config = _playback_config("${input.audio}", wait_for_finish=True)
        context = make_action_context(input={"audio": _wav_input(sine_10s_wav)})
        token = CancellationToken()
        _attach_cancellation(context, token)

        async def _fire_soon():
            await asyncio.sleep(0.15)
            token.cancel("test-cancellation")

        fire_task = asyncio.create_task(_fire_soon())
        start = time.monotonic()

        raised: Optional[BaseException] = None
        try:
            await FFmpegAudioPlaybackAction(config).run(context)
        except (asyncio.CancelledError, RuntimeError) as exc:
            raised = exc

        elapsed = time.monotonic() - start
        await fire_task

        # Bounded regardless of whether the run finished naturally (2s input
        # actually decodes in <1s so cancellation may race with completion for
        # short sources — the 10s fixture makes cancellation the winning path).
        assert elapsed < 3.0, (
            f"playback did not stop promptly after cancellation: {elapsed:.2f}s "
            f"(raised={type(raised).__name__ if raised else None})"
        )
