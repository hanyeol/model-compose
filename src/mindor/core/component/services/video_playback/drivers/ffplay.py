from __future__ import annotations

from typing import Optional, List, Dict, Tuple, Any
from collections.abc import AsyncIterable
from mindor.dsl.schema.component import VideoPlaybackComponentConfig, VideoPlaybackDriver
from mindor.dsl.schema.action import VideoPlaybackActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.audio import is_streamable_audio_format
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from ..base import VideoPlaybackService, register_video_playback_service
from ..base import ComponentActionContext
from .common import VideoPlaybackAction
import asyncio, os

class FFplayVideoPlaybackAction(VideoPlaybackAction):
    async def _play_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        for video in videos:
            await self._play(video, params, cancellation_token)

    async def _play(
        self,
        video: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        video_path, video_spooled = await self._resolve_input_path(video)

        # -autoexit closes the window when playback ends so the process actually
        # terminates on its own; without it ffplay would sit on the last frame
        # until the user closed the window.
        command: List[str] = [ "ffplay", "-hide_banner", "-loglevel", "warning", "-autoexit" ]

        if params["duration"] is not None:
            command.extend([ "-t", str(params["duration"]) ])

        if params["window_title"]:
            command.extend([ "-window_title", str(params["window_title"]) ])

        if params["window_size"]:
            width, height = self._parse_window_size(params["window_size"])
            command.extend([ "-x", str(width), "-y", str(height) ])

        if params["fullscreen"]:
            command.append("-fs")

        if params["always_on_top"]:
            command.append("-alwaysontop")

        if params["borderless"]:
            command.append("-noborder")

        if params["mute"]:
            command.append("-an")
        else:
            command.extend([ "-volume", str(max(0, min(100, int(params["volume"])))) ])

        command.extend([ "-i", video_path if video_path is not None else "pipe:0" ])

        def _cleanup() -> None:
            if video_spooled and video_path is not None:
                try:
                    os.remove(video_path)
                except FileNotFoundError:
                    pass

        source = video.stream if video_path is None else None

        logging.debug("Starting ffplay video playback: %s", " ".join(command))

        if params["wait_for_finish"]:
            await self._run_awaited(command, source, _cleanup, cancellation_token)
        else:
            await self._run_detached(command, source, _cleanup)

    async def _run_awaited(
        self,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
        cleanup,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        # run_subprocess only reacts to asyncio cancellation, but our
        # CancellationToken is a threading.Event that has to be polled.
        # Wrap the ffplay run in a task and cancel it when the token fires;
        # run_subprocess then kills the process on its way out.
        process_task = asyncio.create_task(run_subprocess(
            command,
            source,
            stderr_handler=lambda r: r.read(),
        ))

        watcher_task: Optional[asyncio.Task] = None

        if cancellation_token is not None:
            async def _watch_cancellation() -> None:
                while not cancellation_token.is_cancelled():
                    if process_task.done():
                        return
                    await asyncio.sleep(0.2)
                process_task.cancel()

            watcher_task = asyncio.create_task(_watch_cancellation())

        try:
            process, _, error = await process_task

            if process.returncode != 0:
                error_message = error.decode("utf-8", errors="replace") if error else ""
                raise RuntimeError(f"ffplay video playback failed (exit code {process.returncode}): {error_message}")
        except asyncio.CancelledError:
            logging.info("Video playback cancelled")
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

            cleanup()

    async def _run_detached(
        self,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
        cleanup,
    ) -> None:
        # Fire-and-forget: spawn ffplay and return without awaiting. The caller
        # opted out of playback completion (wait_for_finish=False) so we
        # don't surface a nonzero exit code, but we still ensure temp inputs
        # are cleaned up once the process finishes.
        async def _wait_and_cleanup() -> None:
            try:
                _, _, _ = await run_subprocess(
                    command,
                    source,
                    stderr_handler=lambda r: r.read(),
                )
            finally:
                cleanup()

        asyncio.create_task(_wait_and_cleanup())

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """
        Decide how ffplay should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (flv, mpegts, mp3, wav, ...): feed via pipe:0 (returns None path).
        - Otherwise (mp4/mov/unknown/...): spool to a temp file so ffplay can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if is_streamable_video_format(source.format) or is_streamable_audio_format(source.format):
            return None, False

        logging.debug("ffplay input is not streamable; spooling to a temp file before playback")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

    def _parse_window_size(self, size: str) -> Tuple[int, int]:
        try:
            width_str, height_str = str(size).lower().split("x", 1)
            return int(width_str.strip()), int(height_str.strip())
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid window_size {size!r}; expected 'WIDTHxHEIGHT' (e.g. '1280x720')") from e

@register_video_playback_service(VideoPlaybackDriver.FFPLAY)
class FFplayVideoPlaybackService(VideoPlaybackService):
    def __init__(self, id: str, config: VideoPlaybackComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoPlaybackActionConfig, context: ComponentActionContext) -> Any:
        return await FFplayVideoPlaybackAction(action).run(context)
