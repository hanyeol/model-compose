from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType, ModelDriver
from mindor.dsl.schema.action import ActionConfig, ModelActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ModelTaskService, ModelTaskServiceRegistry
import importlib

class ModelAction:
    def __init__(self, config: ModelActionConfig):
        self.config: ModelActionConfig = config

    async def run(self, context: ComponentActionContext, service: ModelTaskService) -> Any:
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

        self.service: ModelTaskService = self._create_service(self.config.task, self.config.driver)

    def _create_service(self, type: ModelTaskType, driver: ModelDriver) -> ModelTaskService:
        try:
            if type not in ModelTaskServiceRegistry or driver not in ModelTaskServiceRegistry[type]:
                _load_model_task_module(type, driver)
            return ModelTaskServiceRegistry[type][driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported model task type: {type} on {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _start(self) -> None:
        await self.service.start()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ModelAction(action).run(context, self.service)

def _load_model_task_module(task: ModelTaskType, driver: ModelDriver) -> None:
    """Import the module that registers the given model task and driver.

    Convention: a task "foo-bar" (ModelTaskType.value) with driver "baz-qux"
    (ModelDriver.value) maps to mindor.core.component.services.model.tasks.foo_bar.baz_qux
    — either a single-file module (baz_qux.py) or a package (baz_qux/__init__.py).
    Importing the module triggers its @register_model_task_service decorator,
    populating ModelTaskServiceRegistry.
    """
    task_module = task.value.replace("-", "_")
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.model.tasks.{task_module}.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported model task type: {task} on {driver}") from e
