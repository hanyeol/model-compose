from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import (
    ModelComponentConfig,
    ModelSubmoduleConfig,
    ModelQuantizationConfig,
    ModelQuantizationType,
    PeftAdapterConfig,
    HuggingfaceModelConfig,
)
from mindor.dsl.schema.action import (
    MinimaxH3ImageGenerationModelActionConfig,
    MinimaxH3ImageGenerationModelGenerateActionConfig,
    MinimaxH3ImageGenerationModelEditActionConfig,
    AppliedPeftAdapterConfig,
)
from mindor.core.foundation.package.torch import torch_requirements, torchao_int4_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.logger import logging
from .....base import ComponentActionContext, ModelTaskDriver
from ...common import ImageGenerationTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    from transformers import PreTrainedModel
    import torch

# Checkpoint-specific modules that must stay in bfloat16 to preserve output quality.
# Mirrors the lists in the diffusers MiniMax-H3-Image docs; entries not present on
# the 2D image transformer are harmless — `modules_to_not_convert` only applies
# to names that actually exist in the state dict.
_MINIMAX_H3_IMAGE_TRANSFORMER_SKIP_MODULES: Tuple[str, ...] = (
    "proj_in",
    "context_embedder",
    "time_embedder",
    "time_proj",
    "token_refiner",
    "norm_out",
    "proj_out",
)

_MINIMAX_H3_IMAGE_TEXT_ENCODER_SKIP_MODULES: Tuple[str, ...] = (
    "model.visual",
    "model.language_model.embed_tokens",
    "model.language_model.norm",
    "lm_head",
)

# H3-Image samples on a fixed 6-step sigma grid baked into the checkpoint;
# the transformer has one output head per step, so `num_inference_steps` is
# not a user-tunable knob — it's a constant exposed here for Sol-Attn's
# step-counter bookkeeping only.
_MINIMAX_H3_IMAGE_SAMPLE_STEPS = 6

class MinimaxH3ImageGenerationTaskAction(ImageGenerationTaskAction):
    config: MinimaxH3ImageGenerationModelActionConfig

    def __init__(
        self,
        config: MinimaxH3ImageGenerationModelActionConfig,
        pipeline: Any,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.pipeline: Any = pipeline

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        width               = await context.render_scalar(self.config.width, int)
        height              = await context.render_scalar(self.config.height, int)
        num_return_images   = await context.render_scalar(self.config.num_return_images, int)
        seed                = await context.render_scalar(self.config.seed, int) if self.config.seed is not None else None
        min_generation_area = await context.render_scalar(self.config.params.min_generation_area, int)

        params.update({
            "width":               width,
            "height":              height,
            "num_return_images":   num_return_images,
            "seed":                seed,
            "min_generation_area": min_generation_area,
        })

        return params

class MinimaxH3ImageGenerationGenerateAction(MinimaxH3ImageGenerationTaskAction):
    config: MinimaxH3ImageGenerationModelGenerateActionConfig

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        prompt = await context.render_text(self.config.prompt)

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt,), prompt, is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        (prompts,) = inputs

        def _generate() -> List[PILImage.Image]:
            import torch

            results: List[PILImage.Image] = []

            for prompt in prompts:
                if params["seed"] is not None:
                    generator = torch.Generator(device=self.pipeline.device).manual_seed(params["seed"])
                else:
                    generator = None

                # H3-Image is guidance-distilled: no `num_inference_steps`,
                # `guidance_scale` or `negative_prompt`. Omitting `image`
                # selects the `text2image` workflow.
                pipeline_params: Dict[str, Any] = {
                    "prompt":              prompt or "",
                    "height":              params["height"],
                    "width":               params["width"],
                    "min_generation_area": params["min_generation_area"],
                    "generator":           generator,
                    "output":              "images",
                }

                output = self.pipeline(**pipeline_params)
                results.extend(list(output))

            return results

        return await self._run_in_executor(_generate)

class MinimaxH3ImageGenerationEditAction(MinimaxH3ImageGenerationTaskAction):
    config: MinimaxH3ImageGenerationModelEditActionConfig

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        prompt = await context.render_text(self.config.prompt)
        images = await context.render_image_array(self.config.image, single_as_array=True)

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt, images), prompt, is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        prompts, images = inputs
        # `render_image_array(single_as_array=True)` returns an `ImageArrayValue`
        # unit per batch item (each a PIL list after `collect()`); materialize
        # them out of the async loop so the executor closure stays sync.
        images = [ await image.collect() for image in images ]

        def _generate() -> List[PILImage.Image]:
            import torch

            results: List[PILImage.Image] = []

            for prompt, images in zip(prompts, images):
                images = [ image.convert("RGB") for image in images ]

                if params["seed"] is not None:
                    generator = torch.Generator(device=self.pipeline.device).manual_seed(params["seed"])
                else:
                    generator = None

                # Passing `image` selects the `image_conditioned` workflow.
                pipeline_params: Dict[str, Any] = {
                    "prompt":              prompt or "",
                    "image":               images,
                    "height":              params["height"],
                    "width":               params["width"],
                    "min_generation_area": params["min_generation_area"],
                    "generator":           generator,
                    "output":              "images",
                }

                output = self.pipeline(**pipeline_params)
                results.extend(list(output))

            return results

        return await self._run_in_executor(_generate)

class MinimaxH3ImageGenerationBaseDriver(ModelTaskDriver):
    """Shared pipeline loader for the MiniMax-H3 image generation task.

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
            "Pillow>=10",
            "numpy>=1.24",
            "huggingface_hub>=0.25",
        ]

        if self._has_quantization():
            requirements.append("torchao>=0.8")

        if self._has_quantization(ModelQuantizationType.INT4):
            requirements.extend(torchao_int4_requirements())

        if self.config.peft_adapter:
            requirements.append("peft")

        return requirements

    def _has_quantization(self, type: Optional[ModelQuantizationType] = None) -> bool:
        if self.config.quantization is not None:
            if type is None or self.config.quantization.type == type:
                return True

        for name in ("text_encoder", "transformer"):
            submodule = getattr(self.config, name, None)

            if submodule is not None and submodule.quantization is not None:
                if type is None or submodule.quantization.type == type:
                    return True

        return False

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self.pipeline = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None

    async def _load_pipeline(self) -> Any:
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
            from diffusers import ComponentsManager, ModularPipeline
            import torch

            # H3-Image is distributed as Modular Diffusers blocks; the single
            # pipeline runs either the `text2image` or `image_conditioned`
            # workflow depending on whether `image` is passed at __call__ time,
            # so no workflow string is pinned here.
            #
            # ComponentsManager drives placement when cpu_offload is on. It must
            # be created before `from_pretrained` and passed in so loaded
            # components auto-register under its control; after that the manager
            # (not `pipeline.to`) decides when each module is on GPU vs CPU.
            manager = ComponentsManager() if self.config.cpu_offload else None
            pipeline = ModularPipeline.from_pretrained(
                model_path,
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
        config: Optional[ModelSubmoduleConfig],
        model_path: str,
        quantization: Optional[ModelQuantizationConfig],
    ) -> PreTrainedModel:
        model_subfolder: Optional[str] = None

        if config is not None:
            model_path = await self._provision_model(config.model)
        else:
            model_subfolder = "text_encoder"

        def _load() -> PreTrainedModel:
            from transformers import Qwen3VLForConditionalGeneration
            import torch

            logging.info(f"Component '{self.id}': loading {Qwen3VLForConditionalGeneration.__name__} from {model_path}")

            params: Dict[str, Any] = {}

            if config is not None and config.precision is not None:
                params["torch_dtype"] = self._resolve_torch_dtype(config.precision)
            else:
                params["torch_dtype"] = torch.bfloat16

            if config is not None and config.low_cpu_mem_usage:
                params["low_cpu_mem_usage"] = True

            if model_subfolder is not None:
                params["subfolder"] = model_subfolder

            if quantization is not None:
                params["quantization_config"] = self._build_transformers_quantization_config(
                    quantization,
                    skip_modules=_MINIMAX_H3_IMAGE_TEXT_ENCODER_SKIP_MODULES,
                )
                params["low_cpu_mem_usage"] = True

            return Qwen3VLForConditionalGeneration.from_pretrained(model_path, **params)

        return await self._run_in_executor(_load)

    async def _load_pretrained_transformer(
        self,
        config: Optional[ModelSubmoduleConfig],
        model_path: str,
        quantization: Optional[ModelQuantizationConfig],
    ) -> Any:
        model_subfolder: Optional[str] = None

        if config is not None:
            model_path = await self._provision_model(config.model)
        else:
            model_subfolder = "transformer_diffusers"

        def _load() -> Any:
            from diffusers import MiniMaxH3ImageTransformer2DModel
            import torch

            logging.info(f"Component '{self.id}': loading {MiniMaxH3ImageTransformer2DModel.__name__} from {model_path}")

            params: Dict[str, Any] = {}

            if config is not None and config.precision is not None:
                params["torch_dtype"] = self._resolve_torch_dtype(config.precision)
            else:
                params["torch_dtype"] = torch.bfloat16

            if config is not None and config.low_cpu_mem_usage:
                params["low_cpu_mem_usage"] = True

            if model_subfolder is not None:
                params["subfolder"] = model_subfolder

            if quantization is not None:
                params["quantization_config"] = self._build_diffusers_quantization_config(
                    quantization,
                    skip_modules=_MINIMAX_H3_IMAGE_TRANSFORMER_SKIP_MODULES,
                )
                params["low_cpu_mem_usage"] = True

            return MiniMaxH3ImageTransformer2DModel.from_pretrained(model_path, **params)

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

        for adapter, path in zip(adapters, adapter_paths):
            load_params: Dict[str, Any] = { "adapter_name": adapter.name }

            if isinstance(adapter.model, HuggingfaceModelConfig) and adapter.model.filename:
                load_params["weight_name"] = adapter.model.filename

            logging.info(f"Component '{self.id}': loading LoRA adapter '{adapter.name}' from {path}")

            pipeline.load_lora_weights(path, **load_params)

        # Leave the adapters disabled by default; actions turn them on per request.
        if hasattr(pipeline, "disable_lora"):
            pipeline.disable_lora()

    def _apply_peft_adapters(self, adapters: List[AppliedPeftAdapterConfig]) -> None:
        names = [ adapter.name for adapter in adapters ]
        weights = [ float(adapter.weight) for adapter in adapters ]

        if hasattr(self.pipeline, "enable_lora"):
            self.pipeline.enable_lora()

        if hasattr(self.pipeline, "set_adapters"):
            self.pipeline.set_adapters(names, adapter_weights=weights)

    def _disable_peft_adapters(self) -> None:
        if hasattr(self.pipeline, "disable_lora"):
            self.pipeline.disable_lora()

