from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig, DeviceMode
from mindor.core.logger import logging
from .common import ModelTaskService

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer, ProcessorMixin
    import torch

class HuggingfaceModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _load_pretrained_model(self) -> PreTrainedModel:
        model_cls = self._get_model_class()
        model = model_cls.from_pretrained(self.config.model, **self._get_model_params())

        if self.config.device_mode == DeviceMode.SINGLE:
            model = model.to(torch.device(self.config.device))

        return model

    def _get_model_class(self) -> Type[PreTrainedModel]:
        raise NotImplementedError("Model class loader not implemented.")

    def _get_model_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision
            
            if self.config.model.cache_dir:
                params["cache_dir"] = self.config.model.cache_dir

            if self.config.model.local_files_only:
                params["local_files_only"] = True

        if self.config.device_mode != DeviceMode.SINGLE:
            params["device_map"] = self.config.device_mode.value
    
        if self.config.precision is not None:
            params["torch_dtype"] = getattr(torch, self.config.precision.value)
    
        if self.config.low_cpu_mem_usage:
            params["low_cpu_mem_usage"] = True

        return params

    def _get_model_device(self, model: PreTrainedModel) -> torch.device:
        return next(model.parameters()).device

class HuggingfaceLanguageModelTaskService(HuggingfaceModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ 
            "transformers>=4.21.0",
            "torch",
            "sentencepiece",
            "accelerate"
        ]

    async def _serve(self) -> None:
        try:
            self.model = self._load_pretrained_model()
            self.tokenizer = self._load_pretrained_tokenizer()
            self.device = self._get_model_device(self.model)
            logging.info(f"Model and tokenizer loaded successfully on device '{self.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.tokenizer = None
        self.device = None

    def _load_pretrained_tokenizer(self) -> Optional[PreTrainedTokenizer]:
        tokenizer_cls = self._get_tokenizer_class()

        if not tokenizer_cls:
            return None

        return tokenizer_cls.from_pretrained(self.config.model, **self._get_tokenizer_params())

    def _get_tokenizer_class(self) -> Optional[Type[PreTrainedTokenizer]]:
        return None

    def _get_tokenizer_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision

            if self.config.model.cache_dir:
                params["cache_dir"] = self.config.model.cache_dir

            if self.config.model.local_files_only:
                params["local_files_only"] = True

        if not self.config.fast_tokenizer:
            params["use_fast"] = False

        return params

class HuggingfaceMultimodalModelTaskService(HuggingfaceModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.processor: Optional[ProcessorMixin] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ 
            "transformers>=4.21.0",
            "torch",
            "sentencepiece",
            "accelerate"
        ]

    async def _serve(self) -> None:
        try:
            self.model = self._load_pretrained_model()
            self.processor = self._load_pretrained_processor()
            self.device = self._get_model_device(self.model)
            logging.info(f"Model and processor loaded successfully on device '{self.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.processor = None
        self.device = None

    def _load_pretrained_processor(self) -> Optional[ProcessorMixin]:
        processor_cls = self._get_processor_class()

        if not processor_cls:
            return None

        return processor_cls.from_pretrained(self.config.model, **self._get_processor_params())

    def _get_processor_class(self) -> Optional[Type[ProcessorMixin]]:
        return None

    def _get_processor_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision
 
            if self.config.model.cache_dir:
                params["cache_dir"] = self.config.model.cache_dir

            if self.config.model.local_files_only:
                params["local_files_only"] = True

        return params
