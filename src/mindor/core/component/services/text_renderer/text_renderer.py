from typing import List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import TextRendererComponentConfig
from mindor.dsl.schema.action import ActionConfig, TextRendererActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.utils.iterators import BatchSourceIterator
from ...action.base import ComponentAction
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext

class TextRendererAction(ComponentAction):
    def __init__(self, config: TextRendererActionConfig):
        self.config: TextRendererActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        template   = await context.render_text(self.config.template, collect=False)
        batch_size = await context.render_variable(self.config.batch_size)

        is_single_input  = not isinstance(template, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(template, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_templates in BatchSourceIterator(template, batch_size=batch_size or 1):
                    for result in batch_templates:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(template, StreamChunkIterator) and template.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_templates in BatchSourceIterator(template, batch_size=batch_size or 1):
                results.extend(batch_templates)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

@register_component(ComponentType.TEXT_RENDERER)
class TextRendererComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: TextRendererComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await TextRendererAction(action).run(context)
