from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType, ModelDriver
from mindor.dsl.schema.action import ModelActionConfig
from mindor.core.services import AsyncService
from ....context import ComponentActionContext
import asyncio

class ModelTaskService(AsyncService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ModelComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        async def _run():
            return await self._run(action, context, loop)

        return await self.run_in_thread(_run)

    @abstractmethod
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_model_task_service(type: ModelTaskType, driver: ModelDriver):
    def decorator(cls: Type[ModelTaskService]) -> Type[ModelTaskService]:
        if type not in ModelTaskServiceRegistry:
            ModelTaskServiceRegistry[type] = {}
        ModelTaskServiceRegistry[type][driver] = cls
        return cls
    return decorator

ModelTaskServiceRegistry: Dict[ModelTaskType, Dict[ModelDriver, Type[ModelTaskService]]] = {}
