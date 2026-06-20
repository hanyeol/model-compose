from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelActionConfig, HunyuanImageGenerationModelActionConfig
from mindor.core.logger import logging
from ....base import ComponentActionContext
from ..common import ImageGenerationTaskService, ImageGenerationTaskAction
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from diffusers import HunyuanImagePipeline
    import torch

class HunyuanImageGenerationTaskAction(ImageGenerationTaskAction):
    def __init__(
        self,
        config: HunyuanImageGenerationModelActionConfig,
        pipeline: HunyuanImagePipeline,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.config: HunyuanImageGenerationModelActionConfig = config
        self.pipeline: HunyuanImagePipeline = pipeline

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        negative_prompt          = await context.render_variable(self.config.params.negative_prompt)
        num_inference_steps      = int(await context.render_variable(self.config.params.num_inference_steps))
        distilled_guidance_scale = float(await context.render_variable(self.config.params.distilled_guidance_scale))
        width                    = int(await context.render_variable(self.config.params.width))
        height                   = int(await context.render_variable(self.config.params.height))
        num_images_per_prompt    = int(await context.render_variable(self.config.params.num_images_per_prompt))
        seed                     = await context.render_variable(self.config.params.seed)

        params.update({
            "negative_prompt":          negative_prompt,
            "num_inference_steps":      num_inference_steps,
            "distilled_guidance_scale": distilled_guidance_scale,
            "width":                    width,
            "height":                   height,
            "num_images_per_prompt":    num_images_per_prompt,
            "seed":                     int(seed) if seed is not None else None,
        })

        return params

    async def _generate(self, texts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[PILImage.Image]:
        return await loop.run_in_executor(None, self._generate_batch, texts, params)

    def _generate_batch(self, texts: List[str], params: Dict[str, Any]) -> List[PILImage.Image]:
        import torch

        generator: Optional[torch.Generator] = None

        if params["seed"] is not None:
            generator = torch.Generator(device=self.device).manual_seed(params["seed"])

        result = self.pipeline(
            prompt=texts,
            negative_prompt=params["negative_prompt"],
            num_inference_steps=params["num_inference_steps"],
            distilled_guidance_scale=params["distilled_guidance_scale"],
            width=params["width"],
            height=params["height"],
            num_images_per_prompt=params["num_images_per_prompt"],
            generator=generator,
        )

        return list(result.images)

class HunyuanImageGenerationTaskService(ImageGenerationTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[HunyuanImagePipeline] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "diffusers", "transformers", "accelerate", "sentencepiece", "torch" ]

    async def _load_model(self) -> None:
        self.pipeline, self.device = self._load_pretrained_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    def _load_pretrained_pipeline(self) -> Tuple[HunyuanImagePipeline, torch.device]:
        from diffusers import HunyuanImagePipeline
        import torch

        device = self._resolve_device()
        torch_dtype = torch.bfloat16 if device.type in ("cuda", "mps") else torch.float32

        params = self._resolve_pipeline_params()
        params["torch_dtype"] = torch_dtype

        source = self._resolve_pipeline_source()
        logging.info(f"Component '{self.id}': loading Hunyuan-Image pipeline from {source}")

        pipeline = HunyuanImagePipeline.from_pretrained(source, **params)
        pipeline = pipeline.to(device)

        return pipeline, device

    def _resolve_pipeline_source(self) -> str:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            return self.config.model.repository

        if isinstance(self.config.model, LocalModelConfig):
            return self.config.model.path

        if isinstance(self.config.model, str):
            return self.config.model

        raise ValueError(f"Unsupported model config type for Hunyuan-Image: {type(self.config.model).__name__}")

    def _resolve_pipeline_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision
            if self.config.model.cache_dir:
                params["cache_dir"] = self.config.model.cache_dir
            if self.config.model.token:
                params["token"] = self.config.model.token
            if self.config.model.local_files_only:
                params["local_files_only"] = bool(self.config.model.local_files_only)

        return params

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HunyuanImageGenerationTaskAction(action, self.pipeline, self.device).run(context, loop)
