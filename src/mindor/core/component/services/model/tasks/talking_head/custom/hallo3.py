from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, Hallo3TalkingHeadModelActionConfig
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
import os, sys, tempfile, shutil, importlib.util, asyncio

if TYPE_CHECKING:
    import torch

class Hallo3TalkingHeadTaskAction(TalkingHeadTaskAction):
    config: Hallo3TalkingHeadModelActionConfig

    def __init__(
        self,
        config: Hallo3TalkingHeadModelActionConfig,
        generator: Any,
        repo_root: str,
        device: torch.device,
    ):
        super().__init__(config)

        self.generator: Any = generator
        self.repo_root: str = repo_root
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        prompt               = await context.render_text(self.config.params.prompt) if self.config.params.prompt is not None else None
        negative_prompt      = await context.render_text(self.config.params.negative_prompt) if self.config.params.negative_prompt is not None else None
        inference_steps      = await context.render_variable(self.config.params.inference_steps)
        guidance_scale       = await context.render_variable(self.config.params.guidance_scale)
        audio_guidance_scale = await context.render_variable(self.config.params.audio_guidance_scale)
        resolution           = await context.render_variable(self.config.params.resolution)
        num_frames           = await context.render_variable(self.config.params.num_frames)
        shift                = await context.render_variable(self.config.params.shift)
        long_video           = await context.render_variable(self.config.params.long_video)

        params.update({
            "prompt":               prompt,
            "negative_prompt":      negative_prompt,
            "inference_steps":      inference_steps,
            "guidance_scale":       guidance_scale,
            "audio_guidance_scale": audio_guidance_scale,
            "resolution":           resolution,
            "num_frames":           num_frames,
            "shift":                shift,
            "long_video":           long_video,
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
        # Hallo3's VideoGenerator resolves config-relative paths (configs/, pretrained_models/)
        # from the current working directory, so we cd into the installed repo root
        # for the duration of the call and restore afterwards.
        last_cwd = os.getcwd()
        os.chdir(self.repo_root)

        try:
            result_path = self.generator.generate_video(image, audio_path, params.get("prompt") or "")
        finally:
            os.chdir(last_cwd)

        fd, video_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        shutil.move(result_path, video_path)

        return VideoStreamResource(
            FileStreamResource(video_path, auto_delete=True),
            format="mp4",
            attrs={ "fps": str(params["fps"] or 25) },
        )

class Hallo3TalkingHeadTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.generator: Optional[Any] = None
        self.repo_root: Optional[str] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchvision", "torchaudio"),
            "diffusers",
            "transformers",
            "accelerate",
            "einops",
            "omegaconf",
            "SwissArmyTransformer",
            "sentencepiece",
            "opencv-python",
            "imageio",
            "imageio-ffmpeg",
            "librosa",
            "soundfile",
            "audio-separator",
            "insightface",
            "onnxruntime",
            "moviepy<2",
            "safetensors",
            "wandb",
            "deepspeed",
            "gradio",
        ]

    async def _setup(self) -> None:
        if importlib.util.find_spec("hallo3") is None:
            await install_package_from_github(
                "hallo3",
                "https://github.com/fudan-generative-vision/hallo3.git",
                revision="e342dcec7ec1",
                subdirs=[ "hallo3", "configs" ],
            )

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.generator, self.repo_root = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.generator = None

    async def _load_pipeline(self) -> tuple[Any, str]:
        import hallo3

        # Hallo3's internal modules import each other as top-level names
        # (`from diffusion_video import ...`) rather than `from hallo3.…`,
        # so the `hallo3/` package directory must be on sys.path itself.
        hallo3_dir = hallo3.__path__[0]

        if hallo3_dir not in sys.path:
            sys.path.insert(0, hallo3_dir)

        from hallo3.app import VideoGenerator

        model_path = await self._provision_model(self.config.model, prefetch=True)

        # Hallo3 reads `./pretrained_models/hallo3` relative to cwd, so we set up
        # a working root next to site-packages that symlinks the checkpoint dir
        # into `pretrained_models/hallo3` and the installed configs into `configs/`.
        repo_root = os.path.dirname(hallo3.__path__[0])
        pretrained_link = os.path.join(repo_root, "pretrained_models", "hallo3")

        os.makedirs(os.path.dirname(pretrained_link), exist_ok=True)

        if os.path.islink(pretrained_link) or os.path.exists(pretrained_link):
            if os.path.islink(pretrained_link):
                os.unlink(pretrained_link)
            else:
                shutil.rmtree(pretrained_link)

        os.symlink(model_path, pretrained_link)

        last_cwd = os.getcwd()
        os.chdir(repo_root)

        try:
            generator = await asyncio.get_running_loop().run_in_executor(None, VideoGenerator)
        finally:
            os.chdir(last_cwd)

        return generator, repo_root

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Hallo3TalkingHeadTaskAction(
            action,
            self.generator,
            self.repo_root,
            self.device,
        ).run(context)
