from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
from mindor.dsl.schema.component import ModelComponentConfig, MuseTalkPreset
from mindor.dsl.schema.action import ModelActionConfig, MuseTalkLipSyncModelActionConfig, MuseTalkParsingMode
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github
from mindor.core.foundation.streaming.url import download_to_file
from mindor.core.utils.ffmpeg.executable import resolve_ffmpeg_executable
from ......action.media import MediaInputPathResolver
from ....base import ComponentActionContext, ModelTaskService
from ..common import LipSyncTaskAction
import os, sys, tempfile, subprocess, importlib, importlib.util

if TYPE_CHECKING:
    import torch

# Additional checkpoints that MuseTalk's inference pipeline reads relative to
# its own `models/` directory. The main MuseTalk UNet is handled by the
# generic `self.config.model` provisioning; everything below is fetched from
# canonical HuggingFace repos and placed under `<musetalk_pkg>/models/<subdir>`
# so upstream's `os.path.join('./models', ...)` paths resolve unmodified.
_EXTRA_HF_SNAPSHOTS: Dict[str, str] = {
    "sd-vae":            "stabilityai/sd-vae-ft-mse",
    "whisper":           "openai/whisper-tiny",
    "dwpose":            "yzd-v/DWPose",
    "face-parse-bisent": "vivym/face-parsing-bisenet",
}

# torchvision's ResNet18 weights that face-parse-bisent's BiSeNet loads by
# absolute filename; the URL is CDN-hosted and stable.
_RESNET18_URL = "https://download.pytorch.org/models/resnet18-5c106cde.pth"

# On disk, upstream expects UNet weights at models/musetalk/ (v1) or
# models/musetalkV15/ (v1.5); the DSL `allow_patterns` already scopes the
# snapshot to the right subdir, so we symlink it in at load time.
_UNET_SUBDIR: Dict[MuseTalkPreset, str] = {
    MuseTalkPreset.V1:  "musetalk",
    MuseTalkPreset.V15: "musetalkV15",
}

class MuseTalkLipSyncTaskAction(LipSyncTaskAction):
    config: MuseTalkLipSyncModelActionConfig

    def __init__(
        self,
        config: MuseTalkLipSyncModelActionConfig,
        pipeline: Any,
        preset: MuseTalkPreset,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.preset: MuseTalkPreset = preset
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        bbox_shift                 = await context.render_scalar(self.config.params.bbox_shift, int)
        extra_margin               = await context.render_scalar(self.config.params.extra_margin, int)
        parsing_mode               = await context.render_variable(self.config.params.parsing_mode)
        left_cheek_width           = await context.render_scalar(self.config.params.left_cheek_width, int)
        right_cheek_width          = await context.render_scalar(self.config.params.right_cheek_width, int)
        audio_padding_length_left  = await context.render_scalar(self.config.params.audio_padding_length_left, int)
        audio_padding_length_right = await context.render_scalar(self.config.params.audio_padding_length_right, int)
        generator_batch_size       = await context.render_scalar(self.config.params.generator_batch_size, int)
        use_float16                = await context.render_scalar(self.config.params.use_float16, bool)

        try:
            parsing_mode = MuseTalkParsingMode(parsing_mode)
        except ValueError:
            raise ValueError(f"Invalid parsing_mode: {parsing_mode}")

        params.update({
            "bbox_shift":                 bbox_shift,
            "extra_margin":               extra_margin,
            "parsing_mode":               parsing_mode,
            "left_cheek_width":           left_cheek_width,
            "right_cheek_width":          right_cheek_width,
            "audio_padding_length_left":  audio_padding_length_left,
            "audio_padding_length_right": audio_padding_length_right,
            "generator_batch_size":       generator_batch_size,
            "use_float16":                use_float16,
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
            def _generate() -> List[VideoStreamResource]:
                results: List[VideoStreamResource] = []

                for (video_path, _), (audio_path, _) in zip(video_paths, audio_paths):
                    results.append(self._render(video_path, audio_path, params))

                return results

            return await self._run_in_executor(_generate)
        finally:
            for path, spooled in video_paths:
                if spooled and path and os.path.exists(path):
                    os.remove(path)

            for path, spooled in audio_paths:
                if spooled and path and os.path.exists(path):
                    os.remove(path)

    def _render(self, video_path: str, audio_path: str, params: Dict[str, Any]) -> VideoStreamResource:
        from musetalk.utils.utils import datagen, get_video_fps
        from musetalk.utils.preprocessing import get_landmark_and_bbox, coord_placeholder
        from musetalk.utils.blending import get_image
        from tqdm import tqdm
        import numpy as np
        import cv2
        import copy
        import torch

        # v1.5 ignores the DSL-provided `bbox_shift` and always applies
        # `extra_margin` to the detected chin instead.
        if self.preset == MuseTalkPreset.V15:
            bbox_shift = 0
        else:
            bbox_shift = params["bbox_shift"]

        weight_dtype = torch.float16 if params["use_float16"] else torch.float32
        timesteps = torch.tensor([0], device=self.device)

        fps = get_video_fps(video_path)
        frames = self._read_video_frames(video_path)

        # Cache detected face bboxes + frames on disk so re-running with the
        # same video reuses the S3FD result rather than paying detection twice.
        coord_list, frame_list = get_landmark_and_bbox(frames, bbox_shift)

        # Extract whisper features up front; `get_whisper_chunk` slices them
        # into per-frame windows aligned with `fps`.
        audio_processor = self.pipeline["audio_processor"]
        whisper = self.pipeline["whisper"]
        whisper_input_features, librosa_length = audio_processor.get_audio_feature(audio_path)
        whisper_chunks = audio_processor.get_whisper_chunk(
            whisper_input_features,
            self.device,
            weight_dtype,
            whisper,
            librosa_length,
            fps=fps,
            audio_padding_length_left=params["audio_padding_length_left"],
            audio_padding_length_right=params["audio_padding_length_right"],
        )

        vae = self.pipeline["vae"]
        unet = self.pipeline["unet"]
        pe = self.pipeline["pe"]
        face_parsing = self.pipeline["face_parsing"]

        input_latent_list: List[Any] = []

        for bbox, frame in zip(coord_list, frame_list):
            if bbox == coord_placeholder:
                continue

            x1, y1, x2, y2 = bbox

            if self.preset == MuseTalkPreset.V15:
                y2 = min(y2 + params["extra_margin"], frame.shape[0])

            crop_frame = frame[y1:y2, x1:x2]
            crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
            input_latent_list.append(vae.get_latents_for_unet(crop_frame))

        if not input_latent_list:
            raise RuntimeError("Face not detected in any frame; provide a video with a visible face.")

        # Ping-pong the source frames so audio outlasting the video loops
        # smoothly (video → reversed video → video → ...) rather than snapping.
        frame_list_cycle = frame_list + frame_list[::-1]
        coord_list_cycle = coord_list + coord_list[::-1]
        input_latent_list_cycle = input_latent_list + input_latent_list[::-1]

        batch_size = params["generator_batch_size"]
        gen = datagen(
            whisper_chunks=whisper_chunks,
            vae_encode_latents=input_latent_list_cycle,
            batch_size=batch_size,
            delay_frame=0,
            device=self.device,
        )

        res_frame_list: List[Any] = []
        total = int(np.ceil(len(whisper_chunks) / batch_size))

        with torch.no_grad():
            for whisper_batch, latent_batch in tqdm(gen, total=total, desc="MuseTalk generator"):
                audio_feature_batch = pe(whisper_batch)
                latent_batch = latent_batch.to(dtype=unet.model.dtype)
                pred_latents = unet.model(
                    latent_batch,
                    timesteps,
                    encoder_hidden_states=audio_feature_batch,
                ).sample

                for res_frame in vae.decode_latents(pred_latents):
                    res_frame_list.append(res_frame)

        # Blend each generated mouth back into its source frame and stream the
        # composite frames straight into a silent mp4 (no PNG dumps on disk).
        fd, silent_video_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

        writer: Optional[Any] = None

        try:
            for index, res_frame in enumerate(res_frame_list):
                bbox = coord_list_cycle[index % len(coord_list_cycle)]
                ori_frame = copy.deepcopy(frame_list_cycle[index % len(frame_list_cycle)])
                x1, y1, x2, y2 = bbox

                if self.preset == MuseTalkPreset.V15:
                    y2 = min(y2 + params["extra_margin"], ori_frame.shape[0])

                try:
                    res_frame = cv2.resize(res_frame.astype(np.uint8), (x2 - x1, y2 - y1))
                except Exception:
                    continue

                if self.preset == MuseTalkPreset.V15:
                    combine_frame = get_image(ori_frame, res_frame, [x1, y1, x2, y2], mode=params["parsing_mode"].value, fp=face_parsing)
                else:
                    combine_frame = get_image(ori_frame, res_frame, [x1, y1, x2, y2], fp=face_parsing)

                if writer is None:
                    height, width = combine_frame.shape[:2]
                    writer = cv2.VideoWriter(silent_video_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

                writer.write(combine_frame)

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

    @staticmethod
    def _read_video_frames(path: str) -> List[Any]:
        import cv2

        capture = cv2.VideoCapture(path)
        frames: List[Any] = []
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                frames.append(frame)
        finally:
            capture.release()

        if not frames:
            raise ValueError(f"No frames could be read from {path}")

        return frames

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

class MuseTalkLipSyncTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Dict[str, Any]] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchvision", "torchaudio"),
            "diffusers==0.30.2",
            "transformers==4.39.2",
            "accelerate==0.28.0",
            "huggingface_hub==0.30.2",
            "numpy==1.23.5",
            "opencv-python==4.9.0.80",
            "librosa==0.11.0",
            "einops==0.8.1",
            "soundfile==0.12.1",
            "omegaconf",
            "ffmpeg-python",
            "imageio",
            "imageio-ffmpeg",
        ]

    async def _setup(self) -> None:
        # MuseTalk keeps its importable package under `musetalk/` at the repo
        # root alongside `scripts/`, `configs/`, and `models/`. We only need
        # the `musetalk/` Python package — the CLI wrapper in `scripts/` and
        # the sample yaml in `configs/` are avoided so they don't collide
        # with other backends that install their own top-level `scripts` /
        # `configs` directories into site-packages.
        if importlib.util.find_spec("musetalk") is None:
            await install_package_from_github(
                "musetalk",
                "https://github.com/TMElyralab/MuseTalk.git",
                revision="0a89dec45a01",
                subdirs=[ "musetalk" ],
            )

    async def _load_model(self) -> None:
        self.pipeline, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Dict[str, Any], torch.device]:
        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        await self._provision_extra_checkpoints()

        def _load() -> Dict[str, Any]:
            import musetalk  # our installed package
            from transformers import WhisperModel
            from musetalk.utils.utils import load_all_model
            from musetalk.utils.audio_processor import AudioProcessor
            from musetalk.utils.face_parsing import FaceParsing
            import torch

            models_dir = Path(musetalk.__path__[0]).parent / "models"

            # Symlink the user's MuseTalk snapshot (containing musetalk/ or
            # musetalkV15/) into the expected layout so upstream's relative
            # `./models/musetalk*/` paths resolve.
            snapshot_target = models_dir / _UNET_SUBDIR[self.config.preset]
            snapshot_source = Path(model_path) / _UNET_SUBDIR[self.config.preset]

            if not snapshot_target.exists():
                snapshot_target.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(snapshot_source, snapshot_target, target_is_directory=True)

            unet_config_path = str(snapshot_target / "musetalk.json")
            unet_weight_path = str(snapshot_target / ("unet.pth" if self.config.preset == MuseTalkPreset.V15 else "pytorch_model.bin"))
            whisper_path = str(models_dir / "whisper")

            vae, unet, pe = load_all_model(
                unet_model_path=unet_weight_path,
                vae_type="sd-vae",
                unet_config=unet_config_path,
                device=str(device),
            )
            whisper = WhisperModel.from_pretrained(whisper_path).to(device).eval()
            audio_processor = AudioProcessor(feature_extractor_path=whisper_path)

            # v15 uses cheek-widened parsing; v1 skips FaceParsing entirely
            # (the classic blending path in `musetalk.utils.blending.get_image`
            # doesn't call FaceParsing).
            face_parsing = None

            if self.config.preset == MuseTalkPreset.V15:
                face_parsing = FaceParsing(
                    left_cheek_width=90,
                    right_cheek_width=90,
                )

            return {
                "vae":             vae,
                "unet":            unet,
                "pe":              pe,
                "whisper":         whisper,
                "audio_processor": audio_processor,
                "face_parsing":    face_parsing,
            }

        pipeline = await self._run_in_executor(_load)

        return pipeline, device

    async def _provision_extra_checkpoints(self) -> None:
        # Materialise the four side snapshots (VAE, whisper, dwpose,
        # face-parse-bisent) plus the torchvision ResNet18 weights inside the
        # installed MuseTalk package's `models/` directory. Mirrors Sonic's
        # pattern of feeding upstream code its own expected relative paths.
        import musetalk  # requires _setup to have run first

        models_dir = Path(musetalk.__path__[0]).parent / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        def _download_checkpoints() -> None:
            from huggingface_hub import snapshot_download

            for subdir, repo_id in _EXTRA_HF_SNAPSHOTS.items():
                model_dir = models_dir / subdir

                if model_dir.exists() and any(model_dir.iterdir()):
                    continue

                snapshot_download(repo_id, local_dir=str(model_dir))

        await self._run_in_executor(_download_checkpoints)

        # Torchvision's ResNet18 backbone that BiSeNet auto-loads by filename.
        # Placed at both the face-parse-bisent subdir and the torch hub cache
        # to cover either lookup path.
        model_dir = models_dir / "face-parse-bisent" / "resnet18-5c106cde.pth"

        if not model_dir.exists():
            await download_to_file(_RESNET18_URL, model_dir)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await MuseTalkLipSyncTaskAction(action, self.pipeline, self.config.preset, self.device).run(context)
