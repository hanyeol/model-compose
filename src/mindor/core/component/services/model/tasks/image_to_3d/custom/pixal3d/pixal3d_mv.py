from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import Pixal3DMultiViewImageTo3DModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, Pixal3DMultiViewImageTo3DModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.variable.array import ArrayValue
from .....base import ComponentActionContext
from ...common import ImageTo3DTaskAction
from .base import Pixal3DImageTo3DTaskBaseDriver
from PIL import Image as PILImage
import os, tempfile

if TYPE_CHECKING:
    import torch

class Pixal3DMultiViewImageTo3DTaskAction(ImageTo3DTaskAction):
    """Multi-view Pixal3D inference: N posed views collapse into a single GLB.

    Every request bundles a full view rig — image, transform_matrix and
    camera_angle_x are per-view arrays. `_prepare_input` packs the rig-level
    arrays as ArrayValues so `BatchSourceIterator` treats each rig as a single
    element rather than iterating its views.
    """
    config: Pixal3DMultiViewImageTo3DModelActionConfig

    def __init__(
        self,
        config: Pixal3DMultiViewImageTo3DModelActionConfig,
        pipeline: Any,
        pipeline_type: str,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.pipeline_type: str = pipeline_type
        self.device: torch.device = device

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        images         = await context.render_image_array(self.config.image, single_as_array=True)
        transforms     = await context.render_array(self.config.transform_matrix, single_as_array=True)
        camera_angle_x = await context.render_variable(self.config.camera_angle_x)
        mesh_scale     = await context.render_scalar(self.config.mesh_scale, float)

        # A single rig arrives as one ArrayValue; a batch/stream of rigs arrives
        # as list/AsyncIterator of ArrayValues. That distinction feeds the base
        # `run()` transpose so per-rig tuples reach `_generate_batch`.
        is_single_input    = isinstance(images, ImageArrayValue)
        is_streaming_input = isinstance(images, (StreamIterator, AsyncIterator))

        return (images, transforms, camera_angle_x, mesh_scale), is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        params.update({
            "ss_sampling_steps":            await context.render_scalar(self.config.params.ss_sampling_steps, int),
            "ss_guidance_strength":         await context.render_scalar(self.config.params.ss_guidance_strength, float),
            "ss_guidance_rescale":          await context.render_scalar(self.config.params.ss_guidance_rescale, float),
            "ss_rescale_t":                 await context.render_scalar(self.config.params.ss_rescale_t, float),
            "shape_slat_sampling_steps":    await context.render_scalar(self.config.params.shape_slat_sampling_steps, int),
            "shape_slat_guidance_strength": await context.render_scalar(self.config.params.shape_slat_guidance_strength, float),
            "shape_slat_guidance_rescale":  await context.render_scalar(self.config.params.shape_slat_guidance_rescale, float),
            "shape_slat_rescale_t":         await context.render_scalar(self.config.params.shape_slat_rescale_t, float),
            "tex_slat_sampling_steps":      await context.render_scalar(self.config.params.tex_slat_sampling_steps, int),
            "tex_slat_guidance_strength":   await context.render_scalar(self.config.params.tex_slat_guidance_strength, float),
            "tex_slat_guidance_rescale":    await context.render_scalar(self.config.params.tex_slat_guidance_rescale, float),
            "tex_slat_rescale_t":           await context.render_scalar(self.config.params.tex_slat_rescale_t, float),
            "max_num_tokens":               await context.render_scalar(self.config.params.max_num_tokens, int),
            "texture_size":                 await context.render_scalar(self.config.params.texture_size, int),
            "decimation_target":            await context.render_scalar(self.config.params.decimation_target, int),
        })

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Model3DStreamResource]:
        results: List[Model3DStreamResource] = []

        for images, transforms, camera_angle_x, mesh_scale in inputs:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break

            rig_images     = await self._collect_images(images)
            rig_transforms = await self._collect_transforms(transforms)
            rig_angles     = self._resolve_view_angles(camera_angle_x, view_count=len(rig_images))
            rig_scale      = mesh_scale if mesh_scale is not None else 1.0

            if len(rig_transforms) != len(rig_images):
                raise ValueError(
                    f"transform_matrix count ({len(rig_transforms)}) must match image count ({len(rig_images)}).",
                )

            def _run(
                images: List[PILImage.Image] = rig_images,
                transforms: List[List[List[float]]] = rig_transforms,
                angles: List[float] = rig_angles,
                scale: float = rig_scale,
            ) -> Model3DStreamResource:
                return self._render(images, transforms, angles, scale, params)

            results.append(await self._run_in_executor(_run))

        return results

    async def _collect_images(self, images: Any) -> List[PILImage.Image]:
        if isinstance(images, ImageArrayValue):
            return await images.collect()

        raise ValueError(f"`image` must resolve to an image array; got {type(images).__name__}.")

    async def _collect_transforms(self, transforms: Any) -> List[List[List[float]]]:
        if not isinstance(transforms, ArrayValue):
            raise ValueError(f"`transform_matrix` must resolve to an array; got {type(transforms).__name__}.")

        matrices: List[List[List[float]]] = []

        async for entry in transforms:
            if not isinstance(entry, list) or len(entry) != 4:
                raise ValueError(f"Each `transform_matrix` entry must be a 4x4 nested list; got {entry!r}.")

            matrices.append([ [ float(v) for v in row ] for row in entry ])

        return matrices

    @staticmethod
    def _resolve_view_angles(camera_angle_x: Any, view_count: int) -> List[float]:
        if camera_angle_x is None:
            raise ValueError("`camera_angle_x` must be provided as a scalar or a list matching `image` length.")

        if isinstance(camera_angle_x, list):
            if len(camera_angle_x) != view_count:
                raise ValueError(f"camera_angle_x list length ({len(camera_angle_x)}) must match image count ({view_count}).")
            return [ float(v) for v in camera_angle_x ]

        return [ float(camera_angle_x) ] * view_count

    def _render(
        self,
        images: List[PILImage.Image],
        transforms: List[List[List[float]]],
        camera_angles_x: List[float],
        mesh_scale: float,
        params: Dict[str, Any],
    ) -> Model3DStreamResource:
        import torch
        import numpy as np
        import o_voxel

        seed = params["seed"] if params["seed"] is not None else 42

        views_bundle = self._build_views_bundle(images, transforms, camera_angles_x, mesh_scale)

        ss_sampler_override = {
            "steps":             params["ss_sampling_steps"],
            "guidance_strength": params["ss_guidance_strength"],
            "guidance_rescale":  params["ss_guidance_rescale"],
            "rescale_t":         params["ss_rescale_t"],
        }
        shape_sampler_override = {
            "steps":             params["shape_slat_sampling_steps"],
            "guidance_strength": params["shape_slat_guidance_strength"],
            "guidance_rescale":  params["shape_slat_guidance_rescale"],
            "rescale_t":         params["shape_slat_rescale_t"],
        }
        tex_sampler_override = {
            "steps":             params["tex_slat_sampling_steps"],
            "guidance_strength": params["tex_slat_guidance_strength"],
            "guidance_rescale":  params["tex_slat_guidance_rescale"],
            "rescale_t":         params["tex_slat_rescale_t"],
        }

        torch.manual_seed(seed)
        mesh_list, (_, _, grid_size) = self.pipeline.run_mv(
            views_bundle,
            seed=seed,
            sparse_structure_sampler_params=ss_sampler_override,
            shape_slat_sampler_params=shape_sampler_override,
            tex_slat_sampler_params=tex_sampler_override,
            return_latent=True,
            pipeline_type=self.pipeline_type,
            max_num_tokens=params["max_num_tokens"],
        )

        mesh = mesh_list[0]
        glb = o_voxel.postprocess.to_glb(
            vertices=mesh.vertices,
            faces=mesh.faces,
            attr_volume=mesh.attrs,
            coords=mesh.coords,
            attr_layout=self.pipeline.pbr_attr_layout,
            grid_size=grid_size,
            aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
            decimation_target=params["decimation_target"],
            texture_size=params["texture_size"],
            remesh=True,
            remesh_band=1,
            remesh_project=0,
            use_tqdm=False,
        )

        rotation = np.array([
            [-1,  0,  0,  0],
            [ 0,  0, -1,  0],
            [ 0, -1,  0,  0],
            [ 0,  0,  0,  1],
        ], dtype=np.float64)
        glb.apply_transform(rotation)

        fd, glb_path = tempfile.mkstemp(suffix=".glb")
        os.close(fd)

        glb.export(glb_path, extension_webp=True)

        return Model3DStreamResource(FileStreamResource(glb_path, auto_delete=True), format="glb")

    def _build_views_bundle(
        self,
        images: List[PILImage.Image],
        transforms: List[List[List[float]]],
        camera_angles_x: List[float],
        mesh_scale: float,
    ) -> Dict[str, Any]:
        """Assemble the bundle Pixal3DMVImageTo3DPipeline.run_mv expects.

        Mirrors `inference_mv.load_views`: images are matted (via the pipeline's
        rembg model when alpha is missing), premultiplied by alpha, and stacked
        at both stage resolutions (512, 1024). Camera_distance is derived from
        the translation part of each c2w matrix to avoid the "radius" desync
        the upstream script warns about.
        """
        import torch

        rgba_views = [ self._ensure_rgba(image) for image in images ]

        images_tensor = {
            size: torch.stack([ self._to_cond_tensor(view, size) for view in rgba_views ], dim=0)[None]
            for size in (512, 1024)
        }

        transform_tensor = torch.tensor(transforms, dtype=torch.float32)[None]  # [1, V, 4, 4]
        camera_angle_x_tensor = torch.tensor(camera_angles_x, dtype=torch.float32)[None]  # [1, V]
        camera_distance = torch.norm(transform_tensor[:, :, :3, 3], dim=-1)  # [1, V]

        return {
            "images":           images_tensor,
            "camera_angle_x":   camera_angle_x_tensor,
            "camera_distance":  camera_distance,
            "transform_matrix": transform_tensor,
            "mesh_scale":       mesh_scale,
            "view_names":       [ f"view_{i:02d}" for i in range(len(images)) ],
        }

    def _ensure_rgba(self, image: PILImage.Image) -> PILImage.Image:
        import numpy as np

        if image.mode == "RGBA":
            alpha = np.array(image.getchannel(3))

            if not np.all(alpha == 255):
                return image.convert("RGBA")

        matted = self.pipeline.rembg_model(image.convert("RGB"))

        return matted.convert("RGBA")

    def _to_cond_tensor(self, image: PILImage.Image, image_size: int) -> "torch.Tensor":
        import torch
        import numpy as np

        resized = image.resize((image_size, image_size), PILImage.Resampling.LANCZOS)
        alpha = torch.tensor(np.array(resized.getchannel(3))).float() / 255.0
        rgb = torch.tensor(np.array(resized.convert("RGB"))).permute(2, 0, 1).float() / 255.0

        return rgb * alpha.unsqueeze(0)

class Pixal3DMultiViewImageTo3DTaskDriver(Pixal3DImageTo3DTaskBaseDriver):
    config: Pixal3DMultiViewImageTo3DModelComponentConfig

    def _load_pipeline(self, model_path: str) -> Any:
        # The multi-view checkpoints ship in the same HF repo but under
        # `ckpts/*_mv`; the pipeline picks them up via `pipeline_mv.json`.
        from pixal3d.pipelines import Pixal3DMVImageTo3DPipeline
        return Pixal3DMVImageTo3DPipeline.from_pretrained(model_path, "pipeline_mv.json")

    def _build_image_conditioned_extractor(self, stage_config: Dict[str, Any]) -> Any:
        # Multi-view fusion is fixed to "average" so the fused feature shape
        # matches the single-view denoisers; see inference_mv.IMAGE_COND_CONFIGS.
        from pixal3d.trainers.flow_matching.mixins.image_conditioned_proj import DinoV3ProjMultiViewFeatureExtractor
        return DinoV3ProjMultiViewFeatureExtractor(**stage_config, multiview_fusion="average").eval()

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Pixal3DMultiViewImageTo3DTaskAction(
            action,
            self.pipeline,
            self.pipeline_type,
            self.device,
        ).run(context)
