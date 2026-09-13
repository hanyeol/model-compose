from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
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
import os, tempfile, shutil, importlib.util, argparse

if TYPE_CHECKING:
    import torch

class Hallo2TalkingHeadTaskAction(TalkingHeadTaskAction):
    config: Hallo2TalkingHeadModelActionConfig

    def __init__(
        self,
        config: Hallo2TalkingHeadModelActionConfig,
        config_path: str,
        repo_root: str,
        device: torch.device,
    ):
        super().__init__(config)

        self.config_path: str = config_path
        self.repo_root: str = repo_root
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
        from hallo.utils.util import merge_videos
        from pydub import AudioSegment

        work_dir = tempfile.mkdtemp(prefix="hallo2-")

        # Hallo2's `cut_audio` calls `AudioSegment.from_wav()` unconditionally
        # and rejects any container other than WAV. Transcode the driving
        # audio into a wav next to the work dir before handing it off.
        wav_audio_path = os.path.join(work_dir, "driving.wav")
        AudioSegment.from_file(audio_path).export(wav_audio_path, format="wav")

        # `inference_process` resolves `./pretrained_models/...` from the
        # config against cwd, so run the call from the repo root and restore
        # the original directory when it returns.
        last_cwd = os.getcwd()
        os.chdir(self.repo_root)

        try:
            # inference_process merges args into the config via OmegaConf, so
            # `save_path` here overrides `config.save_path` and every artifact
            # lands under our work_dir. `audio_ckpt_dir=None` keeps the config
            # default (`pretrained_models/hallo2`), which resolves through the
            # snapshot symlink we set up.
            args = argparse.Namespace(
                config=self.config_path,
                source_image=image_path,
                driving_audio=wav_audio_path,
                save_path=work_dir,
                pose_weight=float(params["pose_weight"]),
                face_weight=float(params["face_weight"]),
                lip_weight=float(params["lip_weight"]),
                face_expand_ratio=float(params["face_expand_ratio"]),
                audio_ckpt_dir=None,
            )

            # inference_process returns the seg_video directory
            # (`<save_path>/<image_stem>/seg_video`). Upstream's `__main__`
            # calls merge_videos afterwards to stitch the segments into a
            # single MP4 next to it; we replicate that here.
            seg_video_dir = inference_process(args)
            result_path = os.path.join(os.path.dirname(seg_video_dir), "merge_video.mp4")
            merge_videos(seg_video_dir, result_path)

            fd, video_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            shutil.move(result_path, video_path)

            return VideoStreamResource(
                FileStreamResource(video_path, auto_delete=True),
                format="mp4",
                attrs={ "fps": str(params["fps"] or 25) },
            )
        finally:
            os.chdir(last_cwd)
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

        self.config_path: Optional[str] = None
        self.repo_root: Optional[str] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchvision", "torchaudio"),
            "diffusers>=0.32,<0.33",
            "transformers<4.45",
            "accelerate",
            "xformers",
            "einops",
            "omegaconf",
            "opencv-python",
            "imageio",
            "imageio-ffmpeg",
            "librosa",
            "soundfile",
            "audio-separator",
            "insightface==0.7.3",
            "mediapipe",
            "onnxruntime",
            "moviepy<2",
            "safetensors",
            "av<14",
            "icecream",
        ]

    async def _setup(self) -> None:
        if importlib.util.find_spec("hallo") is None:
            await install_package_from_github(
                "hallo",
                "https://github.com/fudan-generative-vision/hallo2.git",
                revision="58a9aa6c9f66",
                subdirs=[ "hallo", "scripts", "configs" ],
            )

    async def _load_model(self) -> None:
        self.config_path, self.repo_root, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.config_path = None
        self.repo_root = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[str, str, torch.device]:
        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        def _load() -> Tuple[str, str]:
            import hallo

            # Config yaml lives inside the repo tree we installed above; `hallo`
            # is a namespace package so `__file__` may be None — use __path__.
            repo_root = os.path.dirname(hallo.__path__[0])
            config_path = os.path.join(repo_root, "configs", "inference", "long.yaml")

            pretrained_symlink = os.path.join(repo_root, "pretrained_models")

            if os.path.islink(pretrained_symlink):
                os.unlink(pretrained_symlink)
            elif os.path.exists(pretrained_symlink):
                shutil.rmtree(pretrained_symlink)

            os.symlink(model_path, pretrained_symlink)

            return config_path, repo_root

        config_path, repo_root = await self._run_in_executor(_load)

        return config_path, repo_root, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Hallo2TalkingHeadTaskAction(
            action,
            self.config_path,
            self.repo_root,
            self.device,
        ).run(context)
