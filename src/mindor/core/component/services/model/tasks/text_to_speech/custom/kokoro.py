from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.dsl.schema.action import KokoroTextToSpeechModelGenerateActionConfig
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from ......base import ComponentActionContext
from ..common import TextToSpeechTaskService, TextToSpeechTaskAction
import asyncio

if TYPE_CHECKING:
    import torch

class KokoroTextToSpeechGenerateTaskAction(TextToSpeechTaskAction):
    config: KokoroTextToSpeechModelGenerateActionConfig

    def __init__(self, config: KokoroTextToSpeechModelGenerateActionConfig, pipeline: Any, device: Optional[torch.device]):
        super().__init__(config, device)

        self.pipeline = pipeline

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        voice = await context.render_variable(self.config.voice)
        speed = await context.render_variable(self.config.speed)

        params["voice"] = voice or "af_heart"
        params["speed"] = float(speed) if speed is not None else 1.0

        return params

    def _generate(self, texts: List[str], params: Dict[str, Any]) -> List[StreamResource]:
        def _generate(text: str) -> StreamResource:
            samples, sample_rate = self._synthesize(text, params["voice"], params["speed"])
            frames, channels = self._encode_samples_to_pcm16(samples)

            return PcmStreamResource(frames, {
                "sample_rate": str(sample_rate),
                "channels":    str(channels),
                "bit_depth":   "16",
            })

        return [ _generate(text) for text in texts ]

    def _synthesize(self, text: str, voice: str, speed: float) -> Tuple[Any, int]:
        import numpy as np

        chunks = []
        for _, _, audio in self.pipeline(text, voice=voice, speed=speed):
            chunks.append(audio)

        samples = np.concatenate(chunks, axis=0) if len(chunks) > 1 else chunks[0]

        return samples, 24000

class KokoroTextToSpeechTaskService(TextToSpeechTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "kokoro", "torch", "numpy", "soundfile" ]

    async def _load_model(self) -> None:
        self.pipeline, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[Any, Any]:
        from kokoro import KPipeline

        device = self._resolve_device()
        lang_code = "a"  # American English default
        pipeline = KPipeline(lang_code=lang_code, device=str(device))

        return pipeline, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        if action.method == TextToSpeechActionMethod.GENERATE:
            return await KokoroTextToSpeechGenerateTaskAction(action, self.pipeline, self.device).run(context, loop)

        raise ValueError(f"Unknown method: {action.method}")
