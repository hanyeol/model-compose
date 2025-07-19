from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from dataclasses import dataclass
from mindor.dsl.schema.controller import ControllerConfig, ControllerType
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.logger import LoggerConfig, LoggerType, ConsoleLoggerConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.services import AsyncService
from mindor.core.component import ComponentService, ComponentGlobalConfigs, create_component
from mindor.core.listener import ListenerService, create_listener
from mindor.core.gateway import GatewayService, create_gateway
from mindor.core.workflow import Workflow, WorkflowResolver, create_workflow
from mindor.core.logger import LoggerService, create_logger
from mindor.core.controller.webui import ControllerWebUI
from mindor.core.utils.workqueue import WorkQueue
from mindor.core.utils.expiring import ExpiringDict
from threading import Lock
import asyncio, ulid

class TaskStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed" 

@dataclass
class TaskState:
    task_id: str
    status: TaskStatus
    output: Optional[Any] = None
    error: Optional[Any] = None

class ControllerService(AsyncService):
    def __init__(
        self,
        config: ControllerConfig,
        workflows: Dict[str, WorkflowConfig],
        components: Dict[str, ComponentConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        loggers: List[LoggerConfig],
        daemon: bool
    ):
        super().__init__(daemon)

        self.config: ControllerConfig = config
        self.workflows: Dict[str, WorkflowConfig] = workflows
        self.components: Dict[str, ComponentConfig] = components
        self.listeners: List[ListenerConfig] = listeners
        self.gateways: List[GatewayConfig] = gateways
        self.loggers: List[LoggerConfig] = loggers
        self.queue: Optional[WorkQueue] = None
        self.task_states: ExpiringDict[TaskState] = ExpiringDict()
        self.task_states_lock: Lock = Lock()
        
        if self.config.max_concurrent_count > 0:
            self.queue = WorkQueue(self.config.max_concurrent_count, self._run_workflow)

    async def run_workflow(self, workflow_id: Optional[str], input: Dict[str, Any], wait_for_completion: bool = True) -> TaskState:
        task_id = ulid.ulid()
        state = TaskState(task_id=task_id, status=TaskStatus.PENDING)
        with self.task_states_lock:
            self.task_states.set(task_id, state)

        if wait_for_completion:
            if self.queue:
                state = await (await self.queue.schedule(task_id, workflow_id, input))
            else:
                state = await self._run_workflow(task_id, workflow_id, input)
        else:
            asyncio.create_task(self._run_workflow(task_id, workflow_id, input))

        return state

    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        with self.task_states_lock:
            return self.task_states.get(task_id)

    async def _start(self) -> None:
        if self.queue:
            await self.queue.start()

        if self.daemon:
            await self._start_loggers()
            await self._start_gateways()
            await self._start_listeners()
            await self._start_components()

            if self.config.webui:
                await self._start_webui()

        await super()._start()

    async def _stop(self) -> None:
        if self.queue:
            await self.queue.stop()

        if self.daemon:
            await self._stop_components()
            await self._stop_listeners()
            await self._stop_gateways()
            await self._stop_loggers()

            if self.config.webui:
                await self._stop_webui()

        await super()._stop()

    async def _start_listeners(self) -> None:
        await asyncio.gather(*[ listener.start() for listener in self._create_listeners() ])

    async def _stop_listeners(self) -> None:
        await asyncio.gather(*[ listener.stop() for listener in self._create_listeners() ])

    async def _start_gateways(self) -> None:
        await asyncio.gather(*[ gateway.start() for gateway in self._create_gateways() ])

    async def _stop_gateways(self) -> None:
        await asyncio.gather(*[ gateway.stop() for gateway in self._create_gateways() ])

    async def _start_components(self) -> None:
        await asyncio.gather(*[ component.start() for component in self._create_components() ])

    async def _stop_components(self) -> None:
        await asyncio.gather(*[ component.stop() for component in self._create_components() ])

    async def _start_loggers(self) -> None:
        await asyncio.gather(*[ logger.start() for logger in self._create_loggers() ])

    async def _stop_loggers(self) -> None:
        await asyncio.gather(*[ logger.stop() for logger in self._create_loggers() ])

    async def _start_webui(self) -> None:
        await asyncio.gather(*[ self._create_webui().start() ])

    async def _stop_webui(self) -> None:
        await asyncio.gather(*[ self._create_webui().stop() ])

    async def _run_workflow(self, task_id: str, workflow_id: Optional[str], input: Dict[str, Any]) -> TaskState:
        state = TaskState(task_id=task_id, status=TaskStatus.PROCESSING)
        with self.task_states_lock:
            self.task_states.set(task_id, state)
        
        try:
            workflow = self._create_workflow(workflow_id)
            output = await workflow.run(task_id, input)
            state = TaskState(task_id=task_id, status=TaskStatus.COMPLETED, output=output)
        except Exception as e:
            state = TaskState(task_id=task_id, status=TaskStatus.FAILED, error=str(e))

        with self.task_states_lock:
            self.task_states.set(task_id, state, 1 * 3600)

        return state

    def _create_listeners(self) -> List[ListenerService]:
        return [ create_listener(f"listener-{index}", config, self.daemon) for index, config in enumerate(self.listeners) ]
    
    def _create_gateways(self) -> List[GatewayService]:
        return [ create_gateway(f"gateway-{index}", config, self.daemon) for index, config in enumerate(self.gateways) ]

    def _create_components(self) -> List[ComponentService]:
        global_configs = self._get_component_global_configs()
        return [ create_component(component_id, config, global_configs, self.daemon) for component_id, config in self.components.items() ]
    
    def _create_loggers(self) -> List[LoggerService]:
        return [ create_logger(f"logger-{index}", config, self.daemon) for index, config in enumerate(self.loggers or [ self._get_default_logger_config() ]) ]

    def _create_webui(self) -> ControllerWebUI:
        return ControllerWebUI(self.config.webui, self.config, self.components, self.workflows, self.daemon)

    def _create_workflow(self, workflow_id: Optional[str]) -> Workflow:
        global_configs = self._get_component_global_configs()
        return create_workflow(*WorkflowResolver(self.workflows).resolve(workflow_id), global_configs)

    def _get_component_global_configs(self) -> ComponentGlobalConfigs:
        return ComponentGlobalConfigs(self.components, self.listeners, self.gateways, self.workflows)

    def _get_default_logger_config(self) -> LoggerConfig:
        return ConsoleLoggerConfig(type=LoggerType.CONSOLE)

def register_controller(type: ControllerType):
    def decorator(cls: Type[ControllerService]) -> Type[ControllerService]:
        ControllerRegistry[type] = cls
        return cls
    return decorator

ControllerRegistry: Dict[ControllerType, Type[ControllerService]] = {}
