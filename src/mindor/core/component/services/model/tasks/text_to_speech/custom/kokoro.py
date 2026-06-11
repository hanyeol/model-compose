from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.core.utils.audio import PcmStreamResource
from ......base import ComponentActionContext
from ..common import TextToSpeechTaskService, TextToSpeechTaskAction
import asyncio

if TYPE_CHECKING:
    import torch

class KokoroTextToSpeechGenerateTaskAction(TextToSpeechTaskAction):
    def __init__(self, config: ModelActionConfig, pipeline: Any, device: Optional[torch.device]):
        super().__init__(config, device)

        self.pipeline = pipeline

    async def _generate(self, text: str, context: ComponentActionContext) -> Any:
        voice = await context.render_variable(self.config.voice)
        speed = await context.render_variable(self.config.speed)

        samples, sample_rate = await asyncio.get_event_loop().run_in_executor(
            None, self._synthesize, text, voice or "af_heart", float(speed) if speed else 1.0
        )
        frames, channels = self._encode_samples_to_pcm16(samples)

        return PcmStreamResource(frames, {
            "sample_rate": str(sample_rate),
            "channels": str(channels),
            "bit_depth": "16",
        })

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
        return ["kokoro", "numpy", "soundfile"]

    def _load_model(self) -> None:
        self.pipeline, self.device = self._load_pretrained_model()

    def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[Any, Any]:
        from kokoro import KPipeline

        device = self._resolve_device()
        lang_code = "a"  # American English default
        pipeline = KPipeline(lang_code=lang_code, device=str(device))

        return pipeline, device

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        if action.method == TextToSpeechActionMethod.GENERATE:
            return await KokoroTextToSpeechGenerateTaskAction(action, self.pipeline, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
