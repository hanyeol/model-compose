from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import TextClassificationModelActionConfig
from ...base import ModelTaskService, ComponentActionContext

class TextClassificationTaskAction:
    def __init__(self, config: TextClassificationModelActionConfig):
        self.config: TextClassificationModelActionConfig = config

    async def run(self, context: ComponentActionContext, labels: Optional[List[str]]) -> Any:
        text = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(text, list))
        uses_array_output: bool = context.contains_variable_reference("result[]", self.config.output)
        texts: List[str] = [ text ] if is_single_input else text
        results = []

        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        async def _process():
            for index in range(0, len(texts), batch_size):
                batch_texts = texts[index:index + batch_size]
                predictions = await self._predict(batch_texts, labels, context)

                if uses_array_output:
                    rendered_outputs = []
                    for prediction in predictions:
                        context.register_source("result[]", prediction)
                        rendered_outputs.append((await context.render_variable(self.config.output)) if self.config.output else prediction)
                    yield rendered_outputs
                else:
                    yield predictions

        if streaming:
            async def _stream_output_generator():
                async for predictions in _process():
                    if not uses_array_output:
                        for prediction in predictions:
                            context.register_source("result", prediction)
                            yield (await context.render_variable(self.config.output)) if self.config.output else prediction
                    else:
                        for prediction in predictions:
                            yield prediction

            return _stream_output_generator()
        else:
            async for predictions in _process():
                results.extend(predictions)

            if not uses_array_output:
                result = results[0] if is_single_input else results
                context.register_source("result", result)
                return (await context.render_variable(self.config.output)) if self.config.output else result
            else:
                return results

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_variable(self.config.text)

    @abstractmethod
    async def _predict(self, texts: List[str], labels: Optional[List[str]], context: ComponentActionContext) -> List[Any]:
        pass

class TextClassificationTaskService(ModelTaskService):
    pass
