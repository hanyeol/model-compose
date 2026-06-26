from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import DelayJobConfig, DelayJobMode
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.foundation.variable.time import parse_duration, parse_datetime
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
from datetime import datetime
import asyncio

@register_job(JobType.DELAY)
class DelayJob(Job):
    def __init__(self, id: str, config: DelayJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def run(self, context: JobContext) -> Any:
        output = await self._delay(self.config.mode, context)

        output = (await context.render_variable(None, self.config.output)) if self.config.output else output
        context.register_source(None, "output", output)

        return output

    async def _delay(self, mode: DelayJobMode, context: JobContext) -> Any:
        if mode == DelayJobMode.TIME_INTERVAL:
            return await self._delay_for_time_interval(context)

        if mode == DelayJobMode.SPECIFIC_TIME:
            return await self._delay_until_specific_time(context)

        raise ValueError(f"Unsupported delay mode: {mode}")

    async def _delay_for_time_interval(self, context: JobContext) -> Any:
        duration = parse_duration((await context.render_variable(None, self.config.duration)) or 0.0)

        job_time_tracker = TimeTracker()
        logging.debug("[task-%s] Delay started for time interval: %d seconds.", context.workflow.task_id, int(duration))

        if duration > 0.0:
            await asyncio.sleep(duration)

        logging.debug("[task-%s] Delay completed in %.2f seconds.", context.workflow.task_id, job_time_tracker.elapsed())

        return None

    async def _delay_until_specific_time(self, context: JobContext) -> Union[Any, RoutingTarget]:
        timezone = await context.render_variable(None, self.config.timezone)
        time = parse_datetime((await context.render_variable(None, self.config.time)) or datetime(2000, 1, 1, 0, 0, 0), timezone)

        now = datetime.now(tz=time.tzinfo)
        duration = max((time - now).total_seconds(), 0.0)

        job_time_tracker = TimeTracker()
        logging.debug("[task-%s] Delay started, waiting until %s", context.workflow.task_id, time)

        if duration > 0.0:
            await asyncio.sleep(duration)

        logging.debug("[task-%s] Delay completed in %.2f seconds.", context.workflow.task_id, job_time_tracker.elapsed())

        return None
