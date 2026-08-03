from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ModelTokenizerComponentConfig, ModelTokenizerTaskType, ModelTokenizerDriver
from mindor.dsl.schema.component.impl.model.tasks.common import ModelConfig
from mindor.dsl.schema.action import ModelTokenizerActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.logger import logging
from ....context import ComponentActionContext
from ...model.utils.provision import ModelProvisioner

class ModelTokenizerTaskService(AsyncService):
    def __init__(self, id: str, config: ModelTokenizerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ModelTokenizerComponentConfig = config
        self.tokenizer = None

        self._model_provisioner: ModelProvisioner = ModelProvisioner()

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def _start(self) -> None:
        logging.info(f"Component '{self.id}': loading tokenizer...")
        await self._load_tokenizer()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        self.tokenizer = None

    @abstractmethod
    async def _load_tokenizer(self) -> None:
        pass

    @abstractmethod
    async def run(self, action: ModelTokenizerActionConfig, context: ComponentActionContext) -> Any:
        pass

    async def _provision_model(self, model: ModelConfig, prefetch: bool = False) -> str:
        return await self._model_provisioner.provision(model, prefetch=prefetch)

def register_model_tokenizer_task_service(task: ModelTokenizerTaskType, driver: ModelTokenizerDriver):
    def decorator(cls: Type[ModelTokenizerTaskService]) -> Type[ModelTokenizerTaskService]:
        if task not in ModelTokenizerTaskServiceRegistry:
            ModelTokenizerTaskServiceRegistry[task] = {}
        ModelTokenizerTaskServiceRegistry[task][driver] = cls
        return cls
    return decorator

ModelTokenizerTaskServiceRegistry: Dict[ModelTokenizerTaskType, Dict[ModelTokenizerDriver, Type[ModelTokenizerTaskService]]] = {}
