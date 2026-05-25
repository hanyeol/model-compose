from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import SearchEngineComponentConfig, SearchEngineDriver
from mindor.dsl.schema.action import ActionConfig, SearchEngineActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import SearchEngineService, SearchEngineServiceRegistry

class SearchEngineAction:
    def __init__(self, config: SearchEngineActionConfig):
        self.config: SearchEngineActionConfig = config

    async def run(self, context: ComponentActionContext, service: SearchEngineService) -> Any:
        return await service.run(self.config, context)

@register_component(ComponentType.SEARCH_ENGINE)
class SearchEngineComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: SearchEngineComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: SearchEngineService = self._create_service(self.config.driver)

    def _create_service(self, driver: SearchEngineDriver) -> SearchEngineService:
        try:
            if not SearchEngineServiceRegistry:
                from . import drivers
            return SearchEngineServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported search engine driver: {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _serve(self) -> None:
        await self.service.start()

    async def _shutdown(self) -> None:
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await SearchEngineAction(action).run(context, self.service)
