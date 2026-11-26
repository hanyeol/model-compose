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

# FP8 exclude keys documented in LakonLab's piH3 demos. DWD and non-DWD land
# on different projection names because the non-DWD path keeps the VAE head.
_PI_H3_DWD_TRANSFORMER_FP8_EXCLUDE_KEYS: Tuple[str, ...] = (
    "lora", "norm_out", "proj_out", "dwd_linear_head",
)

_PI_H3_VAE_TRANSFORMER_FP8_EXCLUDE_KEYS: Tuple[str, ...] = (
    "lora", "self.norm_out", "self.proj_out", "self.audio_proj_out",
)

_PI_H3_TEXT_ENCODER_FP8_EXCLUDE_KEYS: Tuple[str, ...] = (
    "lm_head",
)

# Shared with the base MiniMax-H3 pipeline: the video VAE decodes frame counts
# of the form 17*n + 5, clamped to 5..15 seconds at the fixed 24 fps.
_PI_H3_FRAME_STEP = 17
_PI_H3_FRAME_OFFSET = 5
_PI_H3_MIN_FRAMES = 124
_PI_H3_MAX_FRAMES = 345

# LakonLab's piH3 reference schedule: the video scheduler runs at shift=12 and
# the audio scheduler at shift=3; `max_raw_t` depends on step count.
_PI_H3_VIDEO_SHIFT = 12.0
_PI_H3_AUDIO_SHIFT = 3.0
_PI_H3_MAX_RAW_T: Dict[int, float] = { 2: 0.93, 4: 0.96 }

# RGBColorEncoder constants that the piH3 reference pipeline uses to decode
# `dwd_pixels` back into RGB; non-DWD paths skip this and read `videos` directly.
_PI_H3_RGB_DECODE_MEAN: Tuple[float, float, float] = (-0.03, -0.088, -0.188)
_PI_H3_RGB_DECODE_STD: Tuple[float, float, float] = (0.458, 0.448, 0.45)

# Non-DWD VAE decode tile size pinned in LakonLab's `example_pih3_vae_pipeline.py`.
_PI_H3_VAE_DECODE_TILE_BATCH_SIZE = 28

_PI_H3_DWD_OUTPUT_KEYS: Tuple[str, ...] = ("dwd_pixels", "audio", "sampling_rate")
_PI_H3_VAE_OUTPUT_KEYS: Tuple[str, ...] = ("videos", "audio", "sampling_rate")

# Submodules to materialize via `load_components(names=[...])`. The non-DWD
# path pre-swaps the VAE and the transformer is pre-loaded explicitly to carry
# `trust_remote_code=True` (diffusers refuses to forward it to components from
# a different repo than the pipeline), so neither appears here.
_PI_H3_DWD_COMPONENT_NAMES: Tuple[str, ...] = (
    "text_encoder", "tokenizer", "processor", "vae", "audio_vae",
)
_PI_H3_VAE_COMPONENT_NAMES: Tuple[str, ...] = (
    "text_encoder", "tokenizer", "processor", "audio_vae",
)

class PiH3TextToVideoTaskAction(TextToVideoTaskAction):
    config: PiH3TextToVideoModelActionConfig

    def __init__(
        self,
        config: PiH3TextToVideoModelActionConfig,
        pipeline: Any,
        dwd: bool,
        step_count: int,
        color_encoder: Optional[Any],
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline
        self.dwd: bool = dwd
        self.step_count: int = step_count
        self.color_encoder: Optional[Any] = color_encoder

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        num_frames = await context.render_scalar(self.config.params.num_frames, int)
        num_frames = self._snap_num_frames(num_frames)

        params.update({ "num_frames": num_frames })

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
            output_keys = _PI_H3_DWD_OUTPUT_KEYS if self.dwd else _PI_H3_VAE_OUTPUT_KEYS

            for prompt in prompts:
                if params["seed"] is not None:
                    generator = torch.Generator(device=self.pipeline.device).manual_seed(params["seed"])
                else:
                    generator = None

                output = self.pipeline(
                    prompt=prompt,
                    height=params["height"],
                    width=params["width"],
                    num_frames=params["num_frames"],
                    num_inference_steps=self.step_count,
                    generator=generator,
                    output=list(output_keys),
                )

                results.append(self._encode_video_audio_to_mp4(output, params["frame_rate"]))

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

    def _encode_video_audio_to_mp4(self, output: Any, fps: int) -> VideoStreamResource:
        """Mux pi-H3's joint video+audio output into an in-memory mp4.

        DWD adapters return `dwd_pixels` in the color-encoder's latent space —
        decode through `RGBColorEncoder` and remap `[-1, 1] -> [0, 1]` before
        passing on. Non-DWD adapters return `videos` already in `[0, 1]`.
        Both paths land in the same mp4 writer the rest of the stack uses.
        """
        import av

        audio = self._extract_tensor(output, ("audios", "audio"))

        if self.dwd:
            dwd_pixels = self._extract_tensor(output, ("dwd_pixels",))
            video = self.color_encoder.decode(dwd_pixels).add_(1).mul_(0.5)
        else:
            video = self._extract_tensor(output, ("videos", "frames", "video", "images"))

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

        # DWD adapters expose `sampling_rate` as a sibling key; prefer that over
        # the inherited H3 default when the pipeline reports one.
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

    Follows LakonLab's piH3 reference pipeline — a `MiniMaxH3DWDBlocks` (or
    `MiniMaxH3BlocksMod` for non-DWD) built on `multimodalart/MiniMax-H3-Pruned`,
    with `FlowEulerODEScheduler` instances wired in for video/audio. The LakonLab
    adapter is attached on top of the transformer and, for DWD, an `RGBColorEncoder`
    turns the pipeline's `dwd_pixels` back into RGB.
    """

    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.color_encoder: Optional[Any] = None
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
            "boto3",
            "lpips",
            "bitsandbytes",
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
        self.pipeline, self.color_encoder = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.color_encoder = None

    async def _load_pipeline(self) -> Tuple[Any, Optional[Any]]:
        model_path = await self._provision_model(self.config.model, prefetch=True)

        text_encoder_config = self.config.text_encoder

        if text_encoder_config is not None:
            text_encoder = await self._load_pretrained_text_encoder(text_encoder_config, model_path)
        else:
            text_encoder = None

        transformer = await self._load_pretrained_transformer(model_path)

        distillation_path = await self._provision_model(self.config.distillation.model)
        adapter_subfolder = f"pi_h3_{self.config.step_count}step{'_dwd_adapter' if self.config.dwd else '_adapter'}"

        def _load() -> Tuple[Any, Optional[Any]]:
            from diffusers import ComponentsManager
            from lakonlab.models.architectures import RGBColorEncoder
            from lakonlab.models.diffusions.schedulers import FlowEulerODEScheduler
            from lakonlab.pipelines.utils import load_lakonlab_adapter
            import torch

            # LakonLab routes t2v / i2v / fl2v inside the same Blocks pipeline;
            # the ctor picks DWD vs stock VAE decode, routing is by call-time
            # kwargs (`image=` / `last_image=`), and ComponentsManager drives
            # placement when cpu_offload is on.
            manager = ComponentsManager() if self.config.cpu_offload else None

            if self.config.dwd:
                from lakonlab.pipelines.pipeline_minimax_h3 import MiniMaxH3DWDBlocks

                pipeline = MiniMaxH3DWDBlocks().init_pipeline(model_path, components_manager=manager)
            else:
                from lakonlab.pipelines.pipeline_minimax_h3 import MiniMaxH3BlocksMod

                pipeline = MiniMaxH3BlocksMod().init_pipeline(model_path, components_manager=manager)

            if text_encoder is not None:
                pipeline.update_components(text_encoder=text_encoder)

            # The transformer is injected explicitly because MiniMax-H3 ships
            # it as custom code on the Hub, and diffusers refuses to forward
            # `trust_remote_code` to components whose spec points at a
            # different repo than the pipeline (the local snapshot path we
            # build the pipeline from here) — it would silently land as None
            # and break the adapter attach downstream.
            pipeline.update_components(transformer=transformer)

            if self.config.dwd:
                pipeline.load_components(names=list(_PI_H3_DWD_COMPONENT_NAMES), dtype=torch.bfloat16)
            else:
                # The spec swap must run before `load_components` so the
                # swapped VAE class is what gets instantiated.
                from lakonlab.models.architectures.diffusers.pretrained import AutoencoderKLMiniMaxH3

                vae_spec = pipeline.get_component_spec("vae")
                vae_spec.type_hint = AutoencoderKLMiniMaxH3
                pipeline.update_components(vae=vae_spec.load(dtype=torch.float16))

                pipeline.load_components(names=list(_PI_H3_VAE_COMPONENT_NAMES), dtype=torch.bfloat16)
                pipeline.vae.decode_tile_batch_size = _PI_H3_VAE_DECODE_TILE_BATCH_SIZE

            logging.info(
                f"Component '{self.id}': loading pi-H3 distillation adapter '{adapter_subfolder}' from {distillation_path}"
            )

            load_lakonlab_adapter(pipeline, distillation_path, subfolder=adapter_subfolder)

            # The piH3 reference pins both schedulers to num_train_timesteps=1
            # with step-count-dependent max_raw_t; the trained adapters assume
            # this schedule and ignore the diffusers default.
            max_raw_t = _PI_H3_MAX_RAW_T[self.config.step_count]
            pipeline.update_components(
                scheduler=FlowEulerODEScheduler(
                    num_train_timesteps=1,
                    shift=_PI_H3_VIDEO_SHIFT,
                    max_raw_t=max_raw_t,
                    final_step_size_scale=0.6,
                ),
                audio_scheduler=FlowEulerODEScheduler(
                    num_train_timesteps=1,
                    shift=_PI_H3_AUDIO_SHIFT,
                    max_raw_t=max_raw_t,
                    final_step_size_scale=0.6,
                ),
            )

            if self.config.quantization is not None:
                from lakonlab.ops import quantize_frozen_linears

                logging.info(f"Component '{self.id}': applying LakonLab FP8 quantization to frozen linears")

                if self.config.dwd:
                    pipeline.transformer.requires_grad_(False)
                    quantize_frozen_linears(pipeline.transformer, exclude_keys=list(_PI_H3_DWD_TRANSFORMER_FP8_EXCLUDE_KEYS))
                else:
                    pipeline.transformer.requires_grad_(False)
                    quantize_frozen_linears(pipeline.transformer, exclude_keys=list(_PI_H3_VAE_TRANSFORMER_FP8_EXCLUDE_KEYS))

                if getattr(pipeline, "text_encoder", None) is not None:
                    pipeline.text_encoder.requires_grad_(False)
                    quantize_frozen_linears(pipeline.text_encoder, exclude_keys=list(_PI_H3_TEXT_ENCODER_FP8_EXCLUDE_KEYS))

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

            color_encoder: Optional[Any] = None

            if self.config.dwd:
                color_encoder = RGBColorEncoder(
                    use_affine_norm=True,
                    mean=_PI_H3_RGB_DECODE_MEAN,
                    std=_PI_H3_RGB_DECODE_STD,
                ).to(self.device)

            return pipeline, color_encoder

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

            params: Dict[str, Any] = {}

            if text_encoder_config.precision is not None:
                params["torch_dtype"] = self._resolve_torch_dtype(text_encoder_config.precision)
            else:
                params["torch_dtype"] = torch.bfloat16

            if text_encoder_config.low_cpu_mem_usage:
                params["low_cpu_mem_usage"] = True

            return Qwen3VLForConditionalGeneration.from_pretrained(model_path, **params)

        return await self._run_in_executor(_load)

    async def _load_pretrained_transformer(self, model_path: str) -> Any:
        def _load() -> Any:
            from diffusers import AutoModel
            import torch

            logging.info(f"Component '{self.id}': loading transformer from {model_path}")

            params: Dict[str, Any] = {
                "subfolder": "transformer",
                "trust_remote_code": True,
            }

            if self.config.precision is not None:
                params["torch_dtype"] = self._resolve_torch_dtype(self.config.precision)
            else:
                params["torch_dtype"] = torch.bfloat16

            return AutoModel.from_pretrained(model_path, **params)

        return await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await PiH3TextToVideoTaskAction(
            action,
            self.pipeline,
            self.config.dwd,
            self.config.step_count,
            self.color_encoder,
        ).run(context)
