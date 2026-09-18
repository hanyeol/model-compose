from typing import Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType, ModelDriverType
from mindor.dsl.schema.action import ActionConfig, ModelActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ModelTaskDriver, ModelTaskDriverRegistry
import importlib

class ModelAction:
    def __init__(self, config: ModelActionConfig):
        self.config: ModelActionConfig = config

    async def run(self, context: ComponentActionContext, service: ModelTaskDriver) -> Any:
        return await service.run(self.config, context)

@register_component(ComponentType.MODEL)
class ModelComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ModelComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: ModelTaskDriver = self._create_driver(self.config.task, self.config.driver)

    def _create_driver(self, type: ModelTaskType, driver: ModelDriverType) -> ModelTaskDriver:
        try:
            if type not in ModelTaskDriverRegistry or driver not in ModelTaskDriverRegistry[type]:
                self._load_task_module(type, driver)
            return ModelTaskDriverRegistry[type][driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported model task type: {type} on {driver}")

    def _load_task_module(self, task: ModelTaskType, driver: ModelDriverType) -> None:
        """Import the module that registers the given model task and driver.

        Convention: a task "foo-bar" (ModelTaskType.value) with driver "baz-qux"
        (ModelDriverType.value) maps to mindor.core.component.services.model.tasks.foo_bar.baz_qux
        — either a single-file module (baz_qux.py) or a package (baz_qux/__init__.py).
        Importing the module triggers its @register_model_task_driver decorator,
        populating ModelTaskDriverRegistry.
        """
        task_module = task.value.replace("-", "_")
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.model.tasks.{task_module}.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported model task type: {task} on {driver}") from e

    async def _setup(self) -> None:
        await self.driver.setup()

    async def _teardown(self) -> None:
        await self.driver.teardown()

    async def _start(self) -> None:
        await self.driver.start()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        await self.driver.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ModelAction(action).run(context, self.driver)
