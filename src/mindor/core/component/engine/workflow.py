from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ComponentConfig, WorkflowComponentConfig
from mindor.dsl.schema.action import ActionConfig, WorkflowActionConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.workflow import Workflow, WorkflowResolver, create_workflow
from ..base import ComponentEngine, ComponentType, ActionConfig, register_component
from ..context import ComponentActionContext
import asyncio, os

class WorkflowAction:
    def __init__(self, config: WorkflowActionConfig):
        self.config: WorkflowActionConfig = config
        self.components: Dict[str, ComponentConfig] = None
        self.workflows: Dict[str, WorkflowConfig] = None

    async def run(self, context: ComponentActionContext) -> Any:
        workflow_id = await context.render_variable(self.config.workflow)
        input = await context.render_variable(self.config.input)

        workflow = self._create_workflow(workflow_id)
        output = await workflow.run(context.call_id, input)
        context.register_source("output", output)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else output

    def _create_workflow(self, workflow_id: Optional[str]) -> Workflow:
        return create_workflow(*WorkflowResolver(self.workflows).resolve(workflow_id), self.components)

@register_component(ComponentType.WORKFLOW)
class WorkflowComponent(ComponentEngine):
    def __init__(self, id: str, config: WorkflowComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WorkflowAction(action).run(context)
