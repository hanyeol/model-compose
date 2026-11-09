from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from collections.abc import AsyncIterable, AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, LightAsdActiveSpeakerDetectionModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, LightAsdActiveSpeakerDetectionModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.utils.time import format_timecode
from mindor.core.logger import logging
from ..common import ActiveSpeakerDetectionTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from PIL import Image as PILImage
import sys

if TYPE_CHECKING:
    import numpy as np
    import torch

# Visual frontend expects 112x112 grayscale faces at 25fps. Columbia_test.py
# resizes to 224x224 then takes the central 112x112 (mouth-centered); matching
# that pipeline is what keeps the pretrained weights predictive.
_FACE_RESIZE: int = 224
_FACE_CROP: int = 112

# Audio frontend expects 100Hz MFCC frames at 16kHz mono — python_speech_features
# default (winstep=0.010). 25fps video * 4 = 100Hz audio frames per video frame.
_AUDIO_SAMPLE_RATE: int = 16000
_AUDIO_FRAMES_PER_VIDEO_FRAME: int = 4

# Columbia_test.py scores each track at these window durations (seconds) and
# averages the per-frame logits across runs; the multi-window ensemble smooths
# out boundary effects and lifts AUC vs. a single-pass score.
_SCORING_WINDOW_DURATIONS: Tuple[int, ...] = (1, 2, 3, 4, 5, 6)

class LightAsdModel:
    """CPU-safe stand-in for upstream `ASD`.

    Holds the same two sub-modules the forward path uses (`ASD_Model` under
    `.model`, `lossAV` under `.lossAV`) and exposes just the methods the task
    action calls. Avoids inheriting from upstream's `ASD` to keep the
    `.cuda()`-in-`__init__` behavior out of the way; the checkpoint's
    `model.*` / `lossAV.*` keys land on the right places because this class
    uses matching attribute names.
    """
    def __init__(self, model: Any, lossAV: Any):
        self.model = model
        self.lossAV = lossAV

    def load_state_dict(self, state_dict: Dict[str, Any]) -> None:
        """Port of upstream `ASD.loadParameters`: strip `module.` prefix, verify shape.

        The checkpoint stores keys like `module.model.visualEncoder.block1...`
        — the `module.` prefix comes from upstream's DataParallel wrapping. We
        strip it, verify shape, and copy in place; any key that doesn't line
        up is logged and skipped (same behavior as upstream).
        """
        self_state = self.state_dict()

        for original_name, param in state_dict.items():
            name = original_name

            if name not in self_state:
                name = name.replace("module.", "")

                if name not in self_state:
                    logging.debug(f"Light-ASD checkpoint key skipped (not in model): {original_name}")
                    continue

            if self_state[name].size() != param.size():
                logging.warning(f"Light-ASD checkpoint key size mismatch: {original_name} (model={self_state[name].size()}, loaded={param.size()})")
                continue

            self_state[name].copy_(param)

    def state_dict(self) -> Dict[str, Any]:
        state_dict: Dict[str, Any] = {}

        for key, value in self.model.state_dict().items():
            state_dict[f"model.{key}"] = value

        for key, value in self.lossAV.state_dict().items():
            state_dict[f"lossAV.{key}"] = value

        return state_dict

    def eval(self) -> None:
        self.model.eval()
        self.lossAV.eval()

    def to(self, device: torch.device) -> None:
        self.model.to(device)
        self.lossAV.to(device)

class LightAsdActiveSpeakerDetectionTaskAction(ActiveSpeakerDetectionTaskAction):
    config: LightAsdActiveSpeakerDetectionModelActionConfig

    def __init__(
        self,
        config: LightAsdActiveSpeakerDetectionModelActionConfig,
        model: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.model: Any = model
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        face_crop_scale = await context.render_scalar(self.config.params.face_crop_scale, float)

        if face_crop_scale < 0.0:
            raise ValueError(f"'face_crop_scale' must be >= 0.0, got {face_crop_scale}")

        params.update({ "face_crop_scale": face_crop_scale })

        return params

    async def _detect_batch(
        self,
        frames: List[ImageArrayValue],
        timestamps: Optional[List[ArrayValue]],
        offsets: List[float],
        audios: List[MediaSource],
        tracks: List[ArrayValue],
        frame_rate: float,
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]]:
        results: List[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]] = []

        for index in range(len(frames)):
            results.append(await self._detect(
                frames[index],
                timestamps[index] if timestamps is not None else None,
                offsets[index],
                audios[index],
                tracks[index],
                frame_rate,
                streaming,
                params,
            ))

        return results

    async def _detect(
        self,
        frames: ImageArrayValue,
        timestamps: Optional[ArrayValue],
        offset: float,
        audio: MediaSource,
        tracks: ArrayValue,
        frame_rate: float,
        streaming: bool,
        params: Dict[str, Any],
    ) -> Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]:
        # `frames`/`tracks` may arrive as ImageArrayValue/ArrayValue (with
        # `.collect()`) or as a raw StreamChunkIterator (no `.collect()`), so
        # iterate uniformly instead.
        frames = [ frame async for frame in frames ]
        tracks = [ track async for track in tracks ]

        frame_count = len(frames)
        frame_rate = float(frame_rate) if frame_rate else 25.0
        frame_period = 1.0 / frame_rate

        if timestamps is None:
            timestamps = [ offset + index * frame_period for index in range(frame_count) ]
        else:
            timestamps = [ float(timestamp) for timestamp in timestamps ]

        tracks = self._group_detections_by_track(tracks, frame_count)

        # Decode only the audio span these frames actually cover; without this
        # a call that scores a 6-second clip from a 1-hour source would still
        # pay for decoding + MFCC on the full hour.
        audio_start_time = timestamps[0]
        audio_duration = (timestamps[-1] + frame_period) - audio_start_time
        audio_mfcc = await self._load_audio_mfcc(audio, audio_start_time, audio_duration)

        def _score_tracks() -> List[Dict[str, Any]]:
            # One output entry per track_id, with segments / frame_scores
            # accumulated across every contiguous chunk of that track. A chunk
            # is a maximal run of consecutive frames face-tracking kept
            # unbroken; gaps face-tracking couldn't interpolate (across its
            # `merge_gap`) mark genuine track breaks, so we score each chunk
            # independently and never try to carry context across the gap.
            scored_tracks: Dict[int, Dict[str, Any]] = {}

            for track_id in sorted(tracks.keys()):
                for chunk in self._split_track_by_gaps(tracks[track_id]):
                    scores, start_frame = self._score_track_chunk(
                        frames,
                        timestamps,
                        chunk,
                        audio_mfcc,
                        frame_rate,
                        params["face_crop_scale"]
                    )

                    if scores.size == 0:
                        continue

                    segments, frame_scores = self._segments_from_scores(
                        scores,
                        start_frame,
                        timestamps,
                        frame_period,
                        params
                    )

                    scored_track = scored_tracks.setdefault(track_id, {
                        "track_id": track_id,
                        "segments": [],
                        "frame_scores": []
                    })

                    scored_track["segments"].extend(segments)

                    if frame_scores is not None:
                        scored_track["frame_scores"].extend(frame_scores)

            return [ scored_tracks[track_id] for track_id in sorted(scored_tracks.keys()) ]

        scored_tracks = await self._run_in_executor(_score_tracks)

        if streaming:
            return self._stream_result(scored_tracks, frame_count, params)

        return self._build_result(scored_tracks, frame_count, params)

    async def _load_audio_mfcc(self, audio: MediaSource, start_time: float, duration: float) -> np.ndarray:
        """Load the `start_time`..`start_time+duration` span of `audio` as a
        16kHz mono waveform and return 100Hz MFCC frames.

        Shape: `(T, 13)` indexed against the loaded span (so index 0 corresponds
        to `start_time`, not the start of `audio`). python_speech_features uses
        25ms windows at 10ms hop by default — exactly what Light-ASD trained on.
        """
        import numpy as np
        import python_speech_features

        buffer = await AudioBufferStreamer(
            audio,
            channel="mono",
            sample_rate=_AUDIO_SAMPLE_RATE,
            start_time=start_time,
            duration=duration
        ).collect()

        # python_speech_features expects int16 for its default `preemph` filter
        # to produce the same scale upstream used; our resampled waveform is
        # float32 in [-1, 1]. Scale to int16 range so the MFCC statistics line
        # up with the pretrained weights.
        waveform = (np.clip(buffer.waveform, -1.0, 1.0) * 32767.0).astype(np.int16)

        # python_speech_features returns float64; cast once here so downstream
        # `torch.from_numpy` produces a float32 tensor that matches the model
        # weights (float32).
        return python_speech_features.mfcc(
            waveform,
            samplerate=_AUDIO_SAMPLE_RATE,
            numcep=13,
            winlen=0.025,
            winstep=0.010,
        ).astype(np.float32)

    def _score_track_chunk(
        self,
        frames: List[PILImage.Image],
        timestamps: List[float],
        chunk: List[Tuple[int, Tuple[int, int, int, int]]],
        audio_mfcc: np.ndarray,
        frame_rate: float,
        face_crop_scale: float,
    ) -> Tuple[np.ndarray, int]:
        """Run Light-ASD on one contiguous chunk of a face track.

        Crops each frame to 112x112 grayscale, scores the chunk once per entry
        in `_SCORING_WINDOW_DURATIONS` (each duration partitions the chunk
        into `ceil(length / duration)` sub-windows), and averages the
        per-frame logits across runs. Returns `(scores, start_frame)`:
        `scores` is a float32 array of length equal to the number of frames
        Light-ASD actually scored (may be shorter than the chunk span when
        the audio tail is missing); `start_frame` indexes into `timestamps`.
        """
        import numpy as np
        import torch

        start_frame = chunk[0][0]
        span_length = len(chunk)

        visual_feature = np.stack([
            self._crop_face(frames[frame_number], bounding_box, face_crop_scale)
            for frame_number, bounding_box in chunk
        ], axis=0).astype(np.float32)

        # Align audio to the track's time window: convert the first frame
        # timestamp to an MFCC frame index (100Hz) and slice. `audio_mfcc` is
        # indexed relative to `timestamps[0]` because `_load_audio_mfcc`
        # already trimmed to the frames' span, so subtract that origin before
        # scaling. Clip to the available audio length rather than erroring so
        # a track that extends past the end of the audio still scores — the
        # trailing frames just get whatever audio is actually there.
        audio_start = int(round((timestamps[start_frame] - timestamps[0]) * 100.0))
        audio_end = audio_start + span_length * _AUDIO_FRAMES_PER_VIDEO_FRAME
        audio_start = max(0, min(audio_start, audio_mfcc.shape[0]))
        audio_end = max(audio_start, min(audio_end, audio_mfcc.shape[0]))
        audio_slice = audio_mfcc[audio_start:audio_end]

        # Visual/audio input lengths must satisfy `audio_frames == 4 *
        # video_frames` for the backend's additive fusion to line up. Clip
        # visual to whatever the audio actually covers; drop the trailing
        # video frames that have no audio.
        audio_available_video_frames = audio_slice.shape[0] // _AUDIO_FRAMES_PER_VIDEO_FRAME

        if audio_available_video_frames <= 0:
            return np.zeros(0, dtype=np.float32), start_frame

        visual_feature = visual_feature[:audio_available_video_frames]
        audio_slice = audio_slice[:audio_available_video_frames * _AUDIO_FRAMES_PER_VIDEO_FRAME]

        # Partition the chunk into `duration`-second windows and score each
        # window independently per Columbia_test.py; the final per-frame score
        # is the mean across all duration passes. `batch_size` is the number
        # of sub-windows the chunk breaks into at this duration, matching
        # upstream's `math.ceil(length / duration)`.
        per_duration_scores: List[np.ndarray] = []

        with torch.no_grad():
            for duration in _SCORING_WINDOW_DURATIONS:
                visual_window_size = max(1, int(round(duration * frame_rate)))
                audio_window_size = visual_window_size * _AUDIO_FRAMES_PER_VIDEO_FRAME
                batch_size = (audio_available_video_frames + visual_window_size - 1) // visual_window_size
                scores_for_duration: List[np.ndarray] = []

                for index in range(batch_size):
                    visual_batch = visual_feature[index * visual_window_size:(index + 1) * visual_window_size]
                    audio_batch = audio_slice[index * audio_window_size:(index + 1) * audio_window_size]
                    audio_tensor = torch.from_numpy(audio_batch).unsqueeze(0).to(self.device)
                    visual_tensor = torch.from_numpy(visual_batch).unsqueeze(0).to(self.device)
                    audio_embed = self.model.model.forward_audio_frontend(audio_tensor)
                    visual_embed = self.model.model.forward_visual_frontend(visual_tensor)
                    fused = self.model.model.forward_audio_visual_backend(audio_embed, visual_embed)
                    scores_for_duration.append(np.asarray(self.model.lossAV.forward(fused, labels=None), dtype=np.float32))

                per_duration_scores.append(np.concatenate(scores_for_duration))

        return np.mean(np.stack(per_duration_scores, axis=0), axis=0).astype(np.float32), start_frame

    def _segments_from_scores(
        self,
        scores: np.ndarray,
        start_frame: int,
        timestamps: List[float],
        frame_period: float,
        params: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
        """Smooth per-frame logits and threshold them into timecoded segments.

        Returns `(segments, frame_scores)` where `frame_scores` is `None`
        unless `return_frame_scores` is on.
        """
        smoothing_window = max(1, int(round(params["smoothing_window"] / frame_period)))
        scores = self._smooth_scores(scores, smoothing_window)
        frame_scores: Optional[List[Dict[str, Any]]] = None

        if params["return_frame_scores"]:
            frame_scores = [
                {
                    "timestamp": format_timecode(timestamps[start_frame + index]),
                    "score": float(scores[index])
                }
                for index in range(scores.size)
            ]

        segments = self._build_segments(
            scores,
            start_frame,
            timestamps,
            params["threshold"],
            params["min_segment_duration"],
            params["merge_gap"],
            frame_period,
        )

        return segments, frame_scores

    def _build_result(
        self,
        scored_tracks: List[Dict[str, Any]],
        frame_count: int,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if params["return_speakers"]:
            speakers: List[Dict[str, Any]] = []

            for track in scored_tracks:
                speaker: Dict[str, Any] = {
                    "track_id": track["track_id"],
                    "segments": track["segments"],
                }

                if params["return_frame_scores"]:
                    speaker["frame_scores"] = track["frame_scores"]

                speakers.append(speaker)

            result["speakers"] = speakers

        if params["return_timeline"]:
            timeline: List[Dict[str, Any]] = []

            for track in scored_tracks:
                for segment in track["segments"]:
                    timeline.append({
                        "start_time": segment["start_time"],
                        "end_time":   segment["end_time"],
                        "track_id":   track["track_id"],
                        "score":      segment["score"],
                    })

            timeline.sort(key=lambda entry: entry["start_time"])
            result["active_timeline"] = timeline

        if params["return_metadata"]:
            result["frame_count"] = frame_count
            result["track_count"] = len(scored_tracks)

        return result

    async def _stream_result(
        self,
        scored_tracks: List[Dict[str, Any]],
        frame_count: int,
        params: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Fake streaming by re-emitting the collected segments.

        Light-ASD needs the full audio+track window for stable scores — there
        is no incremental mode. `streaming: true` is supported for API
        consistency with other tasks (speaker-diarization does the same).
        """
        if params["return_speakers"]:
            for track in scored_tracks:
                for segment in track["segments"]:
                    yield { "type": "segment", "track_id": track["track_id"], **segment }

        if params["return_metadata"]:
            yield { "type": "metadata", "frame_count": frame_count, "track_count": len(scored_tracks) }

    @staticmethod
    def _group_detections_by_track(detections: Any, frame_count: int) -> Dict[int, Dict[int, Tuple[int, int, int, int]]]:
        """Flatten a face-tracking `detections` list into per-track frame maps.

        Input is the list emitted by face-tracking with `return_detections: true`:
        `[{number, timestamp, faces: [{track_id, bounding_box: {x, y, width, height}, ...}, ...]}]`.
        Output: `{track_id: {frame_number: (x1, y1, x2, y2), ...}, ...}`.
        Frame numbers outside `[0, frame_count)` are dropped so a stale
        `detections` input can't index past the available frames.
        """
        tracks: Dict[int, Dict[int, Tuple[int, int, int, int]]] = {}

        if not isinstance(detections, list):
            return tracks

        for detection in detections:
            frame_number = detection.get("number")

            if frame_number is None or not (0 <= frame_number < frame_count):
                continue

            for face in detection.get("faces", []) or []:
                track_id = face.get("track_id")
                bounding_box = face.get("bounding_box")

                if track_id is None or bounding_box is None:
                    continue

                x = int(bounding_box["x"])
                y = int(bounding_box["y"])
                width = int(bounding_box["width"])
                height = int(bounding_box["height"])

                tracks.setdefault(track_id, {})[frame_number] = (x, y, x + width, y + height)

        return tracks

    @staticmethod
    def _split_track_by_gaps(
        track: Dict[int, Tuple[int, int, int, int]],
    ) -> List[List[Tuple[int, Tuple[int, int, int, int]]]]:
        """Split one track's frame map into maximal runs of consecutive frames.

        face-tracking already fills short detection gaps inside `merge_gap`
        via its own bbox interpolation, so any remaining gap in `track` means
        face-tracking considered the track broken there. Scoring across such
        a break would feed the model a crop sequence that jumps across a
        genuine identity/pose discontinuity, so we treat each contiguous run
        as an independent scoring unit instead.
        """
        chunks: List[List[Tuple[int, Tuple[int, int, int, int]]]] = []
        chunk: List[Tuple[int, Tuple[int, int, int, int]]] = []

        for frame_number in sorted(track.keys()):
            if chunk and frame_number != chunk[-1][0] + 1:
                chunks.append(chunk)
                chunk = []
            chunk.append((frame_number, track[frame_number]))

        if chunk:
            chunks.append(chunk)

        return chunks

    @staticmethod
    def _crop_face(frame: PILImage.Image, bounding_box: Tuple[int, int, int, int], scale: float) -> np.ndarray:
        """Crop a 112x112 grayscale face from `frame` for Light-ASD's visual frontend.

        Matches upstream Columbia_test.py's two-step: expand the bbox by `scale`
        (left/right/top by `s * scale`, bottom by `2s * scale` where `s = max(w, h) / 2`),
        resize to 224, then take the central 112x112 (mouth-centered). Returns a
        `(112, 112)` uint8-value float32 array matching upstream's `cv2.cvtColor`
        + `cv2.resize` output; the frontend normalizes to `(x/255 - 0.4161) / 0.1688`
        internally. Out-of-frame pixels are padded with 110 to mirror upstream.
        """
        import numpy as np

        x1, y1, x2, y2 = bounding_box
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        half_size = max(x2 - x1, y2 - y1) // 2

        if half_size <= 0:
            # Degenerate box — return a blank frame rather than erroring; the
            # model gets a non-speaking signal and the segment never fires.
            return np.zeros((_FACE_CROP, _FACE_CROP), dtype=np.float32)

        # Columbia_test.py expansion: symmetric left/right/top by `s * scale`,
        # asymmetric bottom by `2s * scale` to pull chin and mouth into frame.
        margin = int(round(half_size * scale))
        crop_x1 = center_x - half_size - margin
        crop_y1 = center_y - half_size
        crop_x2 = center_x + half_size + margin
        crop_y2 = center_y + half_size + 2 * margin

        # Preserve out-of-frame regions as upstream does (constant 110 fill) so
        # the resized 224x224 stays geometrically aligned even near frame edges.
        canvas = PILImage.new("L", (crop_x2 - crop_x1, crop_y2 - crop_y1), 110)
        src_x1 = max(0, crop_x1)
        src_y1 = max(0, crop_y1)
        src_x2 = min(frame.width, crop_x2)
        src_y2 = min(frame.height, crop_y2)

        if src_x2 > src_x1 and src_y2 > src_y1:
            region = frame.crop((src_x1, src_y1, src_x2, src_y2)).convert("L")
            canvas.paste(region, (src_x1 - crop_x1, src_y1 - crop_y1))

        face = canvas.resize((_FACE_RESIZE, _FACE_RESIZE), PILImage.BILINEAR)

        # Take the central _FACE_CROP x _FACE_CROP (mouth-centered). Upstream
        # expresses this as `face[112-56:112+56, 112-56:112+56]` on a 224 frame.
        offset = (_FACE_RESIZE - _FACE_CROP) // 2
        center_crop = face.crop((offset, offset, offset + _FACE_CROP, offset + _FACE_CROP))

        return np.asarray(center_crop, dtype=np.float32)

    @staticmethod
    def _smooth_scores(scores: np.ndarray, window: int) -> np.ndarray:
        """Centered moving-average smoothing of per-frame scores.

        Smoothing suppresses single-frame flickers in the logit stream so the
        threshold crossing produces segments at the plateau boundaries rather
        than at every noisy peak. Set `window <= 1` to disable (passes `scores`
        through untouched).
        """
        import numpy as np

        if window <= 1 or scores.size == 0:
            return scores

        half = window // 2
        padded = np.pad(scores, (half, half), mode="edge")
        kernel = np.ones(window, dtype=np.float32) / float(window)

        return np.convolve(padded, kernel, mode="valid")[:scores.size]

    @staticmethod
    def _build_segments(
        scores: np.ndarray,
        start_frame: int,
        timestamps: List[float],
        threshold: float,
        min_segment_duration: float,
        merge_gap: float,
        frame_period: float,
    ) -> List[Dict[str, Any]]:
        """Threshold smoothed logits into on/off runs, then collapse into segments.

        Each run of `scores[i] > threshold` becomes one segment. Adjacent
        segments separated by less than `merge_gap` seconds are merged (brief
        dips below threshold during a continuous speaking turn); segments
        shorter than `min_segment_duration` are dropped afterwards so the
        duration filter is applied to the merged runs rather than every
        micro-run.
        """
        segments: List[Dict[str, Any]] = []
        run_start: Optional[int] = None
        run_scores: List[float] = []

        for offset, score in enumerate(scores):
            is_speaking = score > threshold

            if is_speaking:
                if run_start is None:
                    run_start = offset

                run_scores.append(float(score))

                continue

            if run_start is not None:
                segments.append({
                    "start_time": timestamps[start_frame + run_start],
                    "end_time":   timestamps[start_frame + offset - 1] + frame_period,
                    "score":      max(run_scores),
                })
                run_start = None
                run_scores = []

                continue

        if run_start is not None:
            segments.append({
                "start_time": timestamps[start_frame + run_start],
                "end_time":   timestamps[start_frame + len(scores) - 1] + frame_period,
                "score":      max(run_scores),
            })

        if merge_gap > 0.0 and segments:
            merged_segments: List[Dict[str, Any]] = [ dict(segments[0]) ]

            for segment in segments[1:]:
                if segment["start_time"] - merged_segments[-1]["end_time"] <= merge_gap:
                    merged_segments[-1]["end_time"] = segment["end_time"]
                    merged_segments[-1]["score"] = max(merged_segments[-1]["score"], segment["score"])
                else:
                    merged_segments.append(dict(segment))

            segments = merged_segments

        segments = [ segment for segment in segments if (segment["end_time"] - segment["start_time"]) >= min_segment_duration ]

        return [
            {
                "start_time": format_timecode(segment["start_time"]),
                "end_time":   format_timecode(segment["end_time"]),
                "duration":   format_timecode(segment["end_time"] - segment["start_time"]),
                "score":      segment["score"],
            }
            for segment in segments
        ]

class LightAsdActiveSpeakerDetectionTaskDriver(ModelTaskDriver):
    config: LightAsdActiveSpeakerDetectionModelComponentConfig

    def __init__(self, id: str, config: LightAsdActiveSpeakerDetectionModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch", "torchaudio"),
            "numpy",
            "scipy",
            "python_speech_features",
        ]

    async def _setup(self) -> None:
        if not is_package_installed("lightasd"):
            # Light-ASD's code sits at the repo root (ASD.py, loss.py, model/)
            # rather than under a src/ subdir, so mount the whole tree as a
            # `lightasd/` package. Internal imports stay top-level
            # (`from loss import lossAV`, `from model.Model import ASD_Model`),
            # so `_load_pretrained_model` adds `lightasd.__path__[0]` to
            # sys.path before importing them.
            await install_package_from_github(
                "lightasd",
                "https://github.com/Junhua-Liao/Light-ASD.git",
                revision="ed38c232de5e",
                subdirs=[ ("lightasd", ".") ],
            )

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[Any, torch.device]:
        import lightasd  # the installed package
        import torch

        repo_root = lightasd.__path__[0]

        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        from model.Model import ASD_Model
        from loss import lossAV

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        def _load() -> Any:
            logging.debug(f"Loading Light-ASD checkpoint: {model_path}")

            # Upstream's `ASD` wrapper calls `.cuda()` in __init__, which fails
            # on CPU/MPS and makes device selection impossible. Rebuild the
            # equivalent on CPU — `ASD_Model` + `lossAV` is what the forward
            # path actually needs — then let the caller move it onto `device`.
            model = LightAsdModel(ASD_Model(), lossAV())
            model.load_state_dict(torch.load(model_path, map_location="cpu"))
            model.eval()
            model.to(device)

            return model

        model = await self._run_in_executor(_load)

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await LightAsdActiveSpeakerDetectionTaskAction(action, self.model, self.device).run(context)
