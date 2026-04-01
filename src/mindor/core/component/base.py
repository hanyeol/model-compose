from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ComponentConfig, ComponentType
from mindor.dsl.schema.action import ActionConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.dsl.schema.runtime import RuntimeType
from mindor.core.foundation import AsyncService
from mindor.core.utils.work_queue import WorkQueue
from mindor.core.utils.active_counter import ActiveCounter
from mindor.core.logger import logging
from .context import ComponentActionContext

class ActionResolver:
    def __init__(self, actions: List[ActionConfig]):
        self.actions: List[ActionConfig] = actions

    def resolve(self, action_id: str, raise_on_error: bool = True) -> Union[Tuple[str, ActionConfig], Tuple[None, None]]:
        if action_id == "__default__":
            action = self.actions[0] if len(self.actions) == 1 else None
            action = action or next((action for action in self.actions if action.default), None)
        else:
            action = next((action for action in self.actions if action.id == action_id), None)

        if action is None:
            if raise_on_error:
                raise ValueError(f"Action not found: {action_id}")
            else:
                return (None, None)

        return action.id, action

class ComponentGlobalConfigs:
    def __init__(
        self, 
        components: List[ComponentConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        workflows: List[WorkflowConfig]
    ):
        self.components: List[ComponentConfig] = components
        self.listeners: List[ListenerConfig] = listeners
        self.gateways: List[GatewayConfig] = gateways
        self.workflows: List[WorkflowConfig] = workflows

class ComponentService(AsyncService):
    def __init__(
        self,
        id: str,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(daemon)

        self.id: str = id
        self.config: ComponentConfig = config
        self.global_configs: ComponentGlobalConfigs = global_configs
        self.work_queue: Optional[WorkQueue] = None
        self._process_manager = None
        self._docker_manager = None
        self._active_counter: ActiveCounter = ActiveCounter()

        if self.config.max_concurrent_count > 0:
            self.work_queue = WorkQueue(self.config.max_concurrent_count, self._run)

    async def start(self, background: bool = False) -> None:
        if self.config.runtime.type == RuntimeType.PROCESS:
            await self._start_process_runtime()
            return

        if self.config.runtime.type == RuntimeType.DOCKER:
            await self._start_docker_runtime()

        await super().start(background)
        await self.wait_until_ready()

    async def stop(self) -> None:
        if self._process_manager:
            await self._stop_process_runtime()
            return

        await super().stop()

        if self._docker_manager:
            await self._stop_docker_runtime()

    async def run(self, action_id: str, run_id: str, input: Dict[str, Any], workflow=None) -> Dict[str, Any]:
        if self._process_manager:
            return await self._process_manager.run(action_id, run_id, input)

        _, action = ActionResolver(self.config.actions).resolve(action_id)
        context = ComponentActionContext(run_id, input, workflow=workflow)

        if self.work_queue:
            return await (await self.work_queue.schedule(action, context))

        self._active_counter.acquire()
        try:
            return await self._run(action, context)
        finally:
            self._active_counter.release()

    async def _start(self) -> None:
        if self.work_queue:
            await self.work_queue.start()

        await super()._start()

    async def _stop(self) -> None:
        if self.work_queue:
            await self.work_queue.stop()

        await self._active_counter.wait_for_zero()
        await super()._stop()

    async def _is_ready(self) -> bool:
        return True

    @abstractmethod
    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        pass

    async def _install_package(self, package_spec: str, repository: Optional[str]) -> None:
        logging.info(f"Installing required module: {package_spec}")
        await super()._install_package(package_spec, repository)

    async def _start_process_runtime(self) -> None:
        from mindor.core.component.runtime import ComponentProcessRuntimeManager
        self._process_manager = ComponentProcessRuntimeManager(self.id, self.config, self.global_configs)
        await self._process_manager.start()
        logging.info(f"Component '{self.id}' started with process runtime")

    async def _stop_process_runtime(self) -> None:
        await self._process_manager.stop()
        logging.info(f"Component '{self.id}' process runtime stopped")

    async def _start_docker_runtime(self) -> None:
        from mindor.core.runtime.docker import DockerRuntimeManager
        self._docker_manager = DockerRuntimeManager(self.config.runtime, verbose=False)
        if not await self._docker_manager.exists_image():
            await self._docker_manager.pull_image()
        if await self._docker_manager.exists_container():
            await self._docker_manager.remove_container(force=True)
        await self._docker_manager.start_container(detach=True)
        logging.info(f"Component '{self.id}' started with Docker runtime")

    async def _stop_docker_runtime(self) -> None:
        await self._docker_manager.stop_container()
        await self._docker_manager.remove_container(force=True)
        logging.info(f"Component '{self.id}' Docker container stopped")

def register_component(type: ComponentType):
    def decorator(cls: Type[ComponentService]) -> Type[ComponentService]:
        ComponentRegistry[type] = cls
        return cls
    return decorator

ComponentRegistry: Dict[ComponentType, Type[ComponentService]] = {}
