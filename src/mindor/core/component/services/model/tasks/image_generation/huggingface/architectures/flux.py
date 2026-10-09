from __future__ import annotations
from typing import TYPE_CHECKING, Type, Optional, Dict, List, Any

from mindor.dsl.schema.action import ModelActionConfig, ImageGenerationActionMethod
from .....base import ComponentActionContext
from ..base import (
    HuggingfaceImageGenerationGenerateTaskAction,
    HuggingfaceImageGenerationInpaintTaskAction,
    HuggingfaceImageGenerationBaseDriver,
)

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class FluxHuggingfaceImageGenerationGenerateTaskAction(HuggingfaceImageGenerationGenerateTaskAction):
    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        guidance_scale      = await context.render_scalar(self.config.params.guidance_scale, float)
        max_sequence_length = await context.render_scalar(self.config.params.max_sequence_length, int)

        params.update({
            "guidance_scale":      guidance_scale,
            "max_sequence_length": max_sequence_length,
        })

        return params

class FluxHuggingfaceImageGenerationInpaintTaskAction(HuggingfaceImageGenerationInpaintTaskAction):
    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        guidance_scale      = await context.render_variable(self.config.params.guidance_scale)
        max_sequence_length = await context.render_variable(self.config.params.max_sequence_length)

        params.update({
            "guidance_scale":      float(guidance_scale),
            "max_sequence_length": int(max_sequence_length),
        })

        return params

class FluxHuggingfaceImageGenerationTaskDriver(HuggingfaceImageGenerationBaseDriver):
    def _get_pipeline_class(self, method: Optional[ImageGenerationActionMethod]) -> Type[DiffusionPipeline]:
        if method is None or method == ImageGenerationActionMethod.GENERATE:
            if self._get_controlnet_count() > 0:
                from diffusers import FluxControlNetPipeline
                return FluxControlNetPipeline
            from diffusers import FluxPipeline
            return FluxPipeline

        if method == ImageGenerationActionMethod.INPAINT:
            if self._get_controlnet_count() > 0:
                from diffusers import FluxControlNetInpaintPipeline
                return FluxControlNetInpaintPipeline
            from diffusers import FluxInpaintPipeline
            return FluxInpaintPipeline

        raise ValueError(f"Unknown method: {method}")

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch
        return torch.bfloat16

    def _get_quantizable_components(self) -> List[str]:
        # text_encoder_2 is T5-XXL (~9GB fp16); biggest single win after transformer.
        return [ "transformer", "text_encoder_2" ]

    def _get_vae_model_class(self) -> Type[Any]:
        from diffusers import AutoencoderKL
        return AutoencoderKL

    def _get_controlnet_model_class(self) -> Type[Any]:
        from diffusers import FluxControlNetModel
        return FluxControlNetModel

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pipeline = self.pipelines.get(action.method)

        if pipeline is None:
            raise ValueError(f"No pipeline loaded for method: {action.method}")

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await FluxHuggingfaceImageGenerationGenerateTaskAction(
                action,
                pipeline,
                self.device,
                self._get_controlnet_count()
            ).run(context)

        if action.method == ImageGenerationActionMethod.INPAINT:
            return await FluxHuggingfaceImageGenerationInpaintTaskAction(
                action,
                pipeline,
                self.device,
                self._get_controlnet_count()
            ).run(context)

        raise ValueError(f"Unknown method: {action.method}")
