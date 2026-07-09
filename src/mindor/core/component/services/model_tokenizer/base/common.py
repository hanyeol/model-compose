from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelTokenizerComponentConfig, ModelTokenizerTaskType, ModelTokenizerDriver
from mindor.dsl.schema.component.impl.model.tasks.common import HuggingfaceModelConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelTokenizerActionConfig
from mindor.core.logger import logging
from ....context import ComponentActionContext

class ModelTokenizerTaskService:
    def __init__(self, id: str, config: ModelTokenizerComponentConfig):
        self.id: str = id
        self.config: ModelTokenizerComponentConfig = config
        self.tokenizer = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    def load(self) -> None:
        if self.tokenizer is None:
            logging.info(f"Component '{self.id}': loading tokenizer...")
            self._load_tokenizer()
            logging.info(f"Component '{self.id}': tokenizer loaded.")

    @abstractmethod
    def _load_tokenizer(self) -> None:
        pass

    @abstractmethod
    async def run(self, action: ModelTokenizerActionConfig, context: ComponentActionContext) -> Any:
        pass

    def _get_model_path(self) -> str:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            return self.config.model.repository

        if isinstance(self.config.model, LocalModelConfig):
            return self.config.model.path

        if isinstance(self.config.model, str):
            return self.config.model

        raise ValueError(f"Unknown model config type: {type(self.config.model)}")

def register_model_tokenizer_task_service(task: ModelTokenizerTaskType, driver: ModelTokenizerDriver):
    def decorator(cls: Type[ModelTokenizerTaskService]) -> Type[ModelTokenizerTaskService]:
        if task not in ModelTokenizerTaskServiceRegistry:
            ModelTokenizerTaskServiceRegistry[task] = {}
        ModelTokenizerTaskServiceRegistry[task][driver] = cls
        return cls
    return decorator

ModelTokenizerTaskServiceRegistry: Dict[ModelTokenizerTaskType, Dict[ModelTokenizerDriver, Type[ModelTokenizerTaskService]]] = {}
