from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from pathlib import Path
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, SonicTalkingHeadModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, rewrite_python_imports
from mindor.core.utils.github import download_github_tarball
from ......action.media import MediaInputPathResolver
from ....base import ComponentActionContext, ModelTaskService
from ..common import TalkingHeadTaskAction
from PIL import Image as PILImage
import os, tempfile, shutil, importlib.util, asyncio, sys

if TYPE_CHECKING:
    import torch

class SonicTalkingHeadTaskAction(TalkingHeadTaskAction):
    config: SonicTalkingHeadModelActionConfig

    def __init__(
        self,
        config: SonicTalkingHeadModelActionConfig,
        pipeline: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        dynamic_scale   = await context.render_variable(self.config.params.dynamic_scale)
        inference_steps = await context.render_variable(self.config.params.inference_steps)
        min_resolution  = await context.render_variable(self.config.params.min_resolution)
        keep_resolution = await context.render_variable(self.config.params.keep_resolution)

        params.update({
            "dynamic_scale":   dynamic_scale,
            "inference_steps": inference_steps,
            "min_resolution":  min_resolution,
            "keep_resolution": keep_resolution,
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

        # Sonic.process writes the mp4 in place and returns 0 on success, -1 on
        # failure (e.g. no face detected in the source image).
        status = self.pipeline.process(
            image_path,
            audio_path,
            video_path,
            min_resolution=int(params["min_resolution"]),
            inference_steps=int(params["inference_steps"]),
            dynamic_scale=float(params["dynamic_scale"]),
            keep_resolution=bool(params["keep_resolution"]),
            seed=int(params["seed"]) if params["seed"] is not None else None,
        )

        if status != 0:
            if os.path.exists(video_path):
                os.remove(video_path)
            raise RuntimeError("Sonic failed to render the talking-head video (no face detected or pipeline error)")

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

class SonicTalkingHeadTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchvision", "torchaudio"),
            "diffusers",
            "transformers",
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
        ]

    async def _setup(self) -> None:
        # Sonic's upstream keeps the top-level `Sonic` class in `sonic.py` at
        # the repo root while its sub-packages live under `src/`, and every
        # internal import uses `from src.…`. Install by copying `src/` in as
        # a proper `sonic/` package (import rewrites happen automatically),
        # then fold `sonic.py`'s contents into `sonic/__init__.py` — with the
        # rewrites applied there too — so callers can `from sonic import Sonic`.
        if importlib.util.find_spec("sonic") is not None:
            return

        await install_package_from_github(
            "sonic",
            "https://github.com/jixiaozhong/Sonic.git",
            revision="c1bd2d133ecc72f1a5abd990f1de101efcc3cfdb",
            subdirs=[ ("sonic", "src"), "config" ],
        )

        # `install_package_from_github` won't drop the loose `sonic.py`; fetch
        # the tarball ourselves and lift that single file into __init__.py.
        await asyncio.get_running_loop().run_in_executor(None, self._merge_sonic_root_module)

    def _merge_sonic_root_module(self) -> None:
        import mindor
        install_root = Path(mindor.__file__).resolve().parent.parent
        sonic_pkg_dir = install_root / "sonic"
        init_path = sonic_pkg_dir / "__init__.py"

        if init_path.exists() and init_path.stat().st_size > 0:
            return

        clone_dir = Path(tempfile.gettempdir()) / "mindor-git-sources" / "sonic"
        sonic_module_file = clone_dir / "sonic.py"

        if not sonic_module_file.exists():
            # tarball already gone (cache miss) — refetch to grab just sonic.py
            asyncio.get_event_loop().run_until_complete(
                download_github_tarball(
                    "https://github.com/jixiaozhong/Sonic.git",
                    "c1bd2d133ecc72f1a5abd990f1de101efcc3cfdb",
                    clone_dir,
                )
            )

        shutil.copy2(sonic_module_file, init_path)
        rewrite_python_imports(sonic_pkg_dir, { "src": "sonic" })

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.pipeline = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None

    async def _load_pipeline(self) -> Any:
        import sonic  # our installed package

        model_path = await self._provision_model(self.config.model, prefetch=True)

        # Sonic resolves every checkpoint path relative to BASE_DIR (defined
        # inside sonic/__init__.py as the module directory). Symlink the user's
        # checkpoint tree in as `checkpoints/` next to the installed package so
        # the hard-coded relative paths in config/inference/sonic.yaml resolve.
        install_root = os.path.dirname(sonic.__file__)
        checkpoint_symlink = os.path.join(install_root, "checkpoints")

        if os.path.islink(checkpoint_symlink):
            os.unlink(checkpoint_symlink)
        elif os.path.exists(checkpoint_symlink):
            shutil.rmtree(checkpoint_symlink)

        os.symlink(model_path, checkpoint_symlink)

        device_index = self.device.index if self.device.index is not None else 0

        def _load() -> Any:
            return sonic.Sonic(device_id=device_index, enable_interpolate_frame=True)

        return await asyncio.get_running_loop().run_in_executor(None, _load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await SonicTalkingHeadTaskAction(action, self.pipeline, self.device).run(context)
