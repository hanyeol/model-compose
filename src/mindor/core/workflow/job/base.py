from typing import Type, Union, Literal, Optional, Awaitable, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from dataclasses import asdict
from mindor.dsl.schema.job import JobConfig, JobType, JobInterruptConfig, JobHookConfig
from mindor.dsl.schema.job.impl.common import JobRetryConfig, JobRetryBackoff, JobOnErrorConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.evaluator.condition import evaluate_condition
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.workflow.interrupt import InterruptPoint
from mindor.core.workflow.hook import HookPoint
from mindor.core.logger import logging
from .context import JobContext
import asyncio, inspect

OnStartedCallback = Callable[[Any], Awaitable[None]]

class RoutingTarget:
    def __init__(self, job_id):
        self.job_id = job_id

class Job(ABC):
    def __init__(self, id: str, config: JobConfig, global_configs: ComponentGlobalConfigs):
        self.id: str = id
        self.config: JobConfig = config
        self.global_configs: ComponentGlobalConfigs = global_configs

        self._on_started: Optional[OnStartedCallback] = None
        self._started_fired: bool = False

    async def run(
        self,
        context: JobContext,
        on_started: Optional[OnStartedCallback] = None,
    ) -> Union[Any, RoutingTarget]:
        max_attempt_count = self.config.retry.max_attempt_count if self.config.retry else 1
        attempt = 0

        self._on_started = on_started
        self._started_fired = False

        while True:
            attempt += 1
            try:
                return await self._run(context)
            except Exception as e:
                if attempt < max_attempt_count:
                    delay = self._resolve_retry_delay(attempt)

                    logging.warning(
                        "[task-%s] Job '%s' attempt %d/%d failed: %s. Retrying in %.2fs.",
                        context.workflow.task_id, self.id, attempt, max_attempt_count, e, delay,
                    )

                    if delay > 0.0:
                        await asyncio.sleep(delay)

                    continue

                if self.config.on_error is None:
                    raise

                logging.warning(
                    "[task-%s] Job '%s' failed, applying on_error: %s",
                    context.workflow.task_id, self.id, e
                )

                if self.config.on_error.to:
                    return RoutingTarget(self.config.on_error.to)

                if self.config.on_error.output is not None:
                    context.register_source(None, "error", { "message": str(e) })
                    return await context.render_variable(None, self.config.on_error.output)

                return None

    def _resolve_retry_delay(self, attempt: int) -> float:
        delay = parse_duration(self.config.retry.delay)

        if self.config.retry.backoff == JobRetryBackoff.EXPONENTIAL:
            delay = delay * (2 ** (attempt - 1))

        if self.config.retry.max_delay is not None:
            delay = min(delay, parse_duration(self.config.retry.max_delay))

        return max(delay, 0.0)

    @abstractmethod
    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        pass

    async def _started(self, input: Any) -> None:
        if not self._started_fired:
            self._started_fired = True
            if self._on_started is not None:
                await self._on_started(input)
 
    async def _before_run(self, context: JobContext, run_id: Optional[str], input: Any) -> Any:
        input = await self._apply_before_interrupt(context, run_id, input)
        input = await self._apply_before_hooks(context, run_id, input)

        return input

    async def _after_run(self, context: JobContext, run_id: Optional[str], input: Any, output: Any) -> Any:
        output = await self._apply_after_interrupt(context, run_id, input, output)
        output = await self._apply_after_hooks(context, run_id, input, output)

        return output

    async def _apply_before_interrupt(self, context: JobContext, run_id: Optional[str], input: Any) -> Any:
        if self.config.interrupt and self.config.interrupt.before:
            logging.info("[task-%s] Job '%s:%s' interrupted at 'before' phase.", context.workflow.task_id, self.id, context.workflow.workflow_id)
            context.register_source(run_id, "job", { "input": input })
            answer = await self._interrupt(context, run_id, "before", self.config.interrupt.before)
            if answer is not None:
                return answer

        return input

    async def _apply_after_interrupt(self, context: JobContext, run_id: Optional[str], input: Any, output: Any) -> Any:
        if self.config.interrupt and self.config.interrupt.after:
            logging.info("[task-%s] Job '%s:%s' interrupted at 'after' phase.", context.workflow.task_id, self.id, context.workflow.workflow_id)
            context.register_source(run_id, "job", { "input": input, "output": output })
            answer = await self._interrupt(context, run_id, "after", self.config.interrupt.after)
            if answer is not None:
                return answer

        return output

    async def _interrupt(self, context: JobContext, run_id: Optional[str], phase: str, interrupt: JobInterruptConfig) -> Any:
        if interrupt.condition:
            input = await context.render_variable(run_id, interrupt.condition.input)
            value = await context.render_variable(run_id, interrupt.condition.value)
            if not evaluate_condition(interrupt.condition.operator, input, value):
                logging.debug("[task-%s] Job '%s:%s' interrupt at '%s' phase skipped: condition not met.", context.workflow.task_id, self.id, context.workflow.workflow_id, phase)
                return None

        message  = (await context.render_variable(run_id, interrupt.message))  if interrupt.message  else None
        metadata = (await context.render_variable(run_id, interrupt.metadata)) if interrupt.metadata else None

        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        future = loop.create_future()

        point = InterruptPoint(
            task_id=context.workflow.task_id,
            job_id=self.id,
            run_id=run_id,
            phase=phase,
            message=message,
            metadata=metadata,
            future=future
        )

        return await context.workflow.interrupt_handler.interrupt(point)

    async def _apply_before_hooks(self, context: JobContext, run_id: Optional[str], input: Any) -> Any:
        if self.config.hook and self.config.hook.before:
            point = HookPoint(
                task_id=context.workflow.task_id,
                job_id=self.id,
                run_id=run_id,
                phase="before"
            )

            for index, entry in enumerate(self.config.hook.before):
                input = await self._run_hook(index, entry, point, (input,))

        return input

    async def _apply_after_hooks(self, context: JobContext, run_id: Optional[str], input: Any, output: Any) -> Any:
        if self.config.hook and self.config.hook.after:
            point = HookPoint(
                task_id=context.workflow.task_id,
                job_id=self.id,
                run_id=run_id,
                phase="after"
            )

            for index, entry in enumerate(self.config.hook.after):
                output = await self._run_hook(index, entry, point, (input, output))

        return output

    async def _run_hook(self, index: int, hook: JobHookConfig, point: HookPoint, args: Tuple[Any, ...]) -> Any:
        namespace: Dict[str, Any] = {}

        try:
            exec(hook.script, namespace)
        except Exception as e:
            logging.error("Job '%s' hook[%d] at '%s' phase failed to compile: %s", self.id, index, point.phase, e)
            raise

        hook_fn = namespace.get("hook")

        if hook_fn is None or not callable(hook_fn):
            raise ValueError(f"Hook script for job '{self.id}' at '{point.phase}' phase (index {index}) must define a callable named 'hook'.")

        result = hook_fn(*args, **asdict(point))

        if inspect.isawaitable(result):
            result = await result

        return result

def register_job(type: JobType):
    def decorator(cls: Type[Job]) -> Type[Job]:
        JobRegistry[type] = cls
        return cls
    return decorator

JobRegistry: Dict[JobType, Type[Job]] = {}
