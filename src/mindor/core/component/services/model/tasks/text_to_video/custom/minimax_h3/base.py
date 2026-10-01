from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, MinimaxH3TextToVideoModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from .....base import ComponentActionContext, ModelTaskDriver
from ...common import TextToVideoTaskAction
import io

if TYPE_CHECKING:
    import torch

class MinimaxH3TextToVideoTaskAction(TextToVideoTaskAction):
    config: MinimaxH3TextToVideoModelActionConfig

    def __init__(
        self,
        config: MinimaxH3TextToVideoModelActionConfig,
        pipeline: Any,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        inference_steps = await context.render_variable(self.config.params.inference_steps)
        guidance_scale  = await context.render_variable(self.config.params.guidance_scale)

        params.update({
            "inference_steps": inference_steps,
            "guidance_scale":  guidance_scale,
        })

        return params

    async def _generate_batch(
        self,
        prompts: List[str],
        negative_prompts: Optional[List[Optional[str]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        def _generate() -> List[VideoStreamResource]:
            import torch

            negatives = negative_prompts if negative_prompts is not None else [ None ] * len(prompts)
            fps = int(params["fps"])
            seed = params["seed"]
            results: List[VideoStreamResource] = []

            for prompt, negative in zip(prompts, negatives):
                generator = torch.Generator(device=self.pipeline.device).manual_seed(int(seed)) if seed is not None else None

                output = self.pipeline(
                    prompt=prompt,
                    negative_prompt=negative,
                    height=int(params["height"]),
                    width=int(params["width"]),
                    num_frames=int(params["num_frames"]),
                    num_inference_steps=int(params["inference_steps"]),
                    guidance_scale=float(params["guidance_scale"]),
                    generator=generator,
                )

                results.append(self._encode_video_audio_to_mp4(output, fps))

            return results

        return await self._run_in_executor(_generate)

    def _encode_video_audio_to_mp4(self, output: Any, fps: int) -> VideoStreamResource:
        """Encode a MiniMax-H3 pipeline output (joint video+audio) into an in-memory mp4.

        MiniMax-H3 returns a video tensor at 24 fps alongside a 32 kHz stereo
        audio track in the same pipeline call. Both tracks are muxed into a
        single mp4 so the pipeline output stays a single `VideoStreamResource`
        the rest of the stack already understands.
        """
        import av

        video = self._extract_tensor(output, ("frames", "videos", "video", "images"))
        audio = self._extract_tensor(output, ("audios", "audio"))

        frames_np = self._video_tensor_to_uint8(video)
        audio_np, audio_rate = self._audio_tensor_to_numpy(audio)

        buffer = io.BytesIO()
        container = av.open(buffer, mode="w", format="mp4")

        try:
            height, width = int(frames_np.shape[1]), int(frames_np.shape[2])
            video_stream = container.add_stream("libx264", rate=fps)
            video_stream.width = width
            video_stream.height = height
            video_stream.pix_fmt = "yuv420p"
            audio_stream = None

            if audio_np is not None:
                audio_stream = container.add_stream("aac", rate=audio_rate)
                audio_stream.layout = "stereo" if audio_np.shape[0] == 2 else "mono"

            for frame in frames_np:
                av_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")

                for packet in video_stream.encode(av_frame):
                    container.mux(packet)

            for packet in video_stream.encode(None):
                container.mux(packet)

            if audio_stream is not None:
                af = av.AudioFrame.from_ndarray(audio_np, format="flt", layout=audio_stream.layout)
                af.sample_rate = audio_rate

                for packet in audio_stream.encode(af):
                    container.mux(packet)

                for packet in audio_stream.encode(None):
                    container.mux(packet)
        finally:
            container.close()

        attrs = { "fps": str(fps) }

        if audio_np is not None:
            attrs["audio_sample_rate"] = str(audio_rate)

        return VideoStreamResource(buffer.getvalue(), format="mp4", attrs=attrs)

    @staticmethod
    def _extract_tensor(output: Any, candidate_keys: Tuple[str, ...]) -> Any:
        for key in candidate_keys:
            tensor = getattr(output, key, None)

            if tensor is not None:
                return tensor

            if isinstance(output, dict) and key in output and output[key] is not None:
                return output[key]

        return None

    @staticmethod
    def _video_tensor_to_uint8(video: Any):
        import numpy as np
        import torch

        tensor = video[0] if isinstance(video, (list, tuple)) else video

        if isinstance(tensor, torch.Tensor):
            tensor = tensor.detach().to("cpu")

            if tensor.ndim == 5 and tensor.shape[0] == 1:
                tensor = tensor[0]

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

        return array

    @staticmethod
    def _audio_tensor_to_numpy(audio: Any):
        import numpy as np
        import torch

        if audio is None:
            return None, 32000

        sample_rate = 32000
        tensor = audio

        if isinstance(audio, (list, tuple)) and audio:
            tensor = audio[0]

        if isinstance(audio, dict):
            tensor = audio.get("waveform") or audio.get("audio")
            sample_rate = int(audio.get("sample_rate", sample_rate))

        if isinstance(tensor, torch.Tensor):
            tensor = tensor.detach().to("cpu")

            if tensor.ndim == 3 and tensor.shape[0] == 1:
                tensor = tensor[0]

            if tensor.ndim == 1:
                tensor = tensor.unsqueeze(0)

            array = tensor.to(torch.float32).numpy()
        else:
            array = np.asarray(tensor, dtype=np.float32)

            if array.ndim == 1:
                array = array[np.newaxis, :]

        return array, sample_rate


class MinimaxH3TextToVideoTaskDriverBase(ModelTaskDriver):
    """Shared pipeline loader for the MiniMax-H3 text-to-video task.

    Subclasses are the per-backend drivers; the only backend-specific
    responsibility they add is (optionally) swapping the main transformer
    blocks' attention processor after the pipeline is loaded.
    """

    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch", "torchvision"),
            "diffusers>=0.36",
            "transformers>=4.45",
            "accelerate>=0.34",
            "safetensors>=0.4",
            "huggingface_hub>=0.25",
            "sentencepiece",
            "soundfile>=0.12",
            "imageio>=2.34",
            "imageio-ffmpeg>=0.5",
            "av>=11",
            "Pillow>=10",
            "numpy>=1.24",
        ]

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.pipeline = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None

    async def _load_pipeline(self) -> Any:
        from diffusers import DiffusionPipeline

        model_path = await self._provision_model(self.config.model, prefetch=True)

        def _load() -> Any:
            import torch

            pipeline = DiffusionPipeline.from_pretrained(
                model_path,
                torch_dtype=torch.bfloat16,
                trust_remote_code=True,
            )

            if self.cpu_offload:
                pipeline.enable_model_cpu_offload()
            else:
                pipeline = pipeline.to(self.device)

            return pipeline

        return await self._run_in_executor(_load)

    @property
    def cpu_offload(self) -> bool:
        return bool(getattr(self.config, "cpu_offload", False))
