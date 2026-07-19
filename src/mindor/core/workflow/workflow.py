from typing import Union, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.workflow import WorkflowConfig, JobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.foundation.cancellation import CancellationToken
from .context import WorkflowContext, WorkflowDelegate
from .interrupt import InterruptHandler
from .notifiers import JobEventCallback, ComponentEventCallback, JobEventNotifier, ComponentEventNotifier
from .runner import WorkflowRunner

class JobGraphValidator:
    def __init__(self, jobs: Dict[str, JobConfig]):
        self.jobs: Dict[str, JobConfig] = jobs

    def validate(self) -> None:
        self._validate_dependency_references()
        self._validate_has_entry_jobs()
        self._validate_has_no_cycles()

    def _validate_dependency_references(self) -> None:
        for job_id, job in self.jobs.items():
            for dependency_id in job.depends_on:
                if dependency_id == job_id:
                    raise  ValueError(f"Job '{job_id}' cannot depend on itself")
                
                if dependency_id not in self.jobs:
                    raise ValueError(f"Job '{job_id}' references a non-existent job '{dependency_id}' in its depends_on list")

    def _validate_has_entry_jobs(self) -> None:
        entry_job_ids = [ job_id for job_id, job in self.jobs.items() if not job.depends_on ]

        if not entry_job_ids:
            raise ValueError("At least one job without any depends_on is required")

    def _validate_has_no_cycles(self) -> None:
        visiting, visited = set(), set()

        def _assert_no_cycle(job_id: str):
            if job_id in visiting:
                raise ValueError(f"Job '{job_id}' is part of a dependency cycle")
            
            if job_id not in visited:
                visiting.add(job_id)

                for dependency_id in self.jobs[job_id].depends_on:
                    _assert_no_cycle(dependency_id)

                visiting.remove(job_id)
                visited.add(job_id)
        
        for job_id in self.jobs:
            if job_id not in visited:
                _assert_no_cycle(job_id)

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

    def validate(self) -> None:
        JobGraphValidator(self.config.jobs).validate()

def create_workflow(id: str, config: WorkflowConfig, global_configs: ComponentGlobalConfigs) -> Workflow:
    return Workflow(id, config, global_configs)
