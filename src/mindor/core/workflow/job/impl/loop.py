from typing import Union, Optional, Dict, Tuple, Any
from mindor.dsl.schema.job import LoopJobConfig
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from mindor.core.component import ComponentGlobalConfigs
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
        input = (await context.render_variable(None, self.config.input)) if self.config.input else context.default_input

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
        loop_input: Any,
        previous_output: Any,
        iteration: int,
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

        try:
            # ${input} = loop's initial input (fixed across iterations, like pipeline).
            context.register_source(run_id, "input", loop_input)

            # ${output} = previous iteration's output; unavailable on the first iteration (like pipeline).
            if iteration > 0:
                context.register_source(run_id, "output", previous_output)

            context.register_source(run_id, "iteration", iteration)

            input = previous_output if iteration > 0 else loop_input
            output = await self._run_inline_job(self.config.do, context, run_id, "do", input=input)

            # Overwrite ${output} with what this iteration just produced so the loop's
            # condition sees the current iteration's result.
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

            if stop_condition is not None:
                should_break = await self._matches_condition(context, run_id, stop_condition)
            else:
                should_break = not await self._matches_condition(context, run_id, continue_condition)

            return output, should_break
        finally:
            context._sources.pop(run_id, None)

    async def _matches_condition(self, context: JobContext, run_id: str, condition: Dict[str, Any]) -> bool:
        async def _evaluate_leaf(leaf: Dict[str, Any]) -> bool:
            input    = await context.render_variable(run_id, leaf.get("input"))
            value    = await context.render_variable(run_id, leaf.get("value"))
            operator = leaf.get("operator", ConditionOperator.EQ.value)

            try:
                operator = ConditionOperator(operator)
            except ValueError as e:
                raise ValueError(f"Unsupported operator in loop job '{self.id}' condition: {operator}") from e

            return evaluate_condition(operator, input, value)

        return await evaluate_where(condition, _evaluate_leaf)
