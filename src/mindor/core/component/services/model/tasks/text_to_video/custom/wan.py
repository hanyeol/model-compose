from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, WanTextToVideoPreset
from mindor.dsl.schema.action import ModelActionConfig, WanTextToVideoModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import TextToVideoTaskAction
import io

if TYPE_CHECKING:
    import torch

_WAN_T2V_TASKS: Dict[WanTextToVideoPreset, str] = {
    WanTextToVideoPreset.T2V_A14B: "t2v-A14B",
    WanTextToVideoPreset.TI2V_5B:  "ti2v-5B",
}

class WanTextToVideoTaskAction(TextToVideoTaskAction):
    config: WanTextToVideoModelActionConfig

    def __init__(self, config: WanTextToVideoModelActionConfig, pipeline: Any, preset: WanTextToVideoPreset, cpu_offload: bool):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.preset: WanTextToVideoPreset = preset
        self.cpu_offload: bool = cpu_offload

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        (prompt,), is_single_input, is_streaming_input = await super()._prepare_input(context)

        negative_prompt = await context.render_text(self.config.negative_prompt) if self.config.negative_prompt is not None else None

        return (prompt, negative_prompt), is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        inference_steps = await context.render_scalar(self.config.params.inference_steps, int)
        guidance_scale  = await context.render_scalar(self.config.params.guidance_scale, float)
        shift           = await context.render_scalar(self.config.params.shift, float)

        params.update({
            "inference_steps": inference_steps,
            "guidance_scale":  guidance_scale,
            "shift":           shift,
        })

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        def _generate() -> List[VideoStreamResource]:
            prompts, negative_prompts = inputs
            negatives = negative_prompts if negative_prompts is not None else [ None ] * len(prompts)
            fps = params["fps"]
            results: List[VideoStreamResource] = []

            for prompt, negative in zip(prompts, negatives):
                size = f"{params['width']}*{params['height']}"
                video = self.pipeline.generate(
                    input_prompt=prompt,
                    size=size,
                    frame_num=params["num_frames"],
                    shift=params["shift"],
                    sample_solver="unipc",
                    sampling_steps=params["inference_steps"],
                    guide_scale=params["guidance_scale"],
                    n_prompt=negative or "",
                    seed=params["seed"] if params["seed"] is not None else -1,
                    offload_model=self.cpu_offload,
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

class WanTextToVideoTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch", "torchvision"),
            "diffusers",
            "transformers",
            "accelerate",
            "sentencepiece",
            "imageio",
            "imageio-ffmpeg",
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

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device_id = self.device.index if self.device.type == "cuda" and self.device.index is not None else 0
        task = _WAN_T2V_TASKS[self.config.preset]

        def _load() -> Any:
            if self.config.preset == WanTextToVideoPreset.T2V_A14B:
                return wan.WanT2V(config=WAN_CONFIGS[task], checkpoint_dir=model_path, device_id=device_id)

            if self.config.preset == WanTextToVideoPreset.TI2V_5B:
                return wan.WanTI2V(config=WAN_CONFIGS[task], checkpoint_dir=model_path, device_id=device_id)

            raise ValueError(f"Unsupported Wan text-to-video preset: {self.config.preset}")

        return await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await WanTextToVideoTaskAction(action, self.pipeline, self.config.preset, self.config.cpu_offload).run(context)
