from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioSourceSeparationModelActionConfig
from mindor.dsl.schema.component import ModelPrecision
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction

if TYPE_CHECKING:
    import torch

class AudioSourceSeparationTaskAction(ModelTaskComponentAction):
    config: AudioSourceSeparationModelActionConfig

    def __init__(
        self,
        config: AudioSourceSeparationModelActionConfig,
        device: Optional[torch.device],
        precision: Optional[ModelPrecision] = None,
    ):
        super().__init__(config)

        self.device: Optional[torch.device] = device
        self.precision: Optional[ModelPrecision] = precision

    async def run(self, context: ComponentActionContext) -> Any:
        input, primary_input, is_single_input, is_streaming_input = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_results = await self._separate_batch(batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(primary_input, StreamChunkIterator) and primary_input.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_results = await self._separate_batch(batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        audio  = await context.render_audio(self.config.audio)
        prompt = await context.render_variable(self.config.prompt) if self.config.prompt is not None else None

        is_single_input    = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(audio, (StreamIterator, AsyncIterator))

        return (audio, prompt), audio, is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        spans       = await context.render_variable(self.config.spans) if self.config.spans is not None else None
        sample_rate = await context.render_scalar(self.config.params.sample_rate, int)

        spans = self._normalize_spans(spans) if spans is not None else None

        return {
            "spans":       spans,
            "sample_rate": sample_rate,
        }

    @staticmethod
    def _normalize_spans(spans: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Normalize the `spans` field into a list of dicts preserving every
        key the user provided. Accepts a single dict or a list of dicts, since
        upstream variables may flow in either shape. Model-specific keys (e.g.
        SAM-Audio's `polarity`) are passed through for the driver to consume."""
        spans = spans if isinstance(spans, list) else [ spans ]

        for index, span in enumerate(spans):
            if not isinstance(span, dict):
                raise ValueError(f"'spans[{index}]' must be a dict, got {type(span).__name__}")

            missing = [ key for key in ("start", "end") if key not in span ]

            if missing:
                raise ValueError(f"'spans[{index}]' is missing required keys: {missing}")

        return [ dict(span) for span in spans ]

    @abstractmethod
    async def _separate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        pass
