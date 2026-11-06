from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Tuple, Any
from mindor.dsl.schema.component import (
    ModelComponentConfig,
    ModelSubmoduleConfig,
    ModelQuantizationConfig,
    ModelQuantizationType,
    PeftAdapterConfig,
    HuggingfaceModelConfig,
)
from mindor.dsl.schema.action import ModelActionConfig, MinimaxH3ImageToVideoModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.logger import logging
from .....base import ComponentActionContext, ModelTaskDriver
from ...common import ImageToVideoTaskAction
import io

if TYPE_CHECKING:
    from transformers import PreTrainedModel
    import torch

# Checkpoint-specific modules that must stay in bfloat16 to preserve output quality.
# Mirrors the lists in the diffusers MiniMax-H3 docs; update when the upstream recipe changes.
_MINIMAX_H3_TRANSFORMER_SKIP_MODULES: Tuple[str, ...] = (
    "proj_in", "audio_proj_in", "context_embedder", "time_embedder", "time_proj",
    "token_refiner", "norm_out", "proj_out", "audio_proj_out",
)

_MINIMAX_H3_TEXT_ENCODER_SKIP_MODULES: Tuple[str, ...] = (
    "model.visual", "model.language_model.embed_tokens", "model.language_model.norm", "lm_head",
)

class MinimaxH3ImageToVideoTaskAction(ImageToVideoTaskAction):
    config: MinimaxH3ImageToVideoModelActionConfig

    def __init__(
        self,
        config: MinimaxH3ImageToVideoModelActionConfig,
        pipeline: Any,
    ):
        super().__init__(config)

        self.pipeline: Any = pipeline

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        (image, last_image, prompt), primary_input, is_single_input, is_streaming_input = await super()._prepare_input(context)

        negative_prompt = await context.render_text(self.config.negative_prompt) if self.config.negative_prompt is not None else None

        return (image, last_image, prompt, negative_prompt), primary_input, is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        inference_steps = await context.render_scalar(self.config.params.inference_steps, int)
        guidance_scale  = await context.render_scalar(self.config.params.guidance_scale, float)
        video_shift     = await context.render_scalar(self.config.params.video_shift, float) if self.config.params.video_shift is not None else None
        audio_shift     = await context.render_scalar(self.config.params.audio_shift, float) if self.config.params.audio_shift is not None else None

        params.update({
            "inference_steps": inference_steps,
            "guidance_scale":  guidance_scale,
            "video_shift":     video_shift,
            "audio_shift":     audio_shift,
        })

        return params

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        images, last_images, prompts, negative_prompts = inputs
        negatives = negative_prompts if negative_prompts is not None else [ None ] * len(prompts)

        def _generate() -> List[VideoStreamResource]:
            import torch

            results: List[VideoStreamResource] = []

            # `set_shift` on a MiniMax-H3 scheduler mutates in-place and only
            # takes effect on the next `set_timesteps` call (which runs inside
            # every pipeline call). Snapshot the previous shift (if we're about
            # to override it) so one request's shift doesn't leak into the next.
            if params["video_shift"] is not None:
                saved_video_shift = self._apply_scheduler_shift("scheduler", params["video_shift"])
            else:
                saved_video_shift = None

            if params["audio_shift"] is not None:
                saved_audio_shift = self._apply_scheduler_shift("audio_scheduler", params["audio_shift"])
            else:
                saved_audio_shift = None

            try:
                for image, last_image, prompt, negative in zip(images, last_images, prompts, negatives):
                    if params["seed"] is not None:
                        generator = torch.Generator(device=self.pipeline.device).manual_seed(params["seed"])
                    else:
                        generator = None

                    pipeline_params: Dict[str, Any] = {
                        "prompt": prompt or "",
                        "image": image,
                        "height": params["height"],
                        "width": params["width"],
                        "num_frames": params["num_frames"],
                        "num_inference_steps": params["inference_steps"],
                        "guidance_scale": params["guidance_scale"],
                        "generator": generator,
                    }

                    if last_image is not None:
                        pipeline_params["last_image"] = last_image

                    if negative is not None:
                        pipeline_params["negative_prompt"] = negative

                    output = self.pipeline(**pipeline_params)

                    results.append(self._encode_video_audio_to_mp4(output, params["frame_rate"]))
            finally:
                if saved_audio_shift is not None:
                    self.pipeline.audio_scheduler.set_shift(saved_audio_shift)

                if saved_video_shift is not None:
                    self.pipeline.scheduler.set_shift(saved_video_shift)

            return results

        return await self._run_in_executor(_generate)

    def _apply_scheduler_shift(self, scheduler_attr: str, shift: float) -> Optional[float]:
        scheduler = getattr(self.pipeline, scheduler_attr, None)

        if scheduler is not None and hasattr(scheduler, "set_shift"):
            previous = getattr(scheduler.config, "shift", None) if hasattr(scheduler, "config") else None
            scheduler.set_shift(shift)

            return previous

        return None

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

class MinimaxH3ImageToVideoBaseDriver(ModelTaskDriver):
    """Shared pipeline loader for the MiniMax-H3 image-to-video task.

    Subclasses are the per-backend drivers; the only backend-specific
    responsibility they add is (optionally) swapping the main transformer
    blocks' attention processor after the pipeline is loaded.
    """

    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        requirements: List[Union[str, Tuple[str, List[str]]]] = [
            *torch_requirements("torch", "torchvision"),
            "diffusers>=0.36",
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

        if self._has_quantization():
            requirements.append("torchao>=0.8")

        return requirements

    def _has_quantization(self) -> bool:
        if self.config.quantization is not None:
            return True

        for name in ("text_encoder", "transformer"):
            submodule = getattr(self.config, name, None)

            if submodule is not None and submodule.quantization is not None:
                return True

        return False

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.pipeline = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None

    async def _load_pipeline(self) -> Any:
        from diffusers import ComponentsManager, ModularPipeline

        model_path = await self._provision_model(self.config.model, prefetch=True)

        text_encoder_config = self.config.text_encoder
        text_encoder_quantization = self._resolve_submodule_quantization(text_encoder_config)

        if text_encoder_config is not None or text_encoder_quantization is not None:
            text_encoder = await self._load_pretrained_text_encoder(
                text_encoder_config,
                model_path,
                text_encoder_quantization,
            )
        else:
            text_encoder = None

        transformer_config = None
        transformer_quantization = self._resolve_submodule_quantization(transformer_config)

        if transformer_config is not None or transformer_quantization is not None:
            transformer = await self._load_pretrained_transformer(
                transformer_config,
                model_path,
                transformer_quantization,
            )
        else:
            transformer = None

        peft_adapters = self.config.peft_adapter or []
        peft_adapter_paths = [ await self._provision_model(adapter.model) for adapter in peft_adapters ]

        def _load() -> Any:
            import torch

            # MiniMax-H3 is distributed as Modular Diffusers blocks; pin the
            # first/last-frame workflow (`fl2va`) so only the keyframe transformer
            # partition is fetched and the pipeline's declared signature is
            # image-to-video (optionally with a last-frame keyframe).
            #
            # ComponentsManager drives placement when cpu_offload is on. It must
            # be created before `from_pretrained` and passed in so loaded
            # components auto-register under its control; after that the manager
            # (not `pipeline.to`) decides when each module is on GPU vs CPU.
            manager = ComponentsManager() if self.config.cpu_offload else None
            pipeline = ModularPipeline.from_pretrained(
                model_path,
                workflow="fl2va",
                components_manager=manager,
            )

            # Inject externally-loaded submodules BEFORE load_components;
            # load_components skips components that are already registered.
            components: Dict[str, Any] = {}

            if text_encoder is not None:
                components["text_encoder"] = text_encoder

            if transformer is not None:
                components["transformer"] = transformer

            if components:
                pipeline.update_components(**components)

            pipeline.load_components(dtype=torch.bfloat16)

            if peft_adapters:
                self._attach_peft_adapters(pipeline, peft_adapters, peft_adapter_paths)

            if manager is not None:
                # Default `memory_reserve_margin` is 3 GB, which is too tight for
                # the 33B Omni-Transformer and causes OOM on the first forward.
                # 12 GB matches the upstream MiniMax-H3 pipeline docs.
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
        text_encoder_config: Optional[ModelSubmoduleConfig],
        model_path: str,
        quantization: Optional[ModelQuantizationConfig],
    ) -> PreTrainedModel:
        from transformers import Qwen3VLForConditionalGeneration

        model_subfolder: Optional[str] = None

        if text_encoder_config is not None:
            model_path = await self._provision_model(text_encoder_config.model)
        else:
            model_subfolder = "text_encoder"

        def _load() -> PreTrainedModel:
            import torch

            logging.info(f"Component '{self.id}': loading {Qwen3VLForConditionalGeneration.__name__} from {model_path}")

            params: Dict[str, Any] = {}

            if text_encoder_config is not None and text_encoder_config.precision is not None:
                params["torch_dtype"] = getattr(torch, text_encoder_config.precision.value)
            else:
                params["torch_dtype"] = torch.bfloat16

            if text_encoder_config is not None and text_encoder_config.low_cpu_mem_usage:
                params["low_cpu_mem_usage"] = True

            if model_subfolder is not None:
                params["subfolder"] = model_subfolder

            if quantization is not None:
                params["quantization_config"] = self._build_transformers_quantization_config(
                    quantization,
                    skip_modules=_MINIMAX_H3_TEXT_ENCODER_SKIP_MODULES,
                )
                params["low_cpu_mem_usage"] = True

            return Qwen3VLForConditionalGeneration.from_pretrained(model_path, **params)

        return await self._run_in_executor(_load)

    async def _load_pretrained_transformer(
        self,
        transformer_config: Optional[ModelSubmoduleConfig],
        model_path: str,
        quantization: Optional[ModelQuantizationConfig],
    ) -> Any:
        from diffusers import MiniMaxH3Transformer3DModel

        model_subfolder: Optional[str] = None

        if transformer_config is not None:
            model_path = await self._provision_model(transformer_config.model)
        else:
            model_subfolder = "transformer"

        def _load() -> Any:
            import torch

            logging.info(f"Component '{self.id}': loading {MiniMaxH3Transformer3DModel.__name__} from {model_path}")

            params: Dict[str, Any] = {}

            if transformer_config is not None and transformer_config.precision is not None:
                params["torch_dtype"] = getattr(torch, transformer_config.precision.value)
            else:
                params["torch_dtype"] = torch.bfloat16

            if transformer_config is not None and transformer_config.low_cpu_mem_usage:
                params["low_cpu_mem_usage"] = True

            if model_subfolder is not None:
                params["subfolder"] = model_subfolder

            if quantization is not None:
                params["quantization_config"] = self._build_diffusers_quantization_config(
                    quantization,
                    skip_modules=_MINIMAX_H3_TRANSFORMER_SKIP_MODULES,
                )
                params["low_cpu_mem_usage"] = True

            return MiniMaxH3Transformer3DModel.from_pretrained(model_path, **params)

        return await self._run_in_executor(_load)

    def _resolve_submodule_quantization(
        self,
        submodule: Optional[ModelSubmoduleConfig],
    ) -> Optional[ModelQuantizationConfig]:
        if submodule is not None and submodule.quantization is not None:
            return submodule.quantization

        return self.config.quantization

    def _build_diffusers_quantization_config(
        self,
        quantization: ModelQuantizationConfig,
        skip_modules: Tuple[str, ...],
    ) -> Any:
        from diffusers import TorchAoConfig

        return TorchAoConfig(
            self._build_quant_type(quantization),
            modules_to_not_convert=list(skip_modules),
        )

    def _build_transformers_quantization_config(
        self,
        quantization: ModelQuantizationConfig,
        skip_modules: Tuple[str, ...],
    ) -> Any:
        from transformers import TorchAoConfig

        return TorchAoConfig(
            self._build_quant_type(quantization),
            modules_to_not_convert=list(skip_modules),
        )

    def _build_quant_type(self, quantization: ModelQuantizationConfig) -> Any:
        # `version=2` tensors are pinnable, which group-offload with streaming requires;
        # the upstream MiniMax-H3 recipe pins the same version for int8 weight-only.
        if quantization.type == ModelQuantizationType.INT8:
            from torchao.quantization import Int8WeightOnlyConfig
            return Int8WeightOnlyConfig(version=2)

        if quantization.type == ModelQuantizationType.INT4:
            from torchao.quantization import Int4WeightOnlyConfig
            return Int4WeightOnlyConfig()

        if quantization.type == ModelQuantizationType.FP8:
            from torchao.quantization import Float8WeightOnlyConfig
            return Float8WeightOnlyConfig()

        raise ValueError(f"Unsupported quantization type: {quantization.type.value!r}.")

    def _attach_peft_adapters(
        self,
        pipeline: Any,
        adapters: List[PeftAdapterConfig],
        adapter_paths: List[str],
    ) -> None:
        if not hasattr(pipeline, "load_lora_weights"):
            raise ValueError(
                f"{type(pipeline).__name__} does not support LoRA loading; remove `peft_adapter` from the component config."
            )

        names: List[str] = []
        weights: List[float] = []

        for index, (adapter, path) in enumerate(zip(adapters, adapter_paths)):
            name = adapter.name or f"peft_adapter_{index}"
            load_params: Dict[str, Any] = { "adapter_name": name }

            if isinstance(adapter.model, HuggingfaceModelConfig) and adapter.model.filename:
                load_params["weight_name"] = adapter.model.filename

            logging.info(f"Component '{self.id}': loading LoRA adapter '{name}' from {path}")
            pipeline.load_lora_weights(path, **load_params)

            names.append(name)
            weights.append(float(adapter.weight))

        if hasattr(pipeline, "set_adapters"):
            pipeline.set_adapters(names, adapter_weights=weights)
