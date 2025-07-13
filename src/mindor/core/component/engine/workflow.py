from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ComponentConfig, WorkflowComponentConfig
from mindor.dsl.schema.action import ActionConfig, WorkflowActionConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from .base import ComponentEngine, ComponentType, ComponentEngineMap, ActionConfig
from .context import ComponentActionContext
import asyncio, os

class WorkflowAction:
    def __init__(self, config: WorkflowActionConfig):
        self.config: WorkflowActionConfig = config
        self.components: Dict[str, ComponentConfig] = None
        self.workflows: Dict[str, WorkflowConfig] = None

    async def run(self, context: ComponentActionContext) -> Any:
        pass

class WorkflowComponent(ComponentEngine):
    def __init__(self, id: str, config: WorkflowComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WorkflowAction(action).run(context)

ComponentEngineMap[ComponentType.WORKFLOW] = WorkflowComponent
