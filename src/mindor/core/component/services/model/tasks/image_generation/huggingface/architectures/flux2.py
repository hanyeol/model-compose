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

class Flux2HuggingfaceImageGenerationTaskAction(HuggingfaceImageGenerationTaskAction):
    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        guidance_scale          = await context.render_scalar(self.config.params.guidance_scale, float)
        max_sequence_length     = await context.render_scalar(self.config.params.max_sequence_length, int)
        text_encoder_out_layers = await context.render_variable(self.config.params.text_encoder_out_layers)

        params.update({
            "guidance_scale":          guidance_scale,
            "max_sequence_length":     max_sequence_length,
            "text_encoder_out_layers": tuple(text_encoder_out_layers),
        })

        return params

class Flux2HuggingfaceImageGenerationGenerateAction(Flux2HuggingfaceImageGenerationTaskAction):
    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        prompt = await context.render_text(self.config.prompt)

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return prompt, prompt, is_single_input, is_streaming_input

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        sigmas = await context.render_variable(self.config.params.sigmas)

        if sigmas is not None and len(sigmas) != params["num_inference_steps"]:
            raise ValueError(
                f"`sigmas` length ({len(sigmas)}) must equal `inference_steps` ({params['num_inference_steps']})."
            )

        if sigmas is not None:
            params["sigmas"] = sigmas

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        prompts = inputs

        def _generate() -> List[PILImage.Image]:
            pipeline_params: Dict[str, Any] = {
                **params["pipeline"],
                "prompt": list(prompts),
            }

            return self._process_pipeline(pipeline_params, params, cancellation_token)

        return await self._run_in_executor(_generate)

class Flux2HuggingfaceImageGenerationTaskDriver(HuggingfaceImageGenerationBaseDriver):
    def _get_diffusers_requirements(self) -> List[str]:
        return [ "diffusers>=0.38.0" ]

    def _get_pipeline_class(self, method: Optional[ImageGenerationActionMethod]) -> Type[DiffusionPipeline]:
        if method is None or method == ImageGenerationActionMethod.GENERATE:
            from diffusers import Flux2Pipeline
            return Flux2Pipeline

        raise ValueError(f"Inpainting is not supported for architecture: flux-2")

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch
        return torch.bfloat16

    def _get_quantizable_components(self) -> List[str]:
        return [ "transformer", "text_encoder" ]

    def _get_vae_model_class(self) -> Type[Any]:
        from diffusers import AutoencoderKLFlux2
        return AutoencoderKLFlux2

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pipeline = self.pipelines.get(action.method)

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await Flux2HuggingfaceImageGenerationGenerateAction(
                action, pipeline, self.device, self._get_controlnet_count()
            ).run(context)

        raise ValueError(f"Unknown method: {action.method}")
