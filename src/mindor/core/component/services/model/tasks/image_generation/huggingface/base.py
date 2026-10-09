from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Type, Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import HuggingfaceImageGenerationModelActionConfig, ImageGenerationActionMethod
from mindor.dsl.schema.component import DiffusionVaeConfig, DiffusionControlNetConfig, DiffusionCpuOffload
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ....base import ComponentActionContext
from ....base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskDriver
from ..common import ImageGenerationGenerateTaskAction, ImageGenerationInpaintTaskAction
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
        pipeline: DiffusionPipeline,
        device: Optional[torch.device],
        controlnet_count: int = 0,
    ):
        super().__init__(config, device)

        self.pipeline: DiffusionPipeline = pipeline
        self.controlnet_count: int = controlnet_count

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        prompt = await context.render_text(self.config.prompt)

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt,), is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        pipeline_params: Dict[str, Any] = await self._resolve_pipeline_params(context)
        seed = await context.render_scalar(self.config.seed, int)

        if self.controlnet_count > 0:
            pipeline_params.update(await self._resolve_controlnet_pipeline_params(context))

        params["pipeline"] = pipeline_params
        params["seed"] = seed

        return params

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        """Build the pipeline kwargs for one generation.

        Default covers the fields every architecture shares (resolution, step
        count, sigmas); subclasses override and extend via
        ``await super()._resolve_pipeline_params(context)`` with their
        architecture-specific knobs (``guidance_scale``, ``max_sequence_length``,
        …).
        """
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

    async def _resolve_controlnet_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        """Collect ControlNet runtime inputs and shape them for the pipeline call."""
        if self.config.control_image is None:
            raise ValueError(
                f"ControlNet is configured on the component ({self.controlnet_count} net(s)) "
                "but `control_image` is not set on the action."
            )

        control_images = await context.render_image_array(self.config.control_image, single_as_array=True)
        control_images = await control_images.collect()

        if len(control_images) != self.controlnet_count:
            raise ValueError(
                f"`control_image` has {len(control_images)} entries but the component "
                f"loaded {self.controlnet_count} ControlNet(s); counts must match."
            )

        conditioning_scale = await context.render_variable(self.config.controlnet_conditioning_scale)
        guidance_start     = await context.render_variable(self.config.control_guidance_start)
        guidance_end       = await context.render_variable(self.config.control_guidance_end)

        return {
            self._controlnet_image_key():    control_images,
            "controlnet_conditioning_scale": conditioning_scale,
            "control_guidance_start":        guidance_start,
            "control_guidance_end":          guidance_end,
        }

    def _build_pipeline_input_params(self, inputs: Any) -> Dict[str, Any]:
        """Translate the batched input tuple into pipeline kwargs.

        Default handles the "prompt only" shape. Override when the architecture
        extends the tuple in `_prepare_input`.
        """
        (prompts,) = inputs

        return {
            "prompt": list(prompts),
        }

    def _controlnet_image_key(self) -> str:
        return "image"

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
                **self._build_pipeline_input_params(inputs),
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
                result = self.pipeline(generator=generator, **pipeline_params)
            except PipelineCancelled:
                raise asyncio.CancelledError()

            return list(result.images)

        return await self._run_in_executor(_generate)

class HuggingfaceImageGenerationInpaintTaskAction(ImageGenerationInpaintTaskAction):
    config: HuggingfaceImageGenerationModelActionConfig

    def __init__(
        self,
        config: HuggingfaceImageGenerationModelActionConfig,
        pipeline: DiffusionPipeline,
        device: Optional[torch.device],
        controlnet_count: int = 0,
    ):
        super().__init__(config, device)

        self.pipeline: DiffusionPipeline = pipeline
        self.controlnet_count: int = controlnet_count

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        pipeline_params: Dict[str, Any] = await self._resolve_pipeline_params(context)
        seed = await context.render_scalar(self.config.seed, int)

        if self.controlnet_count > 0:
            pipeline_params.update(await self._resolve_controlnet_pipeline_params(context))

        params["pipeline"] = pipeline_params
        params["seed"] = seed

        return params

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        """Build the inpaint pipeline kwargs for one call.

        Default covers the fields every architecture shares (resolution, step
        count, denoise strength); subclasses override and extend via
        ``await super()._resolve_pipeline_params(context)`` with their
        architecture-specific knobs (``negative_prompt``, ``guidance_scale``, …).
        """
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

    async def _resolve_controlnet_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        """Collect ControlNet runtime inputs for inpaint pipelines.

        Inpaint pipelines take the base image via ``image`` and the ControlNet
        condition via ``control_image``, so this mirrors the generate helper
        but writes the condition under ``control_image``.
        """
        if self.config.control_image is None:
            raise ValueError(
                f"ControlNet is configured on the component ({self.controlnet_count} net(s)) "
                "but `control_image` is not set on the action."
            )

        control_images = await context.render_image_array(self.config.control_image, single_as_array=True)
        control_images = await control_images.collect()

        if len(control_images) != self.controlnet_count:
            raise ValueError(
                f"`control_image` has {len(control_images)} entries but the component "
                f"loaded {self.controlnet_count} ControlNet(s); counts must match."
            )

        conditioning_scale = await context.render_variable(self.config.controlnet_conditioning_scale)
        guidance_start     = await context.render_variable(self.config.control_guidance_start)
        guidance_end       = await context.render_variable(self.config.control_guidance_end)

        return {
            self._controlnet_image_key():    control_images,
            "controlnet_conditioning_scale": conditioning_scale,
            "control_guidance_start":        guidance_start,
            "control_guidance_end":          guidance_end,
        }

    def _controlnet_image_key(self) -> str:
        return "control_image"

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

class HuggingfaceImageGenerationBaseDriver(HuggingfaceDiffusionPipelineTaskDriver[ImageGenerationActionMethod]):
    def _get_setup_requirements(self) -> List[Union[str, Tuple[str, List[str]]]]:
        return [
            *super()._get_setup_requirements(),
            "sentencepiece",
        ]

    async def _load_pipeline_submodules(self, device: torch.device, dtype: torch.dtype) -> Dict[str, Any]:
        submodules: Dict[str, Any] = {}

        if self.config.vae is not None:
            submodules["vae"] = await self._load_pretrained_vae_model(self.config.vae, device, dtype)

        if self.config.controlnet:
            submodules["controlnet"] = await self._load_pretrained_controlnet_models(self.config.controlnet, device, dtype)

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

    async def _load_pretrained_controlnet_models(
        self,
        controlnets: List[DiffusionControlNetConfig],
        device: torch.device,
        dtype: torch.dtype,
    ) -> Any:
        model_class = self._get_controlnet_model_class()
        model_paths = [ await self._provision_model(controlnet.model) for controlnet in controlnets ]

        def _load() -> Any:
            models: List[Any] = []

            for controlnet, model_path in zip(controlnets, model_paths):
                logging.info(f"Component '{self.id}': loading {model_class.__name__} from {model_path}")

                params: Dict[str, Any] = {
                    **self._get_model_params(controlnet.model),
                    **self._get_model_options(controlnet, default_dtype=dtype),
                }
                models.append(model_class.from_pretrained(model_path, **params).to(device))

            # diffusers accepts a single ControlNetModel for one net and a list
            # for multi-ControlNet (wrapped internally as MultiControlNetModel).
            return models[0] if len(models) == 1 else models

        return await self._run_in_executor(_load)

    def _get_vae_model_class(self) -> Type[Any]:
        raise ValueError(f"VAE override is not supported for architecture: {self.config.architecture}")

    def _get_controlnet_model_class(self) -> Type[Any]:
        raise ValueError(f"ControlNet is not supported for architecture: {self.config.architecture}")

    def _get_controlnet_count(self) -> int:
        return len(self.config.controlnet) if self.config.controlnet else 0

    def _get_cpu_offload(self) -> Optional[DiffusionCpuOffload]:
        return self.config.cpu_offload

    def _get_vae_tiling(self) -> bool:
        return self.config.vae_tiling
