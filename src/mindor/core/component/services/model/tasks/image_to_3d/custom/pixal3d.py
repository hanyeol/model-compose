from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, Pixal3DImageTo3DModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageTo3DTaskAction
from PIL import Image as PILImage
import os, math, tempfile, importlib.util

if TYPE_CHECKING:
    import torch

_MOGE_MODEL_REPO = "Ruicheng/moge-2-vitl"

_IMAGE_COND_CONFIGS: Dict[str, Dict[str, Any]] = {
    "ss": {
        "model_name":      "camenduru/dinov3-vitl16-pretrain-lvd1689m",
        "image_size":      512,
        "grid_resolution": 16,
    },
    "shape_512": {
        "model_name":       "camenduru/dinov3-vitl16-pretrain-lvd1689m",
        "image_size":       512,
        "grid_resolution":  32,
        "use_naf_upsample": True,
        "naf_target_size":  512,
    },
    "shape_1024": {
        "model_name":       "camenduru/dinov3-vitl16-pretrain-lvd1689m",
        "image_size":       1024,
        "grid_resolution":  64,
        "use_naf_upsample": True,
        "naf_target_size":  512,
    },
    "tex_1024": {
        "model_name":       "camenduru/dinov3-vitl16-pretrain-lvd1689m",
        "image_size":       1024,
        "grid_resolution":  64,
        "use_naf_upsample": True,
        "naf_target_size":  1024,
    },
}

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

        ss_sampling_steps            = await context.render_variable(self.config.params.ss_sampling_steps)
        ss_guidance_strength         = await context.render_variable(self.config.params.ss_guidance_strength)
        ss_guidance_rescale          = await context.render_variable(self.config.params.ss_guidance_rescale)
        ss_rescale_t                 = await context.render_variable(self.config.params.ss_rescale_t)
        shape_slat_sampling_steps    = await context.render_variable(self.config.params.shape_slat_sampling_steps)
        shape_slat_guidance_strength = await context.render_variable(self.config.params.shape_slat_guidance_strength)
        shape_slat_guidance_rescale  = await context.render_variable(self.config.params.shape_slat_guidance_rescale)
        shape_slat_rescale_t         = await context.render_variable(self.config.params.shape_slat_rescale_t)
        tex_slat_sampling_steps      = await context.render_variable(self.config.params.tex_slat_sampling_steps)
        tex_slat_guidance_strength   = await context.render_variable(self.config.params.tex_slat_guidance_strength)
        tex_slat_guidance_rescale    = await context.render_variable(self.config.params.tex_slat_guidance_rescale)
        tex_slat_rescale_t           = await context.render_variable(self.config.params.tex_slat_rescale_t)
        max_num_tokens               = await context.render_variable(self.config.params.max_num_tokens)
        manual_fov                   = await context.render_variable(self.config.params.manual_fov)
        extend_pixel                 = await context.render_variable(self.config.params.extend_pixel)
        texture_size                 = await context.render_variable(self.config.params.texture_size)
        decimation_target            = await context.render_variable(self.config.params.decimation_target)

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
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Model3DStreamResource]:
        def _generate() -> List[Model3DStreamResource]:
            results: List[Model3DStreamResource] = []

            for image in images:
                results.append(self._render(image, params))

            return results

        return await self._run_in_executor(_generate)

    def _render(self, image: PILImage.Image, params: Dict[str, Any]) -> Model3DStreamResource:
        import torch
        import numpy as np
        import o_voxel

        # Background removal + framing to the canonical Pixal3D input layout.
        preprocessed = self.pipeline.preprocess_image(image)

        image_resolution = int(params["image_resolution"])
        mesh_scale       = float(params["mesh_scale"])
        extend_pixel     = int(params["extend_pixel"])
        seed             = int(params["seed"]) if params["seed"] is not None else 42

        camera_params = self._resolve_camera_params(
            preprocessed,
            manual_fov=params["manual_fov"],
            image_resolution=image_resolution,
            mesh_scale=mesh_scale,
            extend_pixel=extend_pixel,
        )

        torch.manual_seed(seed)

        ss_sampler_override = {
            "steps":             int(params["ss_sampling_steps"]),
            "guidance_strength": float(params["ss_guidance_strength"]),
            "guidance_rescale":  float(params["ss_guidance_rescale"]),
            "rescale_t":         float(params["ss_rescale_t"]),
        }
        shape_sampler_override = {
            "steps":             int(params["shape_slat_sampling_steps"]),
            "guidance_strength": float(params["shape_slat_guidance_strength"]),
            "guidance_rescale":  float(params["shape_slat_guidance_rescale"]),
            "rescale_t":         float(params["shape_slat_rescale_t"]),
        }
        tex_sampler_override = {
            "steps":             int(params["tex_slat_sampling_steps"]),
            "guidance_strength": float(params["tex_slat_guidance_strength"]),
            "guidance_rescale":  float(params["tex_slat_guidance_rescale"]),
            "rescale_t":         float(params["tex_slat_rescale_t"]),
        }

        mesh_list, _ = self.pipeline.run(
            preprocessed,
            camera_params=camera_params,
            seed=seed,
            sparse_structure_sampler_params=ss_sampler_override,
            shape_slat_sampler_params=shape_sampler_override,
            tex_slat_sampler_params=tex_sampler_override,
            preprocess_image=False,
            return_latent=True,
            pipeline_type=self.pipeline_type,
            max_num_tokens=int(params["max_num_tokens"]),
        )

        mesh = mesh_list[0]
        glb = o_voxel.postprocess.to_glb(
            vertices=mesh.vertices,
            faces=mesh.faces,
            attr_volume=mesh.attrs,
            coords=mesh.coords,
            attr_layout=self.pipeline.pbr_attr_layout,
            grid_size=self._grid_size_from_pipeline_type(self.pipeline_type),
            aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
            decimation_target=int(params["decimation_target"]),
            texture_size=int(params["texture_size"]),
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

        return Model3DStreamResource(
            FileStreamResource(glb_path, auto_delete=True),
            format="glb",
        )

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
        xt, yt = float(target_point[0].item()), float(target_point[1].item())

        focal_length = 16.0 / torch.tan(torch.tensor(camera_angle_x / 2.0))
        f_pixels = float((focal_length * image_resolution / 32.0).item())

        x_ndc = xt - image_resolution / 2.0
        distance_x = f_pixels * xw / x_ndc - yw

        return float(distance_x)

    @staticmethod
    def _grid_size_from_pipeline_type(pipeline_type: str) -> int:
        # `pipeline_type` looks like "1024_cascade" or "1536_cascade" — the
        # numeric prefix is the target grid resolution used by o_voxel.to_glb.
        head = pipeline_type.split("_", 1)[0]
        return int(head)

class Pixal3DImageTo3DTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # Pixal3D pins transformers 4.57.3, diffusers 0.37.1, kornia 0.8.2, timm
        # 1.0.22, trimesh 4.10.1 and installs two source-tree packages via
        # `install_package_from_github` (pixal3d, o_voxel). Refuse to run in the
        # controller's native environment — those pins and copies would either
        # clash with the mindor stack or leak into it.
        self._require_isolated_runtime()

        self.pipeline: Optional[Any] = None
        self.moge_model: Optional[Any] = None
        self.pipeline_type: Optional[str] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        # `natten==0.21.0` builds against CUDA nvcc on install — the driver
        # refuses to load on non-CUDA hosts (see `_load_pipeline`), so requesting
        # the wheel here is safe even though the build itself may fail on
        # CPU-only machines.
        return [
            *torch_requirements("torch", "torchvision"),
            "diffusers==0.37.1",
            "transformers==4.57.3",
            "accelerate==1.13.0",
            "huggingface_hub",
            "safetensors",
            "sentencepiece",
            "kornia==0.8.2",
            "timm==1.0.22",
            "opencv-python-headless==4.12.0.88",
            "trimesh==4.10.1",
            "plyfile==1.1.3",
            "easydict==1.13",
            "zstandard==0.25.0",
            "imageio==2.37.2",
            "imageio-ffmpeg==0.6.0",
            "pillow==12.0.0",
            "tqdm==4.67.1",
            "natten==0.21.0",
            "moge@git+https://github.com/microsoft/MoGe.git",
        ]

    async def _setup(self) -> None:
        # `o_voxel` and `pixal3d` are not published to PyPI — install them by
        # copying the relevant subdirectories out of their GitHub source trees
        # into the mindor site-packages root. TRELLIS.2 stores the `o_voxel`
        # package one level down (`o-voxel/o_voxel/`), so pass the source path
        # explicitly. Pixal3D's `pixal3d/` package sits at the repo root.
        if importlib.util.find_spec("o_voxel") is None:
            await install_package_from_github(
                "o_voxel",
                "https://github.com/microsoft/TRELLIS.2.git",
                subdirs=[ ("o_voxel", "o-voxel/o_voxel") ],
            )

        if importlib.util.find_spec("pixal3d") is None:
            await install_package_from_github(
                "pixal3d",
                "https://github.com/TencentARC/Pixal3D.git",
                subdirs=[ "pixal3d" ],
            )

    async def _load_model(self) -> None:
        self.pipeline, self.moge_model, self.pipeline_type, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.moge_model = None
        self.pipeline_type = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Any, Any, str, torch.device]:
        # Pixal3D hardcodes `.cuda()` on every stage model and its FLEX_GEMM
        # autotuner writes into the pipeline's install directory; both make CPU
        # inference impossible today. Fail loudly here rather than let the
        # pipeline crash mid-generation with an opaque CUDA error.
        device = self._resolve_device(self.config.device)

        if device.type != "cuda":
            raise RuntimeError(
                f"Component '{self.id}': Pixal3D requires a CUDA device, "
                f"but resolved device is '{device.type}'. Set component.device to "
                "'cuda' or a specific 'cuda:N' index."
            )

        # Pixal3D's inference.py sets a handful of process-wide environment
        # switches before importing the pipeline. Do the same here so autotune
        # caches land next to the installed package rather than in whatever
        # cwd the controller happens to have.
        import pixal3d
        pixal3d_dir = os.path.dirname(pixal3d.__file__)
        os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        os.environ.setdefault("ATTN_BACKEND", "flash_attn")
        os.environ.setdefault(
            "FLEX_GEMM_AUTOTUNE_CACHE_PATH",
            os.path.join(pixal3d_dir, "autotune_cache.json"),
        )

        model_path = await self._provision_model(self.config.model, prefetch=True)

        low_vram = bool(self.config.low_vram)
        resolution = self.config.resolution if self.config.resolution is not None else (1024 if low_vram else 1536)
        pipeline_type = f"{resolution}_cascade"

        def _load() -> Tuple[Any, Any]:
            import torch
            from pixal3d.pipelines import Pixal3DImageTo3DPipeline
            from pixal3d.trainers.flow_matching.mixins.image_conditioned_proj import DinoV3ProjFeatureExtractor
            from moge.model.v2 import MoGeModel

            pipeline = Pixal3DImageTo3DPipeline.from_pretrained(model_path)

            for attr, config in (
                ("image_cond_model_ss",         _IMAGE_COND_CONFIGS["ss"]),
                ("image_cond_model_shape_512",  _IMAGE_COND_CONFIGS["shape_512"]),
                ("image_cond_model_shape_1024", _IMAGE_COND_CONFIGS["shape_1024"]),
                ("image_cond_model_tex_1024",   _IMAGE_COND_CONFIGS["tex_1024"]),
            ):
                setattr(pipeline, attr, DinoV3ProjFeatureExtractor(**config).eval())

            if low_vram:
                for attr in (
                    "image_cond_model_ss",
                    "image_cond_model_shape_512",
                    "image_cond_model_shape_1024",
                    "image_cond_model_tex_1024",
                ):
                    module = getattr(pipeline, attr, None)
                    if module is not None and getattr(module, "use_naf_upsample", False):
                        module._load_naf()

                pipeline._device = torch.device(f"cuda:{device.index}" if device.index is not None else "cuda")
                pipeline.low_vram = True
            else:
                pipeline.low_vram = False
                pipeline.cuda()
                for attr in (
                    "image_cond_model_ss",
                    "image_cond_model_shape_512",
                    "image_cond_model_shape_1024",
                    "image_cond_model_tex_1024",
                ):
                    module = getattr(pipeline, attr, None)
                    if module is not None:
                        module.cuda()
                        if getattr(module, "use_naf_upsample", False):
                            module._load_naf()

            moge_model = MoGeModel.from_pretrained(_MOGE_MODEL_REPO).to(device).eval()

            return pipeline, moge_model

        pipeline, moge_model = await self._run_in_executor(_load)

        return pipeline, moge_model, pipeline_type, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Pixal3DImageTo3DTaskAction(
            action,
            self.pipeline,
            self.moge_model,
            self.pipeline_type,
            self.device,
        ).run(context)
