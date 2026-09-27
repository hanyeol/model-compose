from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Union, Any
from mindor.dsl.schema.component import ModelComponentConfig, WanVideoToVideoPreset
from mindor.dsl.schema.action import ModelActionConfig, WanVideoToVideoModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.component.action.media import MediaInputPathResolver
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import VideoToVideoTaskAction
from PIL import Image as PILImage
import io, os, sys, shutil, tempfile

if TYPE_CHECKING:
    import torch

_WAN_V2V_TASKS: Dict[WanVideoToVideoPreset, str] = {
    WanVideoToVideoPreset.ANIMATE_14B: "animate-14B",
}

class WanVideoToVideoTaskAction(VideoToVideoTaskAction):
    config: WanVideoToVideoModelActionConfig

    def __init__(
        self,
        config: WanVideoToVideoModelActionConfig,
        animate_pipeline: Any,
        process_pipeline_factory: Any,
        preset: WanVideoToVideoPreset,
        cpu_offload: bool,
        has_sam2: bool,
        has_flux_kontext: bool,
    ):
        super().__init__(config)

        self.animate_pipeline: Any = animate_pipeline
        self.process_pipeline_factory: Any = process_pipeline_factory
        self.preset: WanVideoToVideoPreset = preset
        self.cpu_offload: bool = cpu_offload
        self.has_sam2: bool = has_sam2
        self.has_flux_kontext: bool = has_flux_kontext

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        inference_steps   = await context.render_scalar(self.config.params.inference_steps, int)
        guidance_scale    = await context.render_scalar(self.config.params.guidance_scale, float)
        shift             = await context.render_scalar(self.config.params.shift, float)
        clip_len          = await context.render_scalar(self.config.params.clip_len, int)
        refert_num        = await context.render_scalar(self.config.params.refert_num, int)
        preprocess_fps    = await context.render_scalar(self.config.params.preprocess_fps, int)
        resolution_width  = await context.render_scalar(self.config.params.resolution_width, int)
        resolution_height = await context.render_scalar(self.config.params.resolution_height, int)
        retarget_flag     = await context.render_scalar(self.config.params.retarget_flag, bool)
        use_flux          = await context.render_scalar(self.config.params.use_flux, bool)
        replace_flag      = await context.render_scalar(self.config.params.replace_flag, bool)
        mask_iterations   = await context.render_scalar(self.config.params.mask_iterations, int)
        mask_kernel_size  = await context.render_scalar(self.config.params.mask_kernel_size, int)
        mask_w_len        = await context.render_scalar(self.config.params.mask_w_len, int)
        mask_h_len        = await context.render_scalar(self.config.params.mask_h_len, int)

        if replace_flag and not self.has_sam2:
            raise ValueError("Wan-Animate `replace_flag=true` requires the component's `sam2_model` to be configured.")

        if use_flux:
            if not retarget_flag:
                raise ValueError("Wan-Animate `use_flux=true` requires `retarget_flag=true`.")

            if not self.has_flux_kontext:
                raise ValueError("Wan-Animate `use_flux=true` requires the component's `flux_kontext_model` to be configured.")

        params.update({
            "inference_steps":   inference_steps,
            "guidance_scale":    guidance_scale,
            "shift":             shift,
            "clip_len":          clip_len,
            "refert_num":        refert_num,
            "preprocess_fps":    preprocess_fps,
            "resolution_width":  resolution_width,
            "resolution_height": resolution_height,
            "retarget_flag":     retarget_flag,
            "use_flux":          use_flux,
            "replace_flag":      replace_flag,
            "mask_iterations":   mask_iterations,
            "mask_kernel_size":  mask_kernel_size,
            "mask_w_len":        mask_w_len,
            "mask_h_len":        mask_h_len,
        })

        return params

    async def _generate_batch(
        self,
        sources: List[Union[MediaSource, ImageArrayValue]],
        prompts: Optional[List[Optional[str]]],
        negative_prompts: Optional[List[Optional[str]]],
        reference_images: Optional[List[Optional[PILImage.Image]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        if reference_images is None or any(image is None for image in reference_images):
            raise ValueError("Wan-Animate requires a `reference_image` for every input in the batch.")

        prompts = prompts if prompts is not None else [ None ] * len(sources)
        negative_prompts = negative_prompts if negative_prompts is not None else [ None ] * len(sources)

        results: List[VideoStreamResource] = []

        for source, prompt, negative_prompt, reference_image in zip(sources, prompts, negative_prompts, reference_images):
            results.append(await self._generate(source, reference_image, prompt, negative_prompt, params))

        return results

    async def _generate(
        self,
        source: Union[MediaSource, ImageArrayValue],
        reference_image: PILImage.Image,
        prompt: Optional[str],
        negative_prompt: Optional[str],
        params: Dict[str, Any],
    ) -> VideoStreamResource:
        workspace = tempfile.mkdtemp(prefix="wan_animate_")
        reference_path = os.path.join(workspace, "reference.png")
        src_root_path = os.path.join(workspace, "src")
        os.makedirs(src_root_path, exist_ok=True)
        reference_image.save(reference_path)

        video_path, video_spooled = await self._resolve_source_path(source, workspace, params)

        def _generate() -> VideoStreamResource:
            process_pipeline = self.process_pipeline_factory(
                replace_flag=params["replace_flag"],
                use_flux=params["use_flux"],
            )
            process_pipeline(
                video_path=video_path,
                refer_image_path=reference_path,
                output_path=src_root_path,
                resolution_area=[params["resolution_width"], params["resolution_height"]],
                fps=params["preprocess_fps"],
                iterations=params["mask_iterations"],
                k=params["mask_kernel_size"],
                w_len=params["mask_w_len"],
                h_len=params["mask_h_len"],
                retarget_flag=params["retarget_flag"],
                use_flux=params["use_flux"],
                replace_flag=params["replace_flag"],
            )

            video = self.animate_pipeline.generate(
                src_root_path=src_root_path,
                replace_flag=params["replace_flag"],
                clip_len=params["clip_len"],
                refert_num=params["refert_num"],
                shift=params["shift"],
                sample_solver="unipc",
                sampling_steps=params["inference_steps"],
                guide_scale=params["guidance_scale"],
                input_prompt=prompt or "",
                n_prompt=negative_prompt or "",
                seed=params["seed"] if params["seed"] is not None else -1,
                offload_model=self.cpu_offload,
            )
            return self._encode_video_tensor_to_mp4(video, params["fps"])

        try:
            return await self._run_in_executor(_generate)
        finally:
            if video_spooled and video_path and os.path.exists(video_path):
                os.remove(video_path)

            shutil.rmtree(workspace, ignore_errors=True)

    async def _resolve_source_path(
        self,
        source: Union[MediaSource, ImageArrayValue],
        workspace: str,
        params: Dict[str, Any],
    ) -> tuple[str, bool]:
        """Return ``(video_path, spooled)`` — the driving clip as a filesystem path.

        MediaSource inputs may resolve to an existing file (not spooled) or a temp
        file the caller must delete. ImageArrayValue inputs are encoded to an mp4
        inside ``workspace``; that file lives with the workspace and isn't reported
        as spooled.
        """
        if isinstance(source, ImageArrayValue):
            frames = await self._collect_frames_from_image_array(
                source,
                params.get("num_frames"),
                params.get("width"),
                params.get("height"),
            )

            if not frames:
                raise ValueError("Wan-Animate received an empty frame sequence via `frames`.")

            video_path = os.path.join(workspace, "driving.mp4")
            fps = params["preprocess_fps"] if params["preprocess_fps"] and params["preprocess_fps"] > 0 else 30
            await self._run_in_executor(self._encode_frames_to_file, frames, video_path, fps)

            return video_path, False

        path, spooled = await MediaInputPathResolver().resolve(source, detect_format=True)

        if path is None:
            raise ValueError("Wan-Animate input video must resolve to a filesystem path.")

        return path, spooled

    @staticmethod
    def _encode_frames_to_file(frames: List[PILImage.Image], path: str, fps: int) -> None:
        import imageio.v3 as iio
        import numpy as np

        array = np.stack([np.asarray(frame.convert("RGB")) for frame in frames], axis=0)
        iio.imwrite(path, array, fps=fps, codec="libx264")

    @staticmethod
    def _encode_video_tensor_to_mp4(video: Any, fps: int) -> VideoStreamResource:
        """Encode a (C, T, H, W) or (T, H, W, C) tensor in [-1, 1] or [0, 1] range to an in-memory mp4."""
        import imageio.v3 as iio
        import numpy as np
        import torch

        tensor = video.detach().cpu() if hasattr(video, "detach") else video

        if isinstance(tensor, torch.Tensor):
            if tensor.ndim == 4 and tensor.shape[0] in (1, 3):
                tensor = tensor.permute(1, 2, 3, 0)
            array = tensor.numpy()
        else:
            array = np.asarray(tensor)

        if array.dtype != np.uint8:
            if array.min() < 0:
                array = (array + 1.0) / 2.0
            array = np.clip(array, 0.0, 1.0)
            array = (array * 255.0).round().astype(np.uint8)

        buffer = io.BytesIO()
        iio.imwrite(buffer, array, extension=".mp4", fps=fps, codec="libx264")

        return VideoStreamResource(buffer.getvalue(), format="mp4", attrs={ "fps": str(fps) })

class WanVideoToVideoTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.animate_pipeline: Optional[Any] = None
        self.pose2d_path: Optional[str] = None
        self.det_path: Optional[str] = None
        self.sam2_path: Optional[str] = None
        self.flux_kontext_path: Optional[str] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *torch_requirements("torch", "torchvision"),
            "diffusers",
            "transformers",
            "accelerate",
            "sentencepiece",
            "imageio-ffmpeg",
            "imageio",
            "decord",
            "opencv-python",
            "wan@git+https://github.com/Wan-Video/Wan2.2.git",
        ]

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.animate_pipeline = await self._load_animate_pipeline()
        self.pose2d_path      = await self._provision_model(self.config.pose2d_model, prefetch=True)
        self.det_path         = await self._provision_model(self.config.det_model, prefetch=True)
        self.sam2_path        = (await self._provision_model(self.config.sam2_model, prefetch=True)) if self.config.sam2_model is not None else None
        self.flux_kontext_path = (await self._provision_model(self.config.flux_kontext_model, prefetch=True)) if self.config.flux_kontext_model is not None else None

    async def _unload_model(self) -> None:
        self.animate_pipeline = None
        self.pose2d_path = None
        self.det_path = None
        self.sam2_path = None
        self.flux_kontext_path = None

    async def _load_animate_pipeline(self) -> Any:
        from wan.configs import WAN_CONFIGS
        import wan

        model_path = await self._provision_model(self.config.model, prefetch=True)

        # Wan2.2's WanAnimate hardcodes `self.device = torch.device(f"cuda:{device_id}")`
        # and uses torch.cuda.amp throughout — there is no viable non-CUDA path today.
        # Fail loudly rather than let the pipeline crash mid-generation with an opaque CUDA error.
        if self.device.type != "cuda":
            raise RuntimeError(
                f"Component '{self.id}': Wan video-to-video requires a CUDA device, "
                f"but resolved device is '{self.device.type}'. Set component.device to "
                "'cuda' or a specific 'cuda:N' index."
            )

        device_id = self.device.index if self.device.index is not None else 0
        task = _WAN_V2V_TASKS[self.config.preset]

        def _load() -> Any:
            if self.config.preset == WanVideoToVideoPreset.ANIMATE_14B:
                return wan.WanAnimate(config=WAN_CONFIGS[task], checkpoint_dir=model_path, device_id=device_id)

            raise ValueError(f"Unsupported Wan video-to-video preset: {self.config.preset}")

        return await self._run_in_executor(_load)

    def _build_process_pipeline(self, replace_flag: bool, use_flux: bool) -> Any:
        # The preprocess modules under wan/modules/animate/preprocess import each other with
        # bare `from pose2d import ...` statements, so the directory must be on sys.path.
        import wan as wan_pkg
        preprocess_dir = os.path.join(os.path.dirname(wan_pkg.__file__), "modules", "animate", "preprocess")
        if preprocess_dir not in sys.path:
            sys.path.insert(0, preprocess_dir)

        from process_pipepline import ProcessPipeline  # noqa: E501 — module name is `process_pipepline` upstream.

        return ProcessPipeline(
            det_checkpoint_path=self.det_path,
            pose2d_checkpoint_path=self.pose2d_path,
            sam_checkpoint_path=self.sam2_path if replace_flag else None,
            flux_kontext_path=self.flux_kontext_path if use_flux else None,
        )

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await WanVideoToVideoTaskAction(
            action,
            self.animate_pipeline,
            self._build_process_pipeline,
            self.config.preset,
            self.config.cpu_offload,
            self.config.sam2_model is not None,
            self.config.flux_kontext_model is not None,
        ).run(context)
