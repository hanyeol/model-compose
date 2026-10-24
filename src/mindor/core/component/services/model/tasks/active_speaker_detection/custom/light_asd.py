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
import numpy as np
import sys

if TYPE_CHECKING:
    import torch

# Visual frontend expects 112x112 grayscale faces at 25fps. Columbia_test.py
# resizes to 224x224 then takes the central 112x112 (mouth-centered); matching
# that pipeline is what keeps the pretrained weights predictive.
_FACE_RESIZE: int = 224
_FACE_CROP: int = 112

# Audio frontend expects 100Hz MFCC frames at 16kHz mono — python_speech_features
# default (winstep=0.010). 25fps video * 4 = 100Hz audio frames per video frame.
_AUDIO_SR: int = 16000
_AUDIO_FRAMES_PER_VIDEO_FRAME: int = 4

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

    async def _detect_batch(
        self,
        frames: List[ImageArrayValue],
        timestamps: Optional[List[ArrayValue]],
        offsets: List[float],
        audios: List[MediaSource],
        tracks: List[Any],
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
        tracks: Any,
        frame_rate: float,
        streaming: bool,
        params: Dict[str, Any],
    ) -> Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]:
        frames = await frames.collect()
        frame_count = len(frames)
        frame_period = 1.0 / float(frame_rate) if frame_rate else 1.0 / 25.0

        if timestamps is None:
            timestamps = [ offset + index * frame_period for index in range(frame_count) ]
        else:
            timestamps = [ float(timestamp) for timestamp in timestamps ]

        tracks = self._group_detections_by_track(tracks, frame_count)
        audio_mfcc = await self._load_audio_mfcc(audio)

        def _score_tracks() -> List[Dict[str, Any]]:
            # One output entry per track_id, with segments / frame_scores
            # accumulated across every contiguous chunk of that track. A chunk
            # is a maximal run of consecutive frames face-tracking kept
            # unbroken; gaps face-tracking couldn't interpolate (across its
            # `merge_gap`) mark genuine track breaks, so we score each chunk
            # independently and never try to carry context across the gap.
            results: Dict[int, Dict[str, Any]] = {}

            for track_id in sorted(tracks.keys()):
                for chunk in self._split_track_by_gaps(tracks[track_id]):
                    scores, start_frame = self._score_track_chunk(frames, timestamps, chunk, audio_mfcc)

                    if scores.size == 0:
                        continue

                    segments, frame_scores = self._segments_from_scores(
                        scores,
                        start_frame,
                        timestamps,
                        frame_period,
                        params
                    )

                    result = results.setdefault(track_id, { "track_id": track_id, "segments": [], "frame_scores": [] })
                    result["segments"].extend(segments)
                    result["frame_scores"].extend(frame_scores)

            return [ results[track_id] for track_id in sorted(results.keys()) ]

        results = await self._run_in_executor(_score_tracks)

        if streaming:
            return self._stream_result(results, frame_count, params)

        return self._build_result(results, frame_count, params)

    async def _load_audio_mfcc(self, audio: MediaSource) -> np.ndarray:
        """Load `audio` as 16kHz mono waveform and return 100Hz MFCC frames.

        Shape: `(T, 13)`. python_speech_features uses 25ms windows at 10ms hop
        by default — exactly what Light-ASD trained on.
        """
        import python_speech_features

        buffer = await AudioBufferStreamer(audio, channel="mono", sample_rate=_AUDIO_SR).collect()
        waveform = buffer.waveform

        # python_speech_features expects int16 for its default `preemph` filter
        # to produce the same scale upstream used; our resampled waveform is
        # float32 in [-1, 1]. Scale to int16 range so the MFCC statistics line
        # up with the pretrained weights.
        waveform_int16 = (np.clip(waveform, -1.0, 1.0) * 32767.0).astype(np.int16)

        return python_speech_features.mfcc(
            waveform_int16,
            samplerate=_AUDIO_SR,
            numcep=13,
            winlen=0.025,
            winstep=0.010,
        )

    def _score_track_chunk(
        self,
        frames: List[PILImage.Image],
        timestamps: List[float],
        chunk: List[Tuple[int, Tuple[int, int, int, int]]],
        audio_mfcc: np.ndarray,
    ) -> Tuple[np.ndarray, int]:
        """Run Light-ASD on one contiguous chunk of a face track.

        Crops each frame to 112x112 grayscale, slices the matching audio
        window, and runs Light-ASD forward. Returns `(scores, start_frame)`:
        `scores` is a float32 array of length equal to the number of frames
        Light-ASD actually scored (may be shorter than the chunk span when
        the audio tail is missing); `start_frame` indexes into `timestamps`.
        """
        import torch

        start_frame = chunk[0][0]
        span_length = len(chunk)

        visual_feature = np.stack([
            self._crop_face(frames[frame_number], bounding_box)
            for frame_number, bounding_box in chunk
        ], axis=0).astype(np.float32)

        # Align audio to the track's time window: convert the first frame
        # timestamp to an MFCC frame index (100Hz) and slice. Clip to the
        # available audio length rather than erroring so a track that extends
        # past the end of the audio still scores — the trailing frames just
        # get whatever audio is actually there.
        audio_start = int(round(timestamps[start_frame] * 100.0))
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

        with torch.no_grad():
            audio_tensor = torch.from_numpy(audio_slice).unsqueeze(0).to(self.device)
            visual_tensor = torch.from_numpy(visual_feature).unsqueeze(0).to(self.device)
            audio_embed = self.model.model.forward_audio_frontend(audio_tensor)
            visual_embed = self.model.model.forward_visual_frontend(visual_tensor)
            fused = self.model.model.forward_audio_visual_backend(audio_embed, visual_embed)
            scores = self.model.lossAV.forward(fused, labels=None)  # numpy array of logits

        return np.asarray(scores, dtype=np.float32), start_frame

    def _segments_from_scores(
        self,
        scores: np.ndarray,
        start_frame: int,
        timestamps: List[float],
        frame_period: float,
        params: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Smooth per-frame logits and threshold them into timecoded segments.

        Returns `(segments, frame_scores)` where `frame_scores` is empty
        unless `return_frame_scores` is on.
        """
        smoothing_window = max(1, int(round(params["smoothing_window"] / frame_period)))
        scores = self._smooth_scores(scores, smoothing_window)

        frame_scores: List[Dict[str, Any]] = []

        if params["return_frame_scores"]:
            frame_scores = [
                { "timestamp": format_timecode(timestamps[start_frame + index]), "score": float(scores[index]) }
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
        results: List[Dict[str, Any]],
        frame_count: int,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        output: Dict[str, Any] = {}

        if params["return_speakers"]:
            speakers: List[Dict[str, Any]] = []

            for track in results:
                speaker: Dict[str, Any] = {
                    "track_id": track["track_id"],
                    "segments": track["segments"],
                }

                if params["return_frame_scores"]:
                    speaker["frame_scores"] = track["frame_scores"]

                speakers.append(speaker)

            output["speakers"] = speakers

        if params["return_timeline"]:
            timeline: List[Dict[str, Any]] = []

            for track in results:
                for segment in track["segments"]:
                    timeline.append({
                        "start_time": segment["start_time"],
                        "end_time":   segment["end_time"],
                        "track_id":   track["track_id"],
                        "score":      segment["score"],
                    })

            timeline.sort(key=lambda entry: entry["start_time"])
            output["active_timeline"] = timeline

        if params["return_metadata"]:
            output["frame_count"] = frame_count
            output["track_count"] = len(results)

        return output

    async def _stream_result(
        self,
        results: List[Dict[str, Any]],
        frame_count: int,
        params: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Fake streaming by re-emitting the collected segments.

        Light-ASD needs the full audio+track window for stable scores — there
        is no incremental mode. `streaming: true` is supported for API
        consistency with other tasks (speaker-diarization does the same).
        """
        if params["return_speakers"]:
            for track in results:
                for segment in track["segments"]:
                    yield { "type": "segment", "track_id": track["track_id"], **segment }

        if params["return_metadata"]:
            yield { "type": "metadata", "frame_count": frame_count, "track_count": len(results) }

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
    def _crop_face(frame: PILImage.Image, bounding_box: Tuple[int, int, int, int]) -> np.ndarray:
        """Crop a 112x112 grayscale face from `frame` for Light-ASD's visual frontend.

        Matches upstream Columbia_test.py's two-step: expand the bbox to a square,
        resize to 224, then take the central 112x112 (mouth-centered). Returns a
        `(112, 112)` uint8-value float32 array matching upstream's `cv2.cvtColor`
        + `cv2.resize` output; the frontend normalizes to `(x/255 - 0.4161) / 0.1688`
        internally.
        """
        x1, y1, x2, y2 = bounding_box
        # Expand to a square around the bbox center to avoid distortion when
        # resizing to 224x224. Face aspect ratios drift from frame to frame in
        # face-tracking output; a square crop keeps the model's view stable.
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        half_size = max(x2 - x1, y2 - y1) // 2

        if half_size <= 0:
            # Degenerate box — return a blank frame rather than erroring; the
            # model gets a non-speaking signal and the segment never fires.
            return np.zeros((_FACE_CROP, _FACE_CROP), dtype=np.float32)

        crop_x1 = max(0, center_x - half_size)
        crop_y1 = max(0, center_y - half_size)
        crop_x2 = min(frame.width, center_x + half_size)
        crop_y2 = min(frame.height, center_y + half_size)

        face = frame.crop((crop_x1, crop_y1, crop_x2, crop_y2)).convert("L").resize((_FACE_RESIZE, _FACE_RESIZE), PILImage.BILINEAR)

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
            merged: List[Dict[str, Any]] = [ dict(segments[0]) ]

            for segment in segments[1:]:
                if segment["start_time"] - merged[-1]["end_time"] <= merge_gap:
                    merged[-1]["end_time"] = segment["end_time"]
                    merged[-1]["score"] = max(merged[-1]["score"], segment["score"])
                else:
                    merged.append(dict(segment))

            segments = merged

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
