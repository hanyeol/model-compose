from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.core.utils.audio import PcmStreamResource
from ......base import ComponentActionContext
from ..common import TextToSpeechTaskService, TextToSpeechTaskAction
import asyncio

if TYPE_CHECKING:
    import torch

class ChatterboxTextToSpeechTaskAction(TextToSpeechTaskAction):
    def __init__(self, config: ModelActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, device)

        self.model = model

    async def _generate(self, text: str, context: ComponentActionContext) -> Any:
        exaggeration  = await context.render_variable(self.config.exaggeration)
        cfg_weight    = await context.render_variable(self.config.cfg_weight)
        temperature   = await context.render_variable(self.config.temperature)
        audio_path    = await self._get_reference_audio(context)

        generate_params: Dict[str, Any] = {}
        if exaggeration is not None:
            generate_params["exaggeration"] = float(exaggeration)
        if cfg_weight is not None:
            generate_params["cfg_weight"] = float(cfg_weight)
        if temperature is not None:
            generate_params["temperature"] = float(temperature)
        if audio_path is not None:
            generate_params["audio_prompt_path"] = audio_path

        samples, sample_rate = await asyncio.get_event_loop().run_in_executor(
            None, self._synthesize, text, generate_params
        )
        frames, channels = self._encode_samples_to_pcm16(samples)

        return PcmStreamResource(frames, {
            "sample_rate": str(sample_rate),
            "channels": str(channels),
            "bit_depth": "16",
        })

    async def _get_reference_audio(self, context: ComponentActionContext) -> Optional[str]:
        return None

    def _synthesize(self, text: str, generate_params: dict) -> Tuple[Any, int]:
        wav = self.model.generate(text, **generate_params)
        return wav.squeeze(0).cpu(), self.model.sr

class ChatterboxTextToSpeechGenerateTaskAction(ChatterboxTextToSpeechTaskAction):
    pass

class ChatterboxTextToSpeechCloneTaskAction(ChatterboxTextToSpeechTaskAction):
    async def _get_reference_audio(self, context: ComponentActionContext) -> Optional[str]:
        return await context.render_file(self.config.reference_audio)

class ChatterboxTextToSpeechTaskService(TextToSpeechTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return ["chatterbox-tts", "numpy", "soundfile"]

    def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    def _unload_model(self) -> None:
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
            return await ChatterboxTextToSpeechGenerateTaskAction(action, self.model, self.device).run(context)

        if action.method == TextToSpeechActionMethod.CLONE:
            return await ChatterboxTextToSpeechCloneTaskAction(action, self.model, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
