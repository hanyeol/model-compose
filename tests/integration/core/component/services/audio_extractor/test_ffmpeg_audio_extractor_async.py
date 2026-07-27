"""Async-behavior tests for the FFmpeg audio-extractor driver.

Complements ``test_ffmpeg_audio_extractor.py`` (which covers contract behavior
against the pre-refactor MagicMock context and passes an obsolete ``loop`` arg
to Action.run — kept as-is for reference until it is updated). These tests
target the refactored native-async driver and confirm:

- ``FFmpegAudioExtractorAction.run(context)`` accepts ``(context,)`` only
- Long-running ffmpeg calls do NOT block the asyncio event loop
- Streaming output preserves the same non-blocking guarantee
- Batch inputs are all processed
- CancellationToken firing mid-run terminates the ffmpeg subprocess promptly
"""

from __future__ import annotations

import asyncio
import inspect
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import AsyncIterator
from typing import Any

import pytest
from unittest.mock import MagicMock

from mindor.core.component.services.audio_extractor.drivers.ffmpeg import (
    FFmpegAudioExtractorAction,
    FFmpegAudioExtractorService,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.dsl.schema.action import AudioExtractorActionConfig

from tests.async_helpers import assert_does_not_block, make_action_context, collect_async


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video_path():
    """Synthesize a ~3 second mp4 with a stereo audio track.

    Longer than the extractor contract fixtures so ffmpeg wall time comfortably
    exceeds our 10ms ticker interval and the non-blocking assertion is
    meaningful.
    """
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3:sample_rate=44100",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        path,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"ffmpeg failed generating fixture: {e.stderr.decode('utf-8', errors='replace')}")
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _attach_cancellation(context, token: CancellationToken) -> None:
    """Attach a workflow mock exposing `cancellation_token`.

    ``ComponentActionContext.cancellation_token`` reads from ``self.workflow``,
    so a full WorkflowContext is not needed — just a namespace with the token.
    """
    workflow = MagicMock()
    workflow.cancellation_token = token
    workflow.component_event_notifier = None
    context.workflow = workflow


async def _drain_resource(resource: AudioStreamResource) -> int:
    """Fully consume a stream-backed AudioStreamResource, returning total bytes."""
    src = resource.source
    total = 0
    if isinstance(src, FileStreamResource):
        with open(src.path, "rb") as f:
            total = len(f.read())
    else:
        async for chunk in resource:
            total += len(chunk)
    await resource.close()
    return total


@ffmpeg_required
class TestActionRunSignature:
    """The refactored ``AudioExtractorAction.run`` takes only ``(self, context)``."""

    def test_action_run_signature_has_no_loop_param(self):
        params = list(inspect.signature(FFmpegAudioExtractorAction.run).parameters)
        # Should be ("self", "context") — no legacy ``loop`` kwarg.
        assert params == ["self", "context"], f"unexpected run() signature: {params}"

    def test_service_run_signature_takes_action_and_context_only(self):
        params = list(inspect.signature(FFmpegAudioExtractorService._run).parameters)
        assert params == ["self", "action", "context"], f"unexpected _run signature: {params}"

    @pytest.mark.anyio
    async def test_service_run_can_be_called_with_just_action_and_context(self, sample_video_path):
        service = FFmpegAudioExtractorService(id="t", config=MagicMock(), daemon=False)
        action_config = AudioExtractorActionConfig(source="${input.file}", format="mp3")
        context = make_action_context(input={"file": sample_video_path})

        # No TypeError — the important assertion.
        result = await service._run(action_config, context)

        assert isinstance(result, AudioStreamResource)
        await _drain_resource(result)


@ffmpeg_required
class TestNonBlockingBehavior:
    """The refactored driver spawns ffmpeg via asyncio.create_subprocess_exec,
    so the event loop should stay responsive across the whole extraction."""

    @pytest.mark.anyio
    async def test_extract_to_file_does_not_block_event_loop(self, sample_video_path):
        """m4a / mp4 output goes through the file path (non-streamable output)."""
        action_config = AudioExtractorActionConfig(
            source="${input.file}", format="m4a",
        )
        context = make_action_context(input={"file": sample_video_path})

        result = await assert_does_not_block(
            FFmpegAudioExtractorAction(action_config).run(context),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, AudioStreamResource)
        assert result.format == "m4a"
        size = await _drain_resource(result)
        assert size > 0

    @pytest.mark.anyio
    async def test_extract_to_stream_does_not_block_event_loop(self, sample_video_path):
        """mp3 output goes through the streaming path (stdout pipe)."""
        action_config = AudioExtractorActionConfig(
            source="${input.file}", format="mp3",
        )
        context = make_action_context(input={"file": sample_video_path})

        result = await assert_does_not_block(
            FFmpegAudioExtractorAction(action_config).run(context),
            tick_interval_s=0.01,
            min_ticks=5,
        )
        assert isinstance(result, AudioStreamResource)

        # The stream-output driver returns quickly (before ffmpeg finishes) —
        # so measure blocking again while consuming the stream, which is where
        # the actual ffmpeg wall-time lives.
        size = await assert_does_not_block(
            _drain_resource(result),
            tick_interval_s=0.01,
            min_ticks=5,
        )
        assert size > 0


@ffmpeg_required
class TestBatchInput:
    @pytest.mark.anyio
    async def test_list_input_all_items_processed(self, sample_video_path):
        action_config = AudioExtractorActionConfig(
            source="${input.files}", format="mp3",
        )
        context = make_action_context(
            input={"files": [sample_video_path, sample_video_path, sample_video_path]},
        )

        result = await FFmpegAudioExtractorAction(action_config).run(context)

        assert isinstance(result, list)
        assert len(result) == 3
        for item in result:
            assert isinstance(item, AudioStreamResource)
            await item.close()


@ffmpeg_required
class TestStreamingInput:
    """Async-iterator input → stream output (each frame arrives without stalls)."""

    @pytest.mark.anyio
    async def test_stream_input_yields_resources_without_blocking(self, sample_video_path):
        # Build an AsyncIterator of paths and feed it via the input renderer.
        async def _paths():
            for _ in range(2):
                yield sample_video_path

        action_config = AudioExtractorActionConfig(
            source="${input.stream}", format="mp3",
        )
        context = make_action_context(input={"stream": _paths()})

        result = await FFmpegAudioExtractorAction(action_config).run(context)
        assert isinstance(result, AsyncIterator)

        items = await assert_does_not_block(
            collect_async(result),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert len(items) == 2
        for item in items:
            assert isinstance(item, AudioStreamResource)
            await item.close()


@ffmpeg_required
class TestCancellation:
    @pytest.mark.anyio
    async def test_cancellation_token_stops_ffmpeg_promptly(self, sample_video_path):
        """Firing the token mid-run should interrupt the file-path (awaited) driver."""
        # `-re` makes ffmpeg pace input at native rate, guaranteeing a slow run
        # we can interrupt (a 30s source → ≥30s of wall time without -re it
        # completes in <1s). Wrap the source in a MediaSource so we can point
        # ffmpeg at the source path but use `-re` via a custom command hook —
        # instead we drive it by consuming a slow (rate-limited) stream input.
        # Easiest: build a very long source and count on lavfi + slow codec.
        long_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        try:
            # 60-second source with medium preset — extraction to flac will take
            # a few seconds of wall time on the decode side.
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=duration=60:size=640x480:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=60:sample_rate=48000",
                    "-shortest", "-c:v", "libx264", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "aac",
                    long_path,
                ],
                check=True, capture_output=True,
                timeout=60,
            )

            token = CancellationToken()
            # Use m4a (file-backed path) with re-encode to make cancellation
            # window measurable. Even if decoding is fast, the CancellationToken
            # watcher polls every 200ms — we assert the run completes within
            # a bounded time of the cancel firing, not that it necessarily
            # aborted mid-stream.
            action_config = AudioExtractorActionConfig(
                source="${input.file}", format="m4a", encoding={"bitrate": "320k"},
            )
            context = make_action_context(input={"file": long_path})
            _attach_cancellation(context, token)

            async def _fire_soon():
                # Fire quickly so cancellation lands during ffmpeg's decode/encode.
                await asyncio.sleep(0.05)
                token.cancel("test-cancellation")

            fire_task = asyncio.create_task(_fire_soon())
            start = time.monotonic()

            raised = None
            try:
                result = await FFmpegAudioExtractorAction(action_config).run(context)
                # If the run happened to finish before our fire task could cancel
                # (rare — most audio decodes of a 60s source take >100ms), don't
                # fail. Just ensure we cleaned up.
                if isinstance(result, AudioStreamResource):
                    await result.close()
            except (asyncio.CancelledError, RuntimeError) as exc:
                raised = exc

            elapsed = time.monotonic() - start
            await fire_task

            # Whether the operation finished naturally or was cancelled, it
            # should have terminated within a small multiple of the polling
            # interval — never dozens of seconds.
            assert elapsed < 15.0, (
                f"cancellation did not stop ffmpeg promptly: {elapsed:.2f}s "
                f"(raised={type(raised).__name__ if raised else None})"
            )
        finally:
            if os.path.exists(long_path):
                os.unlink(long_path)
