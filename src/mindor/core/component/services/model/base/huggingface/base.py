from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Tuple, Any
from pydantic import BaseModel
from mindor.dsl.schema.component import ModelComponentConfig, PeftAdapterConfig, ModelConfig, HuggingfaceModelConfig, ModelPrecision, DeviceMode
from mindor.core.logger import logging
from ..common import ModelTaskService

if TYPE_CHECKING:
    from transformers import PreTrainedModel
    import torch

class HuggingfaceModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _load_pretrained_model(self) -> Tuple[PreTrainedModel, str]:
        model_cls = self._get_model_class()
        params = self._get_model_params(self.config.model)
        options = self._get_model_options(self.config)

        if options:
            params.update(options)

        if self.config.device_mode != DeviceMode.SINGLE:
            params["device_map"] = self.config.device_mode.value

        model_path = await self._provision_model(self.config.model)
        model = model_cls.from_pretrained(model_path, **params)

        if len(self.config.peft_adapters or []) > 0:
            model = await self._load_peft_adapters(model, self.config.peft_adapters)

        if self.config.device_mode == DeviceMode.SINGLE:
            model = model.to(self._resolve_device(self.config.device))

        return model, model_path

    async def _load_peft_adapters(self, base_model: PreTrainedModel, adapter_configs: List[PeftAdapterConfig]) -> PreTrainedModel:
        from peft import PeftModel

        names, weights = self._build_peft_adapter_lists(adapter_configs)
        peft_model_path = await self._provision_model(adapter_configs[0].model)
        peft_model = PeftModel.from_pretrained(
            base_model,
            peft_model_path,
            adapter_name=names[0],
            **self._get_model_params(adapter_configs[0].model),
            **self._get_model_options(adapter_configs[0]),
        )

        for index in range(1, len(adapter_configs)):
            peft_model_path = await self._provision_model(adapter_configs[index].model)
            peft_model.load_adapter(
                peft_model_path,
                adapter_name=names[index],
                **self._get_model_params(adapter_configs[index].model),
                **self._get_model_options(adapter_configs[index]),
            )

        multiple_adapters = len(adapter_configs) > 1
        has_non_unit_weight = any(abs(weight - 1.0) > 1e-12 for weight in weights)

        if multiple_adapters or has_non_unit_weight:
            # Use add_weighted_adapter for merging multiple PEFT adapters with weights
            # Note: This operation can be slow for large models (e.g., 7B+)
            logging.info(f"Merging {len(names)} PEFT adapters with weights {weights}. This may take a while...")
            peft_model.add_weighted_adapter(names, weights=weights, adapter_name="blended_adapter")
            peft_model.set_adapter("blended_adapter")
            logging.info("PEFT adapters merging completed.")
        else:
            peft_model.set_adapter(names[0])

        return peft_model

    def _build_peft_adapter_lists(self, adapter_configs: List[PeftAdapterConfig]) -> Tuple[List[str], List[float]]:
        names: List[str] = []
        weights: List[float] = []

        for index, config in enumerate(adapter_configs):
            names.append(config.name or f"peft_adapter_{index}")
            weights.append(config.weight)

        return names, weights

    def _get_model_class(self) -> Type[PreTrainedModel]:
        raise NotImplementedError("Model class loader not implemented.")

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

    def _get_model_options(self, config: BaseModel, default_dtype: Optional[torch.dtype] = None) -> Dict[str, Any]:
        import torch

        options: Dict[str, Any] = {}

        if default_dtype is not None:
            options["torch_dtype"] = default_dtype

        precision = getattr(config, "precision", None)

        if precision is not None and precision != ModelPrecision.AUTO:
            options["torch_dtype"] = getattr(torch, precision.value)

        if getattr(config, "low_cpu_mem_usage", False):
            options["low_cpu_mem_usage"] = True

        return options

    def _get_model_device(self, model: PreTrainedModel) -> torch.device:
        return next(model.parameters()).device
