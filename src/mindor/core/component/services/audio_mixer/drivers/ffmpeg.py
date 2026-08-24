from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import AudioMixerComponentConfig, AudioMixerDriver
from mindor.dsl.schema.action import (
    AudioMixerActionConfig,
    AudioMixerOverlayDurationMode,
    AudioOverlayPlacement,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import AudioEncoderParams
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.variable.time import parse_time
from mindor.core.utils.ffmpeg.probe import probe_audio
from mindor.core.utils.ffmpeg.codecs import get_audio_codec_for_format
from mindor.core.utils.audio import is_streamable_audio_format
from mindor.core.utils.files import get_temporary_path
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import AudioMixerService, register_audio_mixer_service
from ..base import ComponentActionContext
from .common import AudioMixerAction
import asyncio, os

_DEFAULT_FORMAT = "wav"

class FFmpegAudioMixerAction(AudioMixerAction):
    async def _concat(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AudioStreamResource:
        format = self._resolve_container_format(params["format"])

        if streaming and not is_streamable_audio_format(format):
            logging.warning("Format '%s' is not streamable; falling back to file output.", format)
            streaming = False

        input_paths: List[str] = []
        spooled_paths: List[str] = []

        for audio in audios:
            path, spooled = await MediaInputPathResolver.resolve(audio)
            input_paths.append(path)
            if spooled:
                spooled_paths.append(path)

        command: List[str] = [ "ffmpeg", "-hide_banner", "-y" ]
        for path in input_paths:
            command.extend([ "-i", path ])

        filter_complex, audio_label = self._build_concat_filter(len(input_paths), params.get("crossfade"))
        command.extend([ "-filter_complex", filter_complex ])
        command.extend([ "-map", audio_label ])

        for option, value in self._resolve_encoding_options(params["encoding"], format).items():
            command.extend([ option, value ])

        def _cleanup() -> None:
            for path in spooled_paths:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

        logging.debug("Mixing %d audios with concat filter to '%s'", len(audios), format)

        if streaming:
            return await self._encode_to_stream(command, format, _cleanup, cancellation_token)

        return await self._encode_to_file(command, format, _cleanup, cancellation_token)

    async def _overlay(
        self,
        audio: MediaSource,
        overlays: List[MediaSource],
        placements: List[AudioOverlayPlacement],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AudioStreamResource:
        format = self._resolve_container_format(params["format"])

        if streaming and not is_streamable_audio_format(format):
            logging.warning("Format '%s' is not streamable; falling back to file output.", format)
            streaming = False

        base_path, base_spooled = await MediaInputPathResolver.resolve(audio)

        overlay_paths: List[str] = []
        spooled_paths: List[str] = []

        if base_spooled:
            spooled_paths.append(base_path)

        for overlay in overlays:
            path, spooled = await MediaInputPathResolver.resolve(overlay)
            overlay_paths.append(path)
            if spooled:
                spooled_paths.append(path)

        # `base` mode caps the output at the base's duration via `-t`. `longest`
        # and `shortest` are handled by amix's `duration` option directly.
        output_duration: Optional[float] = None

        if params["duration_mode"] == AudioMixerOverlayDurationMode.BASE:
            (output_duration,) = await probe_audio(base_path, [ "duration" ])

        command: List[str] = [ "ffmpeg", "-hide_banner", "-y" ]
        command.extend([ "-i", base_path ])

        for path in overlay_paths:
            command.extend([ "-i", path ])

        filter_complex, audio_label = self._build_overlay_filter(
            [ self._resolve_overlay_filter_params(placement) for placement in placements ],
            params["duration_mode"],
        )

        command.extend([ "-filter_complex", filter_complex ])
        command.extend([ "-map", audio_label ])

        for option, value in self._resolve_encoding_options(params["encoding"], format).items():
            command.extend([ option, value ])

        if output_duration is not None:
            command.extend([ "-t", str(output_duration) ])

        def _cleanup() -> None:
            for path in spooled_paths:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

        logging.debug("Overlaying %d overlay(s) on base to '%s'", len(overlays), format)

        if streaming:
            return await self._encode_to_stream(command, format, _cleanup, cancellation_token)

        return await self._encode_to_file(command, format, _cleanup, cancellation_token)

    @staticmethod
    def _build_concat_filter(
        count: int,
        crossfade: Optional[float],
    ) -> Tuple[str, str]:
        """Build a filter_complex that produces a single [aout] from `count` audio inputs.

        Without crossfade the ffmpeg `concat` filter joins audio streams
        end-to-end. With crossfade, adjacent pairs are combined via `acrossfade`;
        each pair overlaps by `crossfade` seconds — the standard ffmpeg pattern
        for smooth transitions between clips.
        """
        if crossfade is None or crossfade <= 0:
            streams = "".join(f"[{index}:a:0]" for index in range(count))
            return f"{streams}concat=n={count}:v=0:a=1[aout]", "[aout]"

        # Crossfade path: chain acrossfade across adjacent pairs.
        # Full offset chaining requires per-input duration probing, which is
        # out of scope for the current implementation.
        raise NotImplementedError(
            "concat with crossfade requires per-input duration probing and is not yet supported; "
            "omit `crossfade` to use plain concat."
        )

    @staticmethod
    def _build_overlay_filter(
        placements: List[Tuple[Optional[float], Optional[float], float, float, Optional[float], Optional[float]]],
        duration_mode: AudioMixerOverlayDurationMode,
    ) -> Tuple[str, str]:
        """Build a filter_complex that mixes N overlays (inputs 1..N) with the base (input 0).

        Each overlay goes through its own preparation chain
        (adelay→atrim→volume→pan→afade) so start/end/gain/pan/fade apply
        per-overlay before the final amix combines everything (base + all
        overlays) into `[aout]`.

        `duration_mode` maps directly to amix's `duration` option:
          - base:     `first`      — stop when the base ends
          - shortest: `shortest`   — stop when any input ends
          - longest:  `longest`    — stop when the last input ends
        The `-t` cap in the caller enforces `base` for real, since amix's
        `first` can still trail slightly with padded inputs.
        """
        filter_parts: List[str] = []
        mix_labels: List[str] = [ "[0:a]" ]

        for index, (start, end, gain, pan, fade_in, fade_out) in enumerate(placements):
            input_index = index + 1  # inputs 1..N are overlays; 0 is base.

            chain: List[str] = []

            if start is not None and start > 0:
                delay_ms = int(start * 1000)
                # `all=1` applies the same delay to every channel so stereo stays intact.
                chain.append(f"adelay={delay_ms}:all=1")

            if end is not None:
                # `atrim`'s `end` is absolute along the delayed timeline — matches DSL semantics.
                chain.append(f"atrim=end={end}")
                # atrim keeps original PTS; reset so downstream filters see t=0 at the trim start.
                chain.append("asetpts=PTS-STARTPTS")

            if gain != 1.0:
                chain.append(f"volume={gain}")

            if pan != 0.0:
                # Symmetric stereo pan; center at 0.0, full-left at -1.0, full-right at +1.0.
                left  = max(0.0, 1.0 - pan)
                right = max(0.0, 1.0 + pan)
                chain.append(f"pan=stereo|c0={left}*c0|c1={right}*c1")

            if fade_in is not None and fade_in > 0:
                fade_start = start if start is not None else 0.0
                chain.append(f"afade=t=in:st={fade_start}:d={fade_in}")

            if fade_out is not None and fade_out > 0 and end is not None:
                fade_start = max(0.0, end - fade_out)
                chain.append(f"afade=t=out:st={fade_start}:d={fade_out}")

            prep_label = f"[ovl{index}]"

            if chain:
                filter_parts.append(f"[{input_index}:a]{','.join(chain)}{prep_label}")
            else:
                filter_parts.append(f"[{input_index}:a]anull{prep_label}")

            mix_labels.append(prep_label)

        amix_duration = {
            AudioMixerOverlayDurationMode.BASE:     "first",
            AudioMixerOverlayDurationMode.SHORTEST: "shortest",
            AudioMixerOverlayDurationMode.LONGEST:  "longest",
        }[duration_mode]

        input_count = len(mix_labels)
        filter_parts.append(
            f"{''.join(mix_labels)}amix=inputs={input_count}:duration={amix_duration}:dropout_transition=0:normalize=0[aout]"
        )

        return ";".join(filter_parts), "[aout]"

    async def _encode_to_file(
        self,
        command: List[str],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AudioStreamResource:
        output_path = get_temporary_path(format)

        command = command + [ output_path ]

        process_task = asyncio.create_task(run_subprocess(
            command,
            source=None,
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
                raise RuntimeError(f"ffmpeg audio mixing failed (exit code {process.returncode}): {error_message}")
        except asyncio.CancelledError:
            logging.info("Audio mixing cancelled")
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

            cleanup()

        logging.debug("Audio mixing completed: '%s'", output_path)

        return AudioStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _encode_to_stream(
        self,
        command: List[str],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AudioStreamResource:
        command = command + [ "-f", format, "pipe:1" ]
        error: list = []

        async def _handle_stdout(reader: asyncio.StreamReader) -> AsyncIterator[bytes]:
            while True:
                chunk = await reader.read(65536)

                if not chunk:
                    break

                yield chunk

        async def _handle_stderr(reader: asyncio.StreamReader) -> None:
            while True:
                line = await reader.readline()

                if not line:
                    break

                error.append(line)

        async def _stream() -> AsyncIterator[bytes]:
            watcher_task: Optional[asyncio.Task] = None
            try:
                async with stream_subprocess(
                    command,
                    source=None,
                    stdout_handler=_handle_stdout,
                    stderr_handler=_handle_stderr,
                ) as (process, chunks, _):
                    if cancellation_token is not None:
                        async def _watch_cancellation() -> None:
                            while not cancellation_token.is_cancelled():
                                if process.returncode is not None:
                                    return
                                await asyncio.sleep(0.2)
                            process.kill()

                        watcher_task = asyncio.create_task(_watch_cancellation())

                    async for chunk in chunks:
                        yield chunk

                if process.returncode is not None and process.returncode != 0:
                    error_message = b"".join(error).decode("utf-8", errors="replace")
                    raise RuntimeError(f"ffmpeg audio mixing failed (exit code {process.returncode}): {error_message}")
            finally:
                if watcher_task is not None and not watcher_task.done():
                    watcher_task.cancel()
                    try:
                        await watcher_task
                    except (asyncio.CancelledError, Exception):
                        pass

                cleanup()

        return AudioStreamResource(AsyncIterableStreamResource(_stream()), format=format)

    @staticmethod
    def _resolve_overlay_filter_params(
        placement: AudioOverlayPlacement,
    ) -> Tuple[Optional[float], Optional[float], float, float, Optional[float], Optional[float]]:
        """Coerce a placement's field values into the concrete types the filter builder expects.

        Fields are `Union[float, str]` in the schema so callers can inline
        literal numbers or template references that resolved to strings; cast
        here so the overlay filter always receives numbers.
        """
        return (
            parse_time(placement.start_time) if placement.start_time is not None else None,
            parse_time(placement.end_time)   if placement.end_time   is not None else None,
            float(placement.gain),
            float(placement.pan),
            parse_time(placement.fade_in)    if placement.fade_in    is not None else None,
            parse_time(placement.fade_out)   if placement.fade_out   is not None else None,
        )

    def _resolve_encoding_options(self, encoding: AudioEncoderParams, format: str) -> Dict[str, str]:
        options: Dict[str, str] = {}

        codec = self._resolve_audio_codec(encoding, format)

        if codec:
            options["-c:a"] = codec

        if encoding.bitrate:
            options["-b:a"] = str(encoding.bitrate)

        if encoding.sample_rate:
            options["-ar"] = str(encoding.sample_rate)

        if encoding.channels:
            options["-ac"] = str(encoding.channels)

        return options

    @staticmethod
    def _resolve_container_format(format: Optional[str]) -> str:
        if format:
            return format.lower()

        return _DEFAULT_FORMAT

    @staticmethod
    def _resolve_audio_codec(encoding: AudioEncoderParams, format: str) -> Optional[str]:
        if encoding.codec:
            return encoding.codec

        return get_audio_codec_for_format(format)

@register_audio_mixer_service(AudioMixerDriver.FFMPEG)
class FFmpegAudioMixerService(AudioMixerService):
    def __init__(self, id: str, config: AudioMixerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: AudioMixerActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegAudioMixerAction(action).run(context)
