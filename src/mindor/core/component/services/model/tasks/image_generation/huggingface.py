from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceImageGenerationModelActionConfig, ImageGenerationActionMethod
from mindor.dsl.schema.component import HuggingfaceImageGenerationModelArchitecture, DiffusionVaeConfig
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskDriver
from .common import ImageGenerationGenerateTaskAction, ImageGenerationInpaintTaskAction
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.logger import logging
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

        seed = await context.render_scalar(self.config.seed, int)

        params["pipeline"] = pipeline_params
        params["seed"] = seed

        return params

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        inference_steps   = await context.render_scalar(self.config.params.inference_steps, int)
        width             = await context.render_scalar(self.config.width, int)
        height            = await context.render_scalar(self.config.height, int)
        num_return_images = await context.render_scalar(self.config.num_return_images, int)

        return {
            "num_inference_steps":   inference_steps,
            "width":                 width,
            "height":                height,
            "num_images_per_prompt": num_return_images,
        }

    async def _resolve_architecture_params(self, architecture: HuggingfaceImageGenerationModelArchitecture, context: ComponentActionContext) -> Dict[str, Any]:
        if architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            negative_prompt = await context.render_variable(self.config.negative_prompt)
            guidance_scale  = await context.render_scalar(self.config.params.guidance_scale, float)

            return {
                "negative_prompt": negative_prompt,
                "guidance_scale":  guidance_scale,
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            guidance_scale      = await context.render_scalar(self.config.params.guidance_scale, float)
            max_sequence_length = await context.render_scalar(self.config.params.max_sequence_length, int)

            return {
                "guidance_scale":      guidance_scale,
                "max_sequence_length": max_sequence_length,
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE:
            negative_prompt          = await context.render_variable(self.config.negative_prompt)
            distilled_guidance_scale = await context.render_scalar(self.config.params.distilled_guidance_scale, float)

            return {
                "negative_prompt":          negative_prompt,
                "distilled_guidance_scale": distilled_guidance_scale,
            }

        if architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            negative_prompt = await context.render_variable(self.config.negative_prompt)
            true_cfg_scale  = await context.render_scalar(self.config.params.true_cfg_scale, float)

            return {
                "negative_prompt": negative_prompt,
                "true_cfg_scale":  true_cfg_scale,
            }

        raise ValueError(f"Unknown architecture: {architecture}")

    async def _generate_batch(
        self,
        prompts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        import torch

        def _generate() -> List[PILImage.Image]:
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

        return await self._run_in_executor(_generate)

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
        requirements = [
            *super()._get_setup_requirements(),
            "sentencepiece",
        ]

        if self.config.architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            # QwenImage21Pipeline lives on diffusers main (currently 0.41.0.dev0); not in any
            # tagged release as of 2026-09 (latest v0.40.0). The `>=0.41.0.dev0` pin forces
            # reinstall when an older diffusers is already present (unversioned parent spec
            # would otherwise be considered satisfied) and stays satisfied once 0.41 ships.
            # Qwen3-VL text encoder requires transformers >= 5.17 per the model card, and its
            # processor lazily loads Qwen3VLVideoProcessor which pulls in torchvision.
            requirements.append("diffusers>=0.41.0.dev0@git+https://github.com/huggingface/diffusers.git")
            requirements.append("transformers>=5.17")
            requirements.extend(torch_requirements("torchvision"))

        return requirements

    async def _load_pretrained_pipelines(self, methods: List[Optional[ImageGenerationActionMethod]]) -> Tuple[Dict[Optional[ImageGenerationActionMethod], "DiffusionPipeline"], "torch.device"]:
        # Qwen-Image 2.1 keeps two ~7B modules (transformer, Qwen3-VL text encoder) live in
        # VRAM if fully placed on GPU (~24GB peak at 2048x2048). `enable_model_cpu_offload`
        # keeps only the currently-active submodule on GPU and swaps siblings out to CPU
        # between stages, bringing peak VRAM to ~10-12GB with a modest latency cost.
        # Any other architecture falls through to the base loader (plain `.to(device)`).
        if self.config.architecture != HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            return await super()._load_pretrained_pipelines(methods)

        model_path = await self._provision_model(self.config.model)
        device = self._resolve_device(self.config.device)
        dtype = self._get_pipeline_dtype(device)

        # Model CPU offload only makes sense on CUDA; on CPU/MPS fall back to the base path.
        if device.type != "cuda":
            return await super()._load_pretrained_pipelines(methods)

        base_pipeline_class = self._get_pipeline_class(None)
        method_pipeline_classes: Dict[Optional[ImageGenerationActionMethod], Type[DiffusionPipeline]] = { method: self._get_pipeline_class(method) for method in methods }
        quantization_config = self._resolve_pipeline_quantization_config(device, dtype)

        submodules = await self._load_pipeline_submodules(device, dtype)

        def _load() -> Dict[Optional[ImageGenerationActionMethod], DiffusionPipeline]:
            params: Dict[str, Any] = {
                **self._get_model_params(self.config.model),
                **submodules,
                "torch_dtype": dtype,
            }

            if quantization_config is not None:
                params["quantization_config"] = quantization_config

            logging.info(f"Component '{self.id}': loading {base_pipeline_class.__name__} from {model_path} (CPU offload enabled, device={device})")

            # Do NOT call `.to(device)` before `enable_model_cpu_offload` — diffusers warns
            # that moving the pipeline to CUDA first negates most of the memory savings.
            base_pipeline = base_pipeline_class.from_pretrained(model_path, **params)
            base_pipeline.enable_model_cpu_offload(device=device)

            pipelines: Dict[Optional[ImageGenerationActionMethod], DiffusionPipeline] = {}

            for method, pipeline_class in method_pipeline_classes.items():
                if pipeline_class is base_pipeline_class:
                    pipelines[method] = base_pipeline
                else:
                    logging.info(f"Component '{self.id}': deriving {pipeline_class.__name__} from {base_pipeline_class.__name__}")
                    derived = pipeline_class.from_pipe(base_pipeline)
                    # Offload hooks installed on the base pipeline don't transfer through
                    # `from_pipe`; re-arm them on each derived pipeline so every method
                    # inherits the same low-VRAM behavior.
                    derived.enable_model_cpu_offload(device=device)
                    pipelines[method] = derived

            return pipelines

        pipelines = await self._run_in_executor(_load)

        return pipelines, device

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

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pipeline = self.pipelines.get(action.method)

        if pipeline is None:
            raise ValueError(f"No pipeline loaded for method: {action.method}")

        if action.method == ImageGenerationActionMethod.GENERATE:
            return await HuggingfaceImageGenerationGenerateTaskAction(action, self.config.architecture, pipeline, self.device).run(context)

        if action.method == ImageGenerationActionMethod.INPAINT:
            return await HuggingfaceImageGenerationInpaintTaskAction(action, self.config.architecture, pipeline, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
