from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.workflow import WorkflowConfig, JobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentEngine, ComponentResolver, create_component
from .context import WorkflowContext
from .job import Job, create_job
import asyncio

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
                    raise  ValueError(f"Job '{job_id}' cannot depend on itself.")
                
                if dependency_id not in self.jobs:
                    raise ValueError(f"Job '{job_id}' references a non-existent job '{dependency_id}' in its depends_on list.")

    def _validate_has_entry_jobs(self) -> None:
        entry_job_ids = [ job_id for job_id, job in self.jobs.items() if not job.depends_on ]

        if not entry_job_ids:
            raise ValueError("At least one job without any depends_on is required.")

    def _validate_has_no_cycles(self) -> None:
        visiting, visited = set(), set()

        def _assert_no_cycle(job_id: str):
            if job_id in visiting:
                raise ValueError(f"Job '{job_id}' is part of a dependency cycle.")
            
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
    def __init__(self, workflows: Dict[str, WorkflowConfig]):
        self.workflows: Dict[str, WorkflowConfig] = workflows

    def resolve(self, workflow_id: Optional[str]) -> Tuple[str, WorkflowConfig]:
        workflow_id = workflow_id or self._find_default_id(self.workflows)

        if not workflow_id in self.workflows:
            raise ValueError(f"Workflow not found: {workflow_id}")

        return workflow_id, self.workflows[workflow_id]

    def _find_default_id(self, workflows: Dict[str, WorkflowConfig]) -> str:
        default_ids = [ workflow_id for workflow_id, workflow in workflows.items() if workflow.default ]

        if len(default_ids) > 1:
            raise ValueError("Multiple workflows have default: true")

        if not default_ids and "__default__" not in workflows:
            raise ValueError("No default workflow defined.")

        return default_ids[0] if default_ids else "__default__"

class WorkflowRunner:
    def __init__(self, jobs: Dict[str, JobConfig], components: Dict[str, ComponentConfig]):
        self.jobs: Dict[str, JobConfig] = jobs
        self.components: Dict[str, ComponentConfig] = components

    async def run(self, context: WorkflowContext) -> Any:
        pending_jobs: Dict[str, Job] = { job_id: create_job(job_id, job, self.components) for job_id, job in self.jobs.items() }
        running_job_ids: Set[str] = set()
        completed_job_ids: Set[str] = set()
        scheduled_job_tasks: Dict[str, asyncio.Task] = {}
        output: Any = None

        while pending_jobs:
            runnable_jobs = [ job for job in pending_jobs.values() if self._can_run_job(job, running_job_ids, completed_job_ids) ]

            for job in runnable_jobs:
                if job.id not in scheduled_job_tasks:
                    scheduled_job_tasks[job.id] = asyncio.create_task(job.run(context))
                    running_job_ids.add(job.id)

            if not scheduled_job_tasks:
                raise RuntimeError("No runnable jobs but pending jobs remain.")

            completed_job_tasks, _ = await asyncio.wait(scheduled_job_tasks.values(), return_when=asyncio.FIRST_COMPLETED)

            for completed_job_task in completed_job_tasks:
                completed_job_id = next(job_id for job_id, job_task in scheduled_job_tasks.items() if job_task == completed_job_task)

                completed_job_output = await completed_job_task
                context.complete_job(completed_job_id, completed_job_output)

                if self._is_terminal_job(completed_job_id):
                    if isinstance(output, dict) and isinstance(completed_job_output, dict):
                        output.update(completed_job_output)
                    else:
                        output = completed_job_output

                running_job_ids.remove(completed_job_id)
                completed_job_ids.add(completed_job_id)
                del pending_jobs[completed_job_id]
                del scheduled_job_tasks[completed_job_id]

        return output

    def _can_run_job(self, job: Job, running_job_ids: Set[str], completed_job_ids: Set[str]) -> bool:
        return job.id not in running_job_ids and all(job_id in completed_job_ids for job_id in job.config.depends_on)
    
    def _is_terminal_job(self, job_id: str) -> bool:
        return all(job_id not in job.depends_on for other_id, job in self.jobs.items() if other_id != job_id)

class Workflow:
    def __init__(self, id: str, config: WorkflowConfig, components: Dict[str, ComponentConfig]):
        self.id: str = id
        self.config: WorkflowConfig = config
        self.components: Dict[str, ComponentConfig] = components

    async def run(self, task_id: str, input: Dict[str, Any]) -> Any:
        context = WorkflowContext(task_id, input)
        runner = WorkflowRunner(self.config.jobs, self.components)

        return await runner.run(context)

    def validate(self) -> None:
        JobGraphValidator(self.config.jobs).validate()

def create_workflow(id: str, config: WorkflowConfig, components: Dict[str, ComponentConfig]) -> Workflow:
    return Workflow(id, config, components)
