from typing import Any, Optional
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType, ModelDriverType
from mindor.dsl.schema.action import ActionConfig, ModelActionConfig
from mindor.dsl.schema.component.impl.model.tasks.common import OnDemandConfig
from mindor.core.foundation.variable.time import parse_time
from mindor.core.logger import logging
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ModelTaskDriver, ModelTaskDriverRegistry
import asyncio
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

        if isinstance(self.config.on_demand, OnDemandConfig):
            self._on_demand: Optional[OnDemandConfig] = self.config.on_demand
            self._idle_timeout: float = parse_time(self._on_demand.idle_timeout)
        else:
            self._on_demand: Optional[OnDemandConfig] = None
            self._idle_timeout: float = 0.0

        self._idle_timer_task: Optional[asyncio.Task] = None
        self._stopping: bool = False

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

        self._stopping = False

        if self.config.preload:
            await self.driver.load_model()
            if self._on_demand is not None and self._idle_timeout > 0:
                self._schedule_idle_timer(self._idle_timeout)
        else:
            logging.info(f"Component '{self.id}': model will be loaded on demand")

        await super()._start()

    async def _stop(self) -> None:
        self._stopping = True

        task = self._idle_timer_task
        self._idle_timer_task = None

        if task is not None and not task.done():
            task.cancel()

            try:
                await task
            except BaseException:
                pass

        await super()._stop()

        if self.driver.model_loaded:
            await self.driver.unload_model()

        await self.driver.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ModelAction(action).run(context, self.driver)

    def _on_action_count_changed(self, count: int) -> None:
        if self._on_demand is None or self._stopping:
            return

        if self._idle_timer_task is not None:
            self._cancel_idle_timer()

        if count == 0 and self.driver.model_loaded and self._idle_timeout > 0:
            self._schedule_idle_timer(self._idle_timeout)

    def _schedule_idle_timer(self, timeout: float) -> None:
        self._idle_timer_task = asyncio.create_task(
            self._idle_timer_callback(timeout),
            name=f"model-idle-timer:{self.id}",
        )

    def _cancel_idle_timer(self) -> None:
        task = self._idle_timer_task
        self._idle_timer_task = None

        if task is not None and not task.done():
            task.cancel()

    async def _idle_timer_callback(self, timeout: float) -> None:
        try:
            await asyncio.sleep(timeout)
        except asyncio.CancelledError:
            return

        if not self._stopping and self._get_action_count() == 0:
            try:
                await self.driver.unload_model()
            except BaseException as e:
                logging.exception(f"Component '{self.id}': idle unload failed: {e}")
