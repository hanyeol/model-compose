from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType
from mindor.dsl.schema.action import ModelActionConfig
from mindor.core.services import AsyncService
from ...context import ComponentActionContext

class ModelTaskService(AsyncService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ModelComponentConfig = config

    async def run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_model_task_service(type: ModelTaskType):
    def decorator(cls: Type[ModelTaskService]) -> Type[ModelTaskService]:
        ModelTaskServiceRegistry[type] = cls
        return cls
    return decorator

ModelTaskServiceRegistry: Dict[ModelTaskType, Type[ModelTaskService]] = {}
