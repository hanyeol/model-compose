from typing import Any
from mindor.dsl.schema.component import ModelTokenizerComponentConfig, ModelTokenizerTaskType, ModelTokenizerDriverType
from mindor.dsl.schema.action import ActionConfig, ModelTokenizerActionConfig
from ...action.base import ComponentAction
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ModelTokenizerTaskDriver, ModelTokenizerTaskDriverRegistry
import importlib

class ModelTokenizerAction(ComponentAction):
    def __init__(self, config: ModelTokenizerActionConfig):
        self.config: ModelTokenizerActionConfig = config

    async def run(self, context: ComponentActionContext, service: ModelTokenizerTaskDriver) -> Any:
        return await service.run(self.config, context)

@register_component(ComponentType.MODEL_TOKENIZER)
class ModelTokenizerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ModelTokenizerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: ModelTokenizerTaskDriver = self._create_driver(self.config.task, self.config.driver)

    def _create_driver(self, task: ModelTokenizerTaskType, driver: ModelTokenizerDriverType) -> ModelTokenizerTaskDriver:
        try:
            if task not in ModelTokenizerTaskDriverRegistry or driver not in ModelTokenizerTaskDriverRegistry[task]:
                self._load_task_module(task, driver)
            return ModelTokenizerTaskDriverRegistry[task][driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported tokenizer task type: {task} on {driver}")

    def _load_task_module(self, task: ModelTokenizerTaskType, driver: ModelTokenizerDriverType) -> None:
        """Import the module that registers the given tokenizer task and driver.

        Convention: a task "foo-bar" (ModelTokenizerTaskType.value) with driver
        "baz-qux" (ModelTokenizerDriverType.value) maps to
        mindor.core.component.services.model_tokenizer.tasks.foo_bar.baz_qux —
        either a single-file module (baz_qux.py) or a package (baz_qux/__init__.py).
        Importing the module triggers its @register_model_tokenizer_task_driver
        decorator, populating ModelTokenizerTaskDriverRegistry.
        """
        task_module = task.value.replace("-", "_")
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.model_tokenizer.tasks.{task_module}.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported tokenizer task type: {task} on {driver}") from e

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
        return await ModelTokenizerAction(action).run(context, self.driver)
