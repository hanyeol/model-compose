from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Callable, Any
from dataclasses import dataclass
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoMixerComponentConfig, VideoMixerDriverType
from mindor.dsl.schema.action import (
    VideoMixerActionConfig,
    VideoConcatTransition,
    VideoOverlayAudioMode,
    VideoOverlayDurationMode,
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
from mindor.core.utils.ffmpeg.codecs import get_alpha_input_decoder, get_video_codecs_for_format, is_still_image_codec
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

_AMIX_DURATIONS: Dict[VideoOverlayDurationMode, str] = {
    VideoOverlayDurationMode.BASE:     "first",
    VideoOverlayDurationMode.SHORTEST: "shortest",
    VideoOverlayDurationMode.LONGEST:  "longest",
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

        if params["duration_mode"] == VideoOverlayDurationMode.LONGEST:
            (base_duration,) = await probe_video(base_path, [ "duration" ])
            overlay_durations = [ (await probe_video(path, [ "duration" ]))[0] for path in overlay_paths ]
            longest_duration = max([ base_duration ] + overlay_durations)
            base_pad_duration = max(0.0, longest_duration - base_duration)
        elif params["duration_mode"] == VideoOverlayDurationMode.BASE:
            (output_duration,) = await probe_video(base_path, [ "duration" ])

        # Feeding an audio-less input to amix via `[N:a]` fails hard because the
        # stream specifier can't match. Probe each input up front so the filter
        # builder can substitute anullsrc for the missing tracks and keep the
        # mix graph well-formed.
        base_has_audio = await self._has_audio_stream(base_path)
        overlay_has_audio = [ await self._has_audio_stream(path) for path in overlay_paths ]

        # One probe per overlay covers all four downstream decisions:
        # - codec + nb_frames drive AUTO eof_action (still-image codecs like
        #   png/webp map to `repeat` so watermarks persist; multi-frame video
        #   maps to `pass` so it disappears after its own EOF).
        # - color_space + height drive the per-overlay `in_color_matrix` on
        #   `scale`. Without an input matrix, swscale assumes 601 for un-tagged
        #   YUV, so a 709-but-un-tagged HD overlay (very common — clipper and
        #   mixer outputs are un-tagged) would go through a 601→709 conversion
        #   and come out miscolored on a 709 base.
        overlay_probes = [
            await probe_video(path, ("codec", "nb_frames", "color_space", "height"))
            for path in overlay_paths
        ]

        # Overlay preparation runs each overlay through `format=yuva420p`,
        # whose default RGB→YUV matrix is BT.601 regardless of resolution —
        # that miscolors RGB overlays (PNG/JPEG) landing on an HD base tagged
        # 709. Pull the base's color_space tag (falling back to the
        # height-based rule other drivers use) and pin the overlay chain to
        # the same matrix.
        base_color_space, base_height = await probe_video(base_path, ("color_space", "height"))
        base_matrix = self._resolve_base_color_matrix(base_color_space, base_height)
        overlay_matrices = [
            self._resolve_base_color_matrix(color_space, height)
            for _, _, color_space, height in overlay_probes
        ]

        command: List[str] = [ resolve_ffmpeg_executable(), "-hide_banner", "-y" ]
        command.extend(await self._alpha_input_options(base_path))
        command.extend([ "-i", base_path ])

        for path in overlay_paths:
            command.extend(await self._alpha_input_options(path))
            command.extend([ "-i", path ])

        filter_complex, video_label, audio_label = self._build_overlay_filter(
            [
                self._resolve_overlay_filter_params(placement, overlay_probes[index][0], overlay_probes[index][1])
                for index, placement in enumerate(placements)
            ],
            params["audio_mode"],
            params["duration_mode"],
            base_pad_duration,
            base_has_audio,
            overlay_has_audio,
            base_matrix,
            overlay_matrices,
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

    async def _concat(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        encoding   = params["encoding"]
        crossfade  = params["crossfade"]
        transition = params["transition"]

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

        # Probe each input's audio track so silent clips don't crash the
        # concat/xfade graph — the video and audio filter chains both assume
        # every stream specifier resolves. Durations are needed both for
        # anullsrc padding (unbounded anullsrc turns plain concat into an
        # infinite stream) and for computing cumulative xfade offsets.
        # xfade also refuses inputs whose timebase, fps, or pixel format
        # differ (common across mp4s from different encoders), so when
        # crossfade is on we probe resolution + fps too and normalize every
        # input to the max of those before xfade. All video fields are
        # fetched in one ffprobe call per input to keep this O(N) instead of
        # O(4N).
        has_audios = [ await self._has_audio_stream(path) for path in input_paths ]
        crossfading = crossfade is not None and crossfade > 0
        video_fields = ("duration", "width", "height", "frame_rate") if crossfading else ("duration",)
        video_probes = [ await probe_video(path, video_fields) for path in input_paths ]

        durations = [ duration for duration, *_ in video_probes ]
        resolutions: List[Tuple[int, int]] = []
        frame_rates: List[float] = []

        if crossfading:
            for _, width, height, frame_rate in video_probes:
                resolutions.append((width, height))
                # Fall back to 30 fps when the source doesn't report one
                # (rare; happens with a few odd webm/mkv variants). Any
                # non-None value keeps max() well-defined and lets xfade
                # normalization proceed.
                frame_rates.append(frame_rate if frame_rate is not None else 30.0)

        command: List[str] = [ resolve_ffmpeg_executable(), "-hide_banner", "-y" ]

        for path in input_paths:
            command.extend(await self._alpha_input_options(path))
            command.extend([ "-i", path ])

        filter_complex, video_label, audio_label = self._build_concat_filter(
            has_audios,
            durations,
            resolutions,
            frame_rates,
            crossfade,
            transition,
        )

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

    async def _encode_to_file(
        self,
        command: List[str],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        output_path = get_temporary_path(format)

        # `+faststart` moves the moov atom to the front so mp4/mov files start
        # playing before the whole file is downloaded. It's an ISO-BMFF-only
        # feature — webm/mkv/etc. ignore or reject it, so gate on container.
        if format in ("mp4", "mov", "m4v"):
            command = command + [ "-movflags", "+faststart" ]

        command = command + [ output_path ]

        process_task = asyncio.create_task(run_subprocess(
            command,
            stdin=None,
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
                    stdin=None,
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

    def _build_concat_filter(
        self,
        has_audios: List[bool],
        durations: List[float],
        resolutions: List[Tuple[int, int]],
        frame_rates: List[float],
        crossfade: Optional[float],
        transition: VideoConcatTransition,
    ) -> Tuple[str, str, Optional[str]]:
        """Build a filter_complex that produces a single [vout]/[aout] from the concat inputs.

        Without crossfade the ffmpeg `concat` filter joins video and audio
        end-to-end. `concat=n=N:v=1:a=1` demands every input carries an audio
        track, so silent clips are padded with `anullsrc` matched to the clip's
        own duration before the join.

        With crossfade, adjacent pairs are combined via `xfade` (video) and
        `acrossfade` (audio). xfade refuses inputs whose timebase, fps, or
        pixel format differ (mp4s from different encoders commonly ship with
        distinct AV timebases like 1/15360 vs 1/90000), so each input is
        first normalized to the max resolution and max fps across all inputs
        via `settb=AVTB, fps=<target>, scale=<w>:<h>, setsar=1, format=yuv420p`.
        Each xfade needs the offset at which the transition starts on the
        *cumulative* timeline of everything already chained — that offset is
        `sum(prior durations) - k*crossfade` after `k` prior transitions,
        since each crossfade shortens the total by exactly `crossfade`
        seconds. The audio side mirrors the same chain via `acrossfade`, and
        silent inputs get an anullsrc source so the audio chain never breaks.
        """
        filter_parts: List[str] = []
        count = len(has_audios)

        # Pad silent inputs with anullsrc matched to the clip's video duration
        # so downstream concat/xfade/acrossfade never see a missing audio
        # stream. Unbounded anullsrc would turn plain concat into an infinite
        # stream, so the length is always pinned to the video's duration.
        audio_labels: List[str] = []

        for index, has_audio in enumerate(has_audios):
            if has_audio:
                audio_labels.append(f"[{index}:a]")
            else:
                filter_parts.append(
                    f"anullsrc=channel_layout=stereo:sample_rate=48000:d={durations[index]}[a{index}sil]"
                )
                audio_labels.append(f"[a{index}sil]")

        if crossfade is None or crossfade <= 0:
            # ffmpeg's concat filter expects streams interleaved per input:
            # `[0:v][0:a][1:v][1:a]...` — not all-video-then-all-audio.
            streams = "".join(f"[{index}:v]{audio_labels[index]}" for index in range(count))
            filter_parts.append(f"{streams}concat=n={count}:v=1:a=1[vout][aout]")

            return ";".join(filter_parts), "[vout]", "[aout]"

        # Crossfade path: chain xfade/acrossfade across adjacent pairs.
        # After k prior transitions the running timeline holds
        # `sum(durations[:k+1]) - k*crossfade` seconds of content, so the next
        # xfade must start `crossfade` seconds before that — i.e. at
        # `sum(durations[:k+1]) - (k+1)*crossfade`.
        # Normalize every input to a shared timebase, fps, resolution, sar,
        # and pixel format before xfade — xfade fails hard on any mismatch,
        # and different-encoder mp4s routinely disagree on timebase even at
        # the same nominal fps.
        width  = max(width  for width, _  in resolutions)
        height = max(height for _, height in resolutions)
        fps    = max(frame_rates)

        video_labels: List[str] = []

        for index in range(count):
            normalized_label = f"[v{index}norm]"
            filter_parts.append(
                f"[{index}:v]settb=AVTB,fps={fps},"
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                f"setsar=1,format=yuv420p{normalized_label}"
            )
            video_labels.append(normalized_label)

        current_video_label = video_labels[0]
        current_audio_label = audio_labels[0]

        for pair_index in range(count - 1):
            next_index = pair_index + 1
            offset = sum(durations[: next_index]) - (pair_index + 1) * crossfade

            next_video_label = "[vout]" if next_index == count - 1 else f"[vx{pair_index}]"
            next_audio_label = "[aout]" if next_index == count - 1 else f"[ax{pair_index}]"

            filter_parts.append(
                f"{current_video_label}{video_labels[next_index]}"
                f"xfade=transition={transition.value.replace('-', '')}:duration={crossfade}:offset={offset}"
                f"{next_video_label}"
            )

            filter_parts.append(
                f"{current_audio_label}{audio_labels[next_index]}"
                f"acrossfade=d={crossfade}"
                f"{next_audio_label}"
            )

            current_video_label = next_video_label
            current_audio_label = next_audio_label

        return ";".join(filter_parts), "[vout]", "[aout]"

    def _build_overlay_filter(
        self,
        placements: List[OverlayFilterPlacement],
        audio_mode: VideoOverlayAudioMode,
        duration_mode: VideoOverlayDurationMode,
        base_pad_duration: Optional[float],
        base_has_audio: bool,
        overlay_has_audio: List[bool],
        base_matrix: str,
        overlay_matrices: List[str],
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
        if duration_mode == VideoOverlayDurationMode.LONGEST and base_pad_duration and base_pad_duration > 0:
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

            # Convert to yuva420p using the base's color matrix so RGB
            # overlays (PNG/JPEG) don't hard-code a 601 conversion and end up
            # miscolored on a 709-tagged HD base. `in_color_matrix` is also
            # spelled out per-overlay so swscale doesn't default un-tagged
            # YUV inputs to 601 and run an extra 601→709 conversion on
            # HD-but-un-tagged clipper/mixer outputs (swscale ignores
            # in_color_matrix for RGB, so a shared value is safe there).
            overlay_chain.append(
                f"scale=in_color_matrix={overlay_matrices[index]}:out_color_matrix={base_matrix}:out_range=tv"
            )
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

            if duration_mode == VideoOverlayDurationMode.SHORTEST:
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
        audio_mode: VideoOverlayAudioMode,
        duration_mode: VideoOverlayDurationMode,
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

        if audio_mode == VideoOverlayAudioMode.NONE:
            return None

        if audio_mode == VideoOverlayAudioMode.BASE:
            if not base_has_audio:
                return None

            return "0:a"

        overlay_indices = [ index for index in range(len(placements)) if overlay_has_audio[index] ]

        if audio_mode == VideoOverlayAudioMode.OVERLAY:
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

        # VideoOverlayAudioMode.MIX — include the base plus every overlay,
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
    def _resolve_overlay_filter_params(
        placement: VideoOverlayPlacement,
        codec: Optional[str],
        nb_frames: Optional[int],
    ) -> OverlayFilterPlacement:
        """Coerce a placement's field values into the concrete types the filter builder expects.

        Fields are `Union[int|float, str]` in the schema so callers can inline
        literal numbers or template references that resolved to strings; cast
        here so the overlay filter always receives numbers. `AUTO` for
        eof_action is folded here into `REPEAT` for stills (PNG/JPEG/etc.
        watermarks — codec is authoritative because nb_frames is N/A for
        PNG/JPEG) and `PASS` for animated content (including gif with
        `nb_frames > 1`) — ffmpeg has no `auto` value of its own.
        """
        anchor     = placement.anchor     if isinstance(placement.anchor, VideoOverlayAnchor)        else VideoOverlayAnchor(placement.anchor)
        eof_action = placement.eof_action if isinstance(placement.eof_action, VideoOverlayEofAction) else VideoOverlayEofAction(placement.eof_action)

        if eof_action == VideoOverlayEofAction.AUTO:
            # Both signals must agree on "still" — a still-image codec alone
            # isn't enough because MJPEG is also the codec for real video
            # (webcams, older cameras), and there `nb_frames > 1` correctly
            # says it's animated. PNG/JPEG stills report `nb_frames=None`,
            # which passes the second half of the check.
            is_still_image = is_still_image_codec(codec) and (nb_frames is None or nb_frames <= 1)
            eof_action = VideoOverlayEofAction.REPEAT if is_still_image else VideoOverlayEofAction.PASS

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

        if video and video.frame_rate is not None:
            options["-r"] = str(video.frame_rate)

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
    def _resolve_base_color_matrix(color_space: Optional[str], height: Optional[int]) -> str:
        if color_space in ("bt709", "smpte170m"):
            return color_space

        return "bt709" if height is not None and height >= 720 else "smpte170m"

    @staticmethod
    async def _alpha_input_options(path: str) -> List[str]:
        """Return `["-c:v", <decoder>]` when the file needs an alpha-preserving
        decoder forced ahead of its `-i`, or `[]` otherwise.

        VP8/VP9 side-data alpha is silently dropped by ffmpeg's native
        decoder; mixer inputs land in a filter graph, so alpha lost here can't
        be recovered downstream.
        """
        codec, alpha_mode = await probe_video(path, ("codec", "alpha_mode"))
        alpha_decoder = get_alpha_input_decoder(codec, alpha_mode)

        if alpha_decoder is not None:
            return [ "-c:v", alpha_decoder ]

        return []

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
