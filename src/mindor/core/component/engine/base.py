from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod

from mindor.dsl.schema.component import ComponentConfig, ComponentType
from mindor.dsl.schema.action import ActionConfig
from mindor.core.services import AsyncService
from mindor.core.utils.workqueue import WorkQueue
from .context import ComponentActionContext

class ActionResolver:
    def __init__(self, actions: Dict[str, ActionConfig]):
        self.actions = actions

    def resolve(self, action_id: Optional[str]) -> Tuple[str, ActionConfig]:
        action_id = action_id or self._find_default_id(self.actions)

        if not action_id in self.actions:
            raise ValueError(f"Action not found: {action_id}")

        return action_id, self.actions[action_id]

    def _find_default_id(self, actions: Dict[str, ActionConfig]) -> str:
        default_ids = [ action_id for action_id, action in actions.items() if action.default ]

        if len(default_ids) > 1: 
            raise ValueError("Multiple actions have default: true")

        if not default_ids and "__default__" not in actions:
            raise ValueError("No default action defined.")

        return default_ids[0] if default_ids else "__default__"

class ComponentEngine(AsyncService):
    def __init__(self, id: str, config: ComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ComponentConfig = config
        self.queue: Optional[WorkQueue] = None

        if self.config.max_concurrent_count > 0:
            self.queue = WorkQueue(self.config.max_concurrent_count, self._run)

    async def run(self, action_id: Union[str, None], call_id: str, input: Dict[str, Any]) -> Dict[str, Any]:
        _, action = ActionResolver(self.config.actions).resolve(action_id)
        context = ComponentActionContext(call_id, input)

        if self.queue:
            return await (await self.queue.schedule(action, context))

        return await self._run(action, context)

    async def _start(self) -> None:
        if self.queue:
            await self.queue.start()

        await super()._start()

    async def _stop(self) -> None:
        if self.queue:
            await self.queue.stop()

        await super()._stop()

    @abstractmethod
    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        pass

ComponentEngineMap: Dict[ComponentType, Type[ComponentEngine]] = {}
