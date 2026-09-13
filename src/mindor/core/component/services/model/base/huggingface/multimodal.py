from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig
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

    def _get_setup_requirements(self) -> List[str]:
        return [
            *super()._get_setup_requirements(),
            "peft>=0.5.0",
            "sentencepiece",
        ]

    async def _load_model(self) -> None:
        self.model, model_path = await self._load_pretrained_model()
        self.processor = await self._load_pretrained_processor(model_path)
        self.device = self._get_model_device(self.model)

    async def _unload_model(self) -> None:
        self.model = None
        self.processor = None
        self.device = None

    async def _load_pretrained_processor(self, model_path: str) -> Optional[ProcessorMixin]:
        processor_cls = self._get_processor_class()

        if not processor_cls:
            return None

        def _load() -> ProcessorMixin:
            return processor_cls.from_pretrained(
                model_path,
                **self._get_processor_params(self.config.model)
            )

        return await self._run_in_executor(_load)

    def _get_processor_class(self) -> Optional[Type[ProcessorMixin]]:
        raise NotImplementedError("Processor class loader not implemented.")

    def _get_processor_params(self, model: ModelConfig) -> Dict[str, Any]:
        return self._get_model_params(model)
