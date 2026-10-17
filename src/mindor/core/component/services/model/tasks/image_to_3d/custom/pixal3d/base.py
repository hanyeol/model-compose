from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.natten import natten_requirements
from mindor.core.foundation.package.flash_attn import flash_attn_requirements
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from .....base import ModelTaskDriver
import os, sys, platform

if TYPE_CHECKING:
    import torch

# Shared image-conditioning stage configs used by both SV and MV drivers. The
# MV feature extractor takes an extra `multiview_fusion` flag; that lives on
# the MV driver rather than here so this table remains a pure description of
# the four cascade stages.
_IMAGE_COND_STAGE_CONFIGS: Dict[str, Dict[str, Any]] = {
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

_IMAGE_COND_STAGE_ATTRS = (
    "image_cond_model_ss",
    "image_cond_model_shape_512",
    "image_cond_model_shape_1024",
    "image_cond_model_tex_1024",
)

class Pixal3DImageTo3DTaskBaseDriver(ModelTaskDriver):
    """Shared lifecycle for Pixal3D drivers.

    The single-view and multi-view flavours share setup, requirements, and the
    pipeline-loading skeleton; they diverge only in the concrete pipeline
    class, the feature-extractor class, and any extra state (SV loads MoGe for
    FOV estimation). Subclasses implement those as hooks.
    """
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # Pixal3D pins transformers 4.57.3, diffusers 0.37.1, kornia 0.8.2, timm
        # 1.0.22, trimesh 4.10.1 and installs two source-tree packages via
        # `install_package_from_github` (pixal3d, o_voxel). Refuse to run in the
        # controller's native environment — those pins and copies would either
        # clash with the mindor stack or leak into it.
        self._require_isolated_runtime()

        self.pipeline: Optional[Any] = None
        self.pipeline_type: Optional[str] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        torch_spec, natten_spec = self._get_torch_and_natten_specs()

        return [
            *torch_requirements(torch_spec, "torchvision"),
            *flash_attn_requirements(torch_spec, "flash-attn==2.8.3.post1"),
            *natten_requirements(torch_spec, natten_spec),
            "diffusers==0.37.1",
            "transformers==4.57.3",
            "accelerate==1.13.0",
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
            "einops",
            "utils3d@https://github.com/LDYang694/Storages/releases/download/20260430/utils3d-0.0.2-py3-none-any.whl",
            "moge@git+https://github.com/microsoft/MoGe.git",
            "huggingface_hub>=0.34.0,<1.0",
        ]

    def _get_torch_and_natten_specs(self) -> Tuple[str, str]:
        """Pick the torch / natten pins for this host.

        x86_64 keeps the stack the component was validated on (torch 2.7 +
        natten 0.21.0). natten publishes no aarch64 wheel below torch 2.9, and
        torch 2.7 itself is a poor fit on Linux aarch64 CUDA hosts such as DGX
        Spark (GB10, sm_121): its SDPA gate stops at sm_120, so every fused
        attention backend is refused and SDPA falls back to the math kernel; the
        bundled Triton's ptxas cannot target sm_121a; and its cu128 build forces
        a CUDA 12 toolkit next to the system CUDA 13 for the source-built
        extensions below. aarch64 therefore moves to torch 2.13 (cu130 on a CUDA
        13 driver) with natten 0.21.7, the first release whose cutlass-fna
        config selection is fixed for SM120/SM121 — every piece of which ships
        an aarch64 wheel, and whose Triton bundles a ptxas that knows sm_121.
        """
        if sys.platform == "linux" and platform.machine() == "aarch64":
            return "torch==2.13.*", "natten==0.21.7"

        return "torch==2.7.*", "natten==0.21.0"

    async def _setup(self) -> None:
        # Pixal3D leans on three CUDA-extension packages that are not on PyPI
        # and whose `setup.py` imports torch during the build (pip's isolated
        # build env has no torch, so `--no-build-isolation` is mandatory).
        # Install order matches TRELLIS.2's setup.sh: cuMesh + FlexGEMM +
        # o_voxel (all as buildable source trees), then the pure-Python pixal3d
        # package on top.
        pip_options: List[str] = [ "--no-build-isolation" ]

        if not is_package_installed("cumesh"):
            # CuMesh vendors `third_party/cubvh` as a git submodule; the tarball
            # fallback strips it, so `git` must be available for this to succeed.
            await install_package_from_github(
                "cumesh",
                "https://github.com/JeffreyXiang/CuMesh.git",
                revision="12289e1062f0",
                source_path=".",
                pip_options=pip_options,
            )

        if not is_package_installed("flex_gemm.ops.grid_sample"):
            # MoGe's pyproject.toml hard-pins flex_gemm to a `dev/all_triton` commit
            # that reorganises `ops.grid_sample` under `ops.sample`, but Pixal3D
            # imports the pre-rename layout (`flex_gemm.ops.grid_sample`). Detect the
            # wrong install by probing for that module and reinstall from FlexGEMM's
            # main branch when it's missing — pip's own upgrade heuristics won't
            # touch an already-satisfied `flex_gemm` requirement.
            await install_package_from_github(
                "flex_gemm",
                "https://github.com/JeffreyXiang/FlexGEMM.git",
                revision="6dd94a859c26",
                source_path=".",
                pip_options=[ *pip_options, "--force-reinstall", "--no-deps" ],
            )

        if not is_package_installed("nvdiffrast"):
            # o_voxel's postprocess.py imports `nvdiffrast.torch`; source-built
            # because upstream ships no wheels.
            await install_package_from_github(
                "nvdiffrast",
                "https://github.com/NVlabs/nvdiffrast.git",
                revision="253ac4fcea7d",
                source_path=".",
                pip_options=pip_options,
            )

        if not is_package_installed("o_voxel"):
            # TRELLIS.2's o-voxel lives one level down (`o-voxel/`) and needs a
            # full pip build for its CUDA kernels — the earlier tree-copy path
            # dropped a pure-Python shell that crashed at import time.
            await install_package_from_github(
                "trellis2",
                "https://github.com/microsoft/TRELLIS.2.git",
                revision="75fbf0183001",
                source_path="o-voxel",
                pip_options=pip_options,
            )

        if not is_package_installed("pixal3d"):
            # Pixal3D's `pixal3d/` is pure Python — keep the tree-copy path so
            # its top-level module lands next to `mindor` without invoking pip.
            await install_package_from_github(
                "pixal3d",
                "https://github.com/TencentARC/Pixal3D.git",
                revision="f7cf38429b0b",
                subdirs=[ "pixal3d" ],
            )

    async def _load_model(self) -> None:
        device = self._resolve_device(self.config.device)
        low_vram = bool(self.config.low_vram)

        self._configure_pipeline_env()

        model_path = await self._provision_model(self.config.model, prefetch=True)
        pipeline_type = self._resolve_pipeline_type(low_vram, self.config.resolution)

        def _load() -> Any:
            pipeline = self._load_pipeline(model_path)
            self._attach_image_cond_stages(pipeline)
            self._configure_pipeline_device(pipeline, device, low_vram)

            return pipeline

        self.pipeline = await self._run_in_executor(_load)
        self.pipeline_type = pipeline_type
        self.device = device

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.pipeline_type = None
        self.device = None

    def _configure_pipeline_env(self) -> None:
        """Prime the process-wide switches Pixal3D's inference scripts set up."""
        import pixal3d

        pixal3d_dir = os.path.dirname(pixal3d.__file__)

        os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        os.environ.setdefault("ATTN_BACKEND", "flash_attn")
        os.environ.setdefault("FLEX_GEMM_AUTOTUNE_CACHE_PATH", os.path.join(pixal3d_dir, "autotune_cache.json"))

    def _resolve_pipeline_type(self, low_vram: bool, resolution: Optional[int]) -> str:
        effective = resolution if resolution is not None else (1024 if low_vram else 1536)

        return f"{effective}_cascade"

    def _attach_image_cond_stages(self, pipeline: Any) -> None:
        for attr, stage_config in zip(_IMAGE_COND_STAGE_ATTRS, (
            _IMAGE_COND_STAGE_CONFIGS["ss"],
            _IMAGE_COND_STAGE_CONFIGS["shape_512"],
            _IMAGE_COND_STAGE_CONFIGS["shape_1024"],
            _IMAGE_COND_STAGE_CONFIGS["tex_1024"],
        )):
            setattr(pipeline, attr, self._build_image_conditioned_extractor(stage_config))

    def _configure_pipeline_device(self, pipeline: Any, device: torch.device, low_vram: bool) -> None:
        import torch

        if low_vram:
            for attr in _IMAGE_COND_STAGE_ATTRS:
                module = getattr(pipeline, attr, None)

                if module is not None and getattr(module, "use_naf_upsample", False):
                    module._load_naf()

            pipeline._device = torch.device(f"cuda:{device.index}" if device.index is not None else "cuda")
            pipeline.low_vram = True
        else:
            pipeline.low_vram = False
            pipeline.cuda()

            for attr in _IMAGE_COND_STAGE_ATTRS:
                module = getattr(pipeline, attr, None)

                if module is not None:
                    module.cuda()

                    if getattr(module, "use_naf_upsample", False):
                        module._load_naf()

    def _load_pipeline(self, model_path: str) -> Any:
        """Load the concrete Pixal3D pipeline class from `model_path`."""
        raise NotImplementedError

    def _build_image_conditioned_extractor(self, stage_config: Dict[str, Any]) -> Any:
        """Return an image-conditioning feature extractor for one cascade stage."""
        raise NotImplementedError
