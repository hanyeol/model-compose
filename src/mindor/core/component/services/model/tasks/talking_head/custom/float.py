from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from pathlib import Path
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, FloatTalkingHeadModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import rewrite_python_imports, get_mindor_install_root
from mindor.core.utils.github import download_github_tarball
from ......action.media import MediaInputPathResolver
from ....base import ComponentActionContext, ModelTaskService
from ..common import TalkingHeadTaskAction
from PIL import Image as PILImage
import importlib, importlib.util
import os, tempfile, shutil, asyncio, argparse

if TYPE_CHECKING:
    import torch

class FloatTalkingHeadTaskAction(TalkingHeadTaskAction):
    config: FloatTalkingHeadModelActionConfig

    def __init__(
        self,
        config: FloatTalkingHeadModelActionConfig,
        agent: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.agent: Any = agent
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        emotion         = await context.render_variable(self.config.params.emotion)
        emotion_scale   = await context.render_variable(self.config.params.emotion_scale)
        inference_steps = await context.render_variable(self.config.params.inference_steps)
        cfg_scale       = await context.render_variable(self.config.params.cfg_scale)
        a_cfg_scale     = await context.render_variable(self.config.params.a_cfg_scale)
        e_cfg_scale     = await context.render_variable(self.config.params.e_cfg_scale)
        crop            = await context.render_variable(self.config.params.crop)

        params.update({
            "emotion":         emotion,
            "emotion_scale":   emotion_scale,
            "inference_steps": inference_steps,
            "cfg_scale":       cfg_scale,
            "a_cfg_scale":     a_cfg_scale,
            "e_cfg_scale":     e_cfg_scale,
            "crop":            crop,
        })

        return params

    async def _generate_batch(
        self,
        images: List[PILImage.Image],
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        image_paths = [ self._save_image_to_tempfile(image) for image in images ]
        audio_paths = [ await MediaInputPathResolver().resolve(audio) for audio in audios ]

        try:
            def _generate() -> List[VideoStreamResource]:
                results: List[VideoStreamResource] = []

                for image_path, (audio_path, _) in zip(image_paths, audio_paths):
                    results.append(self._render(image_path, audio_path, params))

                return results

            return await self._run_in_executor(_generate)
        finally:
            for path in image_paths:
                if os.path.exists(path):
                    os.remove(path)

            for path, spooled in audio_paths:
                if spooled and path and os.path.exists(path):
                    os.remove(path)

    def _render(self, image_path: str, audio_path: str, params: Dict[str, Any]) -> VideoStreamResource:
        fd, video_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

        # InferenceAgent.run_inference writes the mp4 to res_video_path and
        # returns the same path. `emo='S2E'` is Float's auto-detect sentinel;
        # explicit labels ('happy', 'sad', ...) override the audio-derived one.
        self.agent.run_inference(
            res_video_path=video_path,
            ref_path=image_path,
            audio_path=audio_path,
            a_cfg_scale=float(params["a_cfg_scale"]),
            r_cfg_scale=float(params["cfg_scale"]),
            e_cfg_scale=float(params["e_cfg_scale"]),
            emo=params["emotion"] or "S2E",
            nfe=int(params["inference_steps"]),
            no_crop=not bool(params["crop"]),
            seed=int(params["seed"]) if params["seed"] is not None else 25,
            verbose=False,
        )

        return VideoStreamResource(
            FileStreamResource(video_path, auto_delete=True),
            format="mp4",
            attrs={ "fps": str(params["fps"] or 25) },
        )

    @staticmethod
    def _save_image_to_tempfile(image: PILImage.Image) -> str:
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        image.save(path, format="PNG")

        return path

class FloatTalkingHeadTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.agent: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch>=2.4,<2.5", "torchvision", "torchaudio"),
            "diffusers>=0.28,<0.35",
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
            "face-alignment",
            "torchdiffeq",
            "albumentations",
            "timm",
            "av<14",
            "huggingface_hub",
        ]

    async def _setup(self) -> None:
        if importlib.util.find_spec("float_talker") is None:
            await asyncio.get_running_loop().run_in_executor(None, self._install_float_package)

    def _install_float_package(self) -> None:
        # `models/`, `options/`, and `generate.py` sit at Float's repo root;
        # funnel them all into one `float_talker/` package so top-level names
        # don't collide with anything else installed alongside model-compose.
        internal_modules = ("models", "options", "generate")

        target = get_mindor_install_root() / "float_talker"

        if target.exists():
            return

        clone_dir = Path(tempfile.gettempdir()) / "mindor-git-sources" / "float_talker"

        if not clone_dir.exists():
            clone_dir.parent.mkdir(parents=True, exist_ok=True)
            # `_install_float_package` already runs inside an executor thread,
            # so it has no event loop of its own — spin one up just for the
            # tarball fetch (which is the only async call here).
            asyncio.run(download_github_tarball(
                "https://github.com/deepbrainai-research/float.git",
                "3b5b2dfc3e65",
                clone_dir,
            ))

        target.mkdir(parents=True, exist_ok=False)
        (target / "__init__.py").write_text("", encoding="utf-8")

        for name in internal_modules:
            src_dir = clone_dir / name
            src_file = clone_dir / f"{name}.py"

            if src_dir.exists() and src_dir.is_dir():
                shutil.copytree(src_dir, target / name)
            elif src_file.exists():
                shutil.copy2(src_file, target / f"{name}.py")

        rewrite_python_imports(target, { name: f"float_talker.{name}" for name in internal_modules })

        importlib.invalidate_caches()

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.agent = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.agent = None

    async def _load_pipeline(self) -> Any:
        from float_talker.generate import InferenceAgent
        from float_talker.options.base_options import BaseOptions

        model_path = await self._provision_model(self.config.model, prefetch=True)

        # BaseOptions parses argparse from sys.argv, so hand it a synthetic
        # argv that points every checkpoint path at the user-provided dir.
        parser = BaseOptions().initialize(argparse.ArgumentParser())
        args = parser.parse_args([
            "--pretrained_dir", model_path,
            "--wav2vec_model_path", os.path.join(model_path, "wav2vec2-base-960h"),
            "--audio2emotion_path", os.path.join(model_path, "wav2vec-english-speech-emotion-recognition"),
        ])

        # InferenceAgent reads `ckpt_path` and `rank` off the Namespace but
        # neither is registered as an argparse flag on BaseOptions.
        args.ckpt_path = os.path.join(model_path, "float.pth")
        args.rank = self.device.index if self.device.index is not None else 0
        args.fps = int(args.fps)

        def _load() -> Any:
            return InferenceAgent(args)

        return await asyncio.get_running_loop().run_in_executor(None, _load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await FloatTalkingHeadTaskAction(action, self.agent, self.device).run(context)
