from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Tuple, Any
from mindor.dsl.schema.component import (
    ModelComponentConfig,
    ModelSubmoduleConfig,
)
from mindor.dsl.schema.action import ModelActionConfig, PiH3TextToVideoModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import (
    install_package,
    install_package_from_github,
    is_package_installed,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.logger import logging
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import TextToVideoTaskAction
import io

if TYPE_CHECKING:
    from transformers import PreTrainedModel
    import torch

# FP8 quantization exclusion lists documented in the LakonLab piH3 recipe.
# The DWD head and pre/post projections must stay in high precision or the
# final-step pixel prediction degrades sharply.
_PI_H3_TRANSFORMER_FP8_EXCLUDE: Tuple[str, ...] = (
    "lora", "norm_out", "proj_out", "dwd_linear_head",
)

_PI_H3_TEXT_ENCODER_FP8_EXCLUDE: Tuple[str, ...] = (
    "lm_head",
)

# Shared with the base MiniMax-H3 pipeline: the video VAE decodes frame counts
# of the form 17*n + 5, clamped to 5..15 seconds at the fixed 24 fps.
_PI_H3_FRAME_STEP = 17
_PI_H3_FRAME_OFFSET = 5
_PI_H3_MIN_FRAMES = 124
_PI_H3_MAX_FRAMES = 345

_PI_H3_DWD_OUTPUT_KEYS: Tuple[str, ...] = ("dwd_pixels", "audio", "sampling_rate")

class PiH3TextToVideoTaskAction(TextToVideoTaskAction):
    config: PiH3TextToVideoModelActionConfig

    def __init__(
        self,
        config: PiH3TextToVideoModelActionConfig,
        pipeline: Any,
        dwd: bool,
        step_count: int,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.dwd: bool = dwd
        self.step_count: int = step_count

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        num_frames  = await context.render_scalar(self.config.params.num_frames, int)
        video_shift = await context.render_scalar(self.config.params.video_shift, float) if self.config.params.video_shift is not None else None
        audio_shift = await context.render_scalar(self.config.params.audio_shift, float) if self.config.params.audio_shift is not None else None

        num_frames = self._snap_num_frames(num_frames)

        params.update({
            "num_frames":  num_frames,
            "video_shift": video_shift,
            "audio_shift": audio_shift,
        })

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        (prompts,) = inputs

        def _generate() -> List[VideoStreamResource]:
            import torch

            results: List[VideoStreamResource] = []

            # `set_shift` on an H3 scheduler mutates in-place and only takes
            # effect on the next `set_timesteps` call. Snapshot the previous
            # value if we're about to override it so one request's shift
            # doesn't leak into the next.
            if params["video_shift"] is not None:
                saved_video_shift = self._apply_scheduler_shift("scheduler", params["video_shift"])
            else:
                saved_video_shift = None

            if params["audio_shift"] is not None:
                saved_audio_shift = self._apply_scheduler_shift("audio_scheduler", params["audio_shift"])
            else:
                saved_audio_shift = None

            try:
                for prompt in prompts:
                    if params["seed"] is not None:
                        generator = torch.Generator(device=self.pipeline.device).manual_seed(params["seed"])
                    else:
                        generator = None

                    pipeline_params: Dict[str, Any] = {
                        "prompt": prompt,
                        "height": params["height"],
                        "width": params["width"],
                        "num_frames": params["num_frames"],
                        "num_inference_steps": self.step_count,
                        "generator": generator,
                    }

                    if self.dwd:
                        pipeline_params["output"] = list(_PI_H3_DWD_OUTPUT_KEYS)

                    output = self.pipeline(**pipeline_params)

                    results.append(self._encode_video_audio_to_mp4(output, params["frame_rate"]))
            finally:
                if saved_audio_shift is not None:
                    self.pipeline.audio_scheduler.set_shift(saved_audio_shift)

                if saved_video_shift is not None:
                    self.pipeline.scheduler.set_shift(saved_video_shift)

            return results

        return await self._run_in_executor(_generate)

    @staticmethod
    def _snap_num_frames(num_frames: int) -> int:
        if num_frames < _PI_H3_MIN_FRAMES:
            num_frames = _PI_H3_MIN_FRAMES

        if num_frames > _PI_H3_MAX_FRAMES:
            raise ValueError(
                f"pi-H3 supports at most {_PI_H3_MAX_FRAMES} frames (got {num_frames})."
            )

        remainder = (num_frames - _PI_H3_FRAME_OFFSET) % _PI_H3_FRAME_STEP

        if remainder != 0:
            num_frames += _PI_H3_FRAME_STEP - remainder

        if num_frames > _PI_H3_MAX_FRAMES:
            raise ValueError(
                f"pi-H3: snapped num_frames {num_frames} exceeds the "
                f"{_PI_H3_MAX_FRAMES}-frame cap."
            )

        return num_frames

    def _apply_scheduler_shift(self, scheduler_attr: str, shift: float) -> Optional[float]:
        scheduler = getattr(self.pipeline, scheduler_attr, None)

        if scheduler is not None and hasattr(scheduler, "set_shift"):
            previous = getattr(scheduler.config, "shift", None) if hasattr(scheduler, "config") else None
            scheduler.set_shift(shift)

            return previous

        return None

    def _encode_video_audio_to_mp4(self, output: Any, fps: int) -> VideoStreamResource:
        """Mux pi-H3's joint video+audio output into an in-memory mp4.

        DWD adapters return a dict with ``dwd_pixels`` (float RGB in [-1, 1]),
        ``audio`` and ``sampling_rate``; non-DWD adapters return the standard
        MiniMax-H3 pipeline output (uint8-compatible frames via `frames`/`videos`).
        Both paths land in the same mp4 writer the rest of the stack already
        understands.
        """
        import av

        if self.dwd:
            video = self._extract_tensor(output, ("dwd_pixels",))
        else:
            video = self._extract_tensor(output, ("frames", "videos", "video", "images"))

        audio = self._extract_tensor(output, ("audios", "audio"))

        frames_np = self._video_tensor_to_uint8(video)
        audio_np, audio_rate = self._audio_tensor_to_numpy(output, audio)

        buffer = io.BytesIO()
        container = av.open(buffer, mode="w", format="mp4")

        try:
            height, width = int(frames_np.shape[1]), int(frames_np.shape[2])
            video_stream = container.add_stream("libx264", rate=int(fps))
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
                # Planar `fltp` matches a (channels, samples) ndarray directly;
                # the packed `flt` variant demands a (1, channels * samples)
                # interleaved buffer and raises on stereo input otherwise.
                af = av.AudioFrame.from_ndarray(audio_np, format="fltp", layout=audio_stream.layout)
                af.sample_rate = audio_rate

                for packet in audio_stream.encode(af):
                    container.mux(packet)

                for packet in audio_stream.encode(None):
                    container.mux(packet)
        finally:
            container.close()

        attrs = { "frame_rate": str(fps) }

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

            array = tensor.to(torch.float32).numpy()
        else:
            array = np.asarray(tensor)

        if array.dtype != np.uint8:
            if array.min() < 0:
                array = (array + 1.0) / 2.0

            array = np.clip(array, 0.0, 1.0)
            array = (array * 255.0).round().astype(np.uint8)

        return array

    @staticmethod
    def _audio_tensor_to_numpy(output: Any, audio: Any):
        import numpy as np
        import torch

        if audio is None:
            return None, 32000

        sample_rate = 32000

        # DWD adapters expose `sampling_rate` as a sibling key; prefer that
        # over the inherited H3 default when the pipeline reports one.
        rate_from_output = None

        if isinstance(output, dict):
            rate_from_output = output.get("sampling_rate")
        else:
            rate_from_output = getattr(output, "sampling_rate", None)

        if rate_from_output is not None:
            sample_rate = int(rate_from_output)

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

class PiH3TextToVideoTaskDriver(ModelTaskDriver):
    """Driver for pi-H3 text-to-video: distilled MiniMax-H3 at 2 or 4 steps.

    pi-H3 ships as LakonLab adapters on top of `multimodalart/MiniMax-H3-Pruned`.
    Load the pruned base through diffusers' ModularPipeline, then call the
    LakonLab adapter loader to splice in the DWD head and distilled weights;
    inference uses the standard pipeline call with `num_inference_steps`
    pinned to the adapter's trained step count.
    """

    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch", "torchvision"),
            "diffusers==0.40.0",
            "peft==0.20.0",
            "transformers>=4.45",
            "accelerate>=0.34",
            "safetensors>=0.4",
            "sentencepiece",
            "soundfile>=0.12",
            "imageio>=2.34",
            "imageio-ffmpeg>=0.5",
            "av>=11",
            "Pillow>=10",
            "numpy>=1.24",
            "huggingface_hub>=0.25",
        ]

    async def _setup(self) -> None:
        # mmcv 1.x's setup.py imports torch at build time, which PEP 517's
        # isolated env hides. `--no-build-isolation` reuses the venv's torch.
        if not is_package_installed("mmcv"):
            await install_package("mmcv==1.6.1", pip_options=[ "--no-build-isolation" ])

        # LakonLab has no PyPI release and its requirements.txt pins the whole
        # training stack; `--no-deps` keeps those pins from stomping ours.
        if not is_package_installed("lakonlab", revision="v0.3.0"):
            await install_package_from_github(
                "lakonlab",
                "https://github.com/Lakonik/LakonLab.git",
                revision="v0.3.0",
                source_path=".",
                pip_options=[ "--no-deps" ],
            )

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.pipeline = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None

    async def _load_pipeline(self) -> Any:
        model_path = await self._provision_model(self.config.model, prefetch=True)

        text_encoder_config = self.config.text_encoder

        if text_encoder_config is not None:
            text_encoder = await self._load_pretrained_text_encoder(text_encoder_config, model_path)
        else:
            text_encoder = None

        distillation_path = await self._provision_model(self.config.distillation.model)
        adapter_subfolder = self._adapter_subfolder()

        def _load() -> Any:
            from diffusers import ComponentsManager, ModularPipeline
            from lakonlab.pipelines.utils import load_lakonlab_adapter
            import torch

            # Pin the text-only workflow (`t2va`) so only the text transformer
            # partition is fetched and the pipeline's declared signature is
            # text-to-video. ComponentsManager drives placement when cpu_offload
            # is on; it must exist before `from_pretrained` so loaded components
            # auto-register under its control.
            manager = ComponentsManager() if self.config.cpu_offload else None
            pipeline = ModularPipeline.from_pretrained(
                model_path,
                workflow="t2va",
                components_manager=manager,
            )

            components: Dict[str, Any] = {}

            if text_encoder is not None:
                components["text_encoder"] = text_encoder

            if components:
                pipeline.update_components(**components)

            pipeline.load_components(dtype=torch.bfloat16)

            logging.info(
                f"Component '{self.id}': loading pi-H3 distillation adapter '{adapter_subfolder}' from {distillation_path}"
            )
            load_lakonlab_adapter(pipeline, distillation_path, subfolder=adapter_subfolder)

            if self.config.quantization is not None:
                self._apply_fp8_quantization(pipeline)

            if manager is not None:
                # 12 GB mirrors the upstream MiniMax-H3 pipeline docs; the
                # default 3 GB margin is too tight for the Omni-Transformer and
                # trips OOM on the first forward.
                manager.enable_auto_cpu_offload(
                    device=self.device,
                    memory_reserve_margin="12GB",
                )
            else:
                pipeline = pipeline.to(self.device)

            return pipeline

        return await self._run_in_executor(_load)

    async def _load_pretrained_text_encoder(
        self,
        text_encoder_config: ModelSubmoduleConfig,
        model_path: str,
    ) -> PreTrainedModel:
        model_path = await self._provision_model(text_encoder_config.model)

        def _load() -> PreTrainedModel:
            from transformers import Qwen3VLForConditionalGeneration
            import torch

            logging.info(f"Component '{self.id}': loading {Qwen3VLForConditionalGeneration.__name__} from {model_path}")

            params: Dict[str, Any] = {
                "torch_dtype": self._resolve_torch_dtype(text_encoder_config.precision) if text_encoder_config.precision is not None else torch.bfloat16,
            }

            if text_encoder_config.low_cpu_mem_usage:
                params["low_cpu_mem_usage"] = True

            return Qwen3VLForConditionalGeneration.from_pretrained(model_path, **params)

        return await self._run_in_executor(_load)

    def _adapter_subfolder(self) -> str:
        suffix = "_dwd_adapter" if self.config.dwd else "_adapter"

        return f"pi_h3_{self.config.step_count}step{suffix}"

    def _apply_fp8_quantization(self, pipeline: Any) -> None:
        from lakonlab.ops import quantize_frozen_linears

        logging.info(f"Component '{self.id}': applying LakonLab FP8 quantization to frozen linears")

        quantize_frozen_linears(pipeline.transformer, exclude_keys=list(_PI_H3_TRANSFORMER_FP8_EXCLUDE))

        text_encoder = getattr(pipeline, "text_encoder", None)

        if text_encoder is not None:
            quantize_frozen_linears(text_encoder, exclude_keys=list(_PI_H3_TEXT_ENCODER_FP8_EXCLUDE))

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await PiH3TextToVideoTaskAction(
            action,
            self.pipeline,
            self.config.dwd,
            self.config.step_count,
        ).run(context)
