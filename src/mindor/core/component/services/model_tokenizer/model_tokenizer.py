from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelTokenizerComponentConfig, ModelTokenizerTaskType, ModelTokenizerDriver
from mindor.dsl.schema.action import ActionConfig, ModelTokenizerActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ModelTokenizerTaskService, ModelTokenizerTaskServiceRegistry
import importlib

class ModelTokenizerAction:
    def __init__(self, config: ModelTokenizerActionConfig):
        self.config: ModelTokenizerActionConfig = config

    async def run(self, context: ComponentActionContext, service: ModelTokenizerTaskService) -> Any:
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

        self.service: ModelTokenizerTaskService = self._create_service(self.config.task, self.config.driver)

    def _create_service(self, task: ModelTokenizerTaskType, driver: ModelTokenizerDriver) -> ModelTokenizerTaskService:
        try:
            if task not in ModelTokenizerTaskServiceRegistry or driver not in ModelTokenizerTaskServiceRegistry[task]:
                _load_tokenizer_task_module(task, driver)
            return ModelTokenizerTaskServiceRegistry[task][driver](self.id, self.config)
        except KeyError:
            raise ValueError(f"Unsupported tokenizer task type: {task} on {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        self.service.load()
        return await ModelTokenizerAction(action).run(context, self.service)

def _load_tokenizer_task_module(task: ModelTokenizerTaskType, driver: ModelTokenizerDriver) -> None:
    """Import the module that registers the given tokenizer task and driver.

    Convention: a task "foo-bar" (ModelTokenizerTaskType.value) with driver
    "baz-qux" (ModelTokenizerDriver.value) maps to
    mindor.core.component.services.model_tokenizer.tasks.foo_bar.baz_qux —
    either a single-file module (baz_qux.py) or a package (baz_qux/__init__.py).
    Importing the module triggers its @register_model_tokenizer_task_service
    decorator, populating ModelTokenizerTaskServiceRegistry.
    """
    task_module = task.value.replace("-", "_")
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.model_tokenizer.tasks.{task_module}.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported tokenizer task type: {task} on {driver}") from e
