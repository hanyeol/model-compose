from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator

from mindor.dsl.schema.action import ModelActionConfig, ImageGenerationActionMethod
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from .....base import ComponentActionContext
from ..base import HuggingfaceImageGenerationTaskAction, HuggingfaceImageGenerationBaseDriver
from PIL import Image as PILImage

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class HunyuanImageHuggingfaceImageGenerationGenerateAction(HuggingfaceImageGenerationTaskAction):
    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        prompt          = await context.render_text(self.config.prompt)
        negative_prompt = await context.render_variable(self.config.negative_prompt)

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt, negative_prompt), is_single_input, is_streaming_input

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        distilled_guidance_scale = await context.render_scalar(self.config.params.distilled_guidance_scale, float)
        sigmas                   = await context.render_variable(self.config.params.sigmas)

        if sigmas is not None and len(sigmas) != params["num_inference_steps"]:
            raise ValueError(
                f"`sigmas` length ({len(sigmas)}) must equal `inference_steps` ({params['num_inference_steps']})."
            )

        params.update({
            "distilled_guidance_scale": distilled_guidance_scale,
        })

        if sigmas is not None:
            params["sigmas"] = sigmas

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        prompts, negative_prompts = inputs

        if all(value is None for value in negative_prompts):
            negative_prompts = None

        def _generate() -> List[PILImage.Image]:
            pipeline_params: Dict[str, Any] = {
                **params["pipeline"],
                "prompt": list(prompts),
            }

            if negative_prompts is not None:
                pipeline_params["negative_prompt"] = list(negative_prompts)

            return self._process_pipeline(pipeline_params, params, cancellation_token)

        return await self._run_in_executor(_generate)

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

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await HunyuanImageHuggingfaceImageGenerationGenerateAction(
                action, pipeline, self.device, self._get_controlnet_count()
            ).run(context)

        raise ValueError(f"Inpainting is not supported for architecture: hunyuan-image")
