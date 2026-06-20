from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.dsl.schema.action import CommonTextToSpeechModelActionConfig
from mindor.dsl.schema.action import ChatterboxTextToSpeechGenerateModelActionConfig
from mindor.dsl.schema.action import ChatterboxTextToSpeechCloneModelActionConfig
from mindor.core.utils.streaming.audio import PcmStreamResource
from mindor.core.utils.streaming.stream import StreamResource
from ......base import ComponentActionContext
from ..common import TextToSpeechTaskService, TextToSpeechTaskAction
import asyncio

if TYPE_CHECKING:
    import torch

class ChatterboxTextToSpeechTaskAction(TextToSpeechTaskAction):
    def __init__(self, config: CommonTextToSpeechModelActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, device)

        self.config: CommonTextToSpeechModelActionConfig = config  # For type only
        self.model = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        exaggeration = await context.render_variable(self.config.exaggeration)
        cfg_weight   = await context.render_variable(self.config.cfg_weight)
        temperature  = await context.render_variable(self.config.temperature)

        generation_params: Dict[str, Any] = {}
        if exaggeration is not None:
            generation_params["exaggeration"] = float(exaggeration)
        if cfg_weight is not None:
            generation_params["cfg_weight"] = float(cfg_weight)
        if temperature is not None:
            generation_params["temperature"] = float(temperature)

        params["generation"] = generation_params

        return params

    async def _generate(self, texts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[StreamResource]:
        async def _synthesize(text: str) -> StreamResource:
            samples, sample_rate = await loop.run_in_executor(None, self._synthesize, text, params["generation"])
            frames, channels = self._encode_samples_to_pcm16(samples)

            return PcmStreamResource(frames, {
                "sample_rate": str(sample_rate),
                "channels":    str(channels),
                "bit_depth":   "16",
            })

        return [ await _synthesize(text) for text in texts ]

    def _synthesize(self, text: str, generation_params: dict) -> Tuple[Any, int]:
        wav = self.model.generate(text, **generation_params)
        return wav.squeeze(0).cpu(), self.model.sr

class ChatterboxTextToSpeechGenerateTaskAction(ChatterboxTextToSpeechTaskAction):
    def __init__(self, config: ChatterboxTextToSpeechGenerateModelActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, model, device)

        self.config: ChatterboxTextToSpeechGenerateModelActionConfig = config  # For type only

class ChatterboxTextToSpeechCloneTaskAction(ChatterboxTextToSpeechTaskAction):
    def __init__(self, config: ChatterboxTextToSpeechCloneModelActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, model, device)

        self.config: ChatterboxTextToSpeechCloneModelActionConfig = config  # For type only

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        reference_audio = await context.render_file(self.config.reference_audio)

        if reference_audio is not None:
            params["generation"]["audio_prompt_path"] = reference_audio

        return params

class ChatterboxTextToSpeechTaskService(TextToSpeechTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "chatterbox-tts", "numpy", "soundfile" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[Any, Any]:
        from chatterbox.tts import ChatterboxTTS

        device = self._resolve_device()
        model = ChatterboxTTS.from_pretrained(str(device))

        return model, device

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        if action.method == TextToSpeechActionMethod.GENERATE:
            return await ChatterboxTextToSpeechGenerateTaskAction(action, self.model, self.device).run(context, loop)

        if action.method == TextToSpeechActionMethod.CLONE:
            return await ChatterboxTextToSpeechCloneTaskAction(action, self.model, self.device).run(context, loop)

        raise ValueError(f"Unknown method: {action.method}")
