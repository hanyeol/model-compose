from __future__ import annotations

from typing import Optional, List, Set, Dict, Tuple, Any
from collections.abc import AsyncIterable
from mindor.dsl.schema.component import AudioPlaybackComponentConfig, AudioPlaybackDriver
from mindor.dsl.schema.action import AudioPlaybackActionConfig, AudioPlaybackSink
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from ..base import AudioPlaybackService, register_audio_playback_service
from ..base import ComponentActionContext
from .common import AudioPlaybackAction
import asyncio, os, platform

# Input container formats safe to feed through ffmpeg pipe:0. Other formats
# (mp4/mov/mkv/webm/avi/...) or unknown formats are spooled to a temp file
# first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "flv", "mpegts", "ts", "mp3", "wav", "flac", "ogg", "opus", "aac",
}

class FFmpegAudioPlaybackAction(AudioPlaybackAction):
    async def _play(
        self,
        audio: MediaSource,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        system = platform.system()
        audio_path, audio_spooled = await self._resolve_input_path(audio)

        command: List[str] = [ "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "warning" ]

        if params["duration"] is not None:
            command.extend([ "-t", str(params["duration"]) ])

        command.extend([ "-i", audio_path if audio_path is not None else "pipe:0" ])

        if params["volume"] != 1.0:
            command.extend([ "-af", f"volume={params['volume']}" ])

        # -vn drops any incidental video stream in the container so the audio
        # sink muxer never sees a track it can't handle.
        command.extend([ "-vn" ])
        command.extend(self._build_audio_output_options(system, params["sink"], params["device"]))

        def _cleanup() -> None:
            if audio_spooled and audio_path is not None:
                try:
                    os.remove(audio_path)
                except FileNotFoundError:
                    pass

        source = audio.stream if audio_path is None else None

        logging.debug("Starting ffmpeg audio playback: %s", " ".join(command))

        if params["blocking"]:
            await self._run_blocking(command, source, _cleanup, cancellation_token)
        else:
            await self._run_detached(command, source, _cleanup)

    def _build_audio_output_options(
        self,
        system: str,
        sink: AudioPlaybackSink,
        device: Optional[Any],
    ) -> List[str]:
        # macOS: audiotoolbox writes to a Core Audio device. The muxer accepts
        #        an integer device index as its output url; -audio_device_index
        #        selects a specific device when sink='device'.
        # Windows: WASAPI is exposed via ffmpeg's "wasapi" output muxer;
        #          the url is the device name ("default" for the OS default).
        # Linux: PulseAudio is exposed via the "pulse" muxer; the url is a
        #        sink name ("default" for the OS default).
        if system == "Darwin":
            if sink == AudioPlaybackSink.DEVICE and device is not None:
                return [ "-f", "audiotoolbox", "-audio_device_index", str(device), "-" ]
            return [ "-f", "audiotoolbox", "-" ]

        if system == "Windows":
            target = str(device) if sink == AudioPlaybackSink.DEVICE and device is not None else "default"
            return [ "-f", "wasapi", target ]

        if system == "Linux":
            target = str(device) if sink == AudioPlaybackSink.DEVICE and device is not None else "default"
            return [ "-f", "pulse", target ]

        raise NotImplementedError(f"Audio playback is not supported on platform: {system}")

    async def _run_blocking(
        self,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
        cleanup,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        # run_subprocess only reacts to asyncio cancellation, but our
        # CancellationToken is a threading.Event that has to be polled.
        # Wrap the ffmpeg run in a task and cancel it when the token fires;
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
                raise RuntimeError(f"ffmpeg audio playback failed (exit code {process.returncode}): {error_message}")
        except asyncio.CancelledError:
            logging.info("Audio playback cancelled")
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
        # Fire-and-forget: spawn ffmpeg and return without awaiting. The caller
        # opted out of playback completion (blocking=False) so we don't surface
        # a nonzero exit code, but we still ensure temp inputs are cleaned up
        # once the process finishes.
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
        Decide how ffmpeg should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (flv, mpegts, mp3, wav, ...): feed via pipe:0 (returns None path).
        - Otherwise (mp4/mov/unknown/...): spool to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if source.format and source.format.lower() in _STREAMABLE_INPUT_FORMATS:
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before playback")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True


@register_audio_playback_service(AudioPlaybackDriver.FFMPEG)
class FFmpegAudioPlaybackService(AudioPlaybackService):
    def __init__(self, id: str, config: AudioPlaybackComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: AudioPlaybackActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegAudioPlaybackAction(action).run(context, loop)
