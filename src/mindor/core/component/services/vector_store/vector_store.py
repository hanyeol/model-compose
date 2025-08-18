from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from mindor.dsl.schema.component import VectorStoreComponentConfig, VectorStoreDriver
from mindor.dsl.schema.action import ActionConfig, VectorStoreActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VectorStoreService, VectorStoreServiceRegistry

class VectorStoreAction:
    def __init__(self, config: VectorStoreActionConfig):
        self.config: VectorStoreActionConfig = config

    async def run(self, context: ComponentActionContext, store_service: VectorStoreService) -> Any:
        return await store_service.run(self.config, context)

@register_component(ComponentType.VECTOR_STORE)
class VectorStoreComponent(ComponentService):
    def __init__(self, id: str, config: VectorStoreComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

        self.store_service = self._create_store_service(self.config.driver)

    def _create_store_service(self, driver: VectorStoreDriver) -> VectorStoreService:
        try:
            if not VectorStoreServiceRegistry:
                from . import drivers
            return VectorStoreServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported vector store driver: {driver}")

    async def _serve(self) -> None:
        await self.store_service.start()

    async def _shutdown(self) -> None:
        await self.store_service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await VectorStoreAction(action).run(context, self.store_service)
