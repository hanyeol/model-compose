from typing import Any
from mindor.dsl.schema.component import WorkflowComponentConfig
from mindor.dsl.schema.action import ActionConfig, WorkflowActionConfig
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext

class WorkflowAction:
    def __init__(self, config: WorkflowActionConfig):
        self.config: WorkflowActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input = await context.render_variable(self.config.input)
        output = await context.workflow.workflow_delegate(self.config.workflow, input, context.workflow.interrupt_handler)
        context.register_source("output", output)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else output

@register_component(ComponentType.WORKFLOW)
class WorkflowComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: WorkflowComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WorkflowAction(action).run(context)
