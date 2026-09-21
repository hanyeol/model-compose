from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import AniGenImageTo3DModelComponentConfig, AniGenSSVariant, AniGenSLATVariant
from mindor.dsl.schema.action import ModelActionConfig, AniGenImageTo3DModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.flash_attn import flash_attn_requirements
from mindor.core.foundation.package.installer import install_package_from_github
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageTo3DTaskAction
from PIL import Image as PILImage
import os, tempfile, importlib.util

if TYPE_CHECKING:
    import torch

_SS_FLOW_SUBDIR = {
    AniGenSSVariant.SOLO: "ckpts/anigen/ss_flow_solo",
    AniGenSSVariant.EPIC: "ckpts/anigen/ss_flow_epic",
    AniGenSSVariant.DUET: "ckpts/anigen/ss_flow_duet",
}

_SLAT_FLOW_SUBDIR = {
    AniGenSLATVariant.AUTO:    "ckpts/anigen/slat_flow_auto",
    AniGenSLATVariant.CONTROL: "ckpts/anigen/slat_flow_control",
}

class AniGenImageTo3DTaskAction(ImageTo3DTaskAction):
    config: AniGenImageTo3DModelActionConfig

    def __init__(
        self,
        config: AniGenImageTo3DModelActionConfig,
        pipeline: Any,
        model_path: str,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.model_path: str = model_path
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        cfg_scale_ss              = await context.render_scalar(self.config.params.cfg_scale_ss, float)
        cfg_scale_slat            = await context.render_scalar(self.config.params.cfg_scale_slat, float)
        ss_steps                  = await context.render_scalar(self.config.params.ss_steps, int)
        slat_steps                = await context.render_scalar(self.config.params.slat_steps, int)
        joints_density            = await context.render_scalar(self.config.params.joints_density, int)
        simplify_ratio            = await context.render_scalar(self.config.params.simplify_ratio, float)
        fill_holes                = await context.render_scalar(self.config.params.fill_holes, bool)
        no_smooth_skin_weights    = await context.render_scalar(self.config.params.no_smooth_skin_weights, bool)
        smooth_skin_weights_iters = await context.render_scalar(self.config.params.smooth_skin_weights_iters, int)
        smooth_skin_weights_alpha = await context.render_scalar(self.config.params.smooth_skin_weights_alpha, float)
        no_filter_skin_weights    = await context.render_scalar(self.config.params.no_filter_skin_weights, bool)
        texture_size              = await context.render_scalar(self.config.params.texture_size, int)
        return_mesh               = await context.render_scalar(self.config.return_mesh, bool)
        return_skeleton           = await context.render_scalar(self.config.return_skeleton, bool)
        return_image              = await context.render_scalar(self.config.return_image, bool)

        if return_mesh is False and return_skeleton is False and return_image is False:
            raise ValueError("At least one of 'return_mesh', 'return_skeleton', or 'return_image' must be true.")

        params.update({
            "cfg_scale_ss":              cfg_scale_ss,
            "cfg_scale_slat":            cfg_scale_slat,
            "ss_steps":                  ss_steps,
            "slat_steps":                slat_steps,
            "joints_density":            joints_density,
            "simplify_ratio":            simplify_ratio,
            "fill_holes":                fill_holes,
            "no_smooth_skin_weights":    no_smooth_skin_weights,
            "smooth_skin_weights_iters": smooth_skin_weights_iters,
            "smooth_skin_weights_alpha": smooth_skin_weights_alpha,
            "no_filter_skin_weights":    no_filter_skin_weights,
            "texture_size":              texture_size,
            "return_mesh":               return_mesh,
            "return_skeleton":           return_skeleton,
            "return_image":              return_image,
        })

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        def _generate() -> List[Any]:
            return [ self._render(image, params) for (image,) in inputs ]

        return await self._run_in_executor(_generate)

    def _render(self, image: PILImage.Image, params: Dict[str, Any]) -> Dict[str, Any]:
        import torch

        seed = params["seed"] if params["seed"] is not None else 42

        # AniGen's pipeline hardcodes relative paths for `torch.hub.load('./ckpts/dinov2', ...)`
        # inside `from_pretrained` (already loaded), but `run()` also writes
        # `skeleton.glb` next to `output_glb` unconditionally — so route both
        # outputs through a caller-owned temp dir we can clean up.
        output_dir = tempfile.mkdtemp(prefix="anigen_")
        output_glb = os.path.join(output_dir, "mesh.glb")

        last_cwd = os.getcwd()

        try:
            # `visualize_skeleton_as_mesh` and DSINE reads use the CWD for
            # relative asset lookups; anchor to the model path so those succeed.
            os.chdir(self.model_path)

            outputs = self.pipeline.run(
                image,
                seed=seed,
                cfg_scale_ss=params["cfg_scale_ss"],
                cfg_scale_slat=params["cfg_scale_slat"],
                ss_steps=params["ss_steps"],
                slat_steps=params["slat_steps"],
                joints_density=params["joints_density"],
                simplify_ratio=params["simplify_ratio"],
                fill_holes=params["fill_holes"],
                no_smooth_skin_weights=params["no_smooth_skin_weights"],
                no_filter_skin_weights=params["no_filter_skin_weights"],
                smooth_skin_weights_iters=params["smooth_skin_weights_iters"],
                smooth_skin_weights_alpha=params["smooth_skin_weights_alpha"],
                texture_size=params["texture_size"],
                output_glb=output_glb,
            )
        finally:
            os.chdir(last_cwd)

        result: Dict[str, Any] = {}

        if params["return_mesh"]:
            result["mesh"] = Model3DStreamResource(
                FileStreamResource(output_glb, auto_delete=True),
                format="glb",
                filename="mesh.glb",
            )

        if params["return_skeleton"]:
            skeleton_glb = os.path.join(output_dir, "skeleton.glb")

            if os.path.exists(skeleton_glb):
                result["skeleton"] = Model3DStreamResource(
                    FileStreamResource(skeleton_glb, auto_delete=True),
                    format="glb",
                    filename="skeleton.glb",
                )

        if params["return_image"]:
            processed_image = outputs.get("processed_image")

            if processed_image is not None:
                result["image"] = ImageStreamResource(processed_image.convert("RGB"), format="png", filename="processed_image.png")

        return result

class AniGenImageTo3DTaskDriver(ModelTaskDriver):
    config: AniGenImageTo3DModelComponentConfig

    def __init__(self, id: str, config: AniGenImageTo3DModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # AniGen pins torch 2.4/2.5 with CUDA-specific spconv/pytorch3d/nvdiffrast
        # extensions, and installs the anigen package alongside `mindor` from a
        # git tree. Isolate the model worker so those pins don't leak into the
        # controller's stack.
        self._require_isolated_runtime()

        self.pipeline: Optional[Any] = None
        self.model_path: Optional[str] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch>=2.4,<2.6", "torchvision"),
            *flash_attn_requirements("torch>=2.4,<2.6", "flash-attn==2.8.3.post1"),
            "imageio>=2.31",
            "imageio-ffmpeg>=0.5",
            "tqdm>=4.60",
            "easydict>=1.10",
            "opencv-python-headless>=4.8",
            "scipy>=1.11,<1.14",
            "ninja",
            "rembg>=2.0",
            "onnxruntime>=1.17",
            "trimesh>=4.0",
            "rtree>=1.0",
            "xatlas>=0.0.9",
            "pyvista>=0.43",
            "pymeshfix>=0.17",
            "igraph>=0.11",
            "pygltflib>=1.16",
            "plyfile>=1.0",
            "numpy>=1.24,<2",
            "psutil>=5.9",
            "safetensors>=0.4",
            "scikit-learn>=1.3",
            "geffnet>=1.0",
            "transformers>=4.40",
            "huggingface_hub>=0.34.0,<1.0",
            "spconv-cu121",
            "utils3d@git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8",
        ]

    async def _setup(self) -> None:
        # AniGen's setup.sh pins pytorch3d 0.7.8 and nvdiffrast 0.3.3, both
        # built from source with `--no-build-isolation` because their setup.py
        # imports torch at build time (pip's isolated build env has none).
        pip_options: List[str] = [ "--no-build-isolation" ]

        if importlib.util.find_spec("pytorch3d") is None:
            await install_package_from_github(
                "pytorch3d",
                "https://github.com/facebookresearch/pytorch3d.git",
                revision="75ebeeaea090",
                source_path=".",
                pip_options=pip_options,
            )

        if importlib.util.find_spec("nvdiffrast") is None:
            await install_package_from_github(
                "nvdiffrast",
                "https://github.com/NVlabs/nvdiffrast.git",
                revision="729261dc64c4",
                source_path=".",
                pip_options=pip_options,
            )

        if importlib.util.find_spec("anigen") is None:
            # AniGen's `anigen/` is pure Python; drop it next to `mindor` so
            # `from anigen.pipelines import AnigenImageTo3DPipeline` resolves
            # without any sys.path manipulation.
            await install_package_from_github(
                "anigen",
                "https://github.com/VAST-AI-Research/AniGen.git",
                revision="c49db3d6b466",
                subdirs=[ "anigen" ],
            )

    async def _load_model(self) -> None:
        self.pipeline, self.model_path, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.model_path = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Any, str, torch.device]:
        # AniGen hardcodes `.cuda()` calls and expects CUDA tensors for DINOv2 /
        # DSINE / flow-matching stages; there's no CPU path today. Fail loudly
        # here rather than let the pipeline crash mid-generation.
        device = self._resolve_device(self.config.device)

        if device.type != "cuda":
            raise RuntimeError(
                f"Component '{self.id}': AniGen requires a CUDA device, "
                f"but resolved device is '{device.type}'. Set component.device to "
                "'cuda' or a specific 'cuda:N' index."
            )

        # AniGen's `from_pretrained` uses relative paths (`ckpts/anigen/...`,
        # `./ckpts/dinov2`) resolved against CWD, and `ensure_ckpts()` writes
        # the HF snapshot into `<local_dir>/ckpts/`. Provision the HF repo into
        # a stable cache directory and treat that directory as the working root
        # for every pipeline call.
        model_path = await self._provision_model(self.config.model, prefetch=True)

        # The `_provision_model` helper drops HF snapshots at the repo root
        # (i.e. the directory that contains `ckpts/anigen/...`). AniGen's
        # `example.py` runs from that root, so we treat it the same way.
        ss_flow_path   = _SS_FLOW_SUBDIR[self.config.ss_variant]
        slat_flow_path = _SLAT_FLOW_SUBDIR[self.config.slat_variant]

        def _load() -> Any:
            from anigen.pipelines import AnigenImageTo3DPipeline

            last_cwd = os.getcwd()

            try:
                os.chdir(model_path)

                pipeline = AnigenImageTo3DPipeline.from_pretrained(
                    ss_flow_path=ss_flow_path,
                    slat_flow_path=slat_flow_path,
                    device=str(device),
                    use_ema=False,
                )
                pipeline.cuda()
            finally:
                os.chdir(last_cwd)

            return pipeline

        pipeline = await self._run_in_executor(_load)

        return pipeline, model_path, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await AniGenImageTo3DTaskAction(
            action,
            self.pipeline,
            self.model_path,
            self.device,
        ).run(context)
