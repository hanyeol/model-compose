from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.core.logger import logging
from ...base import ComponentActionContext
from .common import TextToSpeechTaskService, TextToSpeechTaskAction
import asyncio, io

if TYPE_CHECKING:
    import torch

QWEN_LANGUAGE_MAP: dict[str, str] = {
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "ru": "Russian",
    "pt": "Portuguese",
    "es": "Spanish",
    "it": "Italian",
}

class QwenTextToSpeechTaskAction(TextToSpeechTaskAction):
    def __init__(self, config: ModelActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, device)

        self.model = model

    async def _generate(self, text: str, context: ComponentActionContext) -> bytes:
        import soundfile as sf

        language = await context.render_variable(self.config.language)
        language = self._resolve_language(language) if language else None
        samples, sample_rate = await self._synthesize(text, language, context)

        buffer = io.BytesIO()
        sf.write(buffer, samples[0], sample_rate, format="WAV")

        return buffer.getvalue()

    def _resolve_language(self, language: Optional[str]) -> Optional[str]:
        return QWEN_LANGUAGE_MAP.get(language.split("-")[0])

    @abstractmethod
    async def _synthesize(self, text: str, language: Optional[str], context: ComponentActionContext) -> Tuple[Any, int]:
        pass

class QwenTextToSpeechGenerateTaskAction(QwenTextToSpeechTaskAction):
    async def _synthesize(self, text: str, language: Optional[str], context: ComponentActionContext) -> Tuple[Any, int]:
        voice        = await context.render_variable(self.config.voice)
        instructions = await context.render_variable(self.config.instructions)

        return self.model.generate_custom_voice(
            text=text, 
            language=language,
            speaker=voice,
            instruct=instructions,
        )

class QwenTextToSpeechCloneTaskAction(QwenTextToSpeechTaskAction):
    async def _synthesize(self, text: str, language: Optional[str], context: ComponentActionContext) -> Tuple[Any, int]:
        ref_audio = await context.render_file(self.config.ref_audio)
        ref_text  = await context.render_variable(self.config.ref_text)

        return self.model.generate_voice_clone(
            text=text,
            language=language,
            ref_audio=ref_audio,
            ref_text=ref_text,
        )

class QwenTextToSpeechDesignTaskAction(QwenTextToSpeechTaskAction):
    async def _synthesize(self, text: str, language: Optional[str], context: ComponentActionContext) -> Tuple[Any, int]:
        instructions = await context.render_variable(self.config.instructions)

        return self.model.generate_voice_design(
            text=text,
            language=language,
            instruct=instructions,
        )

class QwenTextToSpeechTaskService(TextToSpeechTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "transformers", "qwen_tts", "sox", "soundfile" ]

    async def _serve(self) -> None:
        try:
            self.model, self.device = self._load_pretrained_model()
            logging.info(f"Model loaded successfully on device '{self.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[Any, torch.device]:
        from qwen_tts import Qwen3TTSModel
        import torch

        # qwen_tts handles model downloading internally via from_pretrained(),
        # so pass the repo ID directly instead of a snapshot_download() path.
        if isinstance(self.config.model, HuggingfaceModelConfig):
            model_id = self.config.model.repository
        else:
            model_id = self._get_model_path()

        device = self._resolve_device()
        model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=device,
            dtype=torch.bfloat16,
            trust_remote_code=True,
        )

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        if action.method == TextToSpeechActionMethod.GENERATE:
            return await QwenTextToSpeechGenerateTaskAction(action, self.model, self.device).run(context)

        if action.method == TextToSpeechActionMethod.CLONE:
            return await QwenTextToSpeechCloneTaskAction(action, self.model, self.device).run(context)

        if action.method == TextToSpeechActionMethod.DESIGN:
            return await QwenTextToSpeechDesignTaskAction(action, self.model, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
