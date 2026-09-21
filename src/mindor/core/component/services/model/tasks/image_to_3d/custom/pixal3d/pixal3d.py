from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import Pixal3DImageTo3DModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, Pixal3DImageTo3DModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from .....base import ComponentActionContext
from ...common import ImageTo3DTaskAction
from .base import Pixal3DImageTo3DTaskBaseDriver
from PIL import Image as PILImage
import os, math, tempfile

if TYPE_CHECKING:
    import torch

_MOGE_MODEL_REPO = "Ruicheng/moge-2-vitl"

class Pixal3DImageTo3DTaskAction(ImageTo3DTaskAction):
    config: Pixal3DImageTo3DModelActionConfig

    def __init__(
        self,
        config: Pixal3DImageTo3DModelActionConfig,
        pipeline: Any,
        moge_model: Any,
        pipeline_type: str,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.moge_model: Any = moge_model
        self.pipeline_type: str = pipeline_type
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        ss_sampling_steps            = await context.render_scalar(self.config.params.ss_sampling_steps, int)
        ss_guidance_strength         = await context.render_scalar(self.config.params.ss_guidance_strength, float)
        ss_guidance_rescale          = await context.render_scalar(self.config.params.ss_guidance_rescale, float)
        ss_rescale_t                 = await context.render_scalar(self.config.params.ss_rescale_t, float)
        shape_slat_sampling_steps    = await context.render_scalar(self.config.params.shape_slat_sampling_steps, int)
        shape_slat_guidance_strength = await context.render_scalar(self.config.params.shape_slat_guidance_strength, float)
        shape_slat_guidance_rescale  = await context.render_scalar(self.config.params.shape_slat_guidance_rescale, float)
        shape_slat_rescale_t         = await context.render_scalar(self.config.params.shape_slat_rescale_t, float)
        tex_slat_sampling_steps      = await context.render_scalar(self.config.params.tex_slat_sampling_steps, int)
        tex_slat_guidance_strength   = await context.render_scalar(self.config.params.tex_slat_guidance_strength, float)
        tex_slat_guidance_rescale    = await context.render_scalar(self.config.params.tex_slat_guidance_rescale, float)
        tex_slat_rescale_t           = await context.render_scalar(self.config.params.tex_slat_rescale_t, float)
        max_num_tokens               = await context.render_scalar(self.config.params.max_num_tokens, int)
        manual_fov                   = await context.render_scalar(self.config.params.manual_fov, float)
        extend_pixel                 = await context.render_scalar(self.config.params.extend_pixel, int)
        texture_size                 = await context.render_scalar(self.config.params.texture_size, int)
        decimation_target            = await context.render_scalar(self.config.params.decimation_target, int)

        params.update({
            "ss_sampling_steps":            ss_sampling_steps,
            "ss_guidance_strength":         ss_guidance_strength,
            "ss_guidance_rescale":          ss_guidance_rescale,
            "ss_rescale_t":                 ss_rescale_t,
            "shape_slat_sampling_steps":    shape_slat_sampling_steps,
            "shape_slat_guidance_strength": shape_slat_guidance_strength,
            "shape_slat_guidance_rescale":  shape_slat_guidance_rescale,
            "shape_slat_rescale_t":         shape_slat_rescale_t,
            "tex_slat_sampling_steps":      tex_slat_sampling_steps,
            "tex_slat_guidance_strength":   tex_slat_guidance_strength,
            "tex_slat_guidance_rescale":    tex_slat_guidance_rescale,
            "tex_slat_rescale_t":           tex_slat_rescale_t,
            "max_num_tokens":               max_num_tokens,
            "manual_fov":                   manual_fov,
            "extend_pixel":                 extend_pixel,
            "texture_size":                 texture_size,
            "decimation_target":            decimation_target,
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

    def _render(self, image: PILImage.Image, params: Dict[str, Any]) -> Model3DStreamResource:
        import numpy as np
        import torch
        import o_voxel

        # Background removal + framing to the canonical Pixal3D input layout.
        preprocessed_image = self.pipeline.preprocess_image(image)

        seed = params["seed"] if params["seed"] is not None else 42

        camera_params = self._resolve_camera_params(
            preprocessed_image,
            manual_fov=params["manual_fov"],
            image_resolution=params["image_resolution"],
            mesh_scale=params["mesh_scale"],
            extend_pixel=params["extend_pixel"],
        )

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
        mesh_list, (_, _, grid_size) = self.pipeline.run(
            preprocessed_image,
            camera_params=camera_params,
            seed=seed,
            sparse_structure_sampler_params=ss_sampler_override,
            shape_slat_sampler_params=shape_sampler_override,
            tex_slat_sampler_params=tex_sampler_override,
            preprocess_image=False,
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

        # Pixal3D emits meshes in a rotated basis; align to the +Y-up / +Z-forward
        # convention expected by trimesh / glTF viewers.
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

    def _resolve_camera_params(
        self,
        image: PILImage.Image,
        manual_fov: Optional[float],
        image_resolution: int,
        mesh_scale: float,
        extend_pixel: int,
    ) -> Dict[str, float]:
        import torch

        if manual_fov is not None and float(manual_fov) > 0:
            camera_angle_x = float(manual_fov)
        else:
            camera_angle_x = self._estimate_fov_via_moge(image)

        distance = self._distance_from_fov(
            camera_angle_x=camera_angle_x,
            grid_point=torch.tensor([-1.0, 0.0, 0.0]),
            target_point=torch.tensor([0 - extend_pixel, image_resolution - 1 + extend_pixel]),
            mesh_scale=mesh_scale,
            image_resolution=image_resolution,
        )

        return {
            "camera_angle_x": camera_angle_x,
            "distance":       distance,
            "mesh_scale":     mesh_scale,
        }

    def _estimate_fov_via_moge(self, image: PILImage.Image) -> float:
        import torch
        import numpy as np

        pil_rgb = image.convert("RGB")
        width, height = pil_rgb.size
        image_np = np.array(pil_rgb).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_np).permute(2, 0, 1).to(self.device)

        with torch.no_grad():
            output = self.moge_model.infer(image_tensor)

        intrinsics = output["intrinsics"].squeeze().cpu().numpy()
        fx_normalized = intrinsics[0, 0]
        fx = fx_normalized * width

        return 2 * math.atan(width / (2 * fx))

    @staticmethod
    def _distance_from_fov(
        camera_angle_x: float,
        grid_point: Any,
        target_point: Any,
        mesh_scale: float,
        image_resolution: int,
    ) -> float:
        import torch

        rotation_matrix = torch.tensor([
            [1.0, 0.0,  0.0],
            [0.0, 0.0, -1.0],
            [0.0, 1.0,  0.0],
        ])
        gp = grid_point.to(torch.float32) @ rotation_matrix.T
        gp = gp / mesh_scale / 2
        xw, yw = gp[0].item(), gp[1].item()
        xt = float(target_point[0].item())

        focal_length = 16.0 / torch.tan(torch.tensor(camera_angle_x / 2.0))
        f_pixels = float((focal_length * image_resolution / 32.0).item())

        x_ndc = xt - image_resolution / 2.0
        distance_x = f_pixels * xw / x_ndc - yw

        return float(distance_x)

class Pixal3DImageTo3DTaskDriver(Pixal3DImageTo3DTaskBaseDriver):
    config: Pixal3DImageTo3DModelComponentConfig

    def __init__(self, id: str, config: Pixal3DImageTo3DModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.moge_model: Optional[Any] = None

    async def _load_model(self) -> None:
        await super()._load_model()

        # MoGe estimates the input image's camera FOV when the user leaves
        # `manual_fov` unset; it's SV-specific because MV inputs carry their
        # own transform matrices.
        def _load() -> Any:
            from moge.model.v2 import MoGeModel
            return MoGeModel.from_pretrained(_MOGE_MODEL_REPO).to(self.device).eval()

        self.moge_model = await self._run_in_executor(_load)

    async def _unload_model(self) -> None:
        await super()._unload_model()

        self.moge_model = None

    def _load_pipeline(self, model_path: str) -> Any:
        from pixal3d.pipelines import Pixal3DImageTo3DPipeline
        return Pixal3DImageTo3DPipeline.from_pretrained(model_path)

    def _build_image_conditioned_extractor(self, stage_config: Dict[str, Any]) -> Any:
        from pixal3d.trainers.flow_matching.mixins.image_conditioned_proj import DinoV3ProjFeatureExtractor
        return DinoV3ProjFeatureExtractor(**stage_config).eval()

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Pixal3DImageTo3DTaskAction(
            action,
            self.pipeline,
            self.moge_model,
            self.pipeline_type,
            self.device,
        ).run(context)
