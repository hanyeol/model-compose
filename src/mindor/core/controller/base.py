from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.system import SystemConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.dsl.schema.runtime import RuntimeType
from mindor.dsl.schema.tracer import TracerConfig
from mindor.dsl.schema.logger import LoggerConfig, LoggerType, ConsoleLoggerConfig
from mindor.core.foundation import AsyncService
from mindor.core.controller.adapters import create_controller_adapter
from mindor.core.component import ComponentService, ComponentGlobalConfigs, create_component
from mindor.core.listener import ListenerService, create_listener
from mindor.core.gateway import GatewayService, create_gateway
from mindor.core.system import SystemService, create_system
from mindor.core.workflow import Workflow, WorkflowResolver, create_workflow
from mindor.core.workflow.interrupt import InterruptHandler, InterruptPoint
from mindor.core.workflow.schema import WorkflowSchema, create_workflow_schemas
from mindor.core.controller.webui import ControllerWebUI, create_webui
from mindor.core.tracer import TracerService, create_tracer
from mindor.core.logger import LoggerService, create_logger, logging
from mindor.core.controller.errors import TaskNotFoundError, TaskNotInterruptedError, JobIdMismatchError, InterruptNotActiveError
from mindor.core.errors import ShutdownError
from mindor.core.utils.work_queue import WorkQueue
from mindor.core.utils.caching import ExpiringDict
from mindor.core.utils.time import parse_duration
from .runtime.specs import ControllerRuntimeSpecs
from .runtime.native import NativeRuntimeLauncher
from .runtime.docker import DockerRuntimeLauncher
from .runtime.apple_container import AppleContainerRuntimeLauncher
from threading import Lock
from pathlib import Path
import asyncio, ulid, os, threading

if TYPE_CHECKING:
    from mindor.core.controller.adapters.base import ControllerAdapterService
    from mindor.core.controller.queue import ControllerQueueService

class TaskStatus(str, Enum):
    PENDING     = "pending"
    PROCESSING  = "processing"
    INTERRUPTED = "interrupted"
    COMPLETED   = "completed"
    FAILED      = "failed"

@dataclass
class InterruptState:
    job_id: str
    phase: Literal[ "before", "after" ]
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class TaskState:
    task_id: str
    status: TaskStatus
    workflow_id: Optional[str] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    interrupt: Optional[InterruptState] = None
    session_id: Optional[str] = None
    metadata: Optional[Any] = None

@dataclass
class JobEvent:
    task_id: str
    workflow_id: str
    job_id: str
    event: Literal[ "started", "completed", "failed", "routed" ]
    run_id: Optional[Union[str, List[str]]] = None
    elapsed: Optional[float] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    next_job_id: Optional[str] = None

@dataclass
class ComponentEvent:
    task_id: str
    workflow_id: str
    job_id: str
    component_id: str
    run_id: str
    event: Literal[ "started", "completed", "failed", "internal" ]
    kind: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    error: Optional[str] = None

TaskStateListener = Callable[[str, TaskState], Awaitable[None]]
JobEventListener = Callable[[JobEvent], Awaitable[None]]
ComponentEventListener = Callable[[ComponentEvent], Awaitable[None]]
TaskEventCallback = Callable[[Union[TaskState, JobEvent, ComponentEvent]], Awaitable[None]]

class ControllerService(AsyncService):
    _shared_instance: Optional[ControllerService] = None
    _shared_instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._shared_instance_lock:
            if cls._shared_instance is None:
                cls._shared_instance = super().__new__(cls)
        return cls._shared_instance

    @classmethod
    def get_shared_instance(cls) -> Optional[ControllerService]:
        return cls._shared_instance

    def __init__(
        self,
        config: ControllerConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig],
        systems: List[SystemConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        tracers: List[TracerConfig],
        loggers: List[LoggerConfig],
        daemon: bool
    ):
        super().__init__(daemon)

        self.config: ControllerConfig = config
        self.workflows: List[WorkflowConfig] = workflows
        self.components: List[ComponentConfig] = components
        self.listeners: List[ListenerConfig] = listeners
        self.gateways: List[GatewayConfig] = gateways
        self.systems: List[SystemConfig] = systems
        self.tracers: List[TracerConfig] = tracers
        self.loggers: List[LoggerConfig] = loggers
        self.workflow_schemas: Dict[str, WorkflowSchema] = create_workflow_schemas(self.workflows, self.components, exclude_private=True)
        self.task_queue: Optional[WorkQueue] = None
        self.task_states: ExpiringDict[TaskState] = ExpiringDict()
        self.task_states_lock: Lock = Lock()
        self.interrupt_handlers: Dict[str, InterruptHandler] = {}
        self.task_events: Dict[str, asyncio.Event] = {}
        self._queue: Optional[ControllerQueueService] = None
        self._inflight_tasks: Set[asyncio.Task] = set()
        self._shutting_down: bool = False
        self._task_state_listeners: List[TaskStateListener] = []
        self._job_event_listeners: List[JobEventListener] = []
        self._component_event_listeners: List[ComponentEventListener] = []
        self._task_event_callbacks: Dict[str, TaskEventCallback] = {}
        self._listener_tasks: Set[asyncio.Task] = set()

        if self.config.max_concurrent_count > 0:
            self.task_queue = WorkQueue(self.config.max_concurrent_count, self._run_workflow)

        if self.config.queue:
            from mindor.core.controller.queue import ControllerQueueService
            self._queue = ControllerQueueService(self.config.queue)

    async def launch_services(self, detach: bool, verbose: bool) -> None:
        if self.config.runtime.type == RuntimeType.NATIVE:
            if detach:
                await self._start_loggers(verbose)
                await NativeRuntimeLauncher().launch_detached()
                await self._stop_loggers()
                return

            await self._start_loggers(verbose)
            await self._setup_systems()
            await self._setup_listeners()
            await self._setup_gateways()
            await self._setup_components()
            await self.start()
            try:
                await self.wait_until_stopped()
            except (asyncio.CancelledError, KeyboardInterrupt):
                await self._stop()
            finally:
                await self._stop_loggers()
            return

        if self.config.runtime.type == RuntimeType.DOCKER:
            await self._start_loggers()
            await DockerRuntimeLauncher(self.config, verbose).launch(self._get_runtime_specs(), detach)
            await self._stop_loggers()
            return

        if self.config.runtime.type == RuntimeType.APPLE_CONTAINER:
            await self._start_loggers()
            await AppleContainerRuntimeLauncher(self.config, verbose).launch(self._get_runtime_specs(), detach)
            await self._stop_loggers()
            return

    async def terminate_services(self, verbose: bool) -> None:
        if self.config.runtime.type == RuntimeType.NATIVE:
            await self._start_loggers(verbose)
            await NativeRuntimeLauncher().stop()
            await self._teardown_components()
            await self._teardown_gateways()
            await self._teardown_listeners()
            await self._teardown_systems()
            await self._stop_loggers()
            return

        if self.config.runtime.type == RuntimeType.DOCKER:
            await self._start_loggers()
            await DockerRuntimeLauncher(self.config, verbose).terminate()
            await self._stop_loggers()
            return

        if self.config.runtime.type == RuntimeType.APPLE_CONTAINER:
            await self._start_loggers()
            await AppleContainerRuntimeLauncher(self.config, verbose).terminate()
            await self._stop_loggers()
            return

    async def start_services(self, verbose: bool) -> None:
        if self.config.runtime.type == RuntimeType.NATIVE:
            await self._start_loggers(verbose)
            await self.start()
            try:
                await self.wait_until_stopped()
            except (asyncio.CancelledError, KeyboardInterrupt):
                await self._stop()
            finally:
                await self._stop_loggers()
            return

        if self.config.runtime.type == RuntimeType.DOCKER:
            await self._start_loggers()
            await DockerRuntimeLauncher(self.config, verbose).start()
            await self._stop_loggers()
            return

        if self.config.runtime.type == RuntimeType.APPLE_CONTAINER:
            await self._start_loggers()
            await AppleContainerRuntimeLauncher(self.config, verbose).start()
            await self._stop_loggers()
            return

    async def stop_services(self, verbose: bool) -> None:
        if self.config.runtime.type == RuntimeType.NATIVE:
            await self._start_loggers(verbose)
            await NativeRuntimeLauncher().stop()
            await self._stop_loggers()
            return

        if self.config.runtime.type == RuntimeType.DOCKER:
            await self._start_loggers()
            await DockerRuntimeLauncher(self.config, verbose).stop()
            await self._stop_loggers()
            return

        if self.config.runtime.type == RuntimeType.APPLE_CONTAINER:
            await self._start_loggers()
            await AppleContainerRuntimeLauncher(self.config, verbose).stop()
            await self._stop_loggers()
            return

    async def run_workflow(
        self,
        workflow_id: str,
        input: Dict[str, Any],
        wait_for_completion: bool = True,
        on_interrupt: Optional[Callable[[InterruptState], Awaitable[Any]]] = None,
        on_event: Optional[TaskEventCallback] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Any] = None
    ) -> TaskState:
        if self._shutting_down:
            raise ShutdownError("Service is shutting down")

        task_id = ulid.ulid()
        state = TaskState(task_id=task_id, status=TaskStatus.PENDING, workflow_id=workflow_id, session_id=session_id, metadata=metadata)
        with self.task_states_lock:
            self.task_states.set(task_id, state)

        if on_event is not None:
            self._task_event_callbacks[task_id] = on_event

        try:
            if self.task_queue:
                future = await self.task_queue.schedule(task_id, workflow_id, input, None, session_id, metadata)
                task = asyncio.ensure_future(future)
            else:
                task = asyncio.create_task(self._run_workflow(task_id, workflow_id, input, on_interrupt, session_id, metadata))
        except Exception as e:
            self._task_event_callbacks.pop(task_id, None)
            state = TaskState(task_id=task_id, status=TaskStatus.FAILED, workflow_id=workflow_id, error=str(e), session_id=session_id, metadata=metadata)
            with self.task_states_lock:
                self.task_states.set(task_id, state, 1 * 3600)
            self._signal_task_state_change(task_id)
            self._notify_task_state_change(task_id)
            raise

        self._inflight_tasks.add(task)
        task.add_done_callback(self._inflight_tasks.discard)
        task.add_done_callback(lambda t: self._handle_task_failure(task_id, workflow_id, t))

        if on_event is not None:
            task.add_done_callback(lambda _: self._task_event_callbacks.pop(task_id, None))

        if wait_for_completion:
            state = await self._wait_for_terminal_state(task_id)

        return state

    async def resume_workflow(self, task_id: str, job_id: str, answer: Any = None) -> TaskState:
        with self.task_states_lock:
            state = self.task_states.get(task_id)

        if not state:
            raise TaskNotFoundError(f"Task not found: {task_id}")

        if state.status != TaskStatus.INTERRUPTED:
            raise TaskNotInterruptedError(f"Task '{task_id}' is not in interrupted state (current: {state.status})")

        if state.interrupt and state.interrupt.job_id != job_id:
            raise JobIdMismatchError(f"Job ID mismatch: expected '{state.interrupt.job_id}', got '{job_id}'")

        handler = self.interrupt_handlers.get(task_id)
        if not handler:
            raise InterruptNotActiveError(f"No active interrupt handler for task '{task_id}'")

        success = handler.resolve(task_id, job_id, answer)
        if not success:
            raise InterruptNotActiveError(f"No active interrupt found for task '{task_id}', job '{job_id}'")

        new_state = TaskState(task_id=task_id, status=TaskStatus.PROCESSING, workflow_id=state.workflow_id, session_id=state.session_id, metadata=state.metadata)
        with self.task_states_lock:
            self.task_states.set(task_id, new_state)
        self._signal_task_state_change(task_id)
        self._notify_task_state_change(task_id)

        return new_state

    async def wait_for_terminal_state(self, task_id: str) -> TaskState:
        return await self._wait_for_terminal_state(task_id)

    def add_task_state_listener(self, listener: TaskStateListener) -> None:
        if listener not in self._task_state_listeners:
            self._task_state_listeners.append(listener)

    def remove_task_state_listener(self, listener: TaskStateListener) -> None:
        try:
            self._task_state_listeners.remove(listener)
        except ValueError:
            pass

    def add_job_event_listener(self, listener: JobEventListener) -> None:
        if listener not in self._job_event_listeners:
            self._job_event_listeners.append(listener)

    def remove_job_event_listener(self, listener: JobEventListener) -> None:
        try:
            self._job_event_listeners.remove(listener)
        except ValueError:
            pass

    def add_component_event_listener(self, listener: ComponentEventListener) -> None:
        if listener not in self._component_event_listeners:
            self._component_event_listeners.append(listener)

    def remove_component_event_listener(self, listener: ComponentEventListener) -> None:
        try:
            self._component_event_listeners.remove(listener)
        except ValueError:
            pass

    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        with self.task_states_lock:
            return self.task_states.get(task_id)

    def is_workflow_available(self, workflow_id: str) -> bool:
        if workflow_id in self.workflow_schemas or self._queue:
            return True
        return False

    async def _start(self) -> None:
        if self.task_queue:
            await self.task_queue.start()

        if self._queue:
            await self._queue.start()

        await self._setup_tracers()
        await self._start_tracers()

        if self.daemon:
            await self._start_systems()
            await self._start_listeners()
            await self._start_gateways()
            await self._start_components()
            await self._start_adapters()

            if self.config.webui:
                await self._setup_webui()
                await self._start_webui()

            asyncio.create_task(self._watch_stop_request())

        await super()._start()

    async def _stop(self) -> None:
        self._shutting_down = True
        timeout = parse_duration(self.config.shutdown_timeout)

        if self._inflight_tasks:
            logging.info("Waiting for %d in-flight task(s) to complete...", len(self._inflight_tasks))
            done, pending = await asyncio.wait(self._inflight_tasks, timeout=timeout)
            if pending:
                logging.warning("Cancelling %d task(s) that did not complete within timeout", len(pending))
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

        if self.task_queue:
            await self.task_queue.stop(timeout=timeout)

        if self._queue:
            await self._queue.stop()

        await self._stop_tracers()

        if self.daemon:
            await self._stop_adapters()
            await self._cancel_pending_listener_tasks()
            await self._stop_components()
            await self._stop_gateways()
            await self._stop_listeners()
            await self._stop_systems()

            if self.config.webui:
                await self._stop_webui()

        await super()._stop()

    async def _serve(self) -> None:
        adapter_tasks = [ adapter.daemon_task for adapter in self._create_adapters() if adapter.daemon_task ]
        if adapter_tasks:
            await asyncio.gather(*adapter_tasks)

    async def _shutdown(self) -> None:
        for adapter in self._create_adapters():
            await adapter._shutdown()

    async def _watch_stop_request(self, interval: float = 1.0) -> None:
        stop_file = Path.cwd() / ".stop"

        while self.started:
            if stop_file.exists():
                await self.stop()
                break
            await asyncio.sleep(interval)

        os.unlink(stop_file)

    async def _setup_systems(self) -> None:
        await asyncio.gather(*[ system.setup() for system in self._create_systems() ])

    async def _teardown_systems(self) -> None:
        await asyncio.gather(*[ system.teardown() for system in self._create_systems() ])

    async def _start_systems(self) -> None:
        await asyncio.gather(*[ system.start() for system in self._create_systems() ])

    async def _stop_systems(self) -> None:
        await asyncio.gather(*[ system.stop() for system in self._create_systems() ])

    async def _setup_listeners(self) -> None:
        await asyncio.gather(*[ listener.setup() for listener in self._create_listeners() ])

    async def _teardown_listeners(self) -> None:
        await asyncio.gather(*[ listener.teardown() for listener in self._create_listeners() ])

    async def _start_listeners(self) -> None:
        await asyncio.gather(*[ listener.start() for listener in self._create_listeners() ])

    async def _stop_listeners(self) -> None:
        await asyncio.gather(*[ listener.stop() for listener in self._create_listeners() ])

    async def _setup_gateways(self) -> None:
        await asyncio.gather(*[ gateway.setup() for gateway in self._create_gateways() ])

    async def _teardown_gateways(self) -> None:
        await asyncio.gather(*[ gateway.teardown() for gateway in self._create_gateways() ])

    async def _start_gateways(self) -> None:
        await asyncio.gather(*[ gateway.start() for gateway in self._create_gateways() ])

    async def _stop_gateways(self) -> None:
        await asyncio.gather(*[ gateway.stop() for gateway in self._create_gateways() ])

    async def _setup_components(self) -> None:
        await asyncio.gather(*[ component.setup() for component in self._create_components() ])

    async def _teardown_components(self) -> None:
        await asyncio.gather(*[ component.teardown() for component in self._create_components() ])

    async def _start_components(self) -> None:
        await asyncio.gather(*[ component.start() for component in self._create_components() ])

    async def _stop_components(self) -> None:
        await asyncio.gather(*[ component.stop() for component in self._create_components() ])

    async def _start_loggers(self, verbose: bool = False) -> None:
        await asyncio.gather(*[ logger.start() for logger in self._create_loggers(verbose) ])

    async def _stop_loggers(self) -> None:
        await asyncio.gather(*[ logger.stop() for logger in self._create_loggers() ])

    async def _setup_tracers(self) -> None:
        await asyncio.gather(*[ tracer.setup() for tracer in self._create_tracers() ])

    async def _start_tracers(self) -> None:
        await asyncio.gather(*[ tracer.start() for tracer in self._create_tracers() ])

    async def _stop_tracers(self) -> None:
        await asyncio.gather(*[ tracer.stop() for tracer in self._create_tracers() ])

    async def _start_adapters(self) -> None:
        await asyncio.gather(*[ adapter.start() for adapter in self._create_adapters() ])

    async def _stop_adapters(self) -> None:
        await asyncio.gather(*[ adapter.stop() for adapter in self._create_adapters() ])

    async def _setup_webui(self) -> None:
        await asyncio.gather(*[ self._create_webui().setup() ])

    async def _start_webui(self) -> None:
        await asyncio.gather(*[ self._create_webui().start() ])

    async def _stop_webui(self) -> None:
        await asyncio.gather(*[ self._create_webui().stop() ])

    def _create_adapters(self) -> List[ControllerAdapterService]:
        return [ create_controller_adapter(config, self, self.daemon) for config in self.config.adapters ]

    def _create_listeners(self) -> List[ListenerService]:
        return [ create_listener(f"listener-{index}", config, self.daemon) for index, config in enumerate(self.listeners) ]

    def _create_gateways(self) -> List[GatewayService]:
        return [ create_gateway(f"gateway-{index}", config, self.daemon) for index, config in enumerate(self.gateways) ]

    def _create_systems(self) -> List[SystemService]:
        return [ create_system(config.id or f"system-{index}", config, self.daemon) for index, config in enumerate(self.systems) ]

    def _create_components(self) -> List[ComponentService]:
        global_configs = self._get_component_global_configs()
        return [ create_component(component.id or "__default__", component, global_configs, self.daemon) for component in self.components ]

    def _create_workflow(self, workflow_id: Optional[str]) -> Workflow:
        global_configs = self._get_component_global_configs()
        return create_workflow(*WorkflowResolver(self.workflows).resolve(workflow_id), global_configs)

    def _create_webui(self) -> ControllerWebUI:
        return create_webui(self.config.webui, self.components, self.workflows, self.daemon)

    def _create_tracers(self) -> List[TracerService]:
        return [ create_tracer(f"tracer-{index}", config, self.daemon) for index, config in enumerate(self.tracers) ]

    def _create_loggers(self, verbose: bool = False) -> List[LoggerService]:
        return [ create_logger(f"logger-{index}", config, self.daemon, verbose) for index, config in enumerate(self.loggers or [ self._get_default_logger_config() ]) ]

    def _get_runtime_specs(self) -> ControllerRuntimeSpecs:
        return ControllerRuntimeSpecs(self.config, self.components, self.listeners, self.gateways, self.workflows, self.tracers, self.loggers)

    def _get_component_global_configs(self) -> ComponentGlobalConfigs:
        return ComponentGlobalConfigs(self.components, self.listeners, self.gateways, self.workflows)

    def _get_default_logger_config(self) -> LoggerConfig:
        return ConsoleLoggerConfig(type=LoggerType.CONSOLE)

    async def _run_workflow(
        self,
        task_id: str,
        workflow_id: str,
        input: Dict[str, Any],
        on_interrupt: Optional[Callable[[InterruptState], Awaitable[Any]]] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Any] = None
    ) -> TaskState:
        state = TaskState(task_id=task_id, status=TaskStatus.PROCESSING, workflow_id=workflow_id, session_id=session_id, metadata=metadata)
        with self.task_states_lock:
            self.task_states.set(task_id, state)
        self._signal_task_state_change(task_id)
        self._notify_task_state_change(task_id)

        async def _on_job_event(payload: Dict[str, Any]) -> None:
            event = JobEvent(
                task_id=task_id,
                workflow_id=payload.get("workflow_id") or workflow_id,
                job_id=payload["job_id"],
                event=payload["event"],
                run_id=payload.get("run_id"),
                elapsed=payload.get("elapsed"),
                input=payload.get("input"),
                output=payload.get("output"),
                error=payload.get("error"),
                next_job_id=payload.get("next_job_id"),
            )
            self._notify_job_event(event)

        async def _on_component_event(payload: Dict[str, Any]) -> None:
            event = ComponentEvent(
                task_id=task_id,
                workflow_id=payload.get("workflow_id") or workflow_id,
                job_id=payload["job_id"],
                component_id=payload["component_id"],
                run_id=payload["run_id"],
                event=payload["event"],
                kind=payload.get("kind"),
                input=payload.get("input"),
                output=payload.get("output"),
                error=payload.get("error"),
            )
            self._notify_component_event(event)

        try:
            async def _run_workflow(workflow_id, input, interrupt_handler):
                if self._queue and not any(workflow.id == workflow_id for workflow in self.workflows):
                    return await self._queue.dispatch(task_id, workflow_id, input, interrupt_handler)

                return await self._create_workflow(workflow_id).run(
                    task_id,
                    input,
                    interrupt_handler,
                    _run_workflow,
                    session_id=session_id,
                    metadata=metadata,
                    on_job_event=_on_job_event,
                    on_component_event=_on_component_event
                )

            interrupt_handler = self._attach_interrupt_handler(task_id, workflow_id, on_interrupt, task_metadata=metadata)
            output = await _run_workflow(workflow_id, input, interrupt_handler)
            state = TaskState(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                workflow_id=workflow_id,
                output=output,
                session_id=session_id,
                metadata=metadata
            )
        except Exception as e:
            import traceback
            error_message = f"{str(e)}\n\nTraceback:\n{''.join(traceback.format_exception(type(e), e, e.__traceback__))}"
            state = TaskState(
                task_id=task_id,
                status=TaskStatus.FAILED,
                workflow_id=workflow_id,
                error=error_message,
                session_id=session_id,
                metadata=metadata
            )
        finally:
            self._detach_interrupt_handler(task_id)

        with self.task_states_lock:
            self.task_states.set(task_id, state, 1 * 3600)
        self._signal_task_state_change(task_id)
        self._notify_task_state_change(task_id)

        return state

    async def _wait_for_terminal_state(self, task_id: str) -> TaskState:
        if task_id not in self.task_events:
            self.task_events[task_id] = asyncio.Event()
        event = self.task_events[task_id]

        while True:
            state = self.get_task_state(task_id)
            if state and state.status in (TaskStatus.INTERRUPTED, TaskStatus.COMPLETED, TaskStatus.FAILED):
                self.task_events.pop(task_id, None)
                return state
            event.clear()
            state = self.get_task_state(task_id)
            if state and state.status in (TaskStatus.INTERRUPTED, TaskStatus.COMPLETED, TaskStatus.FAILED):
                self.task_events.pop(task_id, None)
                return state
            await event.wait()

    def _attach_interrupt_handler(
        self,
        task_id: str,
        workflow_id: str,
        on_interrupt: Optional[Callable[[InterruptState], Awaitable[Any]]] = None,
        task_metadata: Optional[Any] = None
    ) -> InterruptHandler:
        async def _callback(point: InterruptPoint):
            interrupt = InterruptState(
                job_id=point.job_id,
                phase=point.phase,
                message=point.message,
                metadata=point.metadata
            )
            session_id = self.get_task_state(task_id).session_id if self.get_task_state(task_id) else None
            state = TaskState(
                task_id=task_id,
                status=TaskStatus.INTERRUPTED,
                workflow_id=workflow_id,
                interrupt=interrupt,
                session_id=session_id,
                metadata=task_metadata
            )
            with self.task_states_lock:
                self.task_states.set(task_id, state)
            self._signal_task_state_change(task_id)
            self._notify_task_state_change(task_id)

            if on_interrupt:
                answer = await on_interrupt(interrupt)
                point.future.set_result(answer)

        handler = InterruptHandler(_callback)
        self.interrupt_handlers[task_id] = handler

        return handler

    def _detach_interrupt_handler(self, task_id: str) -> None:
        self.interrupt_handlers.pop(task_id, None)

    def _handle_task_failure(self, task_id: str, workflow_id: str, task: asyncio.Task) -> None:
        if task.cancelled() or task.exception() is None:
            return

        state = self.get_task_state(task_id)
        if state and state.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return

        state = TaskState(
            task_id=task_id,
            status=TaskStatus.FAILED,
            workflow_id=workflow_id,
            error=str(task.exception()),
            session_id=state.session_id if state else None,
            metadata=state.metadata if state else None
        )
        with self.task_states_lock:
            self.task_states.set(task_id, state, 1 * 3600)
        self._signal_task_state_change(task_id)
        self._notify_task_state_change(task_id)

    def _signal_task_state_change(self, task_id: str) -> None:
        event = self.task_events.get(task_id)
        if event:
            event.set()

    def _notify_task_state_change(self, task_id: str) -> None:
        state = self.get_task_state(task_id)
        if not state:
            return

        callback = self._task_event_callbacks.get(task_id)
        if callback:
            task = asyncio.create_task(self._invoke_event_callback(callback, state))
            self._listener_tasks.add(task)
            task.add_done_callback(self._listener_tasks.discard)

        for listener in self._task_state_listeners:
            task = asyncio.create_task(self._invoke_task_state_listener(listener, task_id, state))
            self._listener_tasks.add(task)
            task.add_done_callback(self._listener_tasks.discard)

    async def _invoke_task_state_listener(self, listener: TaskStateListener, task_id: str, state: TaskState) -> None:
        try:
            await listener(task_id, state)
        except Exception:
            logging.warning("Task state listener error for task %s", task_id, exc_info=True)

    def _notify_job_event(self, event: JobEvent) -> None:
        callback = self._task_event_callbacks.get(event.task_id)
        if callback:
            task = asyncio.create_task(self._invoke_event_callback(callback, event))
            self._listener_tasks.add(task)
            task.add_done_callback(self._listener_tasks.discard)

        for listener in self._job_event_listeners:
            task = asyncio.create_task(self._invoke_job_event_listener(listener, event))
            self._listener_tasks.add(task)
            task.add_done_callback(self._listener_tasks.discard)

    async def _invoke_job_event_listener(self, listener: JobEventListener, event: JobEvent) -> None:
        try:
            await listener(event)
        except Exception:
            logging.warning("Job event listener error for task %s job %s", event.task_id, event.job_id, exc_info=True)

    def _notify_component_event(self, event: ComponentEvent) -> None:
        callback = self._task_event_callbacks.get(event.task_id)
        if callback:
            task = asyncio.create_task(self._invoke_event_callback(callback, event))
            self._listener_tasks.add(task)
            task.add_done_callback(self._listener_tasks.discard)

        for listener in self._component_event_listeners:
            task = asyncio.create_task(self._invoke_component_event_listener(listener, event))
            self._listener_tasks.add(task)
            task.add_done_callback(self._listener_tasks.discard)

    async def _invoke_component_event_listener(self, listener: ComponentEventListener, event: ComponentEvent) -> None:
        try:
            await listener(event)
        except Exception:
            logging.warning("Component event listener error for task %s component %s", event.task_id, event.component_id, exc_info=True)

    async def _invoke_event_callback(self, callback: TaskEventCallback, event: Union[JobEvent, TaskState, ComponentEvent]) -> None:
        try:
            await callback(event)
        except Exception:
            logging.warning("Event callback error for task %s", event.task_id, exc_info=True)

    async def _cancel_pending_listener_tasks(self) -> None:
        for task in list(self._listener_tasks):
            task.cancel()
        if self._listener_tasks:
            await asyncio.gather(*self._listener_tasks, return_exceptions=True)
        self._listener_tasks.clear()
