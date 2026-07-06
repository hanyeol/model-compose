from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceImageGenerationModelActionConfig, ImageGenerationActionMethod
from mindor.dsl.schema.component import HuggingfaceImageGenerationModelArchitecture
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskService
from .common import ImageGenerationTaskAction
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class HuggingfaceImageGenerationTaskAction(ImageGenerationTaskAction):
    config: HuggingfaceImageGenerationModelActionConfig

    def __init__(
        self,
        config: HuggingfaceImageGenerationModelActionConfig,
        architecture: HuggingfaceImageGenerationModelArchitecture,
        pipeline: DiffusionPipeline,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.architecture: HuggingfaceImageGenerationModelArchitecture = architecture
        self.pipeline: DiffusionPipeline = pipeline

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        pipeline_params: Dict[str, Any] = await self._resolve_pipeline_params(context)
        pipeline_params.update(await self._resolve_architecture_params(self.architecture, context))

        seed = await context.render_variable(self.config.params.seed)

        params["pipeline"] = pipeline_params
        params["seed"] = int(seed) if seed is not None else None

        return params

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_inference_steps   = int(await context.render_variable(self.config.params.num_inference_steps))
        width                 = int(await context.render_variable(self.config.params.width))
        height                = int(await context.render_variable(self.config.params.height))
        num_images_per_prompt = int(await context.render_variable(self.config.params.num_images_per_prompt))

        return {
            "num_inference_steps":   num_inference_steps,
            "width":                 width,
            "height":                height,
            "num_images_per_prompt": num_images_per_prompt,
        }

    async def _resolve_architecture_params(self, architecture: HuggingfaceImageGenerationModelArchitecture, context: ComponentActionContext) -> Dict[str, Any]:
        if architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            negative_prompt = await context.render_variable(self.config.params.negative_prompt)
            guidance_scale  = float(await context.render_variable(self.config.params.guidance_scale))

            return {
                "negative_prompt": negative_prompt,
                "guidance_scale":  guidance_scale,
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            guidance_scale      = float(await context.render_variable(self.config.params.guidance_scale))
            max_sequence_length = int(await context.render_variable(self.config.params.max_sequence_length))

            return {
                "guidance_scale":      guidance_scale,
                "max_sequence_length": max_sequence_length,
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE:
            negative_prompt          = await context.render_variable(self.config.params.negative_prompt)
            distilled_guidance_scale = float(await context.render_variable(self.config.params.distilled_guidance_scale))

            return {
                "negative_prompt":          negative_prompt,
                "distilled_guidance_scale": distilled_guidance_scale,
            }

        raise ValueError(f"Unknown architecture: {architecture}")

    async def _generate(self, prompts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[PILImage.Image]:
        return await loop.run_in_executor(None, self._generate_batch, prompts, params)

    def _generate_batch(self, prompts: List[str], params: Dict[str, Any]) -> List[PILImage.Image]:
        import torch

        generator: Optional[torch.Generator] = None

        if params["seed"] is not None:
            generator = torch.Generator(device=self.device).manual_seed(params["seed"])

        result = self.pipeline(
            prompt=prompts,
            generator=generator,
            **params["pipeline"],
        )

        return list(result.images)

@register_model_task_service(ModelTaskType.IMAGE_GENERATION, ModelDriver.HUGGINGFACE)
class HuggingfaceImageGenerationTaskService(HuggingfaceDiffusionPipelineTaskService):
    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "diffusers", "transformers", "accelerate", "sentencepiece", "torch" ]

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        if action.method == ImageGenerationActionMethod.GENERATE:
            return await HuggingfaceImageGenerationTaskAction(action, self.config.architecture, self.pipeline, self.device).run(context, loop)

        raise ValueError(f"Unknown method: {action.method}")

    def _get_pipeline_class(self) -> Type[DiffusionPipeline]:
        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            from diffusers import StableDiffusionXLPipeline
            return StableDiffusionXLPipeline

        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            from diffusers import FluxPipeline
            return FluxPipeline

        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE:
            from diffusers import HunyuanImagePipeline
            return HunyuanImagePipeline

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch

        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            return torch.float16

        return torch.bfloat16
