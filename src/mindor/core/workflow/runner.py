from typing import Optional, Dict, List, Set, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.workflow import JobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from mindor.core.tracer import tracing
from .context import WorkflowContext
from .job import Job, RoutingTarget, create_job
from .job.streaming import JobOutputStreamIterator, StreamTerminatedEvent
from .job.context import JobContext
import asyncio

class WorkflowRunner:
    def __init__(
        self,
        id: str,
        jobs: List[JobConfig],
        output: Optional[Any],
        global_configs: ComponentGlobalConfigs,
    ):
        self.id: str = id
        self.jobs: Dict[str, JobConfig] = { job.id: job for job in jobs }
        self.output: Optional[Any] = output
        self.global_configs: ComponentGlobalConfigs = global_configs

    async def run(self, context: WorkflowContext) -> Any:
        routing_job_ids: Set[str] = { job_id for job in self.jobs.values() for job_id in job.get_routing_jobs() }
        routing_jobs: Dict[str, Job] = { job_id: create_job(job_id, self.jobs[job_id], self.global_configs) for job_id in routing_job_ids }
        pending_jobs: Dict[str, Job] = { job_id: create_job(job_id, job, self.global_configs) for job_id, job in self.jobs.items() if job_id not in routing_job_ids }
        routable_job_ids: Set[str] = { job_id for job_id in self.jobs if self._is_routable_job(job_id, routing_job_ids) }

        workflow_time_tracker = TimeTracker()
        tracing.on_workflow_start(context.task_id, self.id, context.input, context.context.get("session_id"), context.context.get("metadata"))
        logging.info("[task-%s] Workflow '%s' started.", context.task_id, self.id)

        try:
            output = await self._run_jobs(context, pending_jobs, routing_jobs, routable_job_ids)

            if self.output is not None:
                output = await context.render_variable(self.output)

            if isinstance(output, (StreamIterator, AsyncIterator)):
                async def _on_terminated(event: StreamTerminatedEvent, error: Optional[str]) -> None:
                    elapsed = workflow_time_tracker.elapsed()
                    if event == "completed":
                        tracing.on_workflow_end(context.task_id, self.id, None, elapsed)
                        logging.info("[task-%s] Workflow '%s' completed in %.2f seconds.", context.task_id, self.id, elapsed)
                    elif event == "cancelled":
                        logging.info("[task-%s] Workflow '%s' cancelled after %.2f seconds.", context.task_id, self.id, elapsed)
                    else:
                        tracing.on_workflow_error(context.task_id, self.id, error, elapsed)
                        logging.error("[task-%s] Workflow '%s' failed after %.2f seconds: %s", context.task_id, self.id, elapsed, error)

                output = JobOutputStreamIterator(output, _on_terminated)
            else:
                elapsed = workflow_time_tracker.elapsed()
                tracing.on_workflow_end(context.task_id, self.id, output, elapsed)
                logging.info("[task-%s] Workflow '%s' completed in %.2f seconds.", context.task_id, self.id, elapsed)

            return output
        except asyncio.CancelledError:
            elapsed = workflow_time_tracker.elapsed()
            logging.info("[task-%s] Workflow '%s' cancelled after %.2f seconds.", context.task_id, self.id, elapsed)
            raise
        except Exception as e:
            elapsed = workflow_time_tracker.elapsed()
            tracing.on_workflow_error(context.task_id, self.id, e, elapsed)
            logging.error("[task-%s] Workflow '%s' failed after %.2f seconds: %s", context.task_id, self.id, elapsed, e, exc_info=True)
            raise

    async def _run_jobs(
        self,
        context: WorkflowContext,
        pending_jobs: Dict[str, Job],
        routing_jobs: Dict[str, Job],
        routable_job_ids: Set[str],
    ) -> Any:
        running_job_ids: Set[str] = set()
        completed_job_ids: Set[str] = set()
        scheduled_job_tasks: Dict[str, asyncio.Task] = {}
        job_time_trackers: Dict[str, TimeTracker] = {}
        job_run_counts: Dict[str, int] = {}
        output: Any = None

        while pending_jobs:
            runnable_jobs = [ job for job in pending_jobs.values() if self._is_runnable_job(job, running_job_ids, completed_job_ids, routable_job_ids) ]

            for job in runnable_jobs:
                if job.id not in scheduled_job_tasks:
                    job_time_trackers[job.id] = TimeTracker()
                    context.job_run_ids[job.id] = []
                    try:
                        scheduled_job_tasks[job.id] = self._schedule_job(job, context, job_run_counts)
                    except Exception as e:
                        await context.job_event_notifier.notify(
                            "failed",
                            job.id,
                            self.jobs[job.id].type.value,
                            context=context,
                            error=str(e)
                        )
                        raise

                    running_job_ids.add(job.id)

            if not scheduled_job_tasks:
                raise RuntimeError("No runnable jobs but pending jobs remain.")

            try:
                completed_job_tasks, _ = await asyncio.wait(scheduled_job_tasks.values(), return_when=asyncio.FIRST_COMPLETED)
            except asyncio.CancelledError:
                for job_id, job_task in scheduled_job_tasks.items():
                    if not job_task.done():
                        job_task.cancel()
                await asyncio.gather(*scheduled_job_tasks.values(), return_exceptions=True)
                for job_id in scheduled_job_tasks:
                    job_elapsed = job_time_trackers[job_id].elapsed()
                    await context.job_event_notifier.notify(
                        "cancelled",
                        job_id,
                        self.jobs[job_id].type.value,
                        context=context,
                        elapsed=job_elapsed,
                    )
                    logging.info("[task-%s] Job '%s:%s' cancelled after %.2f seconds.", context.task_id, job_id, self.id, job_elapsed)
                raise

            for completed_job_task in completed_job_tasks:
                completed_job_id = next(job_id for job_id, job_task in scheduled_job_tasks.items() if job_task == completed_job_task)
                is_job_completed = True

                try:
                    completed_job_output = await completed_job_task
                except Exception as e:
                    job_elapsed = job_time_trackers[completed_job_id].elapsed()
                    await context.job_event_notifier.notify(
                        "failed",
                        completed_job_id,
                        self.jobs[completed_job_id].type.value,
                        context=context,
                        elapsed=job_elapsed,
                        error=str(e)
                    )
                    raise

                if isinstance(completed_job_output, RoutingTarget):
                    next_job_id = completed_job_output.job_id
                    job_elapsed = job_time_trackers[completed_job_id].elapsed()

                    if next_job_id in completed_job_ids:
                        rewind_job_ids = self._get_dependent_job_ids(next_job_id, completed_job_ids | { completed_job_id })
                        for rewind_job_id in rewind_job_ids:
                            completed_job_ids.discard(rewind_job_id)
                            context.sources["jobs"].pop(rewind_job_id, None)
                            pending_jobs[rewind_job_id] = create_job(rewind_job_id, self.jobs[rewind_job_id], self.global_configs)
                        if completed_job_id in rewind_job_ids:
                            is_job_completed = False

                    if next_job_id in routing_jobs:
                        await context.job_event_notifier.notify(
                            "routed",
                            completed_job_id,
                            self.jobs[completed_job_id].type.value,
                            context=context,
                            elapsed=job_elapsed,
                            next_job_id=next_job_id
                        )
                        logging.info("[task-%s] Routing to job '%s' from job '%s'.", context.task_id, next_job_id, completed_job_id)

                        pending_jobs[next_job_id] = routing_jobs.pop(next_job_id)

                        job_time_trackers[next_job_id] = TimeTracker()
                        context.job_run_ids[next_job_id] = []
                        try:
                            next_job = pending_jobs[next_job_id]
                            scheduled_job_tasks[next_job_id] = self._schedule_job(next_job, context, job_run_counts)
                        except Exception as e:
                            await context.job_event_notifier.notify(
                                "failed",
                                next_job_id,
                                self.jobs[next_job_id].type.value,
                                context=context,
                                error=str(e)
                            )
                            raise
                        running_job_ids.add(next_job_id)
                    else:
                        context.complete_job(completed_job_id, completed_job_output)
                        await context.job_event_notifier.notify(
                            "completed",
                            completed_job_id,
                            self.jobs[completed_job_id].type.value,
                            context=context,
                            elapsed=job_elapsed,
                            output=None
                        )
                        logging.info("[task-%s] Job '%s:%s' completed without routing.", context.task_id, completed_job_id, self.id)
                else:
                    if isinstance(completed_job_output, (StreamIterator, AsyncIterator)):
                        job_time_tracker = job_time_trackers[completed_job_id]
                        job_id = completed_job_id
                        job_type = self.jobs[completed_job_id].type.value

                        async def _on_terminated(event: StreamTerminatedEvent, error: Optional[str], job_id=job_id, job_type=job_type, job_time_tracker=job_time_tracker) -> None:
                            job_elapsed = job_time_tracker.elapsed()
                            await context.job_event_notifier.notify(
                                event,
                                job_id,
                                job_type,
                                context=context,
                                elapsed=job_elapsed,
                                error=error
                            )
                            if event == "completed":
                                tracing.on_job_end(context.task_id, job_id, self.id, None, job_elapsed)
                                logging.info("[task-%s] Job '%s:%s' completed in %.2f seconds.", context.task_id, job_id, self.id, job_elapsed)
                            else:
                                logging.info("[task-%s] Job '%s:%s' %s after %.2f seconds.", context.task_id, job_id, self.id, event, job_elapsed)

                        completed_job_output = JobOutputStreamIterator(completed_job_output, _on_terminated)

                    context.complete_job(completed_job_id, completed_job_output)

                    if not isinstance(completed_job_output, JobOutputStreamIterator):
                        job_elapsed = job_time_trackers[completed_job_id].elapsed()
                        await context.job_event_notifier.notify(
                            "completed",
                            completed_job_id,
                            self.jobs[completed_job_id].type.value,
                            context=context,
                            elapsed=job_elapsed,
                            output=completed_job_output
                        )
                        tracing.on_job_end(context.task_id, completed_job_id, self.id, completed_job_output, job_elapsed)
                        logging.info("[task-%s] Job '%s:%s' completed in %.2f seconds.", context.task_id, completed_job_id, self.id, job_elapsed)
                        logging.debug("[task-%s] Job '%s:%s' output: %s", context.task_id, completed_job_id, self.id, completed_job_output)

                    if self._is_terminal_job(completed_job_id):
                        if isinstance(output, dict) and isinstance(completed_job_output, dict):
                            output.update(completed_job_output)
                        else:
                            output = completed_job_output

                running_job_ids.remove(completed_job_id)
                del scheduled_job_tasks[completed_job_id]

                if is_job_completed:
                    completed_job_ids.add(completed_job_id)
                    del pending_jobs[completed_job_id]

        return output

    def _schedule_job(
        self,
        job: Job,
        context: WorkflowContext,
        counts: Dict[str, int],
    ) -> asyncio.Task:
        """Enforce max_run_count and create the asyncio.Task running `job`.

        Mutates `counts[job.id]` and raises RuntimeError if the limit is exceeded.
        Kept as a discrete method so both scheduling sites in `_run_jobs`
        (initial dispatch + routing rewind) share one source of truth.
        """
        counts[job.id] = counts.get(job.id, 0) + 1
        if counts[job.id] > job.config.max_run_count:
            raise RuntimeError(f"Job '{job.id}' has reached its max_run_count ({job.config.max_run_count}).")

        async def on_job_start(input: Any, job_id: str = job.id) -> None:
            await context.job_event_notifier.notify(
                "started",
                job_id,
                self.jobs[job_id].type.value,
                context=context,
                input=input
            )
            tracing.on_job_start(context.task_id, job_id, self.id, input)
            logging.info("[task-%s] Job '%s:%s' started.", context.task_id, job_id, self.id)
            logging.debug("[task-%s] Job '%s:%s' input: %s", context.task_id, job_id, self.id, input)

        return asyncio.create_task(job.run(
            JobContext(context, job.id, is_terminal=self._is_terminal_job(job.id)),
            on_start=on_job_start,
        ))

    def _is_runnable_job(
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

    def _get_dependent_job_ids(self, root_job_id: str, candidate_job_ids: Set[str]) -> Set[str]:
        dependents: Set[str] = set()

        def _visit(job_id: str) -> None:
            if job_id in dependents or job_id not in candidate_job_ids:
                return
            dependents.add(job_id)
            for other_id, other_job in self.jobs.items():
                if job_id in other_job.depends_on:
                    _visit(other_id)

        _visit(root_job_id)

        return dependents
