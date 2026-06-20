from typing import Optional, List, Any
from mindor.dsl.schema.component import SearchEngineComponentConfig, SearchEngineDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import SearchEngineService, SearchEngineServiceRegistry

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

    async def _start(self) -> None:
        await self.service.start()
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.service.run(action, context)
