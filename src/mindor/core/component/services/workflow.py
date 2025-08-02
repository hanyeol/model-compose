from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ComponentConfig, WorkflowComponentConfig
from mindor.dsl.schema.action import ActionConfig, WorkflowActionConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.workflow import Workflow, WorkflowResolver, create_workflow
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext

class WorkflowAction:
    def __init__(self, config: WorkflowActionConfig, global_configs: ComponentGlobalConfigs):
        self.config: WorkflowActionConfig = config
        self.global_configs: ComponentGlobalConfigs = global_configs

    async def run(self, context: ComponentActionContext) -> Any:
        workflow_id = await context.render_variable(self.config.workflow)
        input = await context.render_variable(self.config.input)

        workflow = self._create_workflow(workflow_id)
        output = await workflow.run(context.run_id, input)
        context.register_source("output", output)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else output

    def _create_workflow(self, workflow_id: Optional[str]) -> Workflow:
        return create_workflow(*WorkflowResolver(self.global_configs.workflows).resolve(workflow_id), self.global_configs)

@register_component(ComponentType.WORKFLOW)
class WorkflowComponent(ComponentService):
    def __init__(self, id: str, config: WorkflowComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WorkflowAction(action, self.global_configs).run(context)
