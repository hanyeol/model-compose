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

class SdxlHuggingfaceImageGenerationGenerateTaskAction(HuggingfaceImageGenerationGenerateTaskAction):
    async def _prepare_input(self, context: ComponentActionContext):
        (prompt,), is_single_input, is_streaming_input = await super()._prepare_input(context)
        negative_prompt = await context.render_variable(self.config.negative_prompt)

        return (prompt, negative_prompt), is_single_input, is_streaming_input

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        guidance_scale = await context.render_scalar(self.config.params.guidance_scale, float)

        params.update({
            "guidance_scale": guidance_scale,
        })

        return params

    def _build_pipeline_input_params(self, inputs: Any) -> Dict[str, Any]:
        prompts, negative_prompts = inputs

        if all(value is None for value in negative_prompts):
            negative_prompts = None

        return {
            "prompt": list(prompts),
            **({ "negative_prompt": list(negative_prompts) } if negative_prompts is not None else {}),
        }


class SdxlHuggingfaceImageGenerationInpaintTaskAction(HuggingfaceImageGenerationInpaintTaskAction):
    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        negative_prompt = await context.render_variable(self.config.negative_prompt)
        guidance_scale  = await context.render_variable(self.config.params.guidance_scale)

        params.update({
            "negative_prompt": negative_prompt,
            "guidance_scale":  float(guidance_scale),
        })

        return params


class SdxlHuggingfaceImageGenerationTaskDriver(HuggingfaceImageGenerationBaseDriver):
    def _get_pipeline_class(self, method: Optional[ImageGenerationActionMethod]) -> Type[DiffusionPipeline]:
        if method is None or method == ImageGenerationActionMethod.GENERATE:
            if self._get_controlnet_count() > 0:
                from diffusers import StableDiffusionXLControlNetPipeline
                return StableDiffusionXLControlNetPipeline
            else:
                from diffusers import StableDiffusionXLPipeline
                return StableDiffusionXLPipeline

        if method == ImageGenerationActionMethod.INPAINT:
            if self._get_controlnet_count() > 0:
                from diffusers import StableDiffusionXLControlNetInpaintPipeline
                return StableDiffusionXLControlNetInpaintPipeline
            else:
                from diffusers import StableDiffusionXLInpaintPipeline
                return StableDiffusionXLInpaintPipeline

        raise ValueError(f"Unknown method: {method}")

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch
        return torch.float16

    def _get_quantizable_components(self) -> List[str]:
        # VAE and CLIP text encoders are excluded per diffusers guidance —
        # they're small and quantization hurts quality more than it saves.
        return [ "unet" ]

    def _get_vae_model_class(self) -> Type[Any]:
        from diffusers import AutoencoderKL
        return AutoencoderKL

    def _get_controlnet_model_class(self) -> Type[Any]:
        from diffusers import ControlNetModel
        return ControlNetModel

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pipeline = self.pipelines.get(action.method)

        if pipeline is None:
            raise ValueError(f"No pipeline loaded for method: {action.method}")

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await SdxlHuggingfaceImageGenerationGenerateTaskAction(
                action,
                pipeline,
                self.device,
                self._get_controlnet_count()
            ).run(context)

        if action.method == ImageGenerationActionMethod.INPAINT:
            return await SdxlHuggingfaceImageGenerationInpaintTaskAction(
                action,
                pipeline,
                self.device,
                self._get_controlnet_count()
            ).run(context)

        raise ValueError(f"Unknown method: {action.method}")
