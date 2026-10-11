from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator

from mindor.dsl.schema.action import ModelActionConfig, ImageGenerationActionMethod
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from .....base import ComponentActionContext
from ..base import HuggingfaceImageGenerationTaskAction, HuggingfaceImageGenerationBaseDriver
from PIL import Image as PILImage

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class QwenImageHuggingfaceImageGenerationGenerateAction(HuggingfaceImageGenerationTaskAction):
    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        prompt          = await context.render_text(self.config.prompt)
        negative_prompt = await context.render_variable(self.config.negative_prompt)
        image           = await context.render_image_array(self.config.image, single_as_array=True)

        if image is not None:
            image = await image.collect()

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt, negative_prompt, image), is_single_input, is_streaming_input

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_pipeline_params(context)

        true_cfg_scale = await context.render_scalar(self.config.params.true_cfg_scale, float)
        sigmas         = await context.render_variable(self.config.params.sigmas)

        if sigmas is not None and len(sigmas) != params["num_inference_steps"]:
            raise ValueError(
                f"`sigmas` length ({len(sigmas)}) must equal `inference_steps` ({params['num_inference_steps']})."
            )

        params.update({
            "true_cfg_scale": true_cfg_scale,
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
        prompts, negative_prompts, images = inputs

        if all(value is None for value in negative_prompts):
            negative_prompts = None

        if all(value is None for value in images):
            images = None

        def _generate() -> List[PILImage.Image]:
            pipeline_params: Dict[str, Any] = {
                **params["pipeline"],
                "prompt": list(prompts),
            }

            if negative_prompts is not None:
                pipeline_params["negative_prompt"] = list(negative_prompts)

            if images is not None:
                pipeline_params["image"] = list(images)

            return self._process_pipeline(pipeline_params, params, cancellation_token)

        return await self._run_in_executor(_generate)

class QwenImageHuggingfaceImageGenerationTaskDriver(HuggingfaceImageGenerationBaseDriver):
    def _get_torch_requirements(self) -> List[str]:
        # Qwen3-VL text encoder's processor lazily loads Qwen3VLVideoProcessor,
        # which pulls in torchvision.
        return torch_requirements("torch", "torchvision")

    def _get_transformers_requirements(self) -> List[str]:
        # Qwen3-VL text encoder requires transformers >= 5.17 per the model card.
        return [ "transformers>=5.17" ]

    def _get_diffusers_requirements(self) -> List[str]:
        # QwenImage21Pipeline is only on diffusers main (0.41.0.dev0); pin forces
        # reinstall over any older release and stays valid once 0.41 ships.
        return [ "diffusers>=0.41.0.dev0@git+https://github.com/huggingface/diffusers.git" ]

    def _get_pipeline_class(self, method: Optional[ImageGenerationActionMethod]) -> Type[DiffusionPipeline]:
        if method is None or method == ImageGenerationActionMethod.GENERATE:
            from diffusers import QwenImage21Pipeline
            return QwenImage21Pipeline

        raise ValueError(f"Inpainting is not supported for architecture: qwen-image")

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch
        return torch.bfloat16

    def _get_quantizable_components(self) -> List[str]:
        # text_encoder is Qwen3-VL (~7B); quantizing it is the biggest single VRAM win after the transformer.
        return [ "transformer", "text_encoder" ]

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pipeline = self.pipelines.get(action.method)

        if pipeline is None:
            raise ValueError(f"No pipeline loaded for method: {action.method}")

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await QwenImageHuggingfaceImageGenerationGenerateAction(
                action, pipeline, self.device, self._get_controlnet_count()
            ).run(context)

        raise ValueError(f"Inpainting is not supported for architecture: qwen-image")
