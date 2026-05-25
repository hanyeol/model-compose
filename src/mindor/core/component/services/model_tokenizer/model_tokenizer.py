from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelTokenizerComponentConfig, ModelTokenizerTaskType, ModelTokenizerDriver
from mindor.dsl.schema.action import ActionConfig, ModelTokenizerActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ModelTokenizerTaskService, ModelTokenizerTaskServiceRegistry

class ModelTokenizerAction:
    def __init__(self, config: ModelTokenizerActionConfig):
        self.config: ModelTokenizerActionConfig = config

    async def run(self, context: ComponentActionContext, task_service: ModelTokenizerTaskService) -> Any:
        return await task_service.run(self.config, context)

@register_component(ComponentType.MODEL_TOKENIZER)
class ModelTokenizerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ModelTokenizerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.task_service: ModelTokenizerTaskService = self._create_task_service(self.config.task, self.config.driver)

    def _create_task_service(self, task: ModelTokenizerTaskType, driver: ModelTokenizerDriver) -> ModelTokenizerTaskService:
        try:
            if not ModelTokenizerTaskServiceRegistry:
                from . import tasks
            return ModelTokenizerTaskServiceRegistry[task][driver](self.id, self.config)
        except KeyError:
            raise ValueError(f"Unsupported tokenizer task type: {task} on {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.task_service.get_setup_requirements()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        self.task_service.load()
        return await ModelTokenizerAction(action).run(context, self.task_service)
