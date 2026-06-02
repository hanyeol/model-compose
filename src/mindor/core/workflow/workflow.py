from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Awaitable, Any
from types import GeneratorType
from mindor.dsl.schema.workflow import WorkflowConfig, JobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from mindor.core.tracer import tracing
from .context import WorkflowContext, WorkflowDelegate
from .interrupt import InterruptHandler
from .job import Job, RoutingTarget, create_job
import asyncio

JobEventCallback = Callable[[Dict[str, Any]], Awaitable[None]]
ComponentEventCallback = Callable[[Dict[str, Any]], Awaitable[None]]

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

class JobEventNotifier:
    def __init__(self, workflow_id: str, callback: Optional[JobEventCallback]):
        self.workflow_id: str = workflow_id
        self.callback: Optional[JobEventCallback] = callback

    async def notify(
        self,
        event: Literal[ "started", "completed", "failed", "routed" ],
        job_id: str,
        job_type: str,
        context: WorkflowContext,
        elapsed: Optional[float] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        error: Optional[str] = None,
        next_job_id: Optional[str] = None
    ) -> None:
        if self.callback:
            payload = self._build_payload(event, job_id, job_type, context, elapsed, input, output, error, next_job_id)
            try:
                await self.callback(payload)
            except Exception:
                logging.warning("on_job_event callback failed for job '%s'", job_id, exc_info=True)

    def _build_payload(
        self,
        event: Literal[ "started", "completed", "failed", "routed" ],
        job_id: str,
        job_type: str,
        context: WorkflowContext,
        elapsed: Optional[float],
        input: Optional[Any],
        output: Optional[Any],
        error: Optional[str],
        next_job_id: Optional[str]
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = { "event": event, "job_id": job_id, "job_type": job_type, "workflow_id": self.workflow_id }
        run_ids = context.job_run_ids.get(job_id)
        if run_ids:
            payload["run_id"] = run_ids[0] if len(run_ids) == 1 else list(run_ids)
        if elapsed is not None:
            payload["elapsed"] = elapsed
        if input is not None:
            payload["input"] = input
        if output is not None:
            payload["output"] = output
        if error is not None:
            payload["error"] = error
        if next_job_id is not None:
            payload["next_job_id"] = next_job_id
        return payload

class ComponentEventNotifier:
    def __init__(self, workflow_id: str, callback: Optional[ComponentEventCallback]):
        self.workflow_id: str = workflow_id
        self.callback: Optional[ComponentEventCallback] = callback

    async def notify(
        self,
        event: Literal[ "started", "completed", "failed", "internal" ],
        job_id: str,
        component_id: str,
        component_type: str,
        run_id: str,
        kind: Optional[str] = None,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        if self.callback:
            payload = self._build_payload(event, job_id, component_id, component_type, run_id, kind, input, output, error)
            try:
                await self.callback(payload)
            except Exception:
                logging.warning("on_component_event callback failed for component '%s' in job '%s'", component_id, job_id, exc_info=True)

    def _build_payload(
        self,
        event: Literal[ "started", "completed", "failed", "internal" ],
        job_id: str,
        component_id: str,
        component_type: str,
        run_id: str,
        kind: Optional[str],
        input: Optional[Any],
        output: Optional[Any],
        error: Optional[str],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "event": event,
            "workflow_id": self.workflow_id,
            "job_id": job_id,
            "component_id": component_id,
            "component_type": component_type,
            "run_id": run_id,
        }
        if kind is not None:
            payload["kind"] = kind
        if input is not None:
            payload["input"] = input
        if output is not None:
            payload["output"] = output
        if error is not None:
            payload["error"] = error
        return payload

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
                raise ValueError(f"Workflow not found: {workflow_id}")
            else:
                return None, None

        return workflow.id, workflow

class WorkflowRunner:
    def __init__(
        self,
        id: str,
        jobs: List[JobConfig],
        global_configs: ComponentGlobalConfigs,
    ):
        self.id: str = id
        self.jobs: Dict[str, JobConfig] = { job.id: job for job in jobs }
        self.global_configs: ComponentGlobalConfigs = global_configs

    async def run(self, context: WorkflowContext) -> Any:
        routing_job_ids: Set[str] = { job_id for job in self.jobs.values() for job_id in job.get_routing_jobs() }
        routing_jobs: Dict[str, Job] = { job_id: create_job(job_id, self.jobs[job_id], self.global_configs) for job_id in routing_job_ids }
        pending_jobs: Dict[str, Job] = { job_id: create_job(job_id, job, self.global_configs) for job_id, job in self.jobs.items() if job_id not in routing_job_ids }
        routable_job_ids: Set[str] = { job_id for job_id in self.jobs if self._is_routable_job(job_id, routing_job_ids) }
        running_job_ids: Set[str] = set()
        completed_job_ids: Set[str] = set()
        scheduled_job_tasks: Dict[str, asyncio.Task] = {}
        job_time_trackers: Dict[str, TimeTracker] = {}
        output: Any = None

        workflow_time_tracker = TimeTracker()
        logging.info("[task-%s] Workflow '%s' started.", context.task_id, self.id)

        while pending_jobs:
            runnable_jobs = [ job for job in pending_jobs.values() if self._can_run_job(job, running_job_ids, completed_job_ids, routable_job_ids) ]

            for job in runnable_jobs:
                if job.id not in scheduled_job_tasks:
                    context.job_run_ids[job.id] = []
                    scheduled_job_tasks[job.id] = asyncio.create_task(job.run(context))
                    running_job_ids.add(job.id)

                    job_time_trackers[job.id] = TimeTracker()
                    await context.job_event_notifier.notify("started", job.id, self.jobs[job.id].type.value, context=context, input=context.input)
                    tracing.on_job_start(context.task_id, job.id, self.id, context.input)
                    logging.info("[task-%s] Job '%s:%s' started.", context.task_id, job.id, self.id)
                    logging.debug("[task-%s] Job '%s:%s' input: %s", context.task_id, job.id, self.id, context.input)

            if not scheduled_job_tasks:
                raise RuntimeError("No runnable jobs but pending jobs remain.")

            completed_job_tasks, _ = await asyncio.wait(scheduled_job_tasks.values(), return_when=asyncio.FIRST_COMPLETED)

            for completed_job_task in completed_job_tasks:
                completed_job_id = next(job_id for job_id, job_task in scheduled_job_tasks.items() if job_task == completed_job_task)

                try:
                    completed_job_output = await completed_job_task
                except Exception as e:
                    elapsed = job_time_trackers[completed_job_id].elapsed()
                    await context.job_event_notifier.notify("failed", completed_job_id, self.jobs[completed_job_id].type.value, context=context, elapsed=elapsed, error=str(e))
                    raise

                if isinstance(completed_job_output, RoutingTarget):
                    next_job_id = completed_job_output.job_id
                    elapsed = job_time_trackers[completed_job_id].elapsed()

                    if next_job_id in routing_jobs:
                        await context.job_event_notifier.notify("routed", completed_job_id, self.jobs[completed_job_id].type.value, context=context, elapsed=elapsed, next_job_id=next_job_id)
                        logging.info("[task-%s] Routing to job '%s' from job '%s'.", context.task_id, next_job_id, completed_job_id)
                        pending_jobs[next_job_id] = routing_jobs.pop(next_job_id)
                        context.job_run_ids[next_job_id] = []
                        scheduled_job_tasks[next_job_id] = asyncio.create_task(pending_jobs[next_job_id].run(context))
                        running_job_ids.add(next_job_id)
                        job_time_trackers[next_job_id] = TimeTracker()
                        await context.job_event_notifier.notify("started", next_job_id, self.jobs[next_job_id].type.value, context=context, input=context.input)
                        tracing.on_job_start(context.task_id, next_job_id, self.id, context.input)
                    else:
                        context.complete_job(completed_job_id, completed_job_output)
                        await context.job_event_notifier.notify("completed", completed_job_id, self.jobs[completed_job_id].type.value, context=context, elapsed=elapsed, output=None)
                        logging.info("[task-%s] Job '%s:%s' completed without routing.", context.task_id, completed_job_id, self.id)
                else:
                    context.complete_job(completed_job_id, completed_job_output)
                    elapsed = job_time_trackers[completed_job_id].elapsed()
                    await context.job_event_notifier.notify("completed", completed_job_id, self.jobs[completed_job_id].type.value, context=context, elapsed=elapsed, output=completed_job_output)
                    tracing.on_job_end(context.task_id, completed_job_id, self.id, completed_job_output, elapsed)
                    logging.info("[task-%s] Job '%s:%s' completed in %.2f seconds.", context.task_id, completed_job_id, self.id, elapsed)
                    logging.debug("[task-%s] Job '%s:%s' output: %s", context.task_id, completed_job_id, self.id, completed_job_output)

                    if self._is_terminal_job(completed_job_id):
                        if isinstance(output, dict) and isinstance(completed_job_output, dict):
                            output.update(completed_job_output)
                        else:
                            output = completed_job_output

                running_job_ids.remove(completed_job_id)
                completed_job_ids.add(completed_job_id)
                del pending_jobs[completed_job_id]
                del scheduled_job_tasks[completed_job_id]

        if not isinstance(output, GeneratorType):
            logging.info("[task-%s] Workflow '%s' completed in %.2f seconds.", context.task_id, self.id, workflow_time_tracker.elapsed())

        return output

    def _can_run_job(
        self,
        job: Job,
        running_job_ids: Set[str],
        completed_job_ids: Set[str],
        routable_job_ids: Set[str]
    ) -> bool:
        if job.id in running_job_ids:
            return False
        
        if all(job_id in completed_job_ids for job_id in job.config.depends_on):
            return True

        completed = [ job_id for job_id in job.config.depends_on if job_id in completed_job_ids ]
        remaining = [ job_id for job_id in job.config.depends_on if job_id not in completed_job_ids ]

        return bool(completed) and all(job_id in routable_job_ids for job_id in remaining)
    
    def _is_terminal_job(self, job_id: str) -> bool:
        return all(job_id not in job.depends_on for other_id, job in self.jobs.items() if other_id != job_id)
    
    def _is_routable_job(self, job_id: str, routing_job_ids: Set[str]) -> bool:
        return job_id in routing_job_ids or any(self._is_routable_job(depend_job_id, routing_job_ids) for depend_job_id in self.jobs[job_id].depends_on)

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
        session_id: Optional[str] = None,
        metadata: Optional[Any] = None,
        on_job_event: Optional[JobEventCallback] = None,
        on_component_event: Optional[ComponentEventCallback] = None,
    ) -> Any:
        runner = WorkflowRunner(self.id, self.config.jobs, self.global_configs)
        context = WorkflowContext(
            task_id,
            self.id,
            input,
            interrupt_handler,
            workflow_delegate,
            JobEventNotifier(self.id, on_job_event),
            ComponentEventNotifier(self.id, on_component_event),
            session_id=session_id,
            metadata=metadata,
        )

        time_tracker = TimeTracker()
        tracing.on_workflow_start(task_id, self.id, input, session_id, metadata)

        try:
            output = await runner.run(context)
            tracing.on_workflow_end(task_id, self.id, output, time_tracker.elapsed())
            return output
        except Exception as e:
            tracing.on_workflow_error(task_id, self.id, e, time_tracker.elapsed())
            raise

    def validate(self) -> None:
        JobGraphValidator(self.config.jobs).validate()

def create_workflow(id: str, config: WorkflowConfig, global_configs: ComponentGlobalConfigs) -> Workflow:
    return Workflow(id, config, global_configs)
