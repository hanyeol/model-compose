from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import GraphStoreComponentConfig, GraphStoreDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import GraphStoreService, GraphStoreServiceRegistry

@register_component(ComponentType.GRAPH_STORE)
class GraphStoreComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: GraphStoreComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: GraphStoreService = self._create_service(self.config.driver)

    def _create_service(self, driver: GraphStoreDriver) -> GraphStoreService:
        try:
            if not GraphStoreServiceRegistry:
                from . import drivers
            return GraphStoreServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported graph store driver: {driver}")

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
