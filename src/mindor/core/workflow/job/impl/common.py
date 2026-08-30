from typing import Union, Tuple, Any
from mindor.dsl.schema.job import InlineJobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentService, ComponentResolver, create_component
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

    async def _run_inline_job(self, config: InlineJobConfig, context: JobContext, run_id: str, tag: str) -> Any:
        job = create_job(f"{self.id}[{tag}]", config, self.global_configs)

        with context.use_run_id(run_id):
            return await job.run(context)
