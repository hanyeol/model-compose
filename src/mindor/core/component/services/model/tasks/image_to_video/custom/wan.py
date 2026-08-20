from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig, WanImageToVideoPreset
from mindor.dsl.schema.action import ModelActionConfig, WanImageToVideoModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from ....base import ComponentActionContext, ModelTaskService
from ..common import ImageToVideoTaskAction
from PIL import Image as PILImage
import io

if TYPE_CHECKING:
    import torch

_WAN_I2V_TASKS: Dict[WanImageToVideoPreset, str] = {
    WanImageToVideoPreset.WAN22_I2V_A14B: "i2v-A14B",
    WanImageToVideoPreset.WAN22_TI2V_5B:  "ti2v-5B",
}

class WanImageToVideoTaskAction(ImageToVideoTaskAction):
    config: WanImageToVideoModelActionConfig

    def __init__(self, config: WanImageToVideoModelActionConfig, pipeline: Any, preset: WanImageToVideoPreset):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.preset: WanImageToVideoPreset = preset

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        inference_steps = await context.render_variable(self.config.params.inference_steps)
        guidance_scale  = await context.render_variable(self.config.params.guidance_scale)
        shift           = await context.render_variable(self.config.params.shift)

        params.update({
            "inference_steps": inference_steps,
            "guidance_scale":  guidance_scale,
            "shift":           shift,
        })

        return params

    async def _generate_batch(
        self,
        images: List[PILImage.Image],
        prompts: Optional[List[Optional[str]]],
        negative_prompts: Optional[List[Optional[str]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        def _generate() -> List[VideoStreamResource]:
            captions = prompts if prompts is not None else [ None ] * len(images)
            negatives = negative_prompts if negative_prompts is not None else [ None ] * len(images)
            fps = int(params["fps"])
            results: List[VideoStreamResource] = []

            for image, caption, negative in zip(images, captions, negatives):
                width = int(params["width"]) if params["width"] is not None else image.width
                height = int(params["height"]) if params["height"] is not None else image.height
                pixel_area = width * height

                video = self.pipeline.generate(
                    input_prompt=caption or "",
                    img=image,
                    max_area=pixel_area,
                    frame_num=int(params["num_frames"]),
                    shift=float(params["shift"]),
                    sample_solver="unipc",
                    sampling_steps=int(params["inference_steps"]),
                    guide_scale=float(params["guidance_scale"]),
                    n_prompt=negative or "",
                    seed=int(params["seed"]) if params["seed"] is not None else -1,
                    offload_model=False,
                )
                results.append(self._encode_video_tensor_to_mp4(video, fps))

            return results

        return await self._run_in_executor(_generate)

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

class WanImageToVideoTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            "torch",
            "torchvision",
            "diffusers",
            "transformers",
            "accelerate",
            "sentencepiece",
            "imageio-ffmpeg",
            "imageio",
            "wan@git+https://github.com/Wan-Video/Wan2.2.git",
        ]

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.pipeline = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None

    async def _load_pipeline(self) -> Any:
        from wan.configs import WAN_CONFIGS
        import wan

        task = _WAN_I2V_TASKS[self.config.preset]
        model_path = await self._provision_model(self.config.model, prefetch=True)
        device_id = self.device.index if self.device.type == "cuda" and self.device.index is not None else 0

        if self.config.preset == WanImageToVideoPreset.WAN22_I2V_A14B:
            return wan.WanI2V(config=WAN_CONFIGS[task], checkpoint_dir=model_path, device_id=device_id)

        if self.config.preset == WanImageToVideoPreset.WAN22_TI2V_5B:
            return wan.WanTI2V(config=WAN_CONFIGS[task], checkpoint_dir=model_path, device_id=device_id)

        raise ValueError(f"Unsupported Wan image-to-video preset: {self.config.preset}")

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await WanImageToVideoTaskAction(action, self.pipeline, self.config.preset).run(context)
