from typing import Optional, List, Any
from mindor.dsl.schema.component import KeyValueStoreComponentConfig, KeyValueStoreDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import KeyValueStoreService, KeyValueStoreServiceRegistry

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

    async def _start(self) -> None:
        await self.service.start()
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.service.run(action, context)
