from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import Hi3DImageTo3DModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, Hi3DImageTo3DModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.flash_attn import flash_attn_requirements
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.file import FileStreamResource
from ......action.media import MediaInputPathResolver
from mindor.core.utils.files import get_temporary_path
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageTo3DTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

class Hi3DImageTo3DTaskAction(ImageTo3DTaskAction):
    """Image-conditioned mesh refinement with Hi3D v1.0 (Sparc3D).

    Hi3D does not synthesize geometry from an image alone; each request pairs a
    reference image with a mesh produced upstream (any trimesh-readable format:
    GLB, OBJ, PLY, ...). The output is a geometry-only `trimesh.Trimesh`
    exported as GLB.
    """
    config: Hi3DImageTo3DModelActionConfig

    def __init__(
        self,
        config: Hi3DImageTo3DModelActionConfig,
        pipeline: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.device: torch.device = device

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        # Pair each image with its mesh as two zipped slots; the base transpose
        # feeds (image, mesh_source) tuples into `_generate_batch`, which does
        # the per-request path resolve.
        slots, primary_input, is_single_input, is_streaming_input = await super()._prepare_input(context)
        image = slots[0]

        mesh = await context.render_model_3d(self.config.mesh)

        return (image, mesh), primary_input, is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        resolution          = await context.render_scalar(self.config.params.resolution, int)
        num_inference_steps = await context.render_scalar(self.config.params.num_inference_steps, int)

        if resolution not in (512, 1024, 1536):
            raise ValueError(f"Hi3D 'resolution' must be one of 512, 1024, 1536; got {resolution}.")

        params.update({
            "resolution":          resolution,
            "num_inference_steps": num_inference_steps,
        })

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        results: List[Any] = []

        for (image, mesh) in inputs:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break

            if not isinstance(mesh, MediaSource):
                raise ValueError("Hi3D requires a 'mesh' value that resolves to a 3D model source.")

            mesh, _ = await MediaInputPathResolver().resolve(mesh, default_format=mesh.format)

            def _generate(image: PILImage.Image = image, mesh: str = mesh) -> Model3DStreamResource:
                return self._render(image, mesh, params)

            results.append(await self._run_in_executor(_generate))

        return results

    def _render(self, image: PILImage.Image, mesh_path: str, params: Dict[str, Any]) -> Model3DStreamResource:
        import trimesh

        mesh = trimesh.load(mesh_path, force="mesh", process=False)
        seed = params["seed"] if params["seed"] is not None else 0

        result = self.pipeline(
            image.convert("RGB"),
            mesh,
            resolution=params["resolution"],
            num_inference_steps=params["num_inference_steps"],
            seed=seed,
        )

        output_path = get_temporary_path("glb")
        result.mesh.export(output_path)

        return Model3DStreamResource(
            FileStreamResource(output_path, auto_delete=True),
            format="glb",
            filename="mesh.glb",
        )

class Hi3DImageTo3DTaskDriver(ModelTaskDriver):
    config: Hi3DImageTo3DModelComponentConfig

    def __init__(self, id: str, config: Hi3DImageTo3DModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # Hi3D pins torch==2.5.0+cu124, flash-attn==2.7.4.post1, and
        # spconv-cu120==2.3.6; isolate the model worker so those pins don't leak
        # into the controller's stack.
        self._require_isolated_runtime()

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch==2.5.0", "torchvision==0.20.0"),
            *flash_attn_requirements("torch==2.5.0", "flash-attn==2.7.4.post1"),
            "transformers>=4.44",
            "diffusers>=0.30",
            "accelerate",
            "safetensors",
            "huggingface_hub>=0.34.0,<1.0",
            "trimesh>=4.0",
            "numpy>=1.26,<2",
            "spconv-cu120==2.3.6",
            "einops",
            "omegaconf",
            "scipy",
            "Pillow",
        ]

    async def _setup(self) -> None:
        if not is_package_installed("sparc3d"):
            # Hi3D v1.0 ships its inference code as the `sparc3d` package in the
            # repository root; install it directly from the git tree with
            # `--no-build-isolation` because its setup imports torch at build
            # time.
            await install_package_from_github(
                "sparc3d",
                "https://github.com/hi3d-official/Hi3Dv1.0.git",
                source_path=".",
                pip_options=[ "--no-build-isolation" ],
            )

    async def _load_model(self) -> None:
        self.pipeline, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Any, torch.device]:
        # Hi3D's flow-matching stack and spconv kernels run on CUDA only (CC
        # 8.0+, CUDA 12.0–12.5). Fail loudly here rather than crash mid-run.
        device = self._resolve_device(self.config.device)

        if device.type != "cuda":
            raise RuntimeError(
                f"Component '{self.id}': Hi3D requires a CUDA device, "
                f"but resolved device is '{device.type}'. Set component.device to "
                "'cuda' or a specific 'cuda:N' index."
            )

        model_path = await self._provision_model(self.config.model, prefetch=True)

        def _load() -> Any:
            from sparc3d import Sparc3DPipeline

            return Sparc3DPipeline.from_pretrained(model_path).to(str(device))

        pipeline = await self._run_in_executor(_load)

        return pipeline, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Hi3DImageTo3DTaskAction(
            action,
            self.pipeline,
            self.device,
        ).run(context)
