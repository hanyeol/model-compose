from typing import Union, Tuple, Dict, List, Optional, Any
from mindor.dsl.schema.job import JobConfig, InlineJobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs, ComponentResolver, create_component
from ..base import Job
from ..context import JobContext
from ..job import create_job

class ComponentRunnerJob(Job):
    """A job that resolves and runs a component action."""

    async def _create_component(self, id: str, component: Union[ComponentConfig, str]) -> ComponentService:
        service = create_component(*self._resolve_component(id, component), self.global_configs, daemon=False)

        if not service.started:
            await service.start()

        return service

    def _resolve_component(self, id: str, component: Union[ComponentConfig, str]) -> Tuple[str, ComponentConfig]:
        if isinstance(component, str):
            return ComponentResolver(self.global_configs.components).resolve(component)

        return id, component

class CompositeJob(ComponentRunnerJob):
    """A job whose body is one or more inline jobs, dispatched per iteration or step."""

    def __init__(self, id: str, config: JobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

        self._inline_jobs: Dict[str, List[Job]] = {}

    async def _run_inline_job(
        self,
        config: InlineJobConfig,
        context: JobContext,
        run_id: str,
        tag: str,
        input: Optional[Any] = None,
        is_terminal: bool = False,
    ) -> Any:
        job_id = f"{self.id}[{tag}]"
        job = create_job(job_id, config, self.global_configs)
        self._inline_jobs.setdefault(job_id, []).append(job)

        try:
            return await job.run(context, run_id=run_id, default_input=input, is_terminal=is_terminal)
        finally:
            siblings = self._inline_jobs[job_id]
            siblings.remove(job)

            if not siblings:
                del self._inline_jobs[job_id]

    def contains_inline_job(self, job_id: str) -> bool:
        if job_id in self._inline_jobs:
            return True

        for siblings in self._inline_jobs.values():
            for child in siblings:
                if isinstance(child, CompositeJob) and child.contains_inline_job(job_id):
                    return True

        return False
