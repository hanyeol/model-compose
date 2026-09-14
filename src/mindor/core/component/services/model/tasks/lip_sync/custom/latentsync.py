from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
from mindor.dsl.schema.component import ModelComponentConfig, LatentSyncPreset
from mindor.dsl.schema.action import ModelActionConfig, LatentSyncLipSyncModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, get_mindor_install_root
from ......action.media import MediaInputPathResolver
from ....base import ComponentActionContext, ModelTaskService
from ..common import LipSyncTaskAction
import os, sys, tempfile, importlib, importlib.util

if TYPE_CHECKING:
    import torch

# Each release ships as its own HuggingFace repo containing the LatentSync
# UNet checkpoint (`latentsync_unet.pt`) plus a `whisper/tiny.pt` subdir.
_DEFAULT_UNET_CONFIGS: Dict[LatentSyncPreset, str] = {
    LatentSyncPreset.V15: "configs/unet/stage2.yaml",
    LatentSyncPreset.V16: "configs/unet/stage2_512.yaml",
}

class LatentSyncLipSyncTaskAction(LipSyncTaskAction):
    config: LatentSyncLipSyncModelActionConfig

    def __init__(
        self,
        config: LatentSyncLipSyncModelActionConfig,
        pipeline: Any,
        unet_config: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.unet_config: Any = unet_config
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        inference_steps  = await context.render_scalar(self.config.params.inference_steps, int)
        guidance_scale   = await context.render_scalar(self.config.params.guidance_scale, float)
        enable_deepcache = await context.render_scalar(self.config.params.enable_deepcache, bool)
        use_float16      = await context.render_scalar(self.config.params.use_float16, bool)

        params.update({
            "inference_steps":  inference_steps,
            "guidance_scale":   guidance_scale,
            "enable_deepcache": enable_deepcache,
            "use_float16":      use_float16,
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
        import torch
        from accelerate.utils import set_seed

        seed = params["seed"] if params["seed"] is not None else 1247
        set_seed(int(seed))

        weight_dtype = torch.float16 if params["use_float16"] else torch.float32

        # LatentSync's DeepCache helper wraps the UNet only for the call
        # duration; disable on exit so subsequent calls with a different
        # config don't inherit the cached branch.
        deepcache_helper = None
        if params["enable_deepcache"]:
            from DeepCache import DeepCacheSDHelper
            deepcache_helper = DeepCacheSDHelper(pipe=self.pipeline)
            deepcache_helper.set_params(cache_interval=3, cache_branch_id=0)
            deepcache_helper.enable()

        fd, output_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

        try:
            self.pipeline(
                video_path=video_path,
                audio_path=audio_path,
                video_out_path=output_path,
                num_frames=self.unet_config.data.num_frames,
                num_inference_steps=params["inference_steps"],
                guidance_scale=params["guidance_scale"],
                weight_dtype=weight_dtype,
                width=self.unet_config.data.resolution,
                height=self.unet_config.data.resolution,
                mask_image_path=self.unet_config.data.mask_image_path,
            )
        finally:
            if deepcache_helper is not None:
                deepcache_helper.disable()

        return VideoStreamResource(
            FileStreamResource(output_path, auto_delete=True),
            format="mp4",
        )

class LatentSyncLipSyncTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.unet_config: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch==2.5.1", "torchvision==0.20.1"),
            "diffusers==0.32.2",
            "transformers==4.48.0",
            "accelerate==0.26.1",
            "huggingface_hub==0.30.2",
            "decord==0.6.0",
            "einops==0.7.0",
            "omegaconf==2.3.0",
            "opencv-python==4.9.0.80",
            "librosa==0.10.1",
            "ffmpeg-python==0.2.0",
            "imageio==2.31.1",
            "imageio-ffmpeg==0.5.1",
            "face-alignment==1.4.1",
            "insightface==0.7.3",
            "onnxruntime",
            "DeepCache==0.1.1",
            "kornia==0.8.0",
            "numpy==1.26.4",
            "python_speech_features==0.6",
            "scenedetect==0.6.1",
            "lpips==0.1.4",
        ]

    async def _setup(self) -> None:
        # LatentSync's importable code lives under `latentsync/` at the repo
        # root, with `configs/` beside it holding the DDIM scheduler and per-
        # release unet yamls. Install `latentsync/` as a top-level package
        # (its own submodules use `from latentsync.xxx import ...`) and drop
        # `configs/` under a namespaced directory so it doesn't collide with
        # any other backend that installs its own top-level `configs/`.
        if importlib.util.find_spec("latentsync") is None:
            await install_package_from_github(
                "latentsync",
                "https://github.com/bytedance/LatentSync.git",
                revision="a229c3948406",
                subdirs=[ "latentsync", ("latentsync_configs", "configs") ],
            )

    async def _load_model(self) -> None:
        self.pipeline, self.unet_config, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.unet_config = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Any, Any, torch.device]:
        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        def _load() -> Tuple[Any, Any]:
            import torch
            import latentsync
            from omegaconf import OmegaConf
            from diffusers import AutoencoderKL, DDIMScheduler
            from latentsync.models.unet import UNet3DConditionModel
            from latentsync.pipelines.lipsync_pipeline import LipsyncPipeline
            from latentsync.whisper.audio2feature import Audio2Feature

            repo_root = Path(latentsync.__path__[0]).parent
            configs_root = get_mindor_install_root() / "latentsync_configs"

            # Symlink the namespaced configs into `<repo_root>/configs/` so
            # LatentSync's own relative `configs/...` references resolve
            # without requiring `os.chdir(repo_root)` on every inference call.
            configs_target = repo_root / "configs"

            if not configs_target.exists():
                os.symlink(configs_root, configs_target, target_is_directory=True)

            # LatentSync expects `checkpoints/latentsync_unet.pt` and
            # `checkpoints/whisper/tiny.pt` relative to the repo root; the
            # provisioned HF snapshot already lays those out inside `model_path`,
            # so mount the snapshot as `<repo_root>/checkpoints`.
            checkpoints_target = repo_root / "checkpoints"

            if not checkpoints_target.exists():
                os.symlink(model_path, checkpoints_target, target_is_directory=True)

            # Load the unet yaml by its canonical relative path so any
            # `${...}` interpolations resolve to sibling files as upstream expects.
            unet_config = OmegaConf.load(str(repo_root / _DEFAULT_UNET_CONFIGS[self.config.preset]))

            scheduler = DDIMScheduler.from_pretrained(str(repo_root / "configs"))

            audio_encoder = Audio2Feature(
                model_path=str(repo_root / "checkpoints" / "whisper" / "tiny.pt"),
                device=str(device),
                num_frames=unet_config.data.num_frames,
                audio_feat_length=unet_config.data.audio_feat_length,
            )

            vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=torch.float16)
            vae.config.scaling_factor = 0.18215
            vae.config.shift_factor = 0

            unet, _ = UNet3DConditionModel.from_pretrained(
                OmegaConf.to_container(unet_config.model),
                str(repo_root / "checkpoints" / "latentsync_unet.pt"),
                device="cpu",
            )
            unet = unet.to(dtype=torch.float16)

            pipeline = LipsyncPipeline(
                vae=vae,
                audio_encoder=audio_encoder,
                unet=unet,
                scheduler=scheduler,
            ).to(device)

            return pipeline, unet_config

        pipeline, unet_config = await self._run_in_executor(_load)

        return pipeline, unet_config, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await LatentSyncLipSyncTaskAction(action, self.pipeline, self.unet_config, self.device).run(context)
