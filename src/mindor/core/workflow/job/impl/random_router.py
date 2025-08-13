from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import RandomRouterJobConfig, RandomRoutingMode
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.logger import logging
from ..base import Job, JobType, WorkflowContext, RoutingTarget, register_job
import random

@register_job(JobType.RANDOM_ROUTER)
class RandomRouterJob(Job):
    def __init__(self, id: str, config: RandomRouterJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def run(self, context: WorkflowContext) -> Union[Any, RoutingTarget]:
        if self.config.mode == RandomRoutingMode.WEIGHTED:
            weights, targets = [], []
            for routing in self.config.routings:
                weight = await context.render_variable(routing.weight)
                if weight is not None and weight > 0.0:
                    weights.append(weight)
                    targets.append(routing.target)

            if not weights:
                raise ValueError(f"No valid weights found in random-router job '{self.id}'.")

            target = random.choices(targets, weights=weights, k=1)[0]
            return RoutingTarget(target)

        if self.config.mode == RandomRoutingMode.UNIFORM:
            targets = [ routing.target for routing in self.config.routings ]

            if not targets:
                raise ValueError(f"No valid routing found in random-router job '{self.id}'.")

            target = random.choice(targets)
            return RoutingTarget(target)

        raise ValueError(f"Unsupported routing mode: {self.config.mode}")
