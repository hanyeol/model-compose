from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, Any, Tuple, Union, List
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import numpy as np
    import torch

class MusicGenerationTaskAction:
    def __init__(self, config: MusicGenerationModelActionConfig):
        self.config: MusicGenerationModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        prompt     = await context.render_text(self.config.prompt)
        lyrics     = await context.render_text(self.config.lyrics) if self.config.lyrics is not None else None
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(prompt, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_prompts, batch_lyrics in BatchSourceIterator((prompt, lyrics), batch_size=batch_size or 1):
                    batch_results = self._generate(batch_prompts, batch_lyrics, params)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_prompts, batch_lyrics in BatchSourceIterator((prompt, lyrics), batch_size=batch_size or 1):
                batch_results = self._generate(batch_prompts, batch_lyrics, params)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        duration  = await context.render_variable(self.config.params.duration)
        bpm       = await context.render_variable(self.config.params.bpm)
        key_scale = await context.render_variable(self.config.params.key_scale)

        return {
            "duration":  duration,
            "bpm":       bpm,
            "key_scale": key_scale,
        }

    @abstractmethod
    def _generate(self, prompts: List[str], lyrics: Optional[List[Optional[str]]], params: Dict[str, Any]) -> List[Any]:
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

class MusicGenerationTaskService(ModelTaskService):
    pass
