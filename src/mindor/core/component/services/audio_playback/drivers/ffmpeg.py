from __future__ import annotations

from typing import Optional, List, Dict, Any
from collections.abc import AsyncIterable
from mindor.dsl.schema.component import AudioPlaybackComponentConfig, AudioPlaybackDriver
from mindor.dsl.schema.action import AudioPlaybackActionConfig, AudioPlaybackSink
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.audio import is_pcm_format
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import AudioPlaybackService, register_audio_playback_service
from ..base import ComponentActionContext
from .common import AudioPlaybackAction
import asyncio, os, platform

class FFmpegAudioPlaybackAction(AudioPlaybackAction):
    async def _play_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        for audio in audios:
            await self._play(audio, params, cancellation_token)

    async def _play(
        self,
        audio: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        system = platform.system()
        audio_path, audio_spooled = await MediaInputPathResolver.resolve(audio, streamable_media=[ "audio", "video" ])

        command: List[str] = [ "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "warning" ]

        if params["duration"] is not None:
            command.extend([ "-t", str(params["duration"]) ])

        if is_pcm_format(audio.format):
            command.extend([ "-f", audio.format ])

            if audio.attrs.get("sample_rate"):
                command.extend([ "-ar", str(audio.attrs["sample_rate"]) ])
            else:
                raise ValueError(f"Raw PCM source {audio.format!r} requires 'sample_rate' in attrs")
            if audio.attrs.get("channels"):
                command.extend([ "-ac", str(audio.attrs["channels"]) ])
            else:
                raise ValueError(f"Raw PCM source {audio.format!r} requires 'channels' in attrs")

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

    def _build_audio_output_options(
        self,
        system: str,
        sink: AudioPlaybackSink,
        device: Optional[Any],
    ) -> List[str]:
        # macOS: audiotoolbox writes to a Core Audio device. The muxer accepts
        #        an integer device index as its output url; -audio_device_index
        #        selects a specific device when sink='device'.
        if system == "Darwin":
            if sink == AudioPlaybackSink.DEVICE and device is not None:
                return [ "-f", "audiotoolbox", "-audio_device_index", str(device), "-" ]
            return [ "-f", "audiotoolbox", "-" ]

        # Windows: WASAPI is exposed via ffmpeg's "wasapi" output muxer;
        #          the url is the device name ("default" for the OS default).
        if system == "Windows":
            if sink == AudioPlaybackSink.DEVICE and device is not None:
                return [ "-f", "wasapi", str(device) ]
            return [ "-f", "wasapi", "default" ]

        # Linux: PulseAudio is exposed via the "pulse" muxer; the url is a
        #        sink name ("default" for the OS default).
        if system == "Linux":
            if sink == AudioPlaybackSink.DEVICE and device is not None:
                return [ "-f", "pulse", str(device) ]
            return [ "-f", "pulse", "default" ]

        raise NotImplementedError(f"Audio playback is not supported on platform: {system}")

@register_audio_playback_service(AudioPlaybackDriver.FFMPEG)
class FFmpegAudioPlaybackService(AudioPlaybackService):
    def __init__(self, id: str, config: AudioPlaybackComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: AudioPlaybackActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegAudioPlaybackAction(action).run(context)
