from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import WaitJobConfig, WaitJobType
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.utils.time import parse_duration, parse_datetime
from .base import Job, JobType, JobMap, WorkflowContext
from datetime import datetime
import asyncio

class WaitJob(Job):
    def __init__(self, id: str, config: WaitJobConfig, components: Dict[str, ComponentConfig]):
        super().__init__(id, config, components)

    async def run(self, context: WorkflowContext) -> Any:
        if self.config.mode == WaitJobType.TIME_INTERVAL:
            return await self._wait_until_time_interval(context)

        if self.config.mode == WaitJobType.SPECIFIC_TIME:
            return await self._wait_until_specific_time(context)

        return None
    
    async def _wait_until_time_interval(self, context: WorkflowContext) -> Any:
        duration = parse_duration((await context.render_variable(self.config.duration)) or 0.0)
        duration = duration.total_seconds()
        
        if duration > 0.0:
            await asyncio.sleep(duration)

        return None

    async def _wait_until_specific_time(self, context: WorkflowContext) -> Any:
        timezone = await context.render_variable(self.config.timezone)
        time = parse_datetime((await context.render_variable(self.config.time)) or datetime(2000, 1, 1, 0, 0, 0), timezone)
        
        now = datetime.now(tz=time.tzinfo)
        duration = (time - now).total_seconds()

        if duration > 0.0:
            await asyncio.sleep(duration)

        return None

JobMap[JobType.WAIT] = WaitJob
