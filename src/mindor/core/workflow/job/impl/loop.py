from typing import Type, Union, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.job import LoopJobConfig, ComponentJobConfig
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from mindor.core.component import ComponentService, ComponentGlobalConfigs
from mindor.core.foundation.condition import evaluate_condition, evaluate_where
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import JobType, JobContext, RoutingTarget, register_job
from .common import CompositeJob
import asyncio, ulid

@register_job(JobType.LOOP)
class LoopJob(CompositeJob):
    def __init__(self, id: str, config: LoopJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        component: Optional[ComponentService] = None

        if isinstance(self.config.do, ComponentJobConfig):
            component = await self._create_component(self.id, self.config.do.component)

        input = await context.render_variable(None, self.config.input)

        await self._started(input)

        input = await self._before_run(context, None, input)
        cancellation_token = context.cancellation_token

        is_direct_output = not self.config.output or self.config.output == "${output}"

        stop_condition = self.config.until.model_dump(by_alias=True, exclude_none=True) if self.config.until else None
        continue_condition = self.config.while_.model_dump(by_alias=True, exclude_none=True) if self.config.while_ else None

        output: Any = None
        iteration = 0

        while True:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                raise asyncio.CancelledError(cancellation_token.reason or "cancelled")

            if iteration >= self.config.max_iteration_count:
                raise RuntimeError(
                    f"Loop job '{self.id}' exceeded max_iteration_count ({self.config.max_iteration_count})."
                )

            # Runs the iteration and evaluates the condition inside the iteration's
            # run_id scope so that ${output}/${iteration} references resolve to this
            # loop's own values rather than any outer scope's `output` shadowing them.
            output, should_break = await self._run_iteration(
                input,
                output,
                iteration,
                component,
                context,
                stop_condition,
                continue_condition,
            )

            if should_break:
                break

            iteration += 1

        output = await self._after_run(context, None, input, output)

        if not is_direct_output:
            context.register_source(None, "output", output)
            output = await context.render_variable(None, self.config.output, skip_decode=context.is_terminal)

        return output

    async def _run_iteration(
        self,
        input: Any,
        previous_output: Any,
        iteration: int,
        component: Optional[ComponentService],
        context: JobContext,
        stop_condition: Optional[Dict[str, Any]],
        continue_condition: Optional[Dict[str, Any]],
    ) -> Tuple[Any, bool]:
        run_id: str = ulid.ulid()
        context.workflow.record_run_id(self.id, run_id)

        job_time_tracker = TimeTracker()
        logging.debug(
            "[task-%s] Iteration %d '%s' for job '%s:%s' started.",
            context.workflow.task_id,
            iteration,
            run_id,
            self.id,
            context.workflow.workflow_id,
        )

        is_direct_output = not self.config.do.output or self.config.do.output == "${output}"

        try:
            # ${input} = loop's initial input (fixed across iterations, like pipeline).
            context.register_source(run_id, "input", input)

            # ${output} = previous iteration's output; unavailable on the first iteration (like pipeline).
            if iteration > 0:
                context.register_source(run_id, "output", previous_output)

            context.register_source(run_id, "iteration", iteration)

            if component is not None:
                if self.config.do.input is not None:
                    input = await context.render_variable(run_id, self.config.do.input)
                else:
                    input = previous_output if iteration > 0 else input
                output = await component.run(self.config.do.action, run_id, input, workflow=context.workflow, job_id=self.id)
            else:
                output = await self._run_inline_job(self.config.do, context, run_id, "do")

            # Overwrite ${output} with what this iteration just produced so do.output
            # mapping and the loop's condition both see the current iteration's result.
            context.register_source(run_id, "output", output)

            logging.debug(
                "[task-%s] Iteration %d '%s' for job '%s:%s' completed in %.2f seconds.",
                context.workflow.task_id,
                iteration,
                run_id,
                self.id,
                context.workflow.workflow_id,
                job_time_tracker.elapsed(),
            )

            if not is_direct_output:
                output = await context.render_variable(run_id, self.config.do.output, skip_decode=context.is_terminal)
                context.register_source(run_id, "output", output)

            if stop_condition is not None:
                should_break = await self._matches_condition(context, run_id, stop_condition)
            else:
                should_break = not await self._matches_condition(context, run_id, continue_condition)

            return output, should_break
        finally:
            context._sources.pop(run_id, None)

    async def _matches_condition(self, context: JobContext, run_id: str, condition: Dict[str, Any]) -> bool:
        async def _evaluate_leaf(leaf: Dict[str, Any]) -> bool:
            input = await context.render_variable(run_id, leaf.get("input"))
            value = await context.render_variable(run_id, leaf.get("value"))
            operator = ConditionOperator(leaf.get("operator", ConditionOperator.EQ.value))
            return evaluate_condition(operator, input, value)

        return await evaluate_where(condition, _evaluate_leaf)
