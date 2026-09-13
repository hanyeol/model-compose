from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import (
    ModelComponentConfig,
    CommonModelComponentConfig,
    PeftAdapterConfig,
    VaeConfig,
    ModelConfig,
    HuggingfaceModelConfig,
    ModelPrecision,
    ModelQuantizationConfig,
    ModelQuantizationType,
    DeviceMode,
)
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.logger import logging
from ..common import ModelTaskService
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel
    import torch

class HuggingfaceModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> List[str]:
        requirements = [
            *torch_requirements("torch"),
            "transformers>=4.52.0",
            "accelerate",
        ]

        # 0.50.0 is the first release with official MPS kernels — pin it so
        # mac users don't silently pick up an older CUDA-only build. MPS also
        # needs torch >= 2.9 (not enforced here to avoid clashing with other
        # modules' torch pins).
        if self.config.quantization is not None:
            requirements.append("bitsandbytes>=0.50.0")

        return requirements

    async def _load_pretrained_model(self) -> Tuple[PreTrainedModel, str]:
        model_path = await self._provision_model(self.config.model)
        device = self._resolve_device(self.config.device) if self.config.device_mode == DeviceMode.SINGLE else None
        dtype = self._get_model_dtype()

        # from_pretrained downloads/mmaps checkpoint shards and instantiates
        # the model on-device — blocking work that would freeze the loop.
        def _load() -> Tuple[PreTrainedModel, Optional[Any]]:
            params: Dict[str, Any] = {
                **self._get_model_params(self.config.model),
                **self._get_model_options(self.config)
            }

            quantization_config = self._resolve_model_quantization_config(self.config, device, dtype)

            if quantization_config is not None:
                params["quantization_config"] = quantization_config

            if device is not None:
                if quantization_config is not None:
                    params["device_map"] = { "": device }
            else:
                params["device_map"] = self.config.device_mode.value

            model = self._get_model_class().from_pretrained(model_path, **params)

            return model, quantization_config

        model, quantization_config = await self._run_in_executor(_load)

        if len(self.config.peft_adapters or []) > 0:
            model = await self._load_peft_adapters(model, self.config.peft_adapters)

        if device is not None and quantization_config is None:
            model = await self._run_in_executor(model.to, device)

        return model, model_path

    async def _load_peft_adapters(
        self,
        base_model: PreTrainedModel,
        adapter_configs: List[PeftAdapterConfig]
    ) -> PreTrainedModel:
        peft_model_paths = await asyncio.gather(*[
            self._provision_model(config.model) for config in adapter_configs
        ])

        def _load() -> PreTrainedModel:
            from peft import PeftModel

            names, weights = self._build_peft_adapter_lists(adapter_configs)
            multiple_adapters = len(adapter_configs) > 1
            has_non_unit_weight = any(abs(weight - 1.0) > 1e-12 for weight in weights)

            peft_model = PeftModel.from_pretrained(
                base_model,
                peft_model_paths[0],
                adapter_name=names[0],
                **self._get_model_params(adapter_configs[0].model),
                **self._get_model_options(adapter_configs[0]),
            )

            for index in range(1, len(adapter_configs)):
                peft_model.load_adapter(
                    peft_model_paths[index],
                    adapter_name=names[index],
                    **self._get_model_params(adapter_configs[index].model),
                    **self._get_model_options(adapter_configs[index]),
                )

            if multiple_adapters or has_non_unit_weight:
                # Use add_weighted_adapter for merging multiple PEFT adapters with weights.
                # This can take minutes on 7B+ models — keep it off the event loop.
                logging.info(
                    f"Merging {len(names)} PEFT adapters with weights {weights}. "
                    "This may take a while..."
                )
                peft_model.add_weighted_adapter(names, weights=weights, adapter_name="blended_adapter")
                peft_model.set_adapter("blended_adapter")
                logging.info("PEFT adapters merging completed.")
            else:
                peft_model.set_adapter(names[0])

            return peft_model

        return await self._run_in_executor(_load)

    def _build_peft_adapter_lists(
        self,
        adapter_configs: List[PeftAdapterConfig]
    ) -> Tuple[List[str], List[float]]:
        names: List[str] = []
        weights: List[float] = []

        for index, config in enumerate(adapter_configs):
            names.append(config.name or f"peft_adapter_{index}")
            weights.append(config.weight)

        return names, weights

    def _get_model_params(self, model: ModelConfig) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(model, HuggingfaceModelConfig):
            if model.revision:
                params["revision"] = model.revision

            if model.cache_dir:
                params["cache_dir"] = model.cache_dir

            if model.local_files_only:
                params["local_files_only"] = True

            if model.token:
                params["token"] = model.token

        return params

    def _get_model_options(
        self,
        config: Union[CommonModelComponentConfig, PeftAdapterConfig, VaeConfig],
        default_dtype: Optional[torch.dtype] = None
    ) -> Dict[str, Any]:
        import torch

        options: Dict[str, Any] = {}

        if default_dtype is not None:
            options["torch_dtype"] = default_dtype

        if config.precision == ModelPrecision.AUTO:
            # Match the checkpoint's native dtype; without this transformers
            # silently upcasts to float32 and doubles the memory footprint.
            options["torch_dtype"] = "auto"
        elif config.precision is not None:
            options["torch_dtype"] = getattr(torch, config.precision.value)

        if config.low_cpu_mem_usage:
            options["low_cpu_mem_usage"] = True

        return options

    def _resolve_model_quantization_config(
        self,
        config: CommonModelComponentConfig,
        device: Optional[torch.device],
        default_dtype: Optional[torch.dtype] = None
    ) -> Optional[Any]:
        quantization: Optional[ModelQuantizationConfig] = config.quantization

        if quantization is None:
            return None

        # bitsandbytes only ships CUDA and MPS kernels (MPS since 0.50.0, torch >= 2.9).
        # `device is None` means device_mode != SINGLE, so accelerate places shards itself.
        if device is not None and device.type not in ("cuda", "mps"):
            raise ValueError(
                f"quantization requires a CUDA or MPS device; got device={device}. "
                "Set device to 'cuda' / 'mps' or remove the `quantization` field."
            )

        from transformers import BitsAndBytesConfig
        import torch

        if quantization.type == ModelQuantizationType.INT8:
            return BitsAndBytesConfig(load_in_8bit=True)

        # int4/fp4/nf4 all take the 4-bit path; `quant_type` selects the block format.
        if quantization.type in (ModelQuantizationType.INT4, ModelQuantizationType.NF4):
            quant_type = "nf4"
        else:
            quant_type = "fp4"

        if quantization.compute_dtype is not None:
            compute_dtype = getattr(torch, quantization.compute_dtype)
        else:
            compute_dtype = default_dtype

        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=quant_type,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=quantization.double_quant,
        )

    def _get_model_class(self) -> Type[PreTrainedModel]:
        raise NotImplementedError("Model class loader not implemented.")

    def _get_model_dtype(self) -> Optional[torch.dtype]:
        import torch

        # "auto" is a from_pretrained hint, not a real dtype — treat as unset.
        if self.config.precision is not None and self.config.precision != ModelPrecision.AUTO:
            return getattr(torch, self.config.precision.value)

        return None

    def _get_model_device(self, model: PreTrainedModel) -> torch.device:
        return next(model.parameters()).device
