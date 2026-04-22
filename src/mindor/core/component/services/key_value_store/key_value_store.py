from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import KeyValueStoreComponentConfig, KeyValueStoreDriver
from mindor.dsl.schema.action import ActionConfig, KeyValueStoreActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import KeyValueStoreService, KeyValueStoreServiceRegistry

class KeyValueStoreAction:
    def __init__(self, config: KeyValueStoreActionConfig):
        self.config: KeyValueStoreActionConfig = config

    async def run(self, context: ComponentActionContext, service: KeyValueStoreService) -> Any:
        return await service.run(self.config, context)

@register_component(ComponentType.KEY_VALUE_STORE)
class KeyValueStoreComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: KeyValueStoreComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: KeyValueStoreService = self._create_service(self.config.driver)

    def _create_service(self, driver: KeyValueStoreDriver) -> KeyValueStoreService:
        try:
            if not KeyValueStoreServiceRegistry:
                from . import drivers
            return KeyValueStoreServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported key-value store driver: {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _serve(self) -> None:
        await self.service.start()

    async def _shutdown(self) -> None:
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await KeyValueStoreAction(action).run(context, self.service)
