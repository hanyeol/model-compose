from __future__ import annotations
from typing import TYPE_CHECKING, Type, Optional, Dict, List, Any

from mindor.dsl.schema.action import ModelActionConfig, ImageGenerationActionMethod
from .....base import ComponentActionContext
from ..base import (
    HuggingfaceImageGenerationGenerateTaskAction,
    HuggingfaceImageGenerationBaseDriver,
)

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class HunyuanImageHuggingfaceImageGenerationGenerateTaskAction(HuggingfaceImageGenerationGenerateTaskAction):
    async def _prepare_input(self, context: ComponentActionContext):
        (prompt,), is_single_input, is_streaming_input = await super()._prepare_input(context)
        negative_prompt = await context.render_variable(self.config.negative_prompt)

        return (prompt, negative_prompt), is_single_input, is_streaming_input

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        distilled_guidance_scale = await context.render_scalar(self.config.params.distilled_guidance_scale, float)

        params.update({
            "distilled_guidance_scale": distilled_guidance_scale,
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

class HunyuanImageHuggingfaceImageGenerationTaskDriver(HuggingfaceImageGenerationBaseDriver):
    def _get_pipeline_class(self, method: Optional[ImageGenerationActionMethod]) -> Type[DiffusionPipeline]:
        if method is None or method == ImageGenerationActionMethod.GENERATE:
            from diffusers import HunyuanImagePipeline
            return HunyuanImagePipeline

        raise ValueError(f"Inpainting is not supported for architecture: hunyuan-image")

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch
        return torch.bfloat16

    def _get_quantizable_components(self) -> List[str]:
        return [ "transformer", "text_encoder" ]

    def _get_vae_model_class(self) -> Type[Any]:
        from diffusers import AutoencoderKLHunyuanImage
        return AutoencoderKLHunyuanImage

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pipeline = self.pipelines.get(action.method)

        if pipeline is None:
            raise ValueError(f"No pipeline loaded for method: {action.method}")

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await HunyuanImageHuggingfaceImageGenerationGenerateTaskAction(action, pipeline, self.device, self._get_controlnet_count()).run(context)

        raise ValueError(f"Inpainting is not supported for architecture: hunyuan-image")
