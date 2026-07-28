from typing import Union, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.foundation.cancellation import CancellationToken
from .context import WorkflowContext, WorkflowDelegate
from .interrupt import InterruptHandler
from .notifiers import JobEventCallback, ComponentEventCallback, JobEventNotifier, ComponentEventNotifier
from .runner import WorkflowRunner
from .validator import WorkflowValidator

class WorkflowResolver:
    def __init__(self, workflows: List[WorkflowConfig]):
        self.workflows: List[WorkflowConfig] = workflows

    def resolve(self, workflow_id: str, raise_on_error: bool = True) -> Union[Tuple[str, WorkflowConfig], Tuple[None, None]]:
        if workflow_id == "__default__":
            workflow = self.workflows[0] if len(self.workflows) == 1 else None
            workflow = workflow or next((workflow for workflow in self.workflows if workflow.default), None)
        else:
            workflow = next((workflow for workflow in self.workflows if workflow.id == workflow_id), None)

        if workflow is None:
            if raise_on_error:
                raise LookupError(f"Workflow not found: {workflow_id}")
            else:
                return None, None

        return workflow.id, workflow

class Workflow:
    def __init__(self, id: str, config: WorkflowConfig, global_configs: ComponentGlobalConfigs):
        self.id: str = id
        self.config: WorkflowConfig = config
        self.global_configs: ComponentGlobalConfigs = global_configs

    async def run(
        self,
        task_id: str,
        input: Dict[str, Any],
        interrupt_handler: InterruptHandler,
        workflow_delegate: WorkflowDelegate = None,
        cancellation_token: Optional[CancellationToken] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Any] = None,
        on_job_event: Optional[JobEventCallback] = None,
        on_component_event: Optional[ComponentEventCallback] = None,
    ) -> Any:
        runner = WorkflowRunner(self.id, self.config.jobs, self.config.output, self.global_configs)
        context = WorkflowContext(
            task_id,
            self.id,
            input,
            interrupt_handler,
            workflow_delegate,
            JobEventNotifier(self.id, on_job_event),
            ComponentEventNotifier(self.id, on_component_event),
            cancellation_token=cancellation_token,
            session_id=session_id,
            metadata=metadata,
        )

        return await runner.run(context)

    def validate(self) -> List[str]:
        return WorkflowValidator(self.config, self.global_configs.components).validate()

def create_workflow(id: str, config: WorkflowConfig, global_configs: ComponentGlobalConfigs) -> Workflow:
    return Workflow(id, config, global_configs)
