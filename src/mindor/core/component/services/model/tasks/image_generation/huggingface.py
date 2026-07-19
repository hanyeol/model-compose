from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceImageGenerationModelActionConfig, ImageGenerationActionMethod
from mindor.dsl.schema.component import HuggingfaceImageGenerationModelArchitecture
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskService
from .common import ImageGenerationGenerateTaskAction, ImageGenerationInpaintTaskAction
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class PipelineCancelled(Exception):
    pass

class HuggingfaceImageGenerationGenerateTaskAction(ImageGenerationGenerateTaskAction):
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
        num_inference_steps   = await context.render_variable(self.config.params.num_inference_steps)
        width                 = await context.render_variable(self.config.params.width)
        height                = await context.render_variable(self.config.params.height)
        num_images_per_prompt = await context.render_variable(self.config.params.num_images_per_prompt)

        return {
            "num_inference_steps":   int(num_inference_steps),
            "width":                 int(width),
            "height":                int(height),
            "num_images_per_prompt": int(num_images_per_prompt),
        }

    async def _resolve_architecture_params(self, architecture: HuggingfaceImageGenerationModelArchitecture, context: ComponentActionContext) -> Dict[str, Any]:
        if architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            negative_prompt = await context.render_variable(self.config.params.negative_prompt)
            guidance_scale  = await context.render_variable(self.config.params.guidance_scale)

            return {
                "negative_prompt": negative_prompt,
                "guidance_scale":  float(guidance_scale),
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            guidance_scale      = await context.render_variable(self.config.params.guidance_scale)
            max_sequence_length = await context.render_variable(self.config.params.max_sequence_length)

            return {
                "guidance_scale":      float(guidance_scale),
                "max_sequence_length": int(max_sequence_length),
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE:
            negative_prompt          = await context.render_variable(self.config.params.negative_prompt)
            distilled_guidance_scale = await context.render_variable(self.config.params.distilled_guidance_scale)

            return {
                "negative_prompt":          negative_prompt,
                "distilled_guidance_scale": float(distilled_guidance_scale),
            }

        raise ValueError(f"Unknown architecture: {architecture}")

    def _generate(
        self,
        prompts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[PILImage.Image]:
        import torch

        generator: Optional[torch.Generator] = None

        if params["seed"] is not None:
            generator = torch.Generator(device=self.device).manual_seed(params["seed"])

        pipeline_params = params["pipeline"]

        if cancellation_token is not None:
            def _abort_if_cancelled(pipe, step, timestep, callback_kwargs):
                if cancellation_token.is_cancelled():
                    raise PipelineCancelled()
                return callback_kwargs
            pipeline_params = { **pipeline_params, "callback_on_step_end": _abort_if_cancelled }

        try:
            result = self.pipeline(
                prompt=prompts,
                generator=generator,
                **pipeline_params,
            )
        except PipelineCancelled:
            raise asyncio.CancelledError()

        return list(result.images)

class HuggingfaceImageGenerationInpaintTaskAction(ImageGenerationInpaintTaskAction):
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
        num_inference_steps   = await context.render_variable(self.config.params.num_inference_steps)
        width                 = await context.render_variable(self.config.params.width)
        height                = await context.render_variable(self.config.params.height)
        num_images_per_prompt = await context.render_variable(self.config.params.num_images_per_prompt)
        strength              = await context.render_variable(self.config.params.strength)

        return {
            "num_inference_steps":   int(num_inference_steps),
            "width":                 int(width),
            "height":                int(height),
            "num_images_per_prompt": int(num_images_per_prompt),
            "strength":              float(strength),
        }

    async def _resolve_architecture_params(self, architecture: HuggingfaceImageGenerationModelArchitecture, context: ComponentActionContext) -> Dict[str, Any]:
        if architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            negative_prompt = await context.render_variable(self.config.params.negative_prompt)
            guidance_scale  = await context.render_variable(self.config.params.guidance_scale)

            return {
                "negative_prompt": negative_prompt,
                "guidance_scale":  float(guidance_scale),
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            guidance_scale      = await context.render_variable(self.config.params.guidance_scale)
            max_sequence_length = await context.render_variable(self.config.params.max_sequence_length)

            return {
                "guidance_scale":      float(guidance_scale),
                "max_sequence_length": int(max_sequence_length),
            }

        raise ValueError(f"Inpainting is not supported for architecture: {architecture}")

    def _inpaint(
        self,
        prompts: List[str],
        images: List[PILImage.Image],
        mask_images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[PILImage.Image]:
        import torch

        generator: Optional[torch.Generator] = None

        if params["seed"] is not None:
            generator = torch.Generator(device=self.device).manual_seed(params["seed"])

        pipeline_params = params["pipeline"]

        if cancellation_token is not None:
            def _abort_if_cancelled(pipe, step, timestep, callback_kwargs):
                if cancellation_token.is_cancelled():
                    raise PipelineCancelled()
                return callback_kwargs
            pipeline_params = { **pipeline_params, "callback_on_step_end": _abort_if_cancelled }

        try:
            result = self.pipeline(
                prompt=prompts,
                image=images,
                mask_image=mask_images,
                generator=generator,
                **pipeline_params,
            )
        except PipelineCancelled:
            raise asyncio.CancelledError()

        return list(result.images)

@register_model_task_service(ModelTaskType.IMAGE_GENERATION, ModelDriver.HUGGINGFACE)
class HuggingfaceImageGenerationTaskService(HuggingfaceDiffusionPipelineTaskService[ImageGenerationActionMethod]):
    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "diffusers", "transformers", "accelerate", "sentencepiece", "torch" ]

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pipeline = self.pipelines.get(action.method)

        if pipeline is None:
            raise ValueError(f"No pipeline loaded for method: {action.method}")

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await HuggingfaceImageGenerationGenerateTaskAction(action, self.config.architecture, pipeline, self.device).run(context, loop)

        if action.method == ImageGenerationActionMethod.INPAINT:
            return await HuggingfaceImageGenerationInpaintTaskAction(action, self.config.architecture, pipeline, self.device).run(context, loop)

        raise ValueError(f"Unknown method: {action.method}")

    def _get_pipeline_class(self, method: Optional[ImageGenerationActionMethod]) -> Type[DiffusionPipeline]:
        if method is None or method == ImageGenerationActionMethod.GENERATE:
            if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
                from diffusers import StableDiffusionXLPipeline
                return StableDiffusionXLPipeline

            if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
                from diffusers import FluxPipeline
                return FluxPipeline

            if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE:
                from diffusers import HunyuanImagePipeline
                return HunyuanImagePipeline

        if method == ImageGenerationActionMethod.INPAINT:
            if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
                from diffusers import StableDiffusionXLInpaintPipeline
                return StableDiffusionXLInpaintPipeline

            if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
                from diffusers import FluxInpaintPipeline
                return FluxInpaintPipeline

            raise ValueError(f"Inpainting is not supported for architecture: {self.config.architecture}")

        raise ValueError(f"Unknown method '{method}' or architecture '{self.config.architecture}'.")

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch

        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            return torch.float16

        return torch.bfloat16
