from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.workflow import JobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentEngine
from .context import WorkflowContext
import asyncio, ulid

class Job:
    def __init__(self, id: str, config: JobConfig, component_provider: Callable[[str, Union[ComponentConfig, str]], ComponentEngine]):
        self.id: str = id
        self.config: JobConfig = config
        self.component_provider: Callable[[str, Union[ComponentConfig, str]], ComponentEngine] = component_provider

    async def run(self, context: WorkflowContext) -> Any:
        component: ComponentEngine = self.component_provider(self.id, self.config.component)

        if not component.started:
            await component.start()

        input = (await context.render_template(self.config.input)) if self.config.input else context.input
        outputs = []

        async def _run_once():
            call_id = ulid.ulid()
            output = await component.run(self.config.action, call_id, input)

            if output:
                outputs.append(output)

        repeats = (await context.render_template(self.config.repeats)) if self.config.repeats else None
        await asyncio.gather(*[ _run_once() for _ in range(int(repeats or 1)) ])

        output = outputs[0] if len(outputs) == 1 else outputs or None

        if output:
            context.register_source("output", output)

        return (await context.render_template(self.config.output)) if self.config.output else output
