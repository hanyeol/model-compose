from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ShellComponentConfig, ShellDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ShellService, ShellServiceRegistry
import importlib

@register_component(ComponentType.SHELL)
class ShellComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ShellComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: ShellService = self._create_service(self.config.driver)

    def _create_service(self, driver: ShellDriver) -> ShellService:
        try:
            if driver not in ShellServiceRegistry:
                self._load_driver_module(driver)
            return ShellServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported shell driver: {driver}")

    def _load_driver_module(self, driver: ShellDriver) -> None:
        """Import the module that registers the given shell driver.

        Convention: a driver "foo-bar" (ShellDriver.value) maps to
        mindor.core.component.services.shell.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_shell_service decorator,
        populating ShellServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.shell.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported shell driver: {driver}") from e

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _setup(self) -> None:
        await self.service.setup()

    async def _teardown(self) -> None:
        await self.service.teardown()

    async def _start(self) -> None:
        await self.service.start()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.service.run(action, context)
