from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TextToSpeechModelActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.resources import StreamResource
from ...base import ModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import numpy as np
    import torch

class TextToSpeechTaskAction:
    def __init__(self, config: TextToSpeechModelActionConfig, device: Optional[torch.device]):
        self.config: TextToSpeechModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        text       = await context.render_variable(self.config.text)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(text, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._generate(batch_texts, params, loop)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[StreamResource] = []
            async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                batch_results = await self._generate(batch_texts, params, loop)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {}

    @abstractmethod
    async def _generate(self, texts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[StreamResource]:
        pass

    def _encode_samples_to_pcm16(self, samples: Union[torch.Tensor, np.typing.ArrayLike]) -> Tuple[bytes, int]:
        import numpy as np

        if hasattr(samples, "detach"):
            samples = samples.detach()
        if hasattr(samples, "cpu"):
            samples = samples.cpu()
        if hasattr(samples, "numpy"):
            samples = samples.numpy()

        array = np.asarray(samples)
        if array.ndim == 1:
            array = array[:, None]
        elif array.ndim == 2 and array.shape[0] <= 8 and array.shape[0] < array.shape[1]:
            array = array.T
        elif array.ndim != 2:
            raise ValueError(f"Expected mono or stereo audio samples, got shape {array.shape}")

        if np.issubdtype(array.dtype, np.floating):
            array = np.clip(array, -1.0, 1.0)
            array = (array * 32767.0).astype("<i2")
        elif array.dtype != np.int16:
            array = array.astype("<i2")

        return array.tobytes(), int(array.shape[1])

class TextToSpeechTaskService(ModelTaskService):
    pass
