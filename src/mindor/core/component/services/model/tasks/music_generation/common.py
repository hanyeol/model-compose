from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import CommonMusicGenerationModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

class MusicGenerationTaskAction(ComponentAction):
    def __init__(self, config: CommonMusicGenerationModelActionConfig):
        self.config: CommonMusicGenerationModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_inputs = tuple(zip(*batch_inputs))  # Transpose per-slot batches into per-request tuples.
                    batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()

        results: List[Any] = []
        async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
            batch_inputs = tuple(zip(*batch_inputs))  # Transpose per-slot batches into per-request tuples.
            batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
            results.extend(batch_results)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        duration  = await context.render_variable(self.config.params.duration)
        bpm       = await context.render_variable(self.config.params.bpm)
        key_scale = await context.render_variable(self.config.params.key_scale)
        seed      = await context.render_scalar(self.config.seed, int)

        return {
            "duration":  duration,
            "bpm":       bpm,
            "key_scale": key_scale,
            "seed":      seed,
        }

    @abstractmethod
    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        pass

    @abstractmethod
    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        pass
