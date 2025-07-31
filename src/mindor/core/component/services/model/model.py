from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType
from mindor.dsl.schema.action import ActionConfig, ModelActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ModelTaskService, ModelTaskServiceRegistry

class ModelAction:
    def __init__(self, config: ModelActionConfig):
        self.config: ModelActionConfig = config

    async def run(self, context: ComponentActionContext, task_service: ModelTaskService) -> Any:
        return await task_service.run(self.config, context)

@register_component(ComponentType.MODEL)
class ModelComponent(ComponentService):
    def __init__(self, id: str, config: ModelComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

        self.task_service = self._create_task_service(self.config.task)

    def _create_task_service(self, type: ModelTaskType) -> ModelTaskService:
        try:
            if not ModelTaskServiceRegistry:
                from . import tasks
            return ModelTaskServiceRegistry[type](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported model task type: {type}")

    async def _serve(self) -> None:
        await self.task_service.start()

    async def _shutdown(self) -> None:
        await self.task_service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ModelAction(action).run(context, self.task_service)
