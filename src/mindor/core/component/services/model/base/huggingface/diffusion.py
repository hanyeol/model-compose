from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Generic, TypeVar, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import (
    ModelComponentConfig,
    ModelPrecision,
    ModelQuantizationConfig,
    ModelQuantizationType,
    DiffusionCpuOffload,
    DiffusionSubmodule,
)
from mindor.core.logger import logging
from .base import HuggingfaceModelTaskDriver

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

TMethod = TypeVar("TMethod")

class HuggingfaceDiffusionPipelineTaskDriver(HuggingfaceModelTaskDriver, Generic[TMethod]):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipelines: Optional[Dict[Optional[TMethod], DiffusionPipeline]] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> List[str]:
        return [
            *super()._get_setup_requirements(),
            *self._get_diffusers_requirements(),
        ]

    def _get_diffusers_requirements(self) -> List[str]:
        return [ "diffusers" ]

    async def _load_model(self) -> None:
        methods = list({ getattr(action, "method", None) for action in self.config.actions })
        self.pipelines, self.device = await self._load_pretrained_pipelines(methods)

    async def _unload_model(self) -> None:
        self.pipelines = None
        self.device = None

    async def _load_pretrained_pipelines(self, methods: List[Optional[TMethod]]) -> Tuple[Dict[Optional[TMethod], DiffusionPipeline], torch.device]:
        model_path = await self._provision_model(self.config.model)
        device = self._resolve_device(self.config.device)
        dtype = self._get_pipeline_dtype(device)

        base_pipeline_class = self._get_pipeline_class(None)
        method_pipeline_classes: Dict[Optional[TMethod], Type[DiffusionPipeline]] = { method: self._get_pipeline_class(method) for method in methods }
        quantization_config = self._resolve_pipeline_quantization_config(device, dtype)

        submodules = await self._load_pipeline_submodules(device, dtype)
        cpu_offload = self._get_cpu_offload()

        def _load() -> Dict[Optional[TMethod], DiffusionPipeline]:
            params: Dict[str, Any] = {
                **self._get_model_params(self.config.model),
                **submodules,
                "torch_dtype": dtype,
            }

            if quantization_config is not None:
                params["quantization_config"] = quantization_config

            logging.info(f"Component '{self.id}': loading {base_pipeline_class.__name__} from {model_path}")

            # Pipeline-level `.to(device)` is safe even for quantized pipelines
            # (diffusers docs), unlike transformers' Linear4bit which rejects it.
            base_pipeline = base_pipeline_class.from_pretrained(model_path, **params)

            if cpu_offload not in ("model", "sequential") or device.type != "cuda":
                base_pipeline = base_pipeline.to(device)

            self._configure_memory(base_pipeline, device, cpu_offload)

            pipelines: Dict[Optional[TMethod], DiffusionPipeline] = {}

            for method, pipeline_class in method_pipeline_classes.items():
                if pipeline_class is base_pipeline_class:
                    pipelines[method] = base_pipeline
                else:
                    logging.info(f"Component '{self.id}': deriving {pipeline_class.__name__} from {base_pipeline_class.__name__}")
                    derived_pipeline = pipeline_class.from_pipe(base_pipeline)
                    self._configure_memory(derived_pipeline, device, cpu_offload)
                    pipelines[method] = derived_pipeline

            return pipelines

        pipelines = await self._run_in_executor(_load)

        return pipelines, device

    async def _load_pipeline_submodules(self, device: torch.device, dtype: torch.dtype) -> Dict[str, Any]:
        return {}

    def _configure_memory(
        self,
        pipeline: DiffusionPipeline,
        device: torch.device,
        cpu_offload: Optional[DiffusionCpuOffload],
    ) -> None:
        if device.type == "cuda":
            if isinstance(cpu_offload, list):
                self._offload_modules_to_cpu(pipeline, device, cpu_offload)
            elif cpu_offload == "model":
                pipeline.enable_model_cpu_offload(device=device)
            elif cpu_offload == "sequential":
                pipeline.enable_sequential_cpu_offload(device=device)
        else:
            if cpu_offload is not None:
                logging.warning(f"Component '{self.id}': cpu_offload requires CUDA (device={device}); ignoring.")

        # Auto: VAE tiling/slicing — cheap wins with essentially no downside.
        vae = getattr(pipeline, "vae", None)

        if vae is not None:
            if hasattr(vae, "enable_tiling"):
                vae.enable_tiling()

            if hasattr(vae, "enable_slicing"):
                vae.enable_slicing()

    def _offload_modules_to_cpu(
        self,
        pipeline: DiffusionPipeline,
        device: torch.device,
        submodules: List[DiffusionSubmodule],
    ) -> None:
        from accelerate import cpu_offload as offload_to_cpu

        for submodule in submodules:
            name = submodule.value if hasattr(submodule, "value") else submodule
            module = getattr(pipeline, name, None)

            if module is None:
                raise ValueError(f"cpu_offload: submodule '{name}' not present in pipeline.")

            offload_to_cpu(module, execution_device=device)

    def _resolve_pipeline_quantization_config(self, device: torch.device, default_dtype: torch.dtype) -> Optional[Any]:
        import torch

        quantization: Optional[ModelQuantizationConfig] = self.config.quantization

        if quantization is None:
            return None

        # bitsandbytes only ships CUDA and MPS kernels (MPS since 0.50.0, torch >= 2.9).
        # VAE/CLIP text encoders aren't quantized per diffusers docs, so components excludes them.
        if device.type not in ("cuda", "mps"):
            raise ValueError(
                f"quantization requires a CUDA or MPS device; got device={device}. "
                "Set device to 'cuda' / 'mps' or remove the `quantization` field."
            )

        components = self._get_quantizable_components()

        if not components:
            raise ValueError(
                f"quantization is set but this pipeline reports no quantizable components. "
                "Either implement `_get_quantizable_components` in the subclass or remove `quantization`."
            )

        from diffusers.quantizers import PipelineQuantizationConfig

        if quantization.type == ModelQuantizationType.INT8:
            return PipelineQuantizationConfig(
                quant_backend="bitsandbytes_8bit",
                quant_kwargs={ "load_in_8bit": True },
                components_to_quantize=components,
            )

        # int4/fp4/nf4 all take the 4-bit path; `quant_type` selects the block format.
        if quantization.type in (ModelQuantizationType.INT4, ModelQuantizationType.NF4):
            quant_type = "nf4"
        else:
            quant_type = "fp4"

        if quantization.compute_dtype is not None:
            compute_dtype = getattr(torch, quantization.compute_dtype)
        else:
            compute_dtype = default_dtype

        return PipelineQuantizationConfig(
            quant_backend="bitsandbytes_4bit",
            quant_kwargs={
                "load_in_4bit": True,
                "bnb_4bit_quant_type": quant_type,
                "bnb_4bit_compute_dtype": compute_dtype,
                "bnb_4bit_use_double_quant": quantization.double_quant,
            },
            components_to_quantize=components,
        )

    def _get_quantizable_components(self) -> List[str]:
        return []

    def _get_pipeline_class(self, method: Optional[TMethod]) -> Type[DiffusionPipeline]:
        raise NotImplementedError("Pipeline class loader not implemented.")

    def _get_pipeline_dtype(self, device: torch.device) -> torch.dtype:
        import torch

        if device.type in ("cuda", "mps"):
            return self._get_accelerated_dtype()

        return torch.float32

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch

        return torch.bfloat16

    def _get_cpu_offload(self) -> Optional[DiffusionCpuOffload]:
        return None
