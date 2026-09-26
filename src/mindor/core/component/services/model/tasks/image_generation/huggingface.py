from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceImageGenerationModelActionConfig, ImageGenerationActionMethod
from mindor.dsl.schema.component import HuggingfaceImageGenerationModelArchitecture, DiffusionVaeConfig, DiffusionCpuOffload
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskDriver
from .common import ImageGenerationGenerateTaskAction, ImageGenerationInpaintTaskAction
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.logger import logging
from PIL import Image as PILImage
import asyncio
import inspect

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class PipelineCancelled(Exception):
    pass

_pipeline_call_params_cache: Dict[Type, frozenset] = {}

def _pipeline_accepts(pipeline: Any, param_name: str) -> bool:
    pipeline_class = type(pipeline)
    params = _pipeline_call_params_cache.get(pipeline_class)

    if params is None:
        params = frozenset(inspect.signature(pipeline_class.__call__).parameters)
        _pipeline_call_params_cache[pipeline_class] = params

    return param_name in params

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

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        prompt           = await context.render_text(self.config.prompt)
        additional_input = await self._prepare_architecture_input(self.architecture, context)

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt, *additional_input), is_single_input, is_streaming_input

    async def _prepare_architecture_input(self, architecture: HuggingfaceImageGenerationModelArchitecture, context: ComponentActionContext) -> Tuple[Any, ...]:
        if architecture in (
            HuggingfaceImageGenerationModelArchitecture.SDXL,
            HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE
        ):
            negative_prompt = await context.render_variable(self.config.negative_prompt)

            return (negative_prompt,)

        if architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            return ()

        if architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            negative_prompt = await context.render_variable(self.config.negative_prompt)
            image           = await context.render_image_array(self.config.image, single_as_array=True)

            if image is not None:
                image = await image.collect()

            return (negative_prompt, image)

        raise ValueError(f"Unknown architecture: {architecture}")

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        pipeline_params: Dict[str, Any] = await self._resolve_pipeline_params(context)
        pipeline_params.update(await self._resolve_architecture_params(self.architecture, context))

        seed = await context.render_scalar(self.config.seed, int)

        params["pipeline"] = pipeline_params
        params["seed"] = seed

        return params

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        inference_steps   = await context.render_scalar(self.config.params.inference_steps, int)
        width             = await context.render_scalar(self.config.width, int)
        height            = await context.render_scalar(self.config.height, int)
        num_return_images = await context.render_scalar(self.config.num_return_images, int)
        sigmas            = await context.render_variable(self.config.params.sigmas)

        if sigmas is not None and len(sigmas) != inference_steps:
            raise ValueError(f"`sigmas` length ({len(sigmas)}) must equal `inference_steps` ({inference_steps}).")

        params: Dict[str, Any] = {
            "num_inference_steps":   inference_steps,
            "width":                 width,
            "height":                height,
            "num_images_per_prompt": num_return_images,
        }

        if sigmas is not None:
            params["sigmas"] = sigmas

        return params

    async def _resolve_architecture_params(self, architecture: HuggingfaceImageGenerationModelArchitecture, context: ComponentActionContext) -> Dict[str, Any]:
        if architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            guidance_scale = await context.render_scalar(self.config.params.guidance_scale, float)

            return {
                "guidance_scale": guidance_scale,
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            guidance_scale      = await context.render_scalar(self.config.params.guidance_scale, float)
            max_sequence_length = await context.render_scalar(self.config.params.max_sequence_length, int)

            return {
                "guidance_scale":      guidance_scale,
                "max_sequence_length": max_sequence_length,
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE:
            distilled_guidance_scale = await context.render_scalar(self.config.params.distilled_guidance_scale, float)

            return {
                "distilled_guidance_scale": distilled_guidance_scale,
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            true_cfg_scale = await context.render_scalar(self.config.params.true_cfg_scale, float)

            return {
                "true_cfg_scale": true_cfg_scale,
            }

        raise ValueError(f"Unknown architecture: {architecture}")

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        import torch

        def _generate() -> List[PILImage.Image]:
            generator: Optional[torch.Generator] = None

            if params["seed"] is not None:
                generator = torch.Generator(device=self.device).manual_seed(params["seed"])

            pipeline_params = {
                **params["pipeline"],
                **self._build_architecture_input_params(self.architecture, inputs)
            }

            if "sigmas" in pipeline_params and not _pipeline_accepts(self.pipeline, "sigmas"):
                raise ValueError(
                    f"{type(self.pipeline).__name__} does not accept `sigmas`; "
                    "remove `params.sigmas` or switch to an architecture that supports it."
                )

            if cancellation_token is not None:
                def _abort_if_cancelled(pipe, step, timestep, callback_kwargs):
                    if cancellation_token.is_cancelled():
                        raise PipelineCancelled()
                    return callback_kwargs

                pipeline_params["callback_on_step_end"] = _abort_if_cancelled

            try:
                result = self.pipeline(
                    generator=generator,
                    **pipeline_params,
                )
            except PipelineCancelled:
                raise asyncio.CancelledError()

            return list(result.images)

        return await self._run_in_executor(_generate)

    def _build_architecture_input_params(self, architecture: HuggingfaceImageGenerationModelArchitecture, inputs: Any) -> Dict[str, Any]:
        if architecture in (
            HuggingfaceImageGenerationModelArchitecture.SDXL,
            HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE
        ):
            prompts, negative_prompts = inputs

            if all(value is None for value in negative_prompts):
                negative_prompts = None

            return {
                "prompt": list(prompts),
                **({ "negative_prompt": list(negative_prompts) } if negative_prompts is not None else {}),
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            (prompts,) = inputs

            return {
                "prompt": list(prompts),
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            prompts, negative_prompts, images = inputs

            if all(value is None for value in negative_prompts):
                negative_prompts = None

            if all(value is None for value in images):
                images = None

            return {
                "prompt": list(prompts),
                **({ "negative_prompt": list(negative_prompts) } if negative_prompts is not None else {}),
                **({ "image":           list(images)           } if images is not None else {}),
            }

        raise ValueError(f"Unknown architecture: {architecture}")

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

        seed = await context.render_scalar(self.config.seed, int)

        params["pipeline"] = pipeline_params
        params["seed"] = seed

        return params

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        inference_steps   = await context.render_scalar(self.config.params.inference_steps, int)
        width             = await context.render_scalar(self.config.width, int)
        height            = await context.render_scalar(self.config.height, int)
        num_return_images = await context.render_scalar(self.config.num_return_images, int)
        denoise_strength  = await context.render_scalar(self.config.params.denoise_strength, float)

        return {
            "num_inference_steps":   inference_steps,
            "width":                 width,
            "height":                height,
            "num_images_per_prompt": num_return_images,
            "strength":              denoise_strength,
        }

    async def _resolve_architecture_params(self, architecture: HuggingfaceImageGenerationModelArchitecture, context: ComponentActionContext) -> Dict[str, Any]:
        if architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            negative_prompt = await context.render_variable(self.config.negative_prompt)
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

    async def _inpaint_batch(
        self,
        prompts: List[str],
        images: List[PILImage.Image],
        mask_images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        import torch

        def _inpaint() -> List[PILImage.Image]:
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

        return await self._run_in_executor(_inpaint)

@register_model_task_driver(ModelTaskType.IMAGE_GENERATION, ModelDriverType.HUGGINGFACE)
class HuggingfaceImageGenerationTaskDriver(HuggingfaceDiffusionPipelineTaskDriver[ImageGenerationActionMethod]):
    def _get_setup_requirements(self) -> List[str]:
        return [
            *super()._get_setup_requirements(),
            "sentencepiece",
        ]

    def _get_torch_requirements(self) -> List[str]:
        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            # Qwen3-VL text encoder's processor lazily loads Qwen3VLVideoProcessor,
            # which pulls in torchvision.
            return torch_requirements("torch", "torchvision")

        return super()._get_torch_requirements()

    def _get_transformers_requirements(self) -> List[str]:
        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            # Qwen3-VL text encoder requires transformers >= 5.17 per the model card.
            return [ "transformers>=5.17" ]

        return super()._get_transformers_requirements()

    def _get_diffusers_requirements(self) -> List[str]:
        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            # QwenImage21Pipeline is only on diffusers main (0.41.0.dev0); pin forces
            # reinstall over any older release and stays valid once 0.41 ships.
            return [ "diffusers>=0.41.0.dev0@git+https://github.com/huggingface/diffusers.git" ]

        return super()._get_diffusers_requirements()

    async def _load_pipeline_submodules(self, device: torch.device, dtype: torch.dtype) -> Dict[str, Any]:
        submodules: Dict[str, Any] = {}

        if self.config.vae is not None:
            submodules["vae"] = await self._load_pretrained_vae_model(self.config.vae, device, dtype)

        return submodules

    async def _load_pretrained_vae_model(self, vae: DiffusionVaeConfig, device: torch.device, dtype: torch.dtype) -> Any:
        model_class = self._get_vae_model_class()
        model_path = await self._provision_model(vae.model)

        logging.info(f"Component '{self.id}': loading {model_class.__name__} from {model_path}")

        def _load() -> Any:
            params: Dict[str, Any] = {
                **self._get_model_params(vae.model),
                **self._get_model_options(vae, default_dtype=dtype),
            }

            return model_class.from_pretrained(model_path, **params).to(device)

        return await self._run_in_executor(_load)

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

            if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
                from diffusers import QwenImage21Pipeline
                return QwenImage21Pipeline

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

    def _get_quantizable_components(self) -> List[str]:
        # VAE and CLIP text encoders are excluded per diffusers guidance —
        # they're small and quantization hurts quality more than it saves.
        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            return [ "unet" ]

        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            # text_encoder_2 is T5-XXL (~9GB fp16); biggest single win after transformer.
            return [ "transformer", "text_encoder_2" ]

        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE:
            return [ "transformer", "text_encoder" ]

        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            # text_encoder is Qwen3-VL (~7B); quantizing it is the biggest single VRAM win after the transformer.
            return [ "transformer", "text_encoder" ]

        return []

    def _get_vae_model_class(self) -> Type[Any]:
        if self.config.architecture in (
            HuggingfaceImageGenerationModelArchitecture.SDXL,
            HuggingfaceImageGenerationModelArchitecture.FLUX,
        ):
            from diffusers import AutoencoderKL
            return AutoencoderKL

        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE:
            from diffusers import AutoencoderKLHunyuanImage
            return AutoencoderKLHunyuanImage

        raise ValueError(f"VAE override is not supported for architecture: {self.config.architecture}")

    def _get_cpu_offload(self) -> Optional[DiffusionCpuOffload]:
        return self.config.cpu_offload

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pipeline = self.pipelines.get(action.method)

        if pipeline is None:
            raise ValueError(f"No pipeline loaded for method: {action.method}")

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await HuggingfaceImageGenerationGenerateTaskAction(action, self.config.architecture, pipeline, self.device).run(context)

        if action.method == ImageGenerationActionMethod.INPAINT:
            return await HuggingfaceImageGenerationInpaintTaskAction(action, self.config.architecture, pipeline, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
