from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Union, Any
from mindor.dsl.schema.action import ModelActionConfig, AnimateDiffHuggingfaceVideoToVideoModelActionConfig
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceVideoToVideoModelArchitecture
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource, encode_frames_to_mp4
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskService
from .common import VideoToVideoTaskAction
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

class PipelineCancelled(Exception):
    pass

class AnimateDiffHuggingfaceVideoToVideoTaskAction(VideoToVideoTaskAction):
    config: AnimateDiffHuggingfaceVideoToVideoModelActionConfig

    def __init__(
        self,
        config: AnimateDiffHuggingfaceVideoToVideoModelActionConfig,
        pipeline: DiffusionPipeline,
        device: Optional[torch.device],
    ):
        super().__init__(config)

        self.pipeline: DiffusionPipeline = pipeline
        self.device: Optional[torch.device] = device

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        inference_steps  = await context.render_scalar(self.config.params.inference_steps, int)
        guidance_scale   = await context.render_scalar(self.config.params.guidance_scale, float)
        denoise_strength = await context.render_scalar(self.config.params.denoise_strength, float)

        params.update({
            "inference_steps":  inference_steps,
            "guidance_scale":   guidance_scale,
            "denoise_strength": denoise_strength,
        })

        return params

    async def _generate_batch(
        self,
        sources: List[Union[MediaSource, ImageArrayValue]],
        prompts: Optional[List[Optional[str]]],
        negative_prompts: Optional[List[Optional[str]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        batch_frames: List[List[PILImage.Image]] = await self._collect_frames(sources, params)
        prompts = prompts if prompts is not None else [ None ] * len(batch_frames)
        negative_prompts = negative_prompts if negative_prompts is not None else [ None ] * len(batch_frames)

        def _generate() -> List[VideoStreamResource]:
            import torch

            results: List[VideoStreamResource] = []

            for frames, prompt, negative_prompt in zip(batch_frames, prompts, negative_prompts):
                if not frames:
                    raise ValueError("AnimateDiff received an empty frame batch.")

                generator: Optional[torch.Generator] = None

                if params["seed"] is not None:
                    generator = torch.Generator(device=self.device).manual_seed(params["seed"])

                pipeline_params: Dict[str, Any] = {
                    "video":               frames,
                    "prompt":              prompt or "",
                    "strength":            params["denoise_strength"],
                    "guidance_scale":      params["guidance_scale"],
                    "num_inference_steps": params["inference_steps"],
                    "generator":           generator,
                }

                if negative_prompt is not None:
                    pipeline_params["negative_prompt"] = negative_prompt

                if params["width"] is not None:
                    pipeline_params["width"] = params["width"]

                if params["height"] is not None:
                    pipeline_params["height"] = params["height"]

                if cancellation_token is not None:
                    def _abort_if_cancelled(pipe, step, timestep, callback_kwargs):
                        if cancellation_token.is_cancelled():
                            raise PipelineCancelled()

                        return callback_kwargs

                    pipeline_params["callback_on_step_end"] = _abort_if_cancelled

                try:
                    result = self.pipeline(**pipeline_params)
                except PipelineCancelled:
                    raise asyncio.CancelledError()

                frames: List[PILImage.Image] = result.frames[0]
                width, height = frames[0].size # AnimateDiff guarantees uniform frame size
                results.append(encode_frames_to_mp4(frames, width, height, params["fps"]))

            return results

        return await self._run_in_executor(_generate)

    async def _collect_frames(
        self,
        sources: List[Union[MediaSource, ImageArrayValue]],
        params: Dict[str, Any],
    ) -> List[List[PILImage.Image]]:
        num_frames = params.get("num_frames")
        width      = params.get("width")
        height     = params.get("height")

        frames: List[List[PILImage.Image]] = []

        for source in sources:
            if isinstance(source, MediaSource):
                frames.append(await self._collect_frames_from_video(source, num_frames, width, height))
            else:
                frames.append(await self._collect_frames_from_image_array(source, num_frames, width, height))

        return frames

@register_model_task_service(ModelTaskType.VIDEO_TO_VIDEO, ModelDriver.HUGGINGFACE)
class HuggingfaceVideoToVideoTaskService(HuggingfaceDiffusionPipelineTaskService[None]):
    def _get_setup_requirements(self) -> List[str]:
        return [
            *super()._get_setup_requirements(),
            "transformers",
            "accelerate",
            "imageio",
            "imageio-ffmpeg",
        ]

    async def _load_pipeline_submodules(self, device: torch.device, dtype: torch.dtype) -> Dict[str, Any]:
        if self.config.architecture == HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF:
            from diffusers import MotionAdapter

            adapter_path = await self._provision_model(self.config.motion_adapter)
            logging.info(f"Component '{self.id}': loading MotionAdapter from {adapter_path}")

            def _load() -> Any:
                params: Dict[str, Any] = {
                    **self._get_model_params(self.config.motion_adapter),
                    "torch_dtype": dtype,
                }

                return MotionAdapter.from_pretrained(adapter_path, **params).to(device)

            adapter = await self._run_in_executor(_load)

            return { "motion_adapter": adapter }

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_pipeline_class(self, method: Optional[None]) -> Type[DiffusionPipeline]:
        if self.config.architecture == HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF:
            from diffusers import AnimateDiffVideoToVideoPipeline
            return AnimateDiffVideoToVideoPipeline

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch

        if self.config.architecture == HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF:
            return torch.float16

        return torch.bfloat16

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pipeline = self.pipelines.get(None) if self.pipelines else None

        if pipeline is None:
            raise ValueError(f"No pipeline loaded for architecture: {self.config.architecture}")

        if self.config.architecture == HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF:
            return await AnimateDiffHuggingfaceVideoToVideoTaskAction(action, pipeline, self.device).run(context)

        raise ValueError(f"Unknown architecture: {self.config.architecture}")
