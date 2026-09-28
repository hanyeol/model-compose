from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Callable, Any
from dataclasses import dataclass
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoMixerComponentConfig, VideoMixerDriverType
from mindor.dsl.schema.action import (
    VideoMixerActionConfig,
    VideoMixerOverlayAudioMode,
    VideoMixerOverlayDurationMode,
    VideoOverlayAnchor,
    VideoOverlayEofAction,
    VideoOverlayPlacement,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.variable.time import parse_time
from mindor.core.utils.ffmpeg.executable import resolve_ffmpeg_executable
from mindor.core.utils.ffmpeg.probe import probe_video, probe_audio
from mindor.core.utils.ffmpeg.codecs import get_video_codecs_for_format
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.utils.files import get_temporary_path
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import VideoMixerDriver, register_video_mixer_driver
from ..base import ComponentActionContext
from .common import VideoMixerAction
import asyncio, os

_DEFAULT_FORMAT = "mp4"

_AMIX_DURATIONS: Dict[VideoMixerOverlayDurationMode, str] = {
    VideoMixerOverlayDurationMode.BASE:     "first",
    VideoMixerOverlayDurationMode.SHORTEST: "shortest",
    VideoMixerOverlayDurationMode.LONGEST:  "longest",
}

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

@dataclass
class OverlayFilterPlacement:
    """Normalized placement values consumed by the overlay filter builder.

    Time fields are seconds on the base timeline; `gain` is a linear volume
    multiplier for the overlay's audio when routed through amix.
    """
    x: int
    y: int
    width: Optional[int]
    height: Optional[int]
    anchor: VideoOverlayAnchor
    opacity: float
    gain: float
    start_time: Optional[float]
    end_time: Optional[float]
    eof_action: VideoOverlayEofAction

class FFmpegVideoMixerAction(VideoMixerAction):
    async def _concat(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        encoding  = params["encoding"]
        crossfade = params["crossfade"]

        format = self._resolve_container_format(encoding)

        if streaming and not is_streamable_video_format(format):
            logging.warning("Format '%s' is not streamable; falling back to file output.", format)
            streaming = False

        input_paths: List[str] = []
        spooled_paths: List[str] = []

        for video in videos:
            path, spooled = await MediaInputPathResolver().resolve(video)
            input_paths.append(path)

            if spooled:
                spooled_paths.append(path)

        command: List[str] = [ resolve_ffmpeg_executable(), "-hide_banner", "-y" ]

        for path in input_paths:
            command.extend([ "-i", path ])

        filter_complex, video_label, audio_label = self._build_concat_filter(len(input_paths), crossfade)

        command.extend([ "-filter_complex", filter_complex ])
        command.extend([ "-map", video_label ])

        if audio_label is not None:
            command.extend([ "-map", audio_label ])

        encoding_options = self._resolve_encoding_options(encoding, has_audio=audio_label is not None)

        for option, value in encoding_options.items():
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

        base_path, base_spooled = await MediaInputPathResolver().resolve(video)

        overlay_paths: List[str] = []
        spooled_paths: List[str] = []

        if base_spooled:
            spooled_paths.append(base_path)

        for overlay in overlays:
            path, spooled = await MediaInputPathResolver().resolve(overlay)
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

        # Feeding an audio-less input to amix via `[N:a]` fails hard because the
        # stream specifier can't match. Probe each input up front so the filter
        # builder can substitute anullsrc for the missing tracks and keep the
        # mix graph well-formed.
        base_has_audio = await self._has_audio_stream(base_path)
        overlay_has_audio = [ await self._has_audio_stream(path) for path in overlay_paths ]

        command: List[str] = [ resolve_ffmpeg_executable(), "-hide_banner", "-y" ]
        command.extend([ "-i", base_path ])

        for path in overlay_paths:
            command.extend([ "-i", path ])

        filter_complex, video_label, audio_label = self._build_overlay_filter(
            [ self._resolve_overlay_filter_params(placement) for placement in placements ],
            params["audio_mode"],
            params["duration_mode"],
            base_pad_duration,
            base_has_audio,
            overlay_has_audio,
        )

        command.extend([ "-filter_complex", filter_complex ])
        command.extend([ "-map", video_label ])

        if audio_label is not None:
            command.extend([ "-map", audio_label ])

        encoding_options = self._resolve_encoding_options(params["encoding"], has_audio=audio_label is not None)

        for option, value in encoding_options.items():
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

    def _build_overlay_filter(
        self,
        placements: List[OverlayFilterPlacement],
        audio_mode: VideoMixerOverlayAudioMode,
        duration_mode: VideoMixerOverlayDurationMode,
        base_pad_duration: Optional[float],
        base_has_audio: bool,
        overlay_has_audio: List[bool],
    ) -> Tuple[str, str, Optional[str]]:
        """Build a filter_complex that composites N overlays (inputs 1..N) onto the base (input 0).

        Each overlay goes through its own preparation chain (setpts→format→
        scale→opacity) and is then composited onto the running video stream.
        The composite result is chained forward, so overlays stack in DSL order —
        the first overlay lands on the base, the second on that result, and so
        on. `anchor` shifts each overlay relative to (x, y) via ffmpeg overlay
        expressions (`w`/`h` are the overlay's width/height).

        `placement.start_time` shifts the overlay's own PTS via `setpts`
        (video) and `adelay` (audio) so the overlay plays *from its beginning*
        at that base-timeline time, not just becomes visible mid-playback. The
        original `enable=between` gate is kept in sync so late overlays don't
        leak a frame before their shifted start.

        `placement.eof_action` picks what happens after the overlay's own
        stream ends: `repeat` (ffmpeg default) freezes the last frame, `pass`
        lets the base show through, and `endall` cuts the whole output.

        `duration_mode` decides how long the output runs:
          - base:     stop when the base ends (overlay filter default).
          - shortest: stop when the first of base/overlays ends (`overlay=shortest=1`).
          - longest:  stop when the last stream ends. The base is pre-padded with
                      cloned frames (`tpad`) so the overlay filter can keep
                      compositing after the base's own EOF.
        Audio uses the same intent via `amix duration=first|shortest|longest`,
        with `normalize=0` so mixing multiple tracks doesn't halve the base's
        loudness (per-placement `gain` still weights the mix).
        """
        filter_parts: List[str] = []

        # Video pipeline entry — pad the base first when `longest` needs to hold
        # frames past the base's original EOF.
        if duration_mode == VideoMixerOverlayDurationMode.LONGEST and base_pad_duration and base_pad_duration > 0:
            filter_parts.append(f"[0:v]tpad=stop_mode=clone:stop_duration={base_pad_duration}[base_v]")
            current_video_label = "[base_v]"
        else:
            current_video_label = "[0:v]"

        for index, placement in enumerate(placements):
            input_index = index + 1  # inputs 1..N are overlays; 0 is base.
            overlay_chain: List[str] = []

            # Rebase the overlay's own PTS so it starts at `start_time` on the
            # base timeline. Without this, `enable=between(t,start,end)` just
            # gates visibility — the overlay is already `start` seconds in when
            # it first appears.
            if placement.start_time is not None and placement.start_time > 0:
                overlay_chain.append(f"setpts=PTS-STARTPTS+{placement.start_time}/TB")
            else:
                overlay_chain.append("setpts=PTS-STARTPTS")

            overlay_chain.append("format=yuva420p")

            if placement.width or placement.height:
                width  = str(placement.width)  if placement.width  else "-1"
                height = str(placement.height) if placement.height else "-1"
                overlay_chain.append(f"scale={width}:{height}")

            if placement.opacity < 1.0:
                overlay_chain.append(f"colorchannelmixer=aa={placement.opacity}")

            prep_label = f"[ovl{index}]"
            filter_parts.append(f"[{input_index}:v]{','.join(overlay_chain)}{prep_label}")

            ax, ay = _ANCHOR_OFFSETS[placement.anchor]
            pos_x = f"{placement.x}+({ax})"
            pos_y = f"{placement.y}+({ay})"

            overlay_options = [ f"x={pos_x}", f"y={pos_y}" ]

            if placement.start_time is not None or placement.end_time is not None:
                start_time = f"{placement.start_time}" if placement.start_time is not None else "0"
                end_time   = f"{placement.end_time}"   if placement.end_time   is not None else "9e9"
                overlay_options.append(f"enable='between(t,{start_time},{end_time})'")

            overlay_options.append(f"eof_action={placement.eof_action.value}")

            if duration_mode == VideoMixerOverlayDurationMode.SHORTEST:
                overlay_options.append("shortest=1")

            next_video_label = "[vout]" if index == len(placements) - 1 else f"[v{index}]"
            filter_parts.append(f"{current_video_label}{prep_label}overlay={':'.join(overlay_options)}{next_video_label}")
            current_video_label = next_video_label

        audio_label = self._build_overlay_audio_filter(
            filter_parts,
            placements,
            audio_mode,
            duration_mode,
            base_has_audio,
            overlay_has_audio,
        )

        return ";".join(filter_parts), "[vout]", audio_label

    def _build_overlay_audio_filter(
        self,
        filter_parts: List[str],
        placements: List[OverlayFilterPlacement],
        audio_mode: VideoMixerOverlayAudioMode,
        duration_mode: VideoMixerOverlayDurationMode,
        base_has_audio: bool,
        overlay_has_audio: List[bool],
    ) -> Optional[str]:
        """Append audio preparation and mix nodes to `filter_parts` and return the mapped label.

        For each track routed into the mix we run a prep chain of `[async]setpts →
        adelay → volume` (or an anullsrc when the input has no audio). The
        prepared labels are then either mapped straight through or combined via
        `amix normalize=0`. Returning None means the output has no audio track.
        """
        amix_duration = _AMIX_DURATIONS[duration_mode]

        if audio_mode == VideoMixerOverlayAudioMode.NONE:
            return None

        if audio_mode == VideoMixerOverlayAudioMode.BASE:
            if not base_has_audio:
                return None

            return "0:a"

        overlay_indices = [ index for index in range(len(placements)) if overlay_has_audio[index] ]

        if audio_mode == VideoMixerOverlayAudioMode.OVERLAY:
            if not overlay_indices:
                return None

            prepared_labels = [
                self._append_audio_overlay(filter_parts, index + 1, placements[index])
                for index in overlay_indices
            ]

            if len(prepared_labels) == 1:
                return prepared_labels[0]

            weights = " ".join(f"{placements[index].gain}" for index in overlay_indices)
            streams = "".join(prepared_labels)
            filter_parts.append(
                f"{streams}amix=inputs={len(prepared_labels)}:duration={amix_duration}"
                f":normalize=0:weights='{weights}':dropout_transition=0[aout]"
            )

            return "[aout]"

        # VideoMixerOverlayAudioMode.MIX — include the base plus every overlay,
        # substituting anullsrc for tracks that carry no audio so amix stays
        # well-formed. When only the base survives (no overlay has audio), skip
        # amix entirely and map `0:a` directly — inlining `[0:a]` as a
        # standalone filter node would leave the label undefined in the graph.
        if not overlay_indices:
            if base_has_audio:
                return "0:a"

            return None

        prepared_labels: List[str] = []
        weights: List[str] = []

        if base_has_audio:
            prepared_labels.append("[0:a]")
        else:
            filter_parts.append("anullsrc=channel_layout=stereo:sample_rate=48000[abase]")
            prepared_labels.append("[abase]")

        weights.append("1")

        for index in overlay_indices:
            prepared_labels.append(self._append_audio_overlay(filter_parts, index + 1, placements[index]))
            weights.append(f"{placements[index].gain}")

        streams = "".join(prepared_labels)
        filter_parts.append(
            f"{streams}amix=inputs={len(prepared_labels)}:duration={amix_duration}"
            f":normalize=0:weights='{' '.join(weights)}':dropout_transition=0[aout]"
        )

        return "[aout]"

    def _append_audio_overlay(
        self,
        filter_parts: List[str],
        input_index: int,
        placement: OverlayFilterPlacement,
    ) -> str:
        """Append an audio overlay chain (`asetpts → adelay → volume`) for one overlay input."""
        chain: List[str] = [ "asetpts=PTS-STARTPTS" ]

        if placement.start_time is not None and placement.start_time > 0:
            delay_ms = int(placement.start_time * 1000)
            chain.append(f"adelay={delay_ms}:all=1")

        if placement.gain != 1.0:
            chain.append(f"volume={placement.gain}")

        label = f"[a{input_index}]"
        filter_parts.append(f"[{input_index}:a]{','.join(chain)}{label}")

        return label

    @staticmethod
    def _resolve_overlay_filter_params(placement: VideoOverlayPlacement) -> OverlayFilterPlacement:
        """Coerce a placement's field values into the concrete types the filter builder expects.

        Fields are `Union[int|float, str]` in the schema so callers can inline
        literal numbers or template references that resolved to strings; cast
        here so the overlay filter always receives numbers.
        """
        anchor     = placement.anchor     if isinstance(placement.anchor, VideoOverlayAnchor)        else VideoOverlayAnchor(placement.anchor)
        eof_action = placement.eof_action if isinstance(placement.eof_action, VideoOverlayEofAction) else VideoOverlayEofAction(placement.eof_action)

        return OverlayFilterPlacement(
            x=int(placement.x),
            y=int(placement.y),
            width=int(placement.width)   if placement.width  is not None else None,
            height=int(placement.height) if placement.height is not None else None,
            anchor=anchor,
            opacity=float(placement.opacity),
            gain=float(placement.gain),
            start_time=parse_time(placement.start_time) if placement.start_time is not None else None,
            end_time=parse_time(placement.end_time)     if placement.end_time   is not None else None,
            eof_action=eof_action,
        )

    def _resolve_encoding_options(self, encoding: VideoAudioEncodingParams, has_audio: bool) -> Dict[str, str]:
        options: Dict[str, str] = {}

        video = encoding.video
        audio = encoding.audio

        video_codec = self._resolve_video_codec(encoding)

        if video_codec:
            options["-c:v"] = video_codec

        if video and video.quality is not None:
            options["-crf"] = str(video.quality)
        elif video and video.bitrate:
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

    @staticmethod
    async def _has_audio_stream(path: str) -> bool:
        (codec,) = await probe_audio(path, [ "codec" ])

        return codec is not None

@register_video_mixer_driver(VideoMixerDriverType.FFMPEG)
class FFmpegVideoMixerService(VideoMixerDriver):
    def __init__(self, id: str, config: VideoMixerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoMixerActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoMixerAction(action).run(context)
