from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import GraphStoreComponentConfig, GraphStoreDriver
from mindor.dsl.schema.action import ActionConfig, GraphStoreActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import GraphStoreService, GraphStoreServiceRegistry

class GraphStoreAction:
    def __init__(self, config: GraphStoreActionConfig):
        self.config: GraphStoreActionConfig = config

    async def run(self, context: ComponentActionContext, service: GraphStoreService) -> Any:
        return await service.run(self.config, context)

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

    async def _serve(self) -> None:
        await self.service.start()

    async def _shutdown(self) -> None:
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await GraphStoreAction(action).run(context, self.service)
