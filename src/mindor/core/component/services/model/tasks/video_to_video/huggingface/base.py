from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import HuggingfaceVideoToVideoModelActionConfig
from mindor.dsl.schema.component import ModelSubmoduleConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ....base import ComponentActionContext
from ....base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskDriver
from ..common import VideoToVideoTaskAction
import asyncio

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class PipelineCancelled(Exception):
    pass

class HuggingfaceVideoToVideoTaskAction(VideoToVideoTaskAction):
    config: HuggingfaceVideoToVideoModelActionConfig

    def __init__(
        self,
        config: HuggingfaceVideoToVideoModelActionConfig,
        pipeline: DiffusionPipeline,
        device: Optional[torch.device],
    ):
        super().__init__(config)

        self.pipeline: DiffusionPipeline = pipeline
        self.device: Optional[torch.device] = device

    def _process_pipeline(
        self,
        pipeline_params: Dict[str, Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Any:
        """Invoke the diffusers pipeline with a seed generator and cancel hook."""
        import torch

        generator: Optional[torch.Generator] = None

        if params["seed"] is not None:
            generator = torch.Generator(device=self.device).manual_seed(params["seed"])

        if cancellation_token is not None:
            def _abort_if_cancelled(pipe, step, timestep, callback_kwargs):
                if cancellation_token.is_cancelled():
                    raise PipelineCancelled()
                return callback_kwargs

            pipeline_params = { **pipeline_params, "callback_on_step_end": _abort_if_cancelled }

        try:
            return self.pipeline(generator=generator, **pipeline_params)
        except PipelineCancelled:
            raise asyncio.CancelledError()

class HuggingfaceVideoToVideoBaseDriver(HuggingfaceDiffusionPipelineTaskDriver[None]):
    def _get_setup_requirements(self) -> List[Union[str, Tuple[str, List[str]]]]:
        return [
            *super()._get_setup_requirements(),
            "imageio",
            "imageio-ffmpeg",
        ]

    def _get_torch_requirements(self) -> List[str]:
        return torch_requirements("torch", "torchaudio")

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

    def _get_controlnet_model_class(self) -> Type[Any]:
        raise ValueError(f"ControlNet is not supported for architecture: {self.config.architecture}")
