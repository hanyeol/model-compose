from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import ActionJobConfig, JobType
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentEngine, ComponentResolver, create_component
from .base import Job, JobMap, WorkflowContext
import asyncio, ulid

class ActionJob(Job):
    def __init__(self, id: str, config: ActionJobConfig, components: Dict[str, ComponentConfig]):
        super().__init__(id, config, components)

    async def run(self, context: WorkflowContext) -> Any:
        component: ComponentEngine = self._create_component(self.id, await context.render_variable(self.config.component))

        if not component.started:
            await component.start()

        input = (await context.render_variable(self.config.input)) if self.config.input else context.input
        outputs = []

        async def _run_once():
            call_id = ulid.ulid()
            output = await component.run(await context.render_variable(self.config.action), call_id, input)
            context.register_source("output", output)

            output = (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else output
            outputs.append(output)

        repeat_count = (await context.render_variable(self.config.repeat_count)) if self.config.repeat_count else None
        await asyncio.gather(*[ _run_once() for _ in range(int(repeat_count or 1)) ])

        output = outputs[0] if len(outputs) == 1 else outputs or None
        context.register_source("output", output)

        return output

    def _create_component(self, id: str, component: Union[ComponentConfig, str]) -> ComponentEngine:
        return create_component(*self._resolve_component(id, component), daemon=False)

    def _resolve_component(self, id: str, component: Union[ComponentConfig, str]) -> Tuple[str, ComponentConfig]:
        if isinstance(component, str):
            return ComponentResolver(self.components).resolve(component)
    
        return id, component

JobMap[JobType.ACTION] = ActionJob
