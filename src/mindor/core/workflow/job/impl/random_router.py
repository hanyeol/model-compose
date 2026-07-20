from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import RandomRouterJobConfig, RandomRoutingMode
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
import random

@register_job(JobType.RANDOM_ROUTER)
class RandomRouterJob(Job):
    def __init__(self, id: str, config: RandomRouterJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        await self._started(None)

        await self._before_run(context, None, None)

        target = await self._select_target(context)

        await self._after_run(context, None, None, None)

        return RoutingTarget(target)

    async def _select_target(self, context: JobContext) -> str:
        if self.config.mode == RandomRoutingMode.WEIGHTED:
            weights, targets = [], []
            for routing in self.config.routings:
                weight = await context.render_variable(None, routing.weight)
                if weight is not None and weight > 0.0:
                    weights.append(weight)
                    targets.append(routing.to)

            if not weights:
                raise ValueError(f"No valid weights found in random-router job '{self.id}'")

            return random.choices(targets, weights=weights, k=1)[0]

        if self.config.mode == RandomRoutingMode.UNIFORM:
            targets = [ routing.to for routing in self.config.routings ]

            if not targets:
                raise ValueError(f"No valid routing found in random-router job '{self.id}'")

            return random.choice(targets)

        raise ValueError(f"Unsupported routing mode: {self.config.mode}")
