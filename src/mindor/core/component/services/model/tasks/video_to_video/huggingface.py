from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Type, Optional, Dict, List, Tuple, Union, Any
from mindor.dsl.schema.action import ModelActionConfig, AnimateDiffHuggingfaceVideoToVideoModelActionConfig
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig, HuggingfaceVideoToVideoModelArchitecture, DiffusionControlNetConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource, encode_frames_to_mp4
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.diffusion import HuggingfaceDiffusionPipelineTaskDriver
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
        controlnet_count: int = 0,
    ):
        super().__init__(config)

        self.pipeline: DiffusionPipeline = pipeline
        self.device: Optional[torch.device] = device
        self.controlnet_count: int = controlnet_count

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        inference_steps  = await context.render_scalar(self.config.params.inference_steps, int)
        guidance_scale   = await context.render_scalar(self.config.params.guidance_scale, float)
        denoise_strength = await context.render_scalar(self.config.params.denoise_strength, float)
        ip_adapter_scale = await context.render_scalar(self.config.params.ip_adapter_scale, float)

        params.update({
            "inference_steps":  inference_steps,
            "guidance_scale":   guidance_scale,
            "denoise_strength": denoise_strength,
            "ip_adapter_scale": ip_adapter_scale,
        })

        if self.controlnet_count > 0:
            params.update(await self._resolve_controlnet_pipeline_params(context))

        return params

    async def _resolve_controlnet_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        """Collect ControlNet runtime inputs and shape them for the pipeline call."""
        if self.config.conditioning_frames is None:
            raise ValueError(
                f"ControlNet is configured on the component ({self.controlnet_count} net(s)) "
                "but `conditioning_frames` is not set on the action."
            )

        references = self.config.conditioning_frames
        if not isinstance(references, list):
            references = [ references ]

        if len(references) != self.controlnet_count:
            raise ValueError(
                f"`conditioning_frames` has {len(references)} entries but the component "
                f"loaded {self.controlnet_count} ControlNet(s); counts must match."
            )

        conditioning_frames: List[List[PILImage.Image]] = []
        for reference in references:
            frames = await context.render_image_array(reference, single_as_array=True)
            conditioning_frames.append(await frames.collect())

        conditioning_scale = await context.render_variable(self.config.controlnet_conditioning_scale)
        guidance_start     = await context.render_variable(self.config.control_guidance_start)
        guidance_end       = await context.render_variable(self.config.control_guidance_end)

        return {
            "conditioning_frames":           conditioning_frames,
            "controlnet_conditioning_scale": conditioning_scale,
            "control_guidance_start":        guidance_start,
            "control_guidance_end":          guidance_end,
        }

    async def _generate_batch(
        self,
        sources: List[Union[MediaSource, ImageArrayValue]],
        prompts: Optional[List[Optional[str]]],
        negative_prompts: Optional[List[Optional[str]]],
        reference_images: Optional[List[Optional[PILImage.Image]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        batch_frames, batch_fps = await self._collect_frames(sources, params)
        prompts = prompts if prompts is not None else [ None ] * len(batch_frames)
        negative_prompts = negative_prompts if negative_prompts is not None else [ None ] * len(batch_frames)
        reference_images = reference_images if reference_images is not None else [ None ] * len(batch_frames)

        def _generate() -> List[VideoStreamResource]:
            import torch

            results: List[VideoStreamResource] = []

            for frames, fps, prompt, negative_prompt, reference_image in zip(batch_frames, batch_fps, prompts, negative_prompts, reference_images):
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

                if reference_image is not None:
                    # `load_ip_adapter` attaches the projection onto `unet.encoder_hid_proj`;
                    # if it's still None, the component didn't declare `ip_adapter`.
                    if getattr(self.pipeline.unet, "encoder_hid_proj", None) is None:
                        raise ValueError("`reference_image` was supplied but no `ip_adapter` is configured on the component.")

                    pipeline_params["ip_adapter_image"] = reference_image
                    self.pipeline.set_ip_adapter_scale(params["ip_adapter_scale"])

                if self.controlnet_count > 0:
                    conditioning_frames = params["conditioning_frames"]
                    pipeline_params["conditioning_frames"] = conditioning_frames if self.controlnet_count > 1 else conditioning_frames[0]
                    pipeline_params["controlnet_conditioning_scale"] = params["controlnet_conditioning_scale"]
                    pipeline_params["control_guidance_start"] = params["control_guidance_start"]
                    pipeline_params["control_guidance_end"] = params["control_guidance_end"]

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
                fps = params["frame_rate"] if params["frame_rate"] is not None else (int(round(fps)) if fps else 8)
                results.append(encode_frames_to_mp4(frames, width, height, fps))

            return results

        return await self._run_in_executor(_generate)

    async def _collect_frames(
        self,
        sources: List[Union[MediaSource, ImageArrayValue]],
        params: Dict[str, Any],
    ) -> Tuple[List[List[PILImage.Image]], List[Optional[float]]]:
        """Collect batch frames along with each clip's detected native fps.

        Video sources report their native fps via imageio metadata; image_array
        inputs can't, so their slot is left None and callers fall back to the
        action's `fps` (or a default) when encoding.
        """
        num_frames = params.get("num_frames")
        width      = params.get("width")
        height     = params.get("height")

        batch_frames: List[List[PILImage.Image]] = []
        batch_fps: List[Optional[float]] = []

        for source in sources:
            if isinstance(source, MediaSource):
                frames, fps = await self._collect_frames_from_video(source, num_frames, width, height)
                batch_frames.append(frames)
                batch_fps.append(fps)
            else:
                batch_frames.append(await self._collect_frames_from_image_array(source, num_frames, width, height))
                batch_fps.append(None)

        return batch_frames, batch_fps

@register_model_task_driver(ModelTaskType.VIDEO_TO_VIDEO, ModelDriverType.HUGGINGFACE)
class HuggingfaceVideoToVideoTaskDriver(HuggingfaceDiffusionPipelineTaskDriver[None]):
    def _get_setup_requirements(self) -> List[Union[str, Tuple[str, List[str]]]]:
        return [
            *super()._get_setup_requirements(),
            # transformers imports torchaudio at runtime; pin it to the same torch
            # wheel channel so pip doesn't resolve it via PyPI's default index and
            # produce an ABI-incompatible build.
            *torch_requirements("torchaudio"),
            "imageio",
            "imageio-ffmpeg",
        ]

    async def _load_model(self) -> None:
        await super()._load_model()

        if self.config.ip_adapter is not None:
            await self._attach_ip_adapters()

    async def _load_pipeline_submodules(self, device: torch.device, dtype: torch.dtype) -> Dict[str, Any]:
        if self.config.architecture == HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF:
            submodules: Dict[str, Any] = {
                "motion_adapter": await self._load_pretrained_motion_adapter(self.config.motion_adapter, device, dtype),
            }

            if self.config.controlnet:
                submodules["controlnet"] = await self._load_pretrained_controlnet_models(self.config.controlnet, device, dtype)

            return submodules

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    async def _load_pretrained_motion_adapter(
        self,
        motion_adapter: ModelConfig,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Any:
        from diffusers import MotionAdapter

        adapter_path = await self._provision_model(motion_adapter)

        def _load() -> Any:
            logging.info(f"Component '{self.id}': loading {MotionAdapter.__name__} from {adapter_path}")

            params: Dict[str, Any] = {
                **self._get_model_params(motion_adapter),
                "torch_dtype": dtype,
            }

            return MotionAdapter.from_pretrained(adapter_path, **params).to(device)

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

    async def _attach_ip_adapters(self) -> None:
        adapter_path = await self._provision_model(self.config.ip_adapter)
        adapter_filename = self.config.ip_adapter.filename if hasattr(self.config.ip_adapter, "filename") else None

        if not adapter_filename:
            raise ValueError("`ip_adapter.filename` must specify `<subfolder>/<weight_name>` (e.g. `models/ip-adapter_sd15.bin`).")

        subfolder, _, weight_name = adapter_filename.rpartition("/")
        logging.info(f"Component '{self.id}': loading IP-Adapter weights '{weight_name}' from {adapter_path}")

        def _load() -> None:
            for pipeline in self.pipelines.values():
                pipeline.load_ip_adapter(adapter_path, subfolder=subfolder or None, weight_name=weight_name)

        await self._run_in_executor(_load)

    def _get_pipeline_class(self, method: Optional[None]) -> Type[DiffusionPipeline]:
        if self.config.architecture == HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF:
            if self._get_controlnet_count() > 0:
                from diffusers import AnimateDiffVideoToVideoControlNetPipeline
                return AnimateDiffVideoToVideoControlNetPipeline
            else:
                from diffusers import AnimateDiffVideoToVideoPipeline
                return AnimateDiffVideoToVideoPipeline

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_controlnet_model_class(self) -> Type[Any]:
        if self.config.architecture == HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF:
            from diffusers import ControlNetModel
            return ControlNetModel

        raise ValueError(f"ControlNet is not supported for architecture: {self.config.architecture}")

    def _get_controlnet_count(self) -> int:
        return len(self.config.controlnet) if self.config.controlnet else 0

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
            return await AnimateDiffHuggingfaceVideoToVideoTaskAction(action, pipeline, self.device, self._get_controlnet_count()).run(context)

        raise ValueError(f"Unknown architecture: {self.config.architecture}")
