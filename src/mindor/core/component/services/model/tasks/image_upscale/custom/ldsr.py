from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, LdsrImageUpscaleModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext
from ....base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskService
from ..common import ImageUpscaleTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline, LDMSuperResolutionPipeline
    import torch

class LdsrImageUpscaleTaskAction(ImageUpscaleTaskAction):
    config: LdsrImageUpscaleModelActionConfig

    def __init__(
        self,
        config: LdsrImageUpscaleModelActionConfig,
        pipeline: LDMSuperResolutionPipeline,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.pipeline: LDMSuperResolutionPipeline = pipeline

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        num_inference_steps = await context.render_variable(self.config.params.num_inference_steps)
        eta                 = await context.render_variable(self.config.params.eta)
        downsample_method   = await context.render_variable(self.config.params.downsample_method)
        seed                = await context.render_variable(self.config.params.seed) if self.config.params.seed is not None else None

        params.update({
            "num_inference_steps": int(num_inference_steps),
            "eta":                 float(eta),
            "downsample_method":   downsample_method,
            "seed":                int(seed) if seed is not None else None,
        })

        return params

    async def _upscale_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        def _upscale() -> List[PILImage.Image]:
            import torch

            generator: Optional[torch.Generator] = None

            _images = images
            if params["downsample_method"] is not None:
                _images = [ self._downsample_image(image, params["downsample_method"]) for image in _images ]

            if params["seed"] is not None:
                generator = torch.Generator(device=self.device).manual_seed(params["seed"])

            results: List[PILImage.Image] = []

            for image in _images:
                result = self.pipeline(
                    image=image,
                    num_inference_steps=params["num_inference_steps"],
                    eta=params["eta"],
                    generator=generator,
                )
                results.append(result.images[0])

            return results

        return await self._run_in_executor(_upscale)

class LdsrImageUpscaleTaskService(HuggingfaceDiffusionPipelineTaskService[None]):
    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "diffusers", "transformers", "accelerate", "torch" ]

    def _get_pipeline_class(self, method: None) -> Type[DiffusionPipeline]:
        from diffusers import LDMSuperResolutionPipeline
        return LDMSuperResolutionPipeline

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch
        return torch.float16

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await LdsrImageUpscaleTaskAction(action, self.pipelines[None], self.device).run(context)
