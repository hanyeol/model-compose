from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ComponentConfig, ComponentType
from mindor.dsl.schema.action import ActionConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.services import AsyncService
from mindor.core.utils.workqueue import WorkQueue
from .context import ComponentActionContext

class ActionResolver:
    def __init__(self, actions: List[ActionConfig]):
        self.actions: List[ActionConfig] = actions

    def resolve(self, action_id: Optional[str]) -> Tuple[str, ActionConfig]:
        action_id = action_id or self._find_default_id(self.actions)
        action = next((action for action in self.actions if action.id == action_id), None)

        if action is None:
            raise ValueError(f"Action not found: {action_id}")

        return action_id, action

    def _find_default_id(self, actions: List[ActionConfig]) -> str:
        default_ids = [ action.id for action in actions if action.default or action.id == "__default__" ]

        if len(default_ids) > 1: 
            raise ValueError("Multiple actions have default: true")

        if not default_ids:
            raise ValueError("No default action defined.")

        return default_ids[0]

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
    def __init__(self, id: str, config: ComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ComponentConfig = config
        self.global_configs: ComponentGlobalConfigs = global_configs
        self.queue: Optional[WorkQueue] = None

        if self.config.max_concurrent_count > 0:
            self.queue = WorkQueue(self.config.max_concurrent_count, self._run)

    async def setup(self) -> None:
        await self._setup()

    async def teardown(self) -> None:
        await self._teardown()

    async def start(self, background: bool = False) -> None:
        await super().start(background)
        await self.wait_until_ready()

    async def run(self, action_id: Union[str, None], run_id: str, input: Dict[str, Any]) -> Dict[str, Any]:
        _, action = ActionResolver(self.config.actions).resolve(action_id)
        context = ComponentActionContext(run_id, input)

        if self.queue:
            return await (await self.queue.schedule(action, context))

        return await self._run(action, context)

    async def _setup(self) -> None:
        pass

    async def _teardown(self) -> None:
        pass

    async def _start(self) -> None:
        if self.queue:
            await self.queue.start()

        await super()._start()

    async def _stop(self) -> None:
        if self.queue:
            await self.queue.stop()

        await super()._stop()

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _is_ready(self) -> bool:
        return True

    @abstractmethod
    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_component(type: ComponentType):
    def decorator(cls: Type[ComponentService]) -> Type[ComponentService]:
        ComponentRegistry[type] = cls
        return cls
    return decorator

ComponentRegistry: Dict[ComponentType, Type[ComponentService]] = {}
