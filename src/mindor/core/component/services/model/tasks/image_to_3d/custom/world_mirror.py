from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import WorldMirrorImageTo3DModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, WorldMirrorImageTo3DModelActionConfig, WorldMirrorSkyMaskSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.flash_attn import flash_attn_requirements
from mindor.core.foundation.package.installer import install_package_from_github
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageTo3DTaskAction
from PIL import Image as PILImage
import os, json, shutil, tempfile, importlib.util

if TYPE_CHECKING:
    import torch

class WorldMirrorImageTo3DTaskAction(ImageTo3DTaskAction):
    """Multi-image scene reconstruction with HunyuanWorld-Mirror 2.0.

    Every request bundles a full image set into a single reconstruction — the
    input array is treated as one rig, not iterated view-by-view.
    """
    config: WorldMirrorImageTo3DModelActionConfig

    def __init__(
        self,
        config: WorldMirrorImageTo3DModelActionConfig,
        pipeline: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.device: torch.device = device

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        images = await context.render_image_array(self.config.image, single_as_array=True)

        # A single scene arrives as one ImageArrayValue; a batch/stream of scenes
        # arrives as list/AsyncIterator of ImageArrayValues so the base
        # `run()` transpose feeds per-scene tuples into `_generate_batch`.
        is_single_input    = isinstance(images, ImageArrayValue)
        is_streaming_input = isinstance(images, (StreamIterator, AsyncIterator))

        return (images,), is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        target_size             = await context.render_scalar(self.config.params.target_size, int)
        apply_sky_mask          = await context.render_scalar(self.config.params.apply_sky_mask, bool)
        apply_edge_mask         = await context.render_scalar(self.config.params.apply_edge_mask, bool)
        apply_confidence_mask   = await context.render_scalar(self.config.params.apply_confidence_mask, bool)
        sky_mask_source         = await context.render_scalar(self.config.params.sky_mask_source, str)
        model_sky_threshold     = await context.render_scalar(self.config.params.model_sky_threshold, float)
        confidence_percentile   = await context.render_scalar(self.config.params.confidence_percentile, float)
        edge_normal_threshold   = await context.render_scalar(self.config.params.edge_normal_threshold, float)
        edge_depth_threshold    = await context.render_scalar(self.config.params.edge_depth_threshold, float)
        compress_pts            = await context.render_scalar(self.config.params.compress_pts, bool)
        compress_pts_max_points = await context.render_scalar(self.config.params.compress_pts_max_points, int)
        compress_pts_voxel_size = await context.render_scalar(self.config.params.compress_pts_voxel_size, float)
        compress_gs_max_points  = await context.render_scalar(self.config.params.compress_gs_max_points, int)
        max_resolution          = await context.render_scalar(self.config.params.max_resolution, int)
        prior_cameras           = await context.render_scalar(self.config.priors.cameras, str)
        prior_depths            = await context.render_scalar(self.config.priors.depths, str)
        return_gaussians        = await context.render_scalar(self.config.return_gaussians, bool)
        return_points           = await context.render_scalar(self.config.return_points, bool)
        return_cameras          = await context.render_scalar(self.config.return_cameras, bool)
        return_depth            = await context.render_scalar(self.config.return_depth, bool)
        return_normal           = await context.render_scalar(self.config.return_normal, bool)

        try:
            sky_mask_source = WorldMirrorSkyMaskSource(sky_mask_source)
        except ValueError:
            raise ValueError(f"Invalid sky_mask_source: {sky_mask_source}")

        if not any((return_gaussians, return_points, return_cameras, return_depth, return_normal)):
            raise ValueError("At least one of 'return_gaussians', 'return_points', 'return_cameras', 'return_depth', or 'return_normal' must be true.")

        params.update({
            "target_size":             target_size,
            "apply_sky_mask":          apply_sky_mask,
            "apply_edge_mask":         apply_edge_mask,
            "apply_confidence_mask":   apply_confidence_mask,
            "sky_mask_source":         sky_mask_source.value,
            "model_sky_threshold":     model_sky_threshold,
            "confidence_percentile":   confidence_percentile,
            "edge_normal_threshold":   edge_normal_threshold,
            "edge_depth_threshold":    edge_depth_threshold,
            "compress_pts":            compress_pts,
            "compress_pts_max_points": compress_pts_max_points,
            "compress_pts_voxel_size": compress_pts_voxel_size,
            "compress_gs_max_points":  compress_gs_max_points,
            "max_resolution":          max_resolution,
            "prior_cameras":           prior_cameras,
            "prior_depths":            prior_depths,
            "return_gaussians":        return_gaussians,
            "return_points":           return_points,
            "return_cameras":          return_cameras,
            "return_depth":            return_depth,
            "return_normal":           return_normal,
        })

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for (images,) in inputs:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break

            scene_images = await images.collect()

            def _run(scene_images: List[PILImage.Image] = scene_images) -> Dict[str, Any]:
                return self._render(scene_images, params)

            results.append(await self._run_in_executor(_run))

        return results

    def _render(self, images: List[PILImage.Image], params: Dict[str, Any]) -> Dict[str, Any]:
        input_dir  = tempfile.mkdtemp(prefix="world_mirror_in_")
        output_dir = tempfile.mkdtemp(prefix="world_mirror_out_")

        try:
            # WorldMirror only exposes a directory-based entry point; write each
            # image out to the input directory so the pipeline's glob-based
            # loader can pick them up in order.
            for index, image in enumerate(images):
                path = os.path.join(input_dir, f"view_{index:04d}.png")
                image.convert("RGBA" if image.mode == "RGBA" else "RGB").save(path, "PNG")

            self.pipeline(
                input_dir,
                strict_output_path=output_dir,
                target_size=params["target_size"],
                save_depth=params["return_depth"],
                save_normal=params["return_normal"],
                save_gs=params["return_gaussians"],
                save_camera=params["return_cameras"],
                save_points=params["return_points"],
                save_colmap=False,
                save_conf=False,
                save_sky_mask=False,
                apply_sky_mask=params["apply_sky_mask"],
                apply_edge_mask=params["apply_edge_mask"],
                apply_confidence_mask=params["apply_confidence_mask"],
                sky_mask_source=params["sky_mask_source"],
                model_sky_threshold=params["model_sky_threshold"],
                confidence_percentile=params["confidence_percentile"],
                edge_normal_threshold=params["edge_normal_threshold"],
                edge_depth_threshold=params["edge_depth_threshold"],
                compress_pts=params["compress_pts"],
                compress_pts_max_points=params["compress_pts_max_points"],
                compress_pts_voxel_size=params["compress_pts_voxel_size"],
                compress_gs_max_points=params["compress_gs_max_points"],
                max_resolution=params["max_resolution"],
                prior_cam_path=params["prior_cameras"],
                prior_depth_path=params["prior_depths"],
                save_rendered=False,
                log_time=False,
            )

            return self._build_reconstruction_result(output_dir, params)
        finally:
            shutil.rmtree(input_dir, ignore_errors=True)

    def _build_reconstruction_result(self, output_dir: str, params: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if params["return_gaussians"]:
            gaussians_path = os.path.join(output_dir, "gaussians.ply")

            if os.path.exists(gaussians_path):
                result["gaussians"] = Model3DStreamResource(
                    FileStreamResource(gaussians_path, auto_delete=True),
                    format="ply",
                    filename="gaussians.ply",
                )

        if params["return_points"]:
            points_path = os.path.join(output_dir, "points.ply")

            if os.path.exists(points_path):
                result["points"] = Model3DStreamResource(
                    FileStreamResource(points_path, auto_delete=True),
                    format="ply",
                    filename="points.ply",
                )

        if params["return_cameras"]:
            cameras_path = os.path.join(output_dir, "camera_params.json")

            if os.path.exists(cameras_path):
                with open(cameras_path) as f:
                    result["cameras"] = json.load(f)

        if params["return_depth"]:
            result["depth"] = self._collect_view_images(output_dir, "depth", "depth")

        if params["return_normal"]:
            result["normal"] = self._collect_view_images(output_dir, "normal", "normal")

        return result

    def _collect_view_images(self, output_dir: str, subdir: str, prefix: str) -> List[ImageStreamResource]:
        views_dir = os.path.join(output_dir, subdir)

        if not os.path.isdir(views_dir):
            return []

        filenames: List[str] = []

        for name in os.listdir(views_dir):
            if name.startswith(f"{prefix}_") and name.endswith(".png"):
                filenames.append(name)

        images: List[ImageStreamResource] = []

        for filename in sorted(filenames):
            images.append(ImageStreamResource(
                FileStreamResource(os.path.join(views_dir, filename), auto_delete=True),
                format="png",
                filename=filename,
            ))

        return images

class WorldMirrorImageTo3DTaskDriver(ModelTaskDriver):
    config: WorldMirrorImageTo3DModelComponentConfig

    def __init__(self, id: str, config: WorldMirrorImageTo3DModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # WorldMirror pins its own transformer stack (gsplat, FlashAttention,
        # navmesh extensions) and vendors CUDA extensions from source. Isolate
        # the model worker so those pins don't leak into the controller.
        self._require_isolated_runtime()

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch==2.7.1", "torchvision==0.22.1"),
            *flash_attn_requirements("torch==2.7.1", "flash-attn"),
            "diffusers==0.36.0",
            "transformers==5.2.0",
            "accelerate",
            "peft==0.18.1",
            "safetensors",
            "zim_anything",
            "tensorboard",
            "omegaconf",
            "einops",
            "kornia",
            "openai",
            "easydict",
            "scipy==1.14.1",
            "timm==1.0.11",
            "cupy==13.6.0",
            "Pillow",
            "imageio[ffmpeg]",
            "decord",
            "imagesize",
            "opencv-python==4.10.0.84",
            "matplotlib==3.10.3",
            "scikit-image==0.25.2",
            "ftfy",
            "regex",
            "trimesh",
            "plyfile",
            "open3d==0.18.0",
            "pycolmap==3.10.0",
            "torchmetrics",
            "loguru==0.7.3",
            "tqdm",
            "numpy==1.26.4",
            "onnxruntime",
            "huggingface_hub>=0.34.0,<1.0",
        ]

    async def _setup(self) -> None:
        # WorldMirror's setup.sh installs a custom gsplat variant and the
        # HunyuanWorld package tree; both build against torch and need
        # `--no-build-isolation`.
        pip_options: List[str] = [ "--no-build-isolation" ]

        if importlib.util.find_spec("gsplat") is None:
            await install_package_from_github(
                "gsplat",
                "https://github.com/Tencent-Hunyuan/HY-World-2.0.git",
                source_path="hyworld2/worldgen/third_party/gsplat_maskgaussian",
                pip_options=pip_options,
            )

        if importlib.util.find_spec("hyworld2") is None:
            await install_package_from_github(
                "hyworld2",
                "https://github.com/Tencent-Hunyuan/HY-World-2.0.git",
                subdirs=[ "hyworld2" ],
            )

    async def _load_model(self) -> None:
        self.pipeline, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Any, torch.device]:
        device = self._resolve_device(self.config.device)

        model_path = await self._provision_model(self.config.model, prefetch=True)

        disable_heads = [ head.value for head in self.config.disable_heads ] or None
        enable_bf16 = bool(self.config.enable_bf16)
        subfolder = self.config.subfolder

        def _load() -> Any:
            from hyworld2.worldrecon.pipeline import WorldMirrorPipeline

            return WorldMirrorPipeline.from_pretrained(
                model_path,
                subfolder=subfolder,
                enable_bf16=enable_bf16,
                disable_heads=disable_heads,
            )

        pipeline = await self._run_in_executor(_load)

        return pipeline, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await WorldMirrorImageTo3DTaskAction(
            action,
            self.pipeline,
            self.device,
        ).run(context)
