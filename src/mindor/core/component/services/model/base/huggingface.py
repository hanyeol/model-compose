from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import ModelSourceConfig, DeviceMode
from .common import ModelTaskService

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, ProcessorMixin
    import torch

class HuggingfaceModelTaskService(ModelTaskService):
    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ 
            "transformers>=4.21.0",
            "torch",
            "sentencepiece",
            "accelerate"
        ]

    def _load_pretrained_model(self, extra_params: Optional[Dict[str, Any]] = None) -> PreTrainedModel:
        params = self._get_common_model_params()

        if extra_params:
            params.update(extra_params)

        model = self._get_model_class().from_pretrained(self.config.model, **params)

        if self.config.device_mode == DeviceMode.SINGLE:
            model = model.to(torch.device(self.config.device))

        return model

    def _get_common_model_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, ModelSourceConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision

        if self.config.device_mode != DeviceMode.SINGLE:
            params["device_map"] = self.config.device_mode.value
    
        if self.config.precision is not None:
            params["torch_dtype"] = getattr(torch, self.config.precision.value)
    
        if self.config.low_cpu_mem_usage:
            params["low_cpu_mem_usage"] = True

        if self.config.cache_dir:
            params["cache_dir"] = self.config.cache_dir

        if self.config.local_files_only:
            params["local_files_only"] = True

        return params

    def _get_model_class(self) -> Type[PreTrainedModel]:
        raise NotImplementedError("Model class loader not implemented.")

    def _load_pretrained_tokenizer(self, extra_params: Optional[Dict[str, Any]] = None) -> PreTrainedTokenizer:
        params = self._get_common_tokenizer_params()
 
        if extra_params:
            params.update(extra_params)

        return self._get_tokenizer_class().from_pretrained(self.config.model, **params)

    def _get_common_tokenizer_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, ModelSourceConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision
    
        if not self.config.fast_tokenizer:
            params["use_fast"] = False

        if self.config.cache_dir:
            params["cache_dir"] = self.config.cache_dir

        if self.config.local_files_only:
            params["local_files_only"] = True

        return params

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        raise NotImplementedError("Tokenizer class loader not implemented.")

    def _load_pretrained_processor(self, extra_params: Optional[Dict[str, Any]] = None) -> ProcessorMixin:
        params = self._get_common_processor_params()
 
        if extra_params:
            params.update(extra_params)

        return self._get_processor_class().from_pretrained(self.config.model, **params)

    def _get_common_processor_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, ModelSourceConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision
 
        if self.config.cache_dir:
            params["cache_dir"] = self.config.cache_dir

        if self.config.local_files_only:
            params["local_files_only"] = True

        return params

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        raise NotImplementedError("Processor class loader not implemented.")

    def _get_model_device(self, model: PreTrainedModel) -> torch.device:
        return next(model.parameters()).device
