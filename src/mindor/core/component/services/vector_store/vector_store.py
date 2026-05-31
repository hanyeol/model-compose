from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VectorStoreComponentConfig, VectorStoreDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VectorStoreService, VectorStoreServiceRegistry

@register_component(ComponentType.VECTOR_STORE)
class VectorStoreComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VectorStoreComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: VectorStoreService = self._create_service(self.config.driver)

    def _create_service(self, driver: VectorStoreDriver) -> VectorStoreService:
        try:
            if not VectorStoreServiceRegistry:
                from . import drivers
            return VectorStoreServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported vector store driver: {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()
    
    async def _serve(self) -> None:
        await self.service.start()

    async def _shutdown(self) -> None:
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.service.run(action, context)
