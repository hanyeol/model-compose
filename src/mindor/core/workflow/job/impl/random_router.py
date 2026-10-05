from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import RandomRouterJobConfig, RandomRoutingMode
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
import random, hashlib, math

class RandomRoutingSelector:
    def __init__(self, candidates: List[Tuple[str, float]]):
        self.candidates: List[Tuple[str, float]] = candidates

    def select(self, salt: Optional[str], session: Optional[str]) -> str:
        if salt and session:
            return self._pick_hashed(salt, session)

        return self._pick_random()

    def _pick_hashed(self, salt: str, session: str) -> str:
        best_target: Optional[str] = None
        best_score: Optional[float] = None

        for target, weight in self.candidates:
            score = self._score(salt, session, target, weight)

            if best_score is None or score < best_score:
                best_score  = score
                best_target = target

        return best_target

    def _pick_random(self) -> str:
        targets = [ target for target, _ in self.candidates ]
        weights = [ weight for _, weight in self.candidates ]

        return random.choices(targets, weights=weights, k=1)[0]

    def _score(self, salt: str, session: str, target: str, weight: float) -> float:
        digest = hashlib.sha256(f"{salt}\x00{session}\x00{target}".encode("utf-8")).digest()
        u = (int.from_bytes(digest[:8], "big") + 1) / (2 ** 64 + 1)

        return -math.log(u) / weight

@register_job(JobType.RANDOM_ROUTER)
class RandomRouterJob(Job):
    def __init__(self, id: str, config: RandomRouterJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(
        self,
        context: JobContext,
        run_id: Optional[str],
        default_input: Any,
        is_terminal: bool,
    ) -> Union[Any, RoutingTarget]:
        session = await context.render_variable(run_id, self.config.session) if self.config.session else None
        salt    = await context.render_variable(run_id, self.config.salt) if session and self.config.salt else None

        await self._started(None)

        await self._before_run(context, run_id, None)

        candidates = await self._resolve_routing_candidates(context, run_id)

        if not candidates:
            raise ValueError(f"No valid routing found in random-router job '{self.id}'")

        if session and not salt:
            salt = f"{context.workflow.workflow_id}:{self.id}"

        target = RandomRoutingSelector(candidates).select(salt, session)

        await self._after_run(context, run_id, None, None)

        return RoutingTarget(target)

    async def _resolve_routing_candidates(self, context: JobContext, run_id: Optional[str]) -> List[Tuple[str, float]]:
        if self.config.mode == RandomRoutingMode.WEIGHTED:
            candidates: List[Tuple[str, float]] = []

            for routing in self.config.routings:
                weight = await context.render_variable(run_id, routing.weight)

                if weight is not None and weight > 0.0:
                    candidates.append((routing.to, float(weight)))

            return candidates

        if self.config.mode == RandomRoutingMode.UNIFORM:
            return [ (routing.to, 1.0) for routing in self.config.routings ]

        raise ValueError(f"Unsupported routing mode: {self.config.mode}")
