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

class FluxHuggingfaceImageGenerationTaskAction(HuggingfaceImageGenerationTaskAction):
    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        guidance_scale      = await context.render_scalar(self.config.params.guidance_scale, float)
        max_sequence_length = await context.render_scalar(self.config.params.max_sequence_length, int)

        params.update({
            "guidance_scale":      guidance_scale,
            "max_sequence_length": max_sequence_length,
        })

        return params

class FluxHuggingfaceImageGenerationGenerateAction(FluxHuggingfaceImageGenerationTaskAction):
    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        prompt = await context.render_text(self.config.prompt)

        if self.controlnet_count > 0 and self.config.control_image is not None:
            control_image = await context.render_image_array(self.config.control_image, single_as_array=True)
        else:
            control_image = None

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt, control_image), prompt, is_single_input, is_streaming_input

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
        prompts, control_images = inputs

        if self.controlnet_count > 0:
            control_images = await self._build_pipeline_control_images(control_images)
        else:
            control_images = None

        def _generate() -> List[PILImage.Image]:
            pipeline_params: Dict[str, Any] = {
                **params["pipeline"],
                "prompt": list(prompts),
            }

            if control_images is not None:
                pipeline_params["image"] = control_images

            return self._process_pipeline(pipeline_params, params, cancellation_token)

        return await self._run_in_executor(_generate)

class FluxHuggingfaceImageGenerationInpaintAction(FluxHuggingfaceImageGenerationTaskAction):
    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        prompt     = await context.render_text(self.config.prompt)
        image      = await context.render_image(self.config.image)
        mask_image = await context.render_image(self.config.mask_image)

        if self.controlnet_count > 0 and self.config.control_image is not None:
            control_image = await context.render_image_array(self.config.control_image, single_as_array=True)
        else:
            control_image = None

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt, image, mask_image, control_image), prompt, is_single_input, is_streaming_input

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        denoise_strength = await context.render_scalar(self.config.params.denoise_strength, float)

        params.update({
            "strength": denoise_strength,
        })

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        prompts, images, mask_images, control_images = inputs

        if self.controlnet_count > 0:
            control_images = await self._build_pipeline_control_images(control_images)
        else:
            control_images = None

        def _generate() -> List[PILImage.Image]:
            pipeline_params: Dict[str, Any] = {
                **params["pipeline"],
                "prompt":     list(prompts),
                "image":      list(images),
                "mask_image": list(mask_images),
            }

            if control_images is not None:
                pipeline_params["control_image"] = control_images

            return self._process_pipeline(pipeline_params, params, cancellation_token)

        return await self._run_in_executor(_generate)

class FluxHuggingfaceImageGenerationTaskDriver(HuggingfaceImageGenerationBaseDriver):
    def _get_pipeline_class(self, method: Optional[ImageGenerationActionMethod]) -> Type[DiffusionPipeline]:
        if method is None or method == ImageGenerationActionMethod.GENERATE:
            if self._get_controlnet_count() > 0:
                from diffusers import FluxControlNetPipeline
                return FluxControlNetPipeline
            else:
                from diffusers import FluxPipeline
                return FluxPipeline

        if method == ImageGenerationActionMethod.INPAINT:
            if self._get_controlnet_count() > 0:
                from diffusers import FluxControlNetInpaintPipeline
                return FluxControlNetInpaintPipeline
            else:
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

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await FluxHuggingfaceImageGenerationGenerateAction(
                action, pipeline, self.device, self._get_controlnet_count()
            ).run(context)

        if action.method == ImageGenerationActionMethod.INPAINT:
            return await FluxHuggingfaceImageGenerationInpaintAction(
                action, pipeline, self.device, self._get_controlnet_count()
            ).run(context)

        raise ValueError(f"Unknown method: {action.method}")
