from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from pathlib import Path
from mindor.dsl.schema.component import TripoSplatImageTo3DModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TripoSplatImageTo3DModelActionConfig, TripoSplatOutputFormat
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import is_package_installed, rewrite_python_imports, get_mindor_install_root
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.github import download_github_tarball
from mindor.core.utils.files import get_temporary_path
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageTo3DTaskAction
from PIL import Image as PILImage
import asyncio, importlib, os, shutil, tempfile

if TYPE_CHECKING:
    import torch

class TripoSplatImageTo3DTaskAction(ImageTo3DTaskAction):
    """Single-image to 3D Gaussian Splat generation with TripoSplat.

    The pipeline consumes one PIL image per request and returns a Gaussian
    object exportable as `.ply` or `.splat`. Background removal is bundled
    via BiRefNet, so RGB inputs with cluttered backgrounds are handled
    automatically.
    """
    config: TripoSplatImageTo3DModelActionConfig

    def __init__(
        self,
        config: TripoSplatImageTo3DModelActionConfig,
        pipeline: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.device: torch.device = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        steps          = await context.render_scalar(self.config.params.steps, int)
        guidance_scale = await context.render_scalar(self.config.params.guidance_scale, float)
        shift          = await context.render_scalar(self.config.params.shift, float)
        num_gaussians  = await context.render_scalar(self.config.params.num_gaussians, int)
        erode_radius   = await context.render_scalar(self.config.params.erode_radius, int)
        format         = await context.render_scalar(self.config.format, str)

        try:
            format = TripoSplatOutputFormat(format)
        except ValueError:
            raise ValueError(f"Invalid TripoSplat output format: {format}")

        if not 32768 <= num_gaussians <= 262144:
            raise ValueError(f"TripoSplat 'num_gaussians' must be in [32768, 262144]; got {num_gaussians}.")

        params.update({
            "steps":          steps,
            "guidance_scale": guidance_scale,
            "shift":          shift,
            "num_gaussians":  num_gaussians,
            "erode_radius":   erode_radius,
            "format":         format.value,
        })

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        def _generate() -> List[Model3DStreamResource]:
            return [ self._render(image, params) for (image,) in inputs ]

        return await self._run_in_executor(_generate)

    def _render(self, image: PILImage.Image, params: Dict[str, Any]) -> Model3DStreamResource:
        seed = params["seed"] if params["seed"] is not None else 42

        gaussian, _ = self.pipeline.run(
            image.convert("RGBA") if image.mode != "RGBA" else image,
            seed=seed,
            steps=params["steps"],
            guidance_scale=params["guidance_scale"],
            shift=params["shift"],
            num_gaussians=params["num_gaussians"],
            erode_radius=params["erode_radius"],
            show_progress=False,
        )

        format = params["format"]
        output_path = get_temporary_path(format)

        if format == TripoSplatOutputFormat.PLY.value:
            gaussian.save_ply(output_path)
        else:
            gaussian.save_splat(output_path)

        return Model3DStreamResource(
            FileStreamResource(output_path, auto_delete=True),
            format=format,
            filename=f"splat.{format}",
        )

class TripoSplatImageTo3DTaskDriver(ModelTaskDriver):
    config: TripoSplatImageTo3DModelComponentConfig

    def __init__(self, id: str, config: TripoSplatImageTo3DModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # TripoSplat's upstream only pins torch / torchvision versions via the
        # weight dtype choices (bf16 / fp16). Pin them conservatively, drop the
        # inference code next to `mindor` as `triposplat_pipeline/`, and keep
        # the model worker isolated so those pins can't drift the controller's
        # stack.
        self._require_isolated_runtime()

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch>=2.3", "torchvision>=0.18"),
            "numpy>=1.26,<2",
            "safetensors>=0.4",
            "Pillow",
            "tqdm",
            "huggingface_hub>=0.34.0,<1.0",
        ]

    async def _setup(self) -> None:
        if not is_package_installed("triposplat_pipeline"):
            await asyncio.get_running_loop().run_in_executor(None, self._install_triposplat_package)

    def _install_triposplat_package(self) -> None:
        # TripoSplat ships `triposplat.py` and `model.py` as bare top-level
        # files without `__init__.py` or packaging metadata, so
        # `install_package_from_github` can't pip-install it. Funnel both into
        # one `triposplat_pipeline/` package next to `mindor` — same approach
        # the FLOAT talking-head driver uses for its upstream.
        internal_modules = ("triposplat", "model")

        target = get_mindor_install_root() / "triposplat_pipeline"

        if target.exists():
            return

        clone_dir = Path(tempfile.gettempdir()) / "mindor-git-sources" / "triposplat_pipeline"

        if not clone_dir.exists():
            clone_dir.parent.mkdir(parents=True, exist_ok=True)

            # `_install_triposplat_package` already runs inside an executor
            # thread, so it has no event loop of its own — spin one up just
            # for the tarball fetch (which is the only async call here).
            asyncio.run(download_github_tarball(
                "https://github.com/VAST-AI-Research/TripoSplat.git",
                "main",
                clone_dir,
            ))

        target.mkdir(parents=True, exist_ok=False)
        (target / "__init__.py").write_text("", encoding="utf-8")

        for name in internal_modules:
            shutil.copy2(clone_dir / f"{name}.py", target / f"{name}.py")

        # `triposplat.py` imports `model` as a top-level module; rewrite it so
        # the copied `triposplat_pipeline.model` resolves inside the package.
        rewrite_python_imports(target, { name: f"triposplat_pipeline.{name}" for name in internal_modules })

        importlib.invalidate_caches()

    async def _load_model(self) -> None:
        self.pipeline, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Any, torch.device]:
        device = self._resolve_device(self.config.device)

        if device.type != "cuda":
            raise RuntimeError(
                f"Component '{self.id}': TripoSplat uses bfloat16 / fp16 weights and requires a CUDA device, "
                f"but resolved device is '{device.type}'. Set component.device to "
                "'cuda' or a specific 'cuda:N' index."
            )

        model_path = await self._provision_model(self.config.model, prefetch=True)

        def _load() -> Any:
            from triposplat_pipeline.triposplat import TripoSplatPipeline

            # Checkpoint subpaths inside the `VAST-AI/TripoSplat` HF repo.
            return TripoSplatPipeline(
                ckpt_path              = os.path.join(model_path, "diffusion_models/triposplat_fp16.safetensors"),
                decoder_path           = os.path.join(model_path, "vae/triposplat_vae_decoder_fp16.safetensors"),
                dinov3_path            = os.path.join(model_path, "clip_vision/dino_v3_vit_h.safetensors"),
                flux2_vae_encoder_path = os.path.join(model_path, "vae/flux2-vae.safetensors"),
                rmbg_path              = os.path.join(model_path, "background_removal/birefnet.safetensors"),
                device                 = str(device),
            )

        pipeline = await self._run_in_executor(_load)

        return pipeline, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await TripoSplatImageTo3DTaskAction(
            action,
            self.pipeline,
            self.device,
        ).run(context)
