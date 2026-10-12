from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Type, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig, AnimateDiffHuggingfaceVideoToVideoModelActionConfig
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig, HuggingfaceVideoToVideoModelArchitecture, DiffusionControlNetConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
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

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Tuple[Any, ...], bool, bool]:
        video           = await context.render_video(self.config.video) if self.config.video is not None else None
        frames          = await context.render_image_array(self.config.frames, single_as_array=True) if self.config.frames is not None else None
        prompt          = await context.render_text(self.config.prompt) if self.config.prompt is not None else None
        negative_prompt = await context.render_text(self.config.negative_prompt) if self.config.negative_prompt is not None else None
        reference_image = await context.render_image(self.config.reference_image) if self.config.reference_image is not None else None

        if self.controlnet_count > 0 and self.config.conditioning_frames is not None:
            conditioning_frames = await context.render_image_array(self.config.conditioning_frames, single_as_array=True, item_is_list=True)
        else:
            conditioning_frames = None

        source = frames if video is None else video

        is_single_input    = not isinstance(source, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(source, (StreamIterator, AsyncIterator))

        return (source, prompt, negative_prompt, reference_image, conditioning_frames), is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        pipeline_params: Dict[str, Any] = await self._resolve_pipeline_params(context)
        seed             = await context.render_scalar(self.config.seed, int)
        num_frames       = await context.render_scalar(self.config.params.num_frames, int)
        frame_rate       = await context.render_scalar(self.config.params.frame_rate, float)
        ip_adapter_scale = await context.render_scalar(self.config.params.ip_adapter_scale, float)

        free_noise: Optional[Dict[str, Any]] = None

        if self.config.params.free_noise is not None:
            free_noise = {
                "context_length":   await context.render_scalar(self.config.params.free_noise.context_length, int),
                "context_stride":   await context.render_scalar(self.config.params.free_noise.context_stride, int),
                "weighting_scheme": await context.render_variable(self.config.params.free_noise.weighting_scheme),
            }

        params.update({
            "pipeline":         pipeline_params,
            "seed":             seed,
            "num_frames":       num_frames,
            "frame_rate":       frame_rate,
            "ip_adapter_scale": ip_adapter_scale,
            "free_noise":       free_noise,
        })

        return params

    async def _resolve_pipeline_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        """Build the pipeline kwargs shared across the batch (resolution, step
        count, guidance, ControlNet runtime scalars). Per-input kwargs
        (``video``, ``prompt``, ``conditioning_frames``, ``ip_adapter_image``)
        are added in ``_generate_batch``.
        """
        inference_steps   = await context.render_scalar(self.config.params.inference_steps, int)
        guidance_scale    = await context.render_scalar(self.config.params.guidance_scale, float)
        denoise_strength  = await context.render_scalar(self.config.params.denoise_strength, float)
        width             = await context.render_scalar(self.config.params.width, int)
        height            = await context.render_scalar(self.config.params.height, int)
        clip_skip         = await context.render_scalar(self.config.params.clip_skip, int) if self.config.params.clip_skip is not None else None
        decode_chunk_size = await context.render_scalar(self.config.params.decode_chunk_size, int) if self.config.params.decode_chunk_size is not None else None

        params: Dict[str, Any] = {
            "num_inference_steps": inference_steps,
            "guidance_scale":      guidance_scale,
            "strength":            denoise_strength,
        }

        if width is not None:
            params["width"] = width

        if height is not None:
            params["height"] = height

        if clip_skip is not None:
            params["clip_skip"] = clip_skip

        if decode_chunk_size is not None:
            params["decode_chunk_size"] = decode_chunk_size

        if self.controlnet_count > 0:
            if self.config.conditioning_frames is None:
                raise ValueError(
                    f"ControlNet is configured on the component ({self.controlnet_count} net(s)) "
                    "but `conditioning_frames` is not set on the action."
                )

            conditioning_scale = await context.render_variable(self.config.params.controlnet_conditioning_scale)
            guidance_start     = await context.render_variable(self.config.params.control_guidance_start)
            guidance_end       = await context.render_variable(self.config.params.control_guidance_end)

            params.update({
                "controlnet_conditioning_scale": conditioning_scale,
                "control_guidance_start":        guidance_start,
                "control_guidance_end":          guidance_end,
            })

        return params

    async def _build_pipeline_conditioning_frames(
        self,
        conditioning_frames: List[Any],
        num_frames: Optional[int],
        width: Optional[int],
        height: Optional[int],
    ) -> List[Any]:
        """Collect per-input conditioning frames into pipeline's shape.

        Each inner frame sequence is sampled and resized with the same
        first-N truncation and resize transform the input-frame path uses,
        so diffusers' ``check_inputs`` length check passes and the control
        processor doesn't stretch mismatched aspect ratios.

        diffusers wants ``List[PIL]`` (one frame sequence) for a single
        ControlNet and ``List[List[PIL]]`` for multi-ControlNet with
        outer=ControlNet, inner=frames.
        """
        conditioning_frames = [
            [ await self._collect_frames_from_image_array(images, num_frames, width, height) for images in await frames.collect() ]
            for frames in conditioning_frames
        ]

        if self.controlnet_count == 1:
            return [ frames[0] for frames in conditioning_frames ]

        return [ list(frames) for frames in zip(*conditioning_frames) ]

    async def _generate_batch(
        self,
        inputs: Tuple[Any, ...],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        sources, prompts, negative_prompts, reference_images, conditioning_frames = inputs

        batch_frames, batch_fps = await self._collect_batch_frames(sources, params)

        if self.controlnet_count > 0:
            batch_conditioning_frames = await self._build_pipeline_conditioning_frames(
                conditioning_frames,
                params.get("num_frames"),
                params["pipeline"].get("width"),
                params["pipeline"].get("height"),
            )
        else:
            batch_conditioning_frames = None

        prompts = prompts if prompts is not None else [ None ] * len(batch_frames)
        negative_prompts = negative_prompts if negative_prompts is not None else [ None ] * len(batch_frames)
        reference_images = reference_images if reference_images is not None else [ None ] * len(batch_frames)

        def _generate() -> List[VideoStreamResource]:
            # Toggle per invocation so a prior action's FreeNoise state doesn't carry over.
            if params["free_noise"] is not None:
                self.pipeline.enable_free_noise(**params["free_noise"])
            else:
                self.pipeline.disable_free_noise()

            results: List[VideoStreamResource] = []

            for index, (frames, fps, prompt, negative_prompt, reference_image) in enumerate(zip(batch_frames, batch_fps, prompts, negative_prompts, reference_images)):
                if not frames:
                    raise ValueError("AnimateDiff received an empty frame batch.")

                pipeline_params: Dict[str, Any] = {
                    **params["pipeline"],
                    "video":  frames,
                    "prompt": prompt or "",
                }

                if negative_prompt is not None:
                    pipeline_params["negative_prompt"] = negative_prompt

                if reference_image is not None:
                    # `load_ip_adapter` attaches the projection onto `unet.encoder_hid_proj`;
                    # if it's still None, the component didn't declare `ip_adapter`.
                    if getattr(self.pipeline.unet, "encoder_hid_proj", None) is None:
                        raise ValueError("`reference_image` was supplied but no `ip_adapter` is configured on the component.")

                    pipeline_params["ip_adapter_image"] = reference_image
                    self.pipeline.set_ip_adapter_scale(params["ip_adapter_scale"])

                if batch_conditioning_frames is not None:
                    pipeline_params["conditioning_frames"] = (
                        [ frames[index] for frames in batch_conditioning_frames ]
                        if self.controlnet_count > 1
                        else batch_conditioning_frames[index]
                    )

                result = self._process_pipeline(pipeline_params, params, cancellation_token)

                output_frames: List[PILImage.Image] = result.frames[0]
                width, height = output_frames[0].size  # AnimateDiff guarantees uniform frame size
                output_fps = params["frame_rate"] if params["frame_rate"] is not None else (int(round(fps)) if fps else 8)
                results.append(encode_frames_to_mp4(output_frames, width, height, output_fps))

            return results

        return await self._run_in_executor(_generate)

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

    async def _collect_batch_frames(
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
        width      = params["pipeline"].get("width")
        height     = params["pipeline"].get("height")

        batch_frames: List[List[PILImage.Image]] = []
        batch_fps: List[Optional[float]] = []

        for source in sources:
            if isinstance(source, MediaSource):
                frames, fps = await self._collect_frames_from_video(source, num_frames, width, height)
                batch_frames.append(frames)
                batch_fps.append(fps)
            else:
                frames = await self._collect_frames_from_image_array(source, num_frames, width, height)
                batch_frames.append(frames)
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
