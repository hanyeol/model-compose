from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from .base import HuggingfaceModelTaskService

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    import torch

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

    async def _load_model(self) -> None:
        self.model = self._load_pretrained_model()
        self.processor = self._load_pretrained_processor()
        self.device = self._get_model_device(self.model)

    async def _unload_model(self) -> None:
        self.model = None
        self.processor = None
        self.device = None

    def _load_pretrained_processor(self) -> Optional[ProcessorMixin]:
        processor_cls = self._get_processor_class()

        if not processor_cls:
            return None

        return processor_cls.from_pretrained(self._get_model_path(self.config), **self._get_processor_params())

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

            if self.config.model.token:
                params["token"] = self.config.model.token

        return params
