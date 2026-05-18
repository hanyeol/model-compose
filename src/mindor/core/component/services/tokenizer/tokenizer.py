from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import TokenizerComponentConfig, TokenizerTaskType, TokenizerDriver
from mindor.dsl.schema.action import ActionConfig, TokenizerActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import TokenizerTaskService, TokenizerTaskServiceRegistry

class TokenizerAction:
    def __init__(self, config: TokenizerActionConfig):
        self.config: TokenizerActionConfig = config

    async def run(self, context: ComponentActionContext, task_service: TokenizerTaskService) -> Any:
        return await task_service.run(self.config, context)

@register_component(ComponentType.TOKENIZER)
class TokenizerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: TokenizerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.task_service: TokenizerTaskService = self._create_task_service(self.config.task, self.config.driver)

    def _create_task_service(self, task: TokenizerTaskType, driver: TokenizerDriver) -> TokenizerTaskService:
        try:
            if not TokenizerTaskServiceRegistry:
                from . import tasks
            return TokenizerTaskServiceRegistry[task][driver](self.id, self.config)
        except KeyError:
            raise ValueError(f"Unsupported tokenizer task type: {task} on {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.task_service.get_setup_requirements()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        self.task_service.load()
        return await TokenizerAction(action).run(context, self.task_service)
