from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, Hallo2TalkingHeadModelActionConfig
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
import os, tempfile, shutil, importlib.util, argparse, glob

if TYPE_CHECKING:
    import torch

class Hallo2TalkingHeadTaskAction(TalkingHeadTaskAction):
    config: Hallo2TalkingHeadModelActionConfig

    def __init__(
        self,
        config: Hallo2TalkingHeadModelActionConfig,
        model_path: str,
        config_path: str,
        device: torch.device,
    ):
        super().__init__(config)

        self.model_path: str = model_path
        self.config_path: str = config_path
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        pose_weight          = await context.render_variable(self.config.params.pose_weight)
        face_weight          = await context.render_variable(self.config.params.face_weight)
        lip_weight           = await context.render_variable(self.config.params.lip_weight)
        face_expand_ratio    = await context.render_variable(self.config.params.face_expand_ratio)
        inference_steps      = await context.render_variable(self.config.params.inference_steps)
        cfg_scale            = await context.render_variable(self.config.params.cfg_scale)
        motion_module_frames = await context.render_variable(self.config.params.motion_module_frames)
        long_video           = await context.render_variable(self.config.params.long_video)
        high_resolution      = await context.render_variable(self.config.params.high_resolution)

        params.update({
            "pose_weight":          pose_weight,
            "face_weight":          face_weight,
            "lip_weight":           lip_weight,
            "face_expand_ratio":    face_expand_ratio,
            "inference_steps":      inference_steps,
            "cfg_scale":            cfg_scale,
            "motion_module_frames": motion_module_frames,
            "long_video":           long_video,
            "high_resolution":      high_resolution,
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
        from scripts.inference_long import inference_process

        work_dir = tempfile.mkdtemp(prefix="hallo2-")

        try:
            args = argparse.Namespace(
                config=self.config_path,
                source_image=image_path,
                driving_audio=audio_path,
                output=work_dir,
                pose_weight=float(params["pose_weight"]),
                face_weight=float(params["face_weight"]),
                lip_weight=float(params["lip_weight"]),
                face_expand_ratio=float(params["face_expand_ratio"]),
                audio_ckpt_dir=self.model_path,
            )
            inference_process(args)

            # inference_process writes segments to <output>/seg_video/*.mp4 and
            # then calls merge_videos into <output>/merge_video.mp4. Fall back to
            # the last segment if the merge step didn't run in this build.
            result_path = os.path.join(work_dir, "merge_video.mp4")

            if not os.path.exists(result_path):
                segments = sorted(glob.glob(os.path.join(work_dir, "seg_video", "*.mp4")))

                if not segments:
                    raise RuntimeError("Hallo2 produced no output segments")

                result_path = segments[-1]

            fd, video_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            shutil.move(result_path, video_path)

            return VideoStreamResource(
                FileStreamResource(video_path, auto_delete=True),
                format="mp4",
                attrs={ "fps": str(params["fps"] or 25) },
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    @staticmethod
    def _save_image_to_tempfile(image: PILImage.Image) -> str:
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        image.save(path, format="PNG")

        return path

class Hallo2TalkingHeadTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model_path: Optional[str] = None
        self.config_path: Optional[str] = None
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
            "audio-separator",
            "insightface",
            "onnxruntime",
            "moviepy",
            "safetensors",
        ]

    async def _setup(self) -> None:
        # Hallo2's upstream keeps its code under a clean `hallo/` package plus
        # top-level `scripts/`, so we install both alongside model-compose.
        if importlib.util.find_spec("hallo") is None:
            await install_package_from_github(
                "hallo",
                "https://github.com/fudan-generative-vision/hallo2.git",
                revision="58a9aa6c9f66817a6e084f3874cfc01ac24fed3e",
                subdirs=[ "hallo", "scripts" ],
            )

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.model_path, self.config_path = await self._load_pipeline()

    async def _unload_model(self) -> None:
        # Hallo2's inference_process constructs the pipeline lazily inside the
        # call, so there is no long-lived model handle we need to release here.
        pass

    async def _load_pipeline(self) -> tuple[str, str]:
        import hallo

        model_path = await self._provision_model(self.config.model, prefetch=True)

        # Config yaml lives inside the repo tree we installed above.
        repo_root = os.path.dirname(os.path.dirname(hallo.__file__))
        config_path = os.path.join(repo_root, "configs", "inference", "long.yaml")

        return model_path, config_path

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Hallo2TalkingHeadTaskAction(
            action,
            self.model_path,
            self.config_path,
            self.device,
        ).run(context)
