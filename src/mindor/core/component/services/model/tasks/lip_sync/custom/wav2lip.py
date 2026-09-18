from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
from mindor.dsl.schema.component import ModelComponentConfig, Wav2LipPreset
from mindor.dsl.schema.action import ModelActionConfig, Wav2LipLipSyncModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.box import Box
from mindor.core.utils.soundfile.audio import load_pcm_samples
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, get_mindor_install_root
from mindor.core.foundation.streaming.url import download_to_file
from mindor.core.utils.ffmpeg.probe import probe_video
from mindor.core.utils.ffmpeg.executable import resolve_ffmpeg_executable
from ......action.media import MediaInputPathResolver
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import LipSyncTaskAction
import os, sys, tempfile, importlib, importlib.util, subprocess

if TYPE_CHECKING:
    import torch

_S3FD_URL: str = "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"

# Filenames match the basenames of the URLs served by the Easy-Wav2Lip release
# mirror, which is what `LocalModelConfig.apply_default_path` caches on disk
# when the DSL inflates the model config from a preset. Users who point `model`
# at a directory (rather than a specific file) hit this fallback lookup.
_CHECKPOINT_FILENAMES: Dict[Wav2LipPreset, str] = {
    Wav2LipPreset.WAV2LIP:     "Wav2Lip.pth",
    Wav2LipPreset.WAV2LIP_GAN: "Wav2Lip_GAN.pth",
}

class Wav2LipLipSyncTaskAction(LipSyncTaskAction):
    config: Wav2LipLipSyncModelActionConfig

    def __init__(
        self,
        config: Wav2LipLipSyncModelActionConfig,
        model: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.model: Any = model
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        resize_factor             = await context.render_scalar(self.config.params.resize_factor, int)
        frame_crop_box            = await context.render_scalar(self.config.params.frame_crop_box, "box")
        face_bounding_box         = await context.render_scalar(self.config.params.face_bounding_box, "box")
        face_bounding_box_padding = await context.render_scalar(self.config.params.face_bounding_box_padding, "box")
        face_detection_batch_size = await context.render_scalar(self.config.params.face_detection_batch_size, int)
        generator_batch_size      = await context.render_scalar(self.config.params.generator_batch_size, int)
        face_smoothing            = await context.render_scalar(self.config.params.face_smoothing, bool)
        static                    = await context.render_scalar(self.config.params.static, bool)

        params.update({
            "resize_factor":             resize_factor,
            "frame_crop_box":            frame_crop_box,
            "face_bounding_box":         face_bounding_box,
            "face_bounding_box_padding": face_bounding_box_padding,
            "face_detection_batch_size": face_detection_batch_size,
            "generator_batch_size":      generator_batch_size,
            "face_smoothing":            face_smoothing,
            "static":                    static,
        })

        return params

    async def _generate_batch(
        self,
        videos: List[MediaSource],
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        video_paths = [ await MediaInputPathResolver().resolve(video) for video in videos ]
        audio_paths = [ await MediaInputPathResolver().resolve(audio) for audio in audios ]

        try:
            source_fps = None

            if params["fps"] is None and video_paths and video_paths[0][0]:
                (frame_rate,) = await probe_video(video_paths[0][0], ("frame_rate",))
                source_fps = float(frame_rate) if frame_rate else None

            def _generate() -> List[VideoStreamResource]:
                results: List[VideoStreamResource] = []

                for (video_path, _), (audio_path, _) in zip(video_paths, audio_paths):
                    fps = float(params["fps"]) if params["fps"] is not None else (source_fps or 25.0)
                    results.append(self._render(video_path, audio_path, params, fps))

                return results

            return await self._run_in_executor(_generate)
        finally:
            for path, spooled in video_paths:
                if spooled and path and os.path.exists(path):
                    os.remove(path)

            for path, spooled in audio_paths:
                if spooled and path and os.path.exists(path):
                    os.remove(path)

    def _render(self, video_path: str, audio_path: str, params: Dict[str, Any], fps: float) -> VideoStreamResource:
        import numpy as np
        import cv2
        import torch

        # `_load_pipeline` already inserted the Wav2Lip package root into
        # sys.path when it loaded the generator, so `audio` (upstream's top-level
        # module, not the stdlib) resolves without any further setup here.
        import audio as w2l_audio  # justinjohn0306/Wav2Lip's audio.py

        # Wav2Lip's mel pipeline expects a 16 kHz mono float32 waveform, which
        # is exactly what `load_pcm_samples` returns — no need for upstream's
        # `audio.load_wav` (a thin librosa.core.load wrapper) or an ffmpeg
        # detour, since libsndfile handles the source containers we accept.
        waveform, _ = load_pcm_samples(audio_path, sample_rate=16000)

        mel_step_size = 16
        image_size = 96

        frames = self._read_frames(video_path, params["resize_factor"], params["frame_crop_box"], params["static"])
        mel = w2l_audio.melspectrogram(waveform)

        if np.isnan(mel.reshape(-1)).sum() > 0:
            raise RuntimeError("Mel spectrogram contains NaN; try a different TTS audio source.")

        mel_chunks: List[Any] = []
        mel_multiplier = 80.0 / fps
        index = 0

        while True:
            start_index = int(index * mel_multiplier)

            if start_index + mel_step_size > mel.shape[1]:
                mel_chunks.append(mel[:, mel.shape[1] - mel_step_size:])
                break

            mel_chunks.append(mel[:, start_index:start_index + mel_step_size])
            index += 1

        # Wav2Lip loops the source frames if audio outlasts them.
        if len(frames) >= len(mel_chunks):
            frames = frames[:len(mel_chunks)]
        else:
            repeats = (len(mel_chunks) + len(frames) - 1) // len(frames)
            frames = (frames * repeats)[:len(mel_chunks)]

        if params["face_bounding_box"] is None:
            face_crops = self._detect_face_crops(frames, params)
        else:
            face_crops = self._crop_fixed_box(frames, params["face_bounding_box"])

        fd, silent_video_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

        try:
            writer = None
            batch_size = params["generator_batch_size"]

            with torch.no_grad():
                for batch_start in range(0, len(mel_chunks), batch_size):
                    mel_batch = mel_chunks[batch_start:batch_start + batch_size]
                    face_crop_batch = face_crops[batch_start:batch_start + batch_size]

                    img_batch_np = np.asarray([ face_crop for face_crop, _ in face_crop_batch ])
                    mel_batch_np = np.asarray(mel_batch)

                    img_masked = img_batch_np.copy()
                    img_masked[:, image_size // 2:] = 0
                    img_batch_np = np.concatenate((img_masked, img_batch_np), axis=3) / 255.0
                    mel_batch_np = np.reshape(mel_batch_np, [mel_batch_np.shape[0], mel_batch_np.shape[1], mel_batch_np.shape[2], 1])

                    img_batch_t = torch.FloatTensor(np.transpose(img_batch_np, (0, 3, 1, 2))).to(self.device)
                    mel_batch_t = torch.FloatTensor(np.transpose(mel_batch_np, (0, 3, 1, 2))).to(self.device)

                    predictions = self.model(mel_batch_t, img_batch_t)
                    predictions = predictions.cpu().numpy().transpose(0, 2, 3, 1) * 255.0

                    for prediction, (_, coords), source_index in zip(predictions, face_crop_batch, range(batch_start, batch_start + len(predictions))):
                        x1, y1, x2, y2 = coords
                        frame = frames[source_index].copy()
                        resized = cv2.resize(prediction.astype(np.uint8), (x2 - x1, y2 - y1))
                        frame[y1:y2, x1:x2] = resized

                        if writer is None:
                            height, width = frame.shape[:2]
                            writer = cv2.VideoWriter(silent_video_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

                        writer.write(frame)

            if writer is not None:
                writer.release()

            fd, muxed_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)

            self._mux_audio(silent_video_path, audio_path, muxed_path)
        finally:
            if os.path.exists(silent_video_path):
                os.remove(silent_video_path)

        return VideoStreamResource(
            FileStreamResource(muxed_path, auto_delete=True),
            format="mp4",
            attrs={ "fps": str(fps) },
        )

    def _detect_face_crops(self, frames: List[Any], params: Dict[str, Any]) -> List[Tuple[Any, Tuple[int, int, int, int]]]:
        from face_detection.detection.sfd.sfd_detector import SFDDetector
        import face_detection  # from justinjohn0306/Wav2Lip
        import numpy as np
        import cv2

        # The vendored `face_detection` is a fork of the pre-MPS `face-alignment`
        # release; its `FaceAlignment.__init__` only understands `"cpu"` and
        # `"cuda*"`, so on Apple Silicon we run the detector on CPU regardless
        # of where the generator lives. The generator batch on MPS still gets
        # a 2-4x speedup over pure CPU.
        detector_device = "cpu" if self.device.type in [ "mps" ] else str(self.device)
        detector = face_detection.FaceAlignment(
            face_detection.LandmarksType._2D,
            flip_input=False,
            device=detector_device,
        )

        # `FaceAlignment.__init__` constructs an `SFDDetector` but never calls
        # its classmethod `load_model`, leaving `SFDDetector.face_detector`
        # unassigned — every downstream `detect_from_batch` call would then
        # blow up with `AttributeError`. Populate it explicitly so upstream's
        # own dead-code path becomes usable.
        SFDDetector.load_model(detector_device)

        try:
            predictions: List[Optional[Any]] = []
            batch_size = params["face_detection_batch_size"]
            image_size = 96

            while True:
                try:
                    for start in range(0, len(frames), batch_size):
                        predictions.extend(detector.get_detections_for_batch(np.array(frames[start:start + batch_size])))
                    break
                except RuntimeError:
                    if batch_size == 1:
                        raise
                    batch_size //= 2

            # `Box` slots may be `None`; padding treats a missing side as zero.
            padx1, pady1, padx2, pady2 = (element or 0 for element in params["face_bounding_box_padding"])
            results: List[Tuple[int, int, int, int]] = []

            for prediction, frame in zip(predictions, frames):
                if prediction is None:
                    raise ValueError("Face not detected in one of the frames; provide a fixed 'face_bounding_box' or a video with visible faces.")

                x1, y1, x2, y2 = prediction
                results.append((
                    max(0, x1 - padx1),
                    max(0, y1 - pady1),
                    min(frame.shape[1], x2 + padx2),
                    min(frame.shape[0], y2 + pady2),
                ))

            if params["face_smoothing"]:
                results = self._smooth_boxes(results)

            face_crops: List[Tuple[Any, Tuple[int, int, int, int]]] = []

            for frame, (x1, y1, x2, y2) in zip(frames, results):
                face_crop = frame[y1:y2, x1:x2]
                face_crop = cv2.resize(face_crop, (image_size, image_size))
                face_crops.append((face_crop, (x1, y1, x2, y2)))

            return face_crops
        finally:
            del detector

    @staticmethod
    def _read_frames(
        path: str,
        resize_factor: int,
        crop_box: Optional[Box],
        static: bool
    ) -> List[Any]:
        import cv2

        capture = cv2.VideoCapture(path)
        frames: List[Any] = []

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                # Apply resize/crop per frame so the intermediate full-resolution
                # list never sits in memory alongside the processed one.
                if resize_factor > 1:
                    frame = cv2.resize(frame, (frame.shape[1] // resize_factor, frame.shape[0] // resize_factor))

                if crop_box is not None:
                    frame = Wav2LipLipSyncTaskAction._apply_crop(frame, crop_box)

                frames.append(frame)

                if static:
                    break
        finally:
            capture.release()

        if not frames:
            raise ValueError(f"No frames could be read from {path}")

        return frames

    @staticmethod
    def _apply_crop(frame: Any, crop_box: Box) -> Any:
        left, top, right, bottom = crop_box
        height, width = frame.shape[:2]

        # `None` on any edge means "keep the original frame edge on that side".
        x1 = 0      if left   is None else left
        y1 = 0      if top    is None else top
        x2 = width  if right  is None else right
        y2 = height if bottom is None else bottom

        return frame[y1:y2, x1:x2]

    @staticmethod
    def _crop_fixed_box(frames: List[Any], box: Box) -> List[Tuple[Any, Tuple[int, int, int, int]]]:
        import cv2

        if any(element is None for element in box):
            raise ValueError(f"'face_bounding_box' requires all four edges; got {box!r}")

        image_size = 96
        x1, y1, x2, y2 = box
        face_crops: List[Tuple[Any, Tuple[int, int, int, int]]] = []

        for frame in frames:
            face_crop = cv2.resize(frame[y1:y2, x1:x2], (image_size, image_size))
            face_crops.append((face_crop, (x1, y1, x2, y2)))

        return face_crops

    @staticmethod
    def _smooth_boxes(boxes: List[Tuple[int, int, int, int]]) -> List[Tuple[int, int, int, int]]:
        import numpy as np

        window_size = 5
        array = np.array(boxes, dtype=np.float32)

        for index in range(len(array)):
            if index + window_size > len(array):
                window = array[len(array) - window_size:]
            else:
                window = array[index:index + window_size]
            array[index] = np.mean(window, axis=0)

        return [ (int(row[0]), int(row[1]), int(row[2]), int(row[3])) for row in array ]

    @staticmethod
    def _mux_audio(video_path: str, audio_path: str, output_path: str) -> None:
        subprocess.run(
            [
                resolve_ffmpeg_executable(), "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                output_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

class Wav2LipLipSyncTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchvision", "torchaudio"),
            "numpy",
            "librosa",
            "numba",
            "opencv-python",
            "soundfile",
            "tqdm",
        ]

    async def _setup(self) -> None:
        if importlib.util.find_spec("wav2lip") is None:
            # Wav2Lip's code sits at the repo root (audio.py, models/, face_detection/,
            # hparams.py) rather than under a src/ subdir, so mount the whole
            # tree as a `wav2lip/` package. Internal imports stay top-level
            # (`from models import Wav2Lip`), so `_load_pipeline` adds
            # `wav2lip.__path__[0]` to sys.path before importing them.
            # justinjohn0306's fork keeps Wav2Lip runnable on modern torch/librosa;
            # the original Rudrabha/Wav2Lip pins are too stale to install alongside
            # our stack.
            await install_package_from_github(
                "wav2lip",
                "https://github.com/justinjohn0306/Wav2Lip.git",
                revision="ebe4687d9ecc",
                subdirs=[ ("wav2lip", ".") ],
            )

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Any, torch.device]:
        import wav2lip  # the installed package
        import torch

        repo_root = wav2lip.__path__[0]

        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        from models import Wav2Lip

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        await self._provision_s3fd_checkpoint()

        def _load() -> Any:
            if os.path.isdir(model_path):
                checkpoint_path = os.path.join(model_path, _CHECKPOINT_FILENAMES[self.config.preset])
            else:
                checkpoint_path = model_path

            checkpoint = torch.load(checkpoint_path, map_location="cpu")
            state_dict = checkpoint["state_dict"] if "state_dict" in checkpoint else checkpoint
            state_dict = { key.replace("module.", ""): value for key, value in state_dict.items() }

            model = Wav2Lip()
            model.load_state_dict(state_dict)
            model = model.to(device).eval()

            return model

        model = await self._run_in_executor(_load)

        return model, device

    @staticmethod
    async def _provision_s3fd_checkpoint() -> None:
        # `SFDDetector.load_model` skips its own `load_url` fetch when this
        # exact path already exists, so placing the file here is the only way
        # to bypass upstream's flaky download without patching its code.
        target = get_mindor_install_root() / "wav2lip" / "face_detection" / "detection" / "sfd" / "s3fd.pth"

        if not target.exists():
            await download_to_file(_S3FD_URL, target)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Wav2LipLipSyncTaskAction(action, self.model, self.device).run(context)
