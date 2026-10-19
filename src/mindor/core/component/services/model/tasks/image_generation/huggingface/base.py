from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import HuggingfaceImageGenerationModelActionConfig, ImageGenerationActionMethod
from mindor.dsl.schema.component import ModelSubmoduleConfig, DiffusionCpuOffload
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ....base import ComponentActionContext
from ....base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskDriver
from ..common import ImageGenerationTaskAction
from PIL import Image as PILImage
import asyncio
import inspect

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class PipelineCancelled(Exception):
    pass

class HuggingfaceImageGenerationTaskAction(ImageGenerationTaskAction):
    config: HuggingfaceImageGenerationModelActionConfig

    _pipeline_call_params_cache: Dict[Type, frozenset] = {}

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

        params.update({
            "pipeline": pipeline_params,
            "seed":     seed,
        })

        return params

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        """Build the pipeline kwargs shared across generate/inpaint for one call.

        Default covers the fields every architecture shares (resolution, step
        count) plus ControlNet runtime scalars when ControlNet is configured;
        subclasses override and extend via
        ``await super()._resolve_pipeline_params(context)`` with their
        architecture-specific knobs (``guidance_scale``, ``max_sequence_length``,
        …) and method-specific additions (``sigmas`` for generate,
        ``strength`` for inpaint). The per-input ``control_image`` itself is
        threaded via ``_prepare_input`` and materialized per-batch in
        ``_generate_batch``.
        """
        inference_steps   = await context.render_scalar(self.config.params.inference_steps, int)
        width             = await context.render_scalar(self.config.width, int)
        height            = await context.render_scalar(self.config.height, int)
        num_return_images = await context.render_scalar(self.config.num_return_images, int)

        params: Dict[str, Any] = {
            "num_inference_steps":   inference_steps,
            "width":                 width,
            "height":                height,
            "num_images_per_prompt": num_return_images,
        }

        if self.controlnet_count > 0:
            conditioning_scale = await context.render_variable(self.config.params.controlnet_conditioning_scale)
            guidance_start     = await context.render_variable(self.config.params.control_guidance_start)
            guidance_end       = await context.render_variable(self.config.params.control_guidance_end)

            params.update({
                "controlnet_conditioning_scale": conditioning_scale,
                "control_guidance_start":        guidance_start,
                "control_guidance_end":          guidance_end,
            })

        return params

    async def _build_pipeline_control_images(self, control_images: List[Any]) -> Any:
        """Collect per-input control images and transpose into pipeline's shape.

        diffusers wants ``List[PIL]`` for a single ControlNet and
        ``List[List[PIL]]`` for multi-ControlNet with outer=ControlNet,
        inner=per-input — the opposite nesting of our batch tuple.
        """
        control_images = [ await images.collect() for images in control_images ]

        if self.controlnet_count == 1:
            return [ images[0] for images in control_images ]

        return [ list(images) for images in zip(*control_images) ]

    def _process_pipeline(
        self,
        pipeline_params: Dict[str, Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[PILImage.Image]:
        """Invoke the diffusers pipeline with a seed generator and cancel hook.

        Shared across generate/inpaint subclasses — they build the kwargs,
        this runs them.
        """
        import torch

        generator: Optional[torch.Generator] = None

        if params["seed"] is not None:
            generator = torch.Generator(device=self.device).manual_seed(params["seed"])

        if "sigmas" in pipeline_params and not self._pipeline_accepts_param(self.pipeline, "sigmas"):
            raise ValueError(
                f"{type(self.pipeline).__name__} does not accept `sigmas`; "
                "remove `params.sigmas` or switch to an architecture that supports it."
            )

        if cancellation_token is not None:
            def _abort_if_cancelled(pipe, step, timestep, callback_kwargs):
                if cancellation_token.is_cancelled():
                    raise PipelineCancelled()
                return callback_kwargs

            pipeline_params = { **pipeline_params, "callback_on_step_end": _abort_if_cancelled }

        try:
            result = self.pipeline(generator=generator, **pipeline_params)
        except PipelineCancelled:
            raise asyncio.CancelledError()

        return list(result.images)

    @classmethod
    def _pipeline_accepts_param(cls, pipeline: Any, param: str) -> bool:
        pipeline_class = type(pipeline)
        params = cls._pipeline_call_params_cache.get(pipeline_class)

        if params is None:
            params = frozenset(inspect.signature(pipeline_class.__call__).parameters)
            cls._pipeline_call_params_cache[pipeline_class] = params

        return param in params

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

    async def _load_pretrained_vae_model(self, vae: ModelSubmoduleConfig, device: torch.device, dtype: torch.dtype) -> Any:
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
        controlnets: List[ModelSubmoduleConfig],
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
