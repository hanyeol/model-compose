from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from typing_extensions import Self
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
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
                raise LookupError(f"Action not found: {action_id}")
            else:
                return (None, None)

        return action.id, action

class ComponentGlobalConfigs(BaseModel):
    components: List[ComponentConfig] = Field(default_factory=list)
    listeners:  List[ListenerConfig]  = Field(default_factory=list)
    gateways:   List[GatewayConfig]   = Field(default_factory=list)
    workflows:  List[WorkflowConfig]  = Field(default_factory=list)

    @classmethod
    def create(cls,
        components: List[ComponentConfig],
        listeners:  List[ListenerConfig],
        gateways:   List[GatewayConfig],
        workflows:  List[WorkflowConfig],
    ) -> Self:
        return cls(
            components=components,
            listeners=listeners,
            gateways=gateways,
            workflows=workflows,
        )

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
        self._process_launcher = None
        self._virtualenv_launcher = None
        self._docker_launcher = None
        self._apple_container_launcher = None
        self._active_counter: ActiveCounter = ActiveCounter()

        if self.config.max_concurrent_count > 0:
            self.work_queue = WorkQueue(self.config.max_concurrent_count, self._run)

    async def setup(self) -> None:
        # Components running in an isolated runtime install their dependencies inside that
        # isolated environment (worker venv / container build). Skip the host-side install
        # here so we do not leak component dependencies into the parent interpreter.
        if self.config.runtime.type in (
            RuntimeType.PROCESS,
            RuntimeType.VIRTUALENV,
            RuntimeType.DOCKER,
            RuntimeType.APPLE_CONTAINER,
        ):
            return
        await super().setup()

    async def start(self, background: bool = False) -> None:
        if self.config.runtime.type == RuntimeType.PROCESS:
            await self._start_process_runtime()
            self.started = True
            return

        if self.config.runtime.type == RuntimeType.VIRTUALENV:
            await self._start_virtualenv_runtime()
            self.started = True
            return

        if self.config.runtime.type == RuntimeType.DOCKER:
            await self._start_docker_runtime()

        if self.config.runtime.type == RuntimeType.APPLE_CONTAINER:
            await self._start_apple_container_runtime()

        await super().start(background)
        await self.wait_until_ready()

    async def stop(self) -> None:
        if self._process_launcher:
            await self._stop_process_runtime()
            self.started = False
            return

        if self._virtualenv_launcher:
            await self._stop_virtualenv_runtime()
            self.started = False
            return

        await super().stop()

        if self._docker_launcher:
            await self._stop_docker_runtime()

        if self._apple_container_launcher:
            await self._stop_apple_container_runtime()

    async def run(self, action_id: str, run_id: str, input: Dict[str, Any], workflow=None, job_id: Optional[str] = None) -> Dict[str, Any]:
        if self._process_launcher:
            return await self._process_launcher.run(action_id, run_id, input)

        if self._virtualenv_launcher:
            return await self._virtualenv_launcher.run(action_id, run_id, input)

        if self._docker_launcher:
            return await self._docker_launcher.run(action_id, run_id, input)

        if self._apple_container_launcher:
            return await self._apple_container_launcher.run(action_id, run_id, input)

        _, action = ActionResolver(self.config.actions).resolve(action_id)
        context = ComponentActionContext(
            run_id,
            input,
            workflow=workflow,
            component_id=self.id,
            component_type=self.config.type.value,
            job_id=job_id
        )

        await context.event_notifier.notify("started", input=input)

        try:
            if self.work_queue:
                output = await (await self.work_queue.schedule(action, context))
            else:
                self._active_counter.acquire()
                try:
                    output = await self._run(action, context)
                finally:
                    self._active_counter.release()
        except Exception as e:
            await context.event_notifier.notify("failed", error=str(e))
            raise

        await context.event_notifier.notify("completed", output=output)

        return output

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
        from mindor.core.component.runtime.process import ComponentProcessRuntimeLauncher

        self._process_launcher = ComponentProcessRuntimeLauncher(self.id, self.config, self.global_configs)
        await self._process_launcher.start()
        logging.info(f"Component '{self.id}' started with process runtime")

    async def _stop_process_runtime(self) -> None:
        await self._process_launcher.stop()
        logging.info(f"Component '{self.id}' process runtime stopped")

    async def _start_virtualenv_runtime(self) -> None:
        from mindor.core.component.runtime.virtualenv import ComponentVirtualEnvRuntimeLauncher

        self._virtualenv_launcher = ComponentVirtualEnvRuntimeLauncher(self.id, self.config, self.global_configs)
        await self._virtualenv_launcher.start()
        logging.info(f"Component '{self.id}' started with virtualenv runtime")

    async def _stop_virtualenv_runtime(self) -> None:
        await self._virtualenv_launcher.stop()
        logging.info(f"Component '{self.id}' virtualenv runtime stopped")

    async def _start_docker_runtime(self) -> None:
        from mindor.core.component.runtime.docker import ComponentDockerRuntimeLauncher

        self._docker_launcher = ComponentDockerRuntimeLauncher(self.id, self.config, self.global_configs)
        await self._docker_launcher.start()
        logging.info(f"Component '{self.id}' started with Docker runtime")

    async def _stop_docker_runtime(self) -> None:
        await self._docker_launcher.stop()
        logging.info(f"Component '{self.id}' Docker runtime stopped")

    async def _start_apple_container_runtime(self) -> None:
        from mindor.core.component.runtime.apple_container import ComponentAppleContainerRuntimeLauncher

        self._apple_container_launcher = ComponentAppleContainerRuntimeLauncher(self.id, self.config, self.global_configs)
        await self._apple_container_launcher.start()
        logging.info(f"Component '{self.id}' started with Apple Container runtime")

    async def _stop_apple_container_runtime(self) -> None:
        await self._apple_container_launcher.stop()
        logging.info(f"Component '{self.id}' Apple Container runtime stopped")

def register_component(type: ComponentType):
    def decorator(cls: Type[ComponentService]) -> Type[ComponentService]:
        ComponentRegistry[type] = cls
        return cls
    return decorator

ComponentRegistry: Dict[ComponentType, Type[ComponentService]] = {}
