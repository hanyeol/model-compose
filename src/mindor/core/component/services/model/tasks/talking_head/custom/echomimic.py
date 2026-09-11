from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, EchoMimicPreset
from mindor.dsl.schema.action import ModelActionConfig, EchoMimicTalkingHeadModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github
from ......action.media import MediaInputPathResolver
from ....base import ComponentActionContext, ModelTaskService
from ..common import TalkingHeadTaskAction
from PIL import Image as PILImage
import  importlib, importlib.util
import os, tempfile, asyncio

if TYPE_CHECKING:
    import torch

# Repo URL + pinned revision for each preset. The pin guards against upstream
# layout changes silently invalidating the `subdirs=[(pkg, "src")]` rename
# and import rewrite.
_ECHOMIMIC_REPOS: Dict[EchoMimicPreset, Tuple[str, str]] = {
    EchoMimicPreset.V1: (
        "https://github.com/antgroup/echomimic.git",
        "c32b3a557003",
    ),
    EchoMimicPreset.V2: (
        "https://github.com/antgroup/echomimic_v2.git",
        "38c86809efa0",
    ),
}

# Each preset gets its own top-level package so v1 and v2 checkpoints/code can
# coexist in the same site-packages without stepping on each other's `src/`.
_ECHOMIMIC_MODULES: Dict[EchoMimicPreset, str] = {
    EchoMimicPreset.V1: "echomimic",
    EchoMimicPreset.V2: "echomimic_v2",
}

class EchoMimicTalkingHeadTaskAction(TalkingHeadTaskAction):
    config: EchoMimicTalkingHeadModelActionConfig

    def __init__(
        self,
        config: EchoMimicTalkingHeadModelActionConfig,
        pipeline: Any,
        preset: EchoMimicPreset,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.preset: EchoMimicPreset = preset
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        pose            = await context.render_variable(self.config.params.pose)
        width           = await context.render_variable(self.config.params.width)
        height          = await context.render_variable(self.config.params.height)
        inference_steps = await context.render_variable(self.config.params.inference_steps)
        cfg_scale       = await context.render_variable(self.config.params.cfg_scale)
        context_frames  = await context.render_variable(self.config.params.context_frames)
        context_overlap = await context.render_variable(self.config.params.context_overlap)
        motion_sync     = await context.render_variable(self.config.params.motion_sync)
        sample_rate     = await context.render_variable(self.config.params.sample_rate)

        params.update({
            "pose":            pose,
            "width":           width,
            "height":          height,
            "inference_steps": inference_steps,
            "cfg_scale":       cfg_scale,
            "context_frames":  context_frames,
            "context_overlap": context_overlap,
            "motion_sync":     motion_sync,
            "sample_rate":     sample_rate,
        })

        return params

    async def _generate_batch(
        self,
        images: List[PILImage.Image],
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        audio_paths = [ await MediaInputPathResolver().resolve(audio) for audio in audios ]

        try:
            def _generate() -> List[VideoStreamResource]:
                results: List[VideoStreamResource] = []

                for image, (audio_path, _) in zip(images, audio_paths):
                    results.append(self._render(image, audio_path, params))

                return results

            return await self._run_in_executor(_generate)
        finally:
            for path, spooled in audio_paths:
                if spooled and path and os.path.exists(path):
                    os.remove(path)

    def _render(self, image: PILImage.Image, audio_path: str, params: Dict[str, Any]) -> VideoStreamResource:
        import torch

        width       = int(params["width"])
        height      = int(params["height"])
        fps         = int(params["fps"] or 25)
        sample_rate = int(params["sample_rate"])

        # Preset-specific extras: v2 needs a pose sequence tensor and forwards
        # it to the pipeline, while v1 works from an audio-derived face mask.
        extra_kwargs: Dict[str, Any] = {}
        if self.preset == EchoMimicPreset.V2:
            pose_dir = params.get("pose")
            if not pose_dir:
                raise RuntimeError("EchoMimic v2 requires a `pose` directory containing per-frame .npy files")
            extra_kwargs["poses_tensor"] = self._load_pose_tensor(pose_dir, width, height)
        else:
            extra_kwargs["face_mask_tensor"] = self._build_face_mask(image, width, height)

        generator = torch.Generator(device=self.device).manual_seed(int(params["seed"])) if params["seed"] is not None else None

        video_length = self._resolve_video_length(audio_path, sample_rate, fps)

        output = self.pipeline(
            ref_image=image,
            audio_path=audio_path,
            width=width,
            height=height,
            video_length=video_length,
            num_inference_steps=int(params["inference_steps"]),
            guidance_scale=float(params["cfg_scale"]),
            generator=generator,
            audio_sample_rate=sample_rate,
            context_frames=int(params["context_frames"]),
            fps=fps,
            context_overlap=int(params["context_overlap"]),
            **extra_kwargs,
        )

        module_name = _ECHOMIMIC_MODULES[self.preset]
        save_videos_grid = importlib.import_module(f"{module_name}.utils.util").save_videos_grid

        fd, video_only_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        save_videos_grid(output.videos, video_only_path, n_rows=1, fps=fps)

        fd, video_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        self._mux_audio(video_only_path, audio_path, video_path, fps)

        if os.path.exists(video_only_path):
            os.remove(video_only_path)

        return VideoStreamResource(
            FileStreamResource(video_path, auto_delete=True),
            format="mp4",
            attrs={ "fps": str(fps) },
        )

    def _build_face_mask(self, image: PILImage.Image, width: int, height: int) -> Any:
        import torch

        # v1's pipeline_echo_mimic expects a (B, 1, 1, H, W) mask; the reference
        # inference script builds this from an insightface bbox, but a full-frame
        # mask is a safe default when no bbox is supplied.
        # Match the face_locator's dtype (fp16 when the pipeline was loaded in
        # fp16) — its conv layers reject a mixed-precision input tensor.
        dtype = next(self.pipeline.face_locator.parameters()).dtype
        return torch.ones(1, 1, 1, height, width, dtype=dtype, device=self.device)

    def _load_pose_tensor(self, pose_dir: str, width: int, height: int) -> Any:
        from echomimic_v2.utils.dwpose_util import draw_pose_select_v2
        import numpy as np, torch, glob

        pose_files = sorted(glob.glob(os.path.join(pose_dir, "*.npy")))
        if not pose_files:
            raise RuntimeError(f"EchoMimic v2 pose directory has no .npy frames: {pose_dir}")

        pose_frames = []
        for path in pose_files:
            detected_pose = np.load(path, allow_pickle=True).item()
            frame = draw_pose_select_v2(detected_pose, height, width)
            pose_frames.append(frame)

        # Stack to (L, H, W, 3) -> (3, L, H, W) -> (1, 3, L, H, W). Match the
        # pose_encoder's dtype so v2's conv layers get consistent precision.
        arr = np.stack(pose_frames, axis=0).astype(np.float32) / 255.0
        dtype = next(self.pipeline.pose_encoder.parameters()).dtype
        return torch.from_numpy(arr).permute(3, 0, 1, 2).unsqueeze(0).to(self.device, dtype=dtype)

    def _resolve_video_length(self, audio_path: str, sample_rate: int, fps: int) -> int:
        import librosa

        duration = librosa.get_duration(path=audio_path)
        return max(1, int(round(duration * fps)))

    def _mux_audio(self, video_path: str, audio_path: str, output_path: str, fps: int) -> None:
        import subprocess

        subprocess.run(
            [
                "ffmpeg", "-y",
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


class EchoMimicTalkingHeadTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchvision", "torchaudio"),
            "diffusers==0.24.0",
            "transformers>=4.38.2,<4.49",
            "accelerate",
            "einops",
            "omegaconf",
            "opencv-python",
            "imageio",
            "imageio-ffmpeg",
            "librosa",
            "soundfile",
            "moviepy",
            "safetensors",
            "insightface",
            "onnxruntime",
            "mediapipe",
            "torchmetrics",
            "torchtyping",
            "ffmpeg-python==0.2.0",
            "av",
            "huggingface_hub>=0.20,<0.26",
        ]

    async def _setup(self) -> None:
        module_name = _ECHOMIMIC_MODULES[self.config.preset]

        if importlib.util.find_spec(module_name) is None:
            repo_url, revision = _ECHOMIMIC_REPOS[self.config.preset]

            await install_package_from_github(
                module_name,
                repo_url,
                revision=revision,
                subdirs=[ (module_name, "src"), "configs" ],
            )

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.pipeline = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None

    async def _load_pipeline(self) -> Any:
        # EchoMimic's inference script hand-wires each sub-model from checkpoint
        # paths listed in configs/prompts/{animation,infer}.yaml. Rather than
        # duplicate that logic here, delegate to the upstream builder that
        # replicates infer_audio2vid.py's pipeline assembly.
        from omegaconf import OmegaConf

        model_path = await self._provision_model(self.config.model, prefetch=True)

        module_name = _ECHOMIMIC_MODULES[self.config.preset]
        module = importlib.import_module(module_name)
        repo_root = os.path.dirname(os.path.dirname(module.__file__))

        prompt_name = "animation.yaml" if self.config.preset == EchoMimicPreset.V1 else "infer.yaml"
        config = OmegaConf.load(os.path.join(repo_root, "configs", "prompts", prompt_name))
        inference_config = OmegaConf.load(os.path.join(repo_root, "configs", "inference", "inference_v2.yaml"))

        # Rebind checkpoint paths under the user-provided directory. The upstream
        # yaml uses `./pretrained_weights/...` — we accept anything and just swap
        # the root prefix so ops can point at their own snapshot layout.
        for key, value in list(config.items()):
            if isinstance(value, str) and value.startswith("./pretrained_weights/"):
                config[key] = os.path.join(model_path, value[len("./pretrained_weights/"):])

        if self.config.preset == EchoMimicPreset.V1:
            pipeline_module = importlib.import_module(f"{module_name}.pipelines.pipeline_echo_mimic")
            pipeline_cls = pipeline_module.Audio2VideoPipeline
        else:
            pipeline_module = importlib.import_module(f"{module_name}.pipelines.pipeline_echomimicv2")
            pipeline_cls = pipeline_module.EchoMimicV2Pipeline

        def _load() -> Any:
            return self._build_pipeline(pipeline_cls, config, inference_config, module_name)

        return await asyncio.get_running_loop().run_in_executor(None, _load)

    def _build_pipeline(self, pipeline_cls: type, config: Any, inference_config: Any, module_name: str) -> Any:
        # Mirrors upstream infer_audio2vid.py (v1) / infer.py (v2) sub-model wiring.
        # Both variants share VAE + reference UNet + audio processor + DDIM scheduler;
        # they diverge on the denoising UNet class (Echo vs EMO) and the spatial
        # conditioner (FaceLocator[1ch] vs PoseEncoder[3ch]).
        from omegaconf import OmegaConf
        from diffusers import AutoencoderKL, DDIMScheduler
        import torch

        unet_2d_cls = importlib.import_module(f"{module_name}.models.unet_2d_condition").UNet2DConditionModel
        audio_loader = importlib.import_module(f"{module_name}.models.whisper.audio2feature").load_audio_model

        if self.config.preset == EchoMimicPreset.V1:
            denoising_unet_cls = importlib.import_module(f"{module_name}.models.unet_3d_echo").EchoUNet3DConditionModel
            conditioner_cls = importlib.import_module(f"{module_name}.models.face_locator").FaceLocator
            conditioner_channels = 1
            conditioner_ckpt_key = "face_locator_path"
        else:
            denoising_unet_cls = importlib.import_module(f"{module_name}.models.unet_3d_emo").EMOUNet3DConditionModel
            conditioner_cls = importlib.import_module(f"{module_name}.models.pose_encoder").PoseEncoder
            conditioner_channels = 3
            conditioner_ckpt_key = "pose_encoder_path"

        weight_dtype = torch.float16 if config.get("weight_dtype", "fp32") == "fp16" else torch.float32

        vae = AutoencoderKL.from_pretrained(config.pretrained_vae_path).to(self.device, dtype=weight_dtype)

        reference_unet = unet_2d_cls.from_pretrained(
            config.pretrained_base_model_path,
            subfolder="unet",
        ).to(dtype=weight_dtype, device=self.device)
        reference_unet.load_state_dict(torch.load(config.reference_unet_path, map_location="cpu"))

        denoising_unet = denoising_unet_cls.from_pretrained_2d(
            config.pretrained_base_model_path,
            config.motion_module_path,
            subfolder="unet",
            unet_additional_kwargs=inference_config.unet_additional_kwargs,
        ).to(dtype=weight_dtype, device=self.device)
        denoising_unet.load_state_dict(
            torch.load(config.denoising_unet_path, map_location="cpu"),
            strict=False,
        )

        # FaceLocator (v1) / PoseEncoder (v2) share the (320, conditioning_channels,
        # block_out_channels=(16, 32, 96, 256)) construction signature — only the
        # conditioning channel count differs.
        conditioner = conditioner_cls(
            320,
            conditioning_channels=conditioner_channels,
            block_out_channels=(16, 32, 96, 256),
        )
        conditioner.load_state_dict(torch.load(config[conditioner_ckpt_key]))
        conditioner.to(dtype=weight_dtype, device=self.device)

        audio_processor = audio_loader(model_path=config.audio_model_path, device=self.device)
        scheduler = DDIMScheduler(**OmegaConf.to_container(inference_config.noise_scheduler_kwargs))

        pipeline_params = {
            "vae":             vae,
            "reference_unet":  reference_unet,
            "denoising_unet":  denoising_unet,
            "audio_guider":    audio_processor,
            "scheduler":       scheduler,
        }

        if self.config.preset == EchoMimicPreset.V1:
            pipeline_params["face_locator"] = conditioner
        else:
            pipeline_params["pose_encoder"] = conditioner

        return pipeline_cls(**pipeline_params).to(self.device, dtype=weight_dtype)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await EchoMimicTalkingHeadTaskAction(
            action,
            self.pipeline,
            self.config.preset,
            self.device,
        ).run(context)
