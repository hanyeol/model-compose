from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, SadTalkerPreset, SadTalkerPreprocess
from mindor.dsl.schema.action import ModelActionConfig, SadTalkerTalkingHeadModelActionConfig
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
import os, tempfile, shutil, importlib.util

if TYPE_CHECKING:
    import torch

_SADTALKER_PRESET_SIZE: Dict[SadTalkerPreset, int] = {
    SadTalkerPreset.V002_256: 256,
    SadTalkerPreset.V002_512: 512,
}

class SadTalkerTalkingHeadTaskAction(TalkingHeadTaskAction):
    config: SadTalkerTalkingHeadModelActionConfig

    def __init__(
        self,
        config: SadTalkerTalkingHeadModelActionConfig,
        pipeline: Dict[str, Any],
        preset: SadTalkerPreset,
        preprocess: SadTalkerPreprocess,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Dict[str, Any] = pipeline
        self.preset: SadTalkerPreset = preset
        self.preprocess: SadTalkerPreprocess = preprocess
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        ref_eyeblink        = await context.render_variable(self.config.params.ref_eyeblink)
        ref_pose            = await context.render_variable(self.config.params.ref_pose)
        pose_style          = await context.render_variable(self.config.params.pose_style)
        expression_scale    = await context.render_variable(self.config.params.expression_scale)
        input_yaw           = await context.render_variable(self.config.params.input_yaw)
        input_pitch         = await context.render_variable(self.config.params.input_pitch)
        input_roll          = await context.render_variable(self.config.params.input_roll)
        still               = await context.render_variable(self.config.params.still)
        enhancer            = await context.render_variable(self.config.params.enhancer)
        background_enhancer = await context.render_variable(self.config.params.background_enhancer)
        face3dvis           = await context.render_variable(self.config.params.face3dvis)
        size                = await context.render_variable(self.config.params.size)
        facerender_batch    = await context.render_variable(self.config.params.facerender_batch_size)

        params.update({
            "ref_eyeblink":         ref_eyeblink,
            "ref_pose":             ref_pose,
            "pose_style":           pose_style,
            "expression_scale":     expression_scale,
            "input_yaw":            input_yaw,
            "input_pitch":          input_pitch,
            "input_roll":           input_roll,
            "still":                still,
            "enhancer":             enhancer.value if hasattr(enhancer, "value") else enhancer,
            "background_enhancer":  background_enhancer.value if hasattr(background_enhancer, "value") else background_enhancer,
            "face3dvis":            face3dvis,
            "size":                 size,
            "facerender_batch":     facerender_batch,
        })

        return params

    async def _generate_batch(
        self,
        images: List[PILImage.Image],
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        # SadTalker's pipeline works on filesystem paths — decode inputs to
        # temp files up front so the executor thread does pure CPU/GPU work.
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
        from sadtalker.generate_batch import get_data
        from sadtalker.generate_facerender_batch import get_facerender_data

        size             = int(params["size"] or _SADTALKER_PRESET_SIZE[self.preset])
        preprocess       = self.preprocess.value
        still            = bool(params["still"])
        pose_style       = int(params["pose_style"])
        expression_scale = float(params["expression_scale"])
        facerender_batch = int(params["facerender_batch"])

        work_dir = tempfile.mkdtemp(prefix="sadtalker-")

        try:
            preprocess_model = self.pipeline["preprocess"]
            audio_to_coeff   = self.pipeline["audio_to_coeff"]
            animate_model    = self.pipeline["animate"]

            first_frame_dir = os.path.join(work_dir, "first_frame_dir")
            os.makedirs(first_frame_dir, exist_ok=True)
            first_coeff_path, crop_pic_path, crop_info = preprocess_model.generate(
                image_path,
                first_frame_dir,
                preprocess,
                source_image_flag=True,
                pic_size=size,
            )

            if first_coeff_path is None:
                raise RuntimeError("SadTalker failed to detect a face in the input image")

            ref_eyeblink_coeff_path = self._extract_ref_coeff(
                preprocess_model, params.get("ref_eyeblink"), work_dir, "eyeblink", preprocess, size,
            )
            ref_pose_coeff_path = self._extract_ref_coeff(
                preprocess_model, params.get("ref_pose"), work_dir, "pose", preprocess, size,
            )

            batch = get_data(
                first_coeff_path,
                audio_path,
                self.device,
                ref_eyeblink_coeff_path=ref_eyeblink_coeff_path,
                still=still,
            )
            coeff_path = audio_to_coeff.generate(batch, work_dir, pose_style, ref_pose_coeff_path)

            if params.get("face3dvis"):
                from sadtalker.face3d.visualize import gen_composed_video

                gen_composed_video(
                    None,
                    self.device,
                    first_coeff_path,
                    coeff_path,
                    audio_path,
                    os.path.join(work_dir, "3dface.mp4"),
                )

            data = get_facerender_data(
                coeff_path,
                crop_pic_path,
                first_coeff_path,
                audio_path,
                facerender_batch,
                params.get("input_yaw"),
                params.get("input_pitch"),
                params.get("input_roll"),
                expression_scale=expression_scale,
                still_mode=still,
                preprocess=preprocess,
                size=size,
            )

            result_path = animate_model.generate(
                data,
                work_dir,
                image_path,
                crop_info,
                enhancer=params.get("enhancer"),
                background_enhancer=params.get("background_enhancer"),
                preprocess=preprocess,
                img_size=size,
            )

            # Move the result out of work_dir so we can drop the intermediate
            # artifacts immediately while the mp4 stays around until the
            # downstream FileStreamResource is fully consumed.
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

    def _extract_ref_coeff(
        self,
        preprocess_model: Any,
        ref_video: Optional[str],
        work_dir: str,
        kind: str,
        preprocess: str,
        size: int,
    ) -> Optional[str]:
        if not ref_video:
            return None

        ref_dir = os.path.join(work_dir, f"ref_{kind}")
        os.makedirs(ref_dir, exist_ok=True)

        coeff_path, _, _ = preprocess_model.generate(
            ref_video, ref_dir, preprocess, source_image_flag=False, pic_size=size,
        )

        return coeff_path

    @staticmethod
    def _save_image_to_tempfile(image: PILImage.Image) -> str:
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        image.save(path, format="PNG")

        return path

class SadTalkerTalkingHeadTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._require_isolated_runtime()

        self.pipeline: Optional[Dict[str, Any]] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchvision"),
            "numpy<1.24",
            "scipy<1.14",
            "scikit-image<0.24",
            "numba<0.60",
            "librosa<0.11",
            "kornia<0.7.4",
            "resampy",
            "pydub",
            "yacs",
            "pyyaml",
            "joblib",
            "imageio",
            "imageio-ffmpeg",
            "opencv-python",
            "tqdm",
            "face-alignment",
            "gfpgan",
            "facexlib",
            "basicsr",
            "safetensors",
            "av",
            "huggingface_hub",
        ]

    async def _setup(self) -> None:
        # SadTalker's code lives under a bare `src/` in the upstream repo, which
        # would collide with model-compose's editable-install root. Rename it to
        # `sadtalker/` on install; the tuple form triggers automatic rewrites of
        # `import src.…` inside the copied tree.
        if importlib.util.find_spec("sadtalker") is None:
            await install_package_from_github(
                "sadtalker",
                "https://github.com/OpenTalker/SadTalker.git",
                revision="cd4c0465ae0b",
                subdirs=[ ("sadtalker", "src") ],
            )

        # basicsr 1.4.2 imports `torchvision.transforms.functional_tensor`, which
        # was removed in torchvision 0.17. Rewrite the broken import in place.
        # Locate the file via find_spec instead of importing basicsr directly —
        # importing already fails on the same missing module.
        basicsr_spec = importlib.util.find_spec("basicsr")

        if basicsr_spec and basicsr_spec.origin:
            degradations_path = os.path.join(os.path.dirname(basicsr_spec.origin), "data", "degradations.py")

            if os.path.exists(degradations_path):
                with open(degradations_path, "r", encoding="utf-8") as f:
                    text = f.read()

                if "torchvision.transforms.functional_tensor" in text:
                    with open(degradations_path, "w", encoding="utf-8") as f:
                        f.write(text.replace(
                            "from torchvision.transforms.functional_tensor import rgb_to_grayscale",
                            "from torchvision.transforms.functional import rgb_to_grayscale",
                        ))

                    importlib.invalidate_caches()

    async def _load_model(self) -> None:
        self.pipeline, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Dict[str, Any], torch.device]:
        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        def _load() -> Dict[str, Any]:
            from sadtalker.utils.preprocess import CropAndExtract
            from sadtalker.test_audio2coeff import Audio2Coeff
            from sadtalker.facerender.animate import AnimateFromCoeff
            from sadtalker.utils.init_path import init_path
            import sadtalker

            config_dir = os.path.join(sadtalker.__path__[0], "config")
            sadtalker_paths = init_path(
                model_path,
                config_dir,
                _SADTALKER_PRESET_SIZE[self.config.preset],
                False,
                self.config.preprocess.value
            )

            return {
                "preprocess":     CropAndExtract(sadtalker_paths, device),
                "audio_to_coeff": Audio2Coeff(sadtalker_paths, device),
                "animate":        AnimateFromCoeff(sadtalker_paths, device),
            }

        pipeline = await self._run_in_executor(_load)

        return pipeline, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await SadTalkerTalkingHeadTaskAction(
            action,
            self.pipeline,
            self.config.preset,
            self.config.preprocess,
            self.device,
        ).run(context)
