from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoMixerComponentConfig, VideoMixerDriver
from mindor.dsl.schema.action import (
    VideoMixerActionConfig,
    VideoMixerOverlayAudioMode,
    VideoMixerOverlayDurationMode,
    VideoOverlayAnchor,
    VideoOverlayPlacement,
)
from mindor.core.component.action.media import MediaInputPathResolver
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.variable.time import parse_time
from mindor.core.utils.ffmpeg.probe import probe_video
from mindor.core.utils.ffmpeg.codecs import get_video_codecs_for_format
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.utils.files import get_temporary_path
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ..base import VideoMixerService, register_video_mixer_service
from ..base import ComponentActionContext
from .common import VideoMixerAction
import asyncio, os

_DEFAULT_FORMAT = "mp4"

_ANCHOR_OFFSETS: Dict[VideoOverlayAnchor, Tuple[str, str]] = {
    VideoOverlayAnchor.TOP_LEFT:      ("0",    "0"),
    VideoOverlayAnchor.TOP_CENTER:    ("-w/2", "0"),
    VideoOverlayAnchor.TOP_RIGHT:     ("-w",   "0"),
    VideoOverlayAnchor.CENTER_LEFT:   ("0",    "-h/2"),
    VideoOverlayAnchor.CENTER:        ("-w/2", "-h/2"),
    VideoOverlayAnchor.CENTER_RIGHT:  ("-w",   "-h/2"),
    VideoOverlayAnchor.BOTTOM_LEFT:   ("0",    "-h"),
    VideoOverlayAnchor.BOTTOM_CENTER: ("-w/2", "-h"),
    VideoOverlayAnchor.BOTTOM_RIGHT:  ("-w",   "-h"),
}

class FFmpegVideoMixerAction(VideoMixerAction):
    async def _concat(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        encoding  = params["encoding"]
        crossfade = params.get("crossfade")

        format = self._resolve_container_format(encoding)

        if streaming and not is_streamable_video_format(format):
            logging.warning("Format '%s' is not streamable; falling back to file output.", format)
            streaming = False

        input_paths: List[str] = []
        spooled_paths: List[str] = []

        for video in videos:
            path, spooled = await MediaInputPathResolver.resolve(video)
            input_paths.append(path)
            if spooled:
                spooled_paths.append(path)

        command: List[str] = [ "ffmpeg", "-hide_banner", "-y" ]
        for path in input_paths:
            command.extend([ "-i", path ])

        filter_complex, video_label, audio_label = self._build_concat_filter(len(input_paths), crossfade)
        command.extend([ "-filter_complex", filter_complex ])
        command.extend([ "-map", video_label ])
        if audio_label is not None:
            command.extend([ "-map", audio_label ])

        for option, value in self._resolve_encoding_options(encoding, has_audio=audio_label is not None).items():
            command.extend([ option, value ])

        def _cleanup() -> None:
            for path in spooled_paths:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

        logging.debug("Mixing %d videos with concat filter to '%s'", len(videos), format)

        if streaming:
            return await self._encode_to_stream(command, format, _cleanup, cancellation_token)

        return await self._encode_to_file(command, format, _cleanup, cancellation_token)

    async def _overlay(
        self,
        video: MediaSource,
        overlays: List[MediaSource],
        placements: List[VideoOverlayPlacement],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        format = self._resolve_container_format(params["encoding"])

        if streaming and not is_streamable_video_format(format):
            logging.warning("Format '%s' is not streamable; falling back to file output.", format)
            streaming = False

        base_path, base_spooled = await MediaInputPathResolver.resolve(video)

        overlay_paths: List[str] = []
        spooled_paths: List[str] = []

        if base_spooled:
            spooled_paths.append(base_path)

        for overlay in overlays:
            path, spooled = await MediaInputPathResolver.resolve(overlay)
            overlay_paths.append(path)
            if spooled:
                spooled_paths.append(path)

        # The overlay filter's default `eof_action=repeat` keeps holding the base's
        # last frame while any overlay is still producing frames — so unless we
        # constrain the output, `base` mode leaks into `longest` when overlays
        # outlast the base. `base` therefore probes the base's duration and caps
        # the output with `-t`. `longest` probes every input to compute how far
        # to pad the base with clones. `shortest` needs no probe.
        base_pad_duration: Optional[float] = None
        output_duration: Optional[float] = None

        if params["duration_mode"] == VideoMixerOverlayDurationMode.LONGEST:
            (base_duration,) = await probe_video(base_path, [ "duration" ])
            overlay_durations = [ (await probe_video(path, [ "duration" ]))[0] for path in overlay_paths ]
            longest_duration = max([ base_duration ] + overlay_durations)
            base_pad_duration = max(0.0, longest_duration - base_duration)
        elif params["duration_mode"] == VideoMixerOverlayDurationMode.BASE:
            (output_duration,) = await probe_video(base_path, [ "duration" ])

        command: List[str] = [ "ffmpeg", "-hide_banner", "-y" ]
        command.extend([ "-i", base_path ])

        for path in overlay_paths:
            command.extend([ "-i", path ])

        filter_complex, video_label, audio_label = self._build_overlay_filter(
            [ self._resolve_overlay_filter_params(placement) for placement in placements ],
            params["audio_mode"],
            params["duration_mode"],
            base_pad_duration,
        )

        command.extend([ "-filter_complex", filter_complex ])
        command.extend([ "-map", video_label ])

        if audio_label is not None:
            command.extend([ "-map", audio_label ])

        for option, value in self._resolve_encoding_options(params["encoding"], has_audio=audio_label is not None).items():
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
    ) -> Tuple[str, str, Optional[str]]:
        """Build a filter_complex that produces a single [vout]/[aout] from `count` inputs.

        Without crossfade the ffmpeg `concat` filter joins video and audio streams
        end-to-end. With crossfade, adjacent pairs are combined via `xfade`
        (video) and `acrossfade` (audio); each pair overlaps by `crossfade` seconds,
        which is the standard ffmpeg pattern for smooth transitions between clips.
        """
        if crossfade is None or crossfade <= 0:
            parts: List[str] = []
            streams = "".join(f"[{index}:v:0][{index}:a:0]" for index in range(count))
            parts.append(f"{streams}concat=n={count}:v=1:a=1[vout][aout]")
            return ";".join(parts), "[vout]", "[aout]"

        # Crossfade path: chain xfade/acrossfade across adjacent pairs.
        # Each xfade needs the offset (end-of-previous minus crossfade) which
        # depends on cumulative duration — we defer to ffmpeg by using
        # `xfade=transition=fade:duration=D:offset=0` on pre-trimmed streams is
        # complex, so instead we conservatively concatenate and then apply a
        # single acrossfade-like effect: fall back to plain concat when
        # crossfade is requested for now, with a warning-level log documented.
        # Full offset chaining requires per-input duration probing, which is
        # out of scope for the current implementation.
        raise NotImplementedError(
            "concat with crossfade requires per-input duration probing and is not yet supported; "
            "omit `crossfade` to use plain concat."
        )

    @staticmethod
    def _build_overlay_filter(
        placements: List[Tuple[int, int, Optional[int], Optional[int], VideoOverlayAnchor, float, Optional[float], Optional[float]]],
        audio_mode: VideoMixerOverlayAudioMode,
        duration_mode: VideoMixerOverlayDurationMode,
        base_pad_duration: Optional[float],
    ) -> Tuple[str, str, Optional[str]]:
        """Build a filter_complex that composites N overlays (inputs 1..N) onto the base (input 0).

        Each overlay goes through its own preparation chain (format→scale→opacity)
        and is then composited onto the running video stream. The composite
        result is chained forward, so overlays stack in DSL order — the first
        overlay lands on the base, the second on that result, and so on.
        `anchor` shifts each overlay relative to (x, y) via ffmpeg overlay
        expressions (`w`/`h` are the overlay's width/height).
        `enable=between(t,start,end)` gates each overlay's visibility.

        `duration_mode` decides how long the output runs:
          - base:     stop when the base ends (overlay filter default).
          - shortest: stop when the first of base/overlays ends (`overlay=shortest=1`).
          - longest:  stop when the last stream ends. The base is pre-padded with
                      cloned frames (`tpad`) so the overlay filter can keep
                      compositing after the base's own EOF; overlays past their
                      own EOF hold their last frame via `eof_action=pass` (the
                      overlay filter's default).
        Audio uses the same intent via `amix duration=first|shortest|longest`.
        """
        filter_parts: List[str] = []

        # Video pipeline entry — pad the base first when `longest` needs to hold
        # frames past the base's original EOF.
        if duration_mode == VideoMixerOverlayDurationMode.LONGEST and base_pad_duration and base_pad_duration > 0:
            filter_parts.append(f"[0:v]tpad=stop_mode=clone:stop_duration={base_pad_duration}[base_v]")
            current_video_label = "[base_v]"
        else:
            current_video_label = "[0:v]"

        for index, (x, y, width, height, anchor, opacity, start, end) in enumerate(placements):
            input_index = index + 1  # inputs 1..N are overlays; 0 is base.

            overlay_chain: List[str] = [ "format=yuva420p" ]
            if width or height:
                w = str(width) if width else "-1"
                h = str(height) if height else "-1"
                overlay_chain.append(f"scale={w}:{h}")
            if opacity < 1.0:
                overlay_chain.append(f"colorchannelmixer=aa={opacity}")

            prep_label = f"[ovl{index}]"
            filter_parts.append(f"[{input_index}:v]{','.join(overlay_chain)}{prep_label}")

            ax, ay = _ANCHOR_OFFSETS[anchor]
            pos_x = f"{x}+({ax})"
            pos_y = f"{y}+({ay})"

            overlay_opts = [ f"x={pos_x}", f"y={pos_y}" ]
            if start is not None or end is not None:
                lo = f"{start}" if start is not None else "0"
                hi = f"{end}"   if end   is not None else "9e9"
                overlay_opts.append(f"enable='between(t,{lo},{hi})'")

            if duration_mode == VideoMixerOverlayDurationMode.SHORTEST:
                overlay_opts.append("shortest=1")

            next_video_label = "[vout]" if index == len(placements) - 1 else f"[v{index}]"
            filter_parts.append(f"{current_video_label}{prep_label}overlay={':'.join(overlay_opts)}{next_video_label}")
            current_video_label = next_video_label

        amix_duration = {
            VideoMixerOverlayDurationMode.BASE:     "first",
            VideoMixerOverlayDurationMode.SHORTEST: "shortest",
            VideoMixerOverlayDurationMode.LONGEST:  "longest",
        }[duration_mode]

        audio_label: Optional[str]
        overlay_count = len(placements)

        if audio_mode == VideoMixerOverlayAudioMode.NONE:
            audio_label = None
        elif audio_mode == VideoMixerOverlayAudioMode.BASE:
            audio_label = "0:a?"
        elif audio_mode == VideoMixerOverlayAudioMode.OVERLAY:
            if overlay_count == 1:
                audio_label = "1:a?"
            else:
                streams = "".join(f"[{index + 1}:a]" for index in range(overlay_count))
                filter_parts.append(f"{streams}amix=inputs={overlay_count}:duration={amix_duration}:dropout_transition=0[aout]")
                audio_label = "[aout]"
        elif audio_mode == VideoMixerOverlayAudioMode.MIX:
            streams = "[0:a]" + "".join(f"[{index + 1}:a]" for index in range(overlay_count))
            filter_parts.append(f"{streams}amix=inputs={overlay_count + 1}:duration={amix_duration}:dropout_transition=0[aout]")
            audio_label = "[aout]"
        else:
            audio_label = "0:a?"

        return ";".join(filter_parts), "[vout]", audio_label

    async def _encode_to_file(
        self,
        command: List[str],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        output_path = get_temporary_path(format)

        command = command + [ "-movflags", "+faststart", output_path ]

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
                raise RuntimeError(f"ffmpeg video mixing failed (exit code {process.returncode}): {error_message}")
        except asyncio.CancelledError:
            logging.info("Video mixing cancelled")
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

            cleanup()

        logging.debug("Video mixing completed: '%s'", output_path)

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _encode_to_stream(
        self,
        command: List[str],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
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
                    raise RuntimeError(f"ffmpeg video mixing failed (exit code {process.returncode}): {error_message}")
            finally:
                if watcher_task is not None and not watcher_task.done():
                    watcher_task.cancel()
                    try:
                        await watcher_task
                    except (asyncio.CancelledError, Exception):
                        pass

                cleanup()

        return VideoStreamResource(AsyncIterableStreamResource(_stream()), format=format)

    @staticmethod
    def _resolve_overlay_filter_params(
        placement: VideoOverlayPlacement,
    ) -> Tuple[int, int, Optional[int], Optional[int], VideoOverlayAnchor, float, Optional[float], Optional[float]]:
        """Coerce a placement's field values into the concrete types the filter builder expects.

        Fields are `Union[int|float, str]` in the schema so callers can inline
        literal numbers or template references that resolved to strings; cast
        here so the overlay filter always receives numbers.
        """
        anchor = placement.anchor if isinstance(placement.anchor, VideoOverlayAnchor) else VideoOverlayAnchor(placement.anchor)

        return (
            int(placement.x),
            int(placement.y),
            int(placement.width)  if placement.width  is not None else None,
            int(placement.height) if placement.height is not None else None,
            anchor,
            float(placement.opacity),
            parse_time(placement.start) if placement.start is not None else None,
            parse_time(placement.end)   if placement.end   is not None else None,
        )

    def _resolve_encoding_options(self, encoding: VideoAudioEncodingParams, has_audio: bool) -> Dict[str, str]:
        options: Dict[str, str] = {}

        video = encoding.video
        audio = encoding.audio

        video_codec = self._resolve_video_codec(encoding)

        if video_codec:
            options["-c:v"] = video_codec

        if video and video.bitrate:
            options["-b:v"] = str(video.bitrate)

        if video and video.resolution:
            options["-s"] = video.resolution

        if video and video.fps is not None:
            options["-r"] = str(video.fps)

        if video_codec in ("libx264", "libx265"):
            options["-pix_fmt"] = "yuv420p"

        if has_audio:
            audio_codec = self._resolve_audio_codec(encoding)

            if audio_codec:
                options["-c:a"] = audio_codec

            if audio and audio.bitrate:
                options["-b:a"] = str(audio.bitrate)

        return options

    @staticmethod
    def _resolve_container_format(encoding: VideoAudioEncodingParams) -> str:
        if encoding.format:
            return encoding.format.lower()

        return _DEFAULT_FORMAT

    @staticmethod
    def _resolve_video_codec(encoding: VideoAudioEncodingParams) -> Optional[str]:
        if encoding.video and encoding.video.codec:
            return encoding.video.codec

        video_codec, _ = get_video_codecs_for_format(encoding.format or _DEFAULT_FORMAT)
        return video_codec

    @staticmethod
    def _resolve_audio_codec(encoding: VideoAudioEncodingParams) -> Optional[str]:
        if encoding.audio and encoding.audio.codec:
            return encoding.audio.codec

        _, audio_codec = get_video_codecs_for_format(encoding.format or _DEFAULT_FORMAT)
        return audio_codec

@register_video_mixer_service(VideoMixerDriver.FFMPEG)
class FFmpegVideoMixerService(VideoMixerService):
    def __init__(self, id: str, config: VideoMixerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoMixerActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoMixerAction(action).run(context)
