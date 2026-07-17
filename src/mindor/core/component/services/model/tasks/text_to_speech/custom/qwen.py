from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.dsl.schema.action import CommonTextToSpeechModelActionConfig
from mindor.dsl.schema.action import QwenTextToSpeechModelGenerateActionConfig
from mindor.dsl.schema.action import QwenTextToSpeechModelCloneActionConfig
from mindor.dsl.schema.action import QwenTextToSpeechModelDesignActionConfig
from mindor.core.logger import logging
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm16
from ......base import ComponentActionContext
from ..common import TextToSpeechTaskService, TextToSpeechTaskAction
import asyncio

if TYPE_CHECKING:
    import torch

_QWEN_LANGUAGE_MAP: dict[str, str] = {
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
    config: CommonTextToSpeechModelActionConfig

    def __init__(self, config: CommonTextToSpeechModelActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, device)

        self.model = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        language = await context.render_variable(self.config.language)

        params["language"] = self._resolve_language(language) if language else None

        return params

    def _generate(self, texts: List[str], params: Dict[str, Any]) -> List[StreamResource]:
        def _generate(text: str) -> StreamResource:
            samples, sample_rate = self._synthesize(text, params)
            frames, channels = encode_waveform_to_pcm16(samples[0])

            return PcmStreamResource(frames, {
                "sample_rate": str(sample_rate),
                "channels":    str(channels),
                "bit_depth":   "16",
            })

        return [ _generate(text) for text in texts ]

    def _resolve_language(self, language: Optional[str]) -> Optional[str]:
        return _QWEN_LANGUAGE_MAP.get(language.split("-")[0])

    @abstractmethod
    def _synthesize(self, text: str, params: Dict[str, Any]) -> Tuple[Any, int]:
        pass

class QwenTextToSpeechGenerateTaskAction(QwenTextToSpeechTaskAction):
    config: QwenTextToSpeechModelGenerateActionConfig

    def __init__(self, config: QwenTextToSpeechModelGenerateActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, model, device)

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        voice        = await context.render_variable(self.config.voice)
        instructions = await context.render_variable(self.config.instructions)

        params["voice"]        = voice
        params["instructions"] = instructions

        return params

    def _synthesize(self, text: str, params: Dict[str, Any]) -> Tuple[Any, int]:
        return self.model.generate_custom_voice(
            text=text,
            language=params["language"],
            speaker=params["voice"],
            instruct=params["instructions"],
        )

class QwenTextToSpeechCloneTaskAction(QwenTextToSpeechTaskAction):
    config: QwenTextToSpeechModelCloneActionConfig

    def __init__(self, config: QwenTextToSpeechModelCloneActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, model, device)

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        reference_audio = await context.render_file(self.config.reference_audio)
        reference_text  = await context.render_variable(self.config.reference_text)

        params["reference_audio"] = reference_audio
        params["reference_text"]  = reference_text

        return params

    def _synthesize(self, text: str, params: Dict[str, Any]) -> Tuple[Any, int]:
        return self.model.generate_voice_clone(
            text=text,
            language=params["language"],
            ref_audio=params["reference_audio"],
            ref_text=params["reference_text"],
        )

class QwenTextToSpeechDesignTaskAction(QwenTextToSpeechTaskAction):
    config: QwenTextToSpeechModelDesignActionConfig

    def __init__(self, config: QwenTextToSpeechModelDesignActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, model, device)

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        instructions = await context.render_variable(self.config.instructions)

        params["instructions"] = instructions

        return params

    def _synthesize(self, text: str, params: Dict[str, Any]) -> Tuple[Any, int]:
        return self.model.generate_voice_design(
            text=text,
            language=params["language"],
            instruct=params["instructions"],
        )

class QwenTextToSpeechTaskService(TextToSpeechTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "transformers", "qwen_tts", "torch", "huggingface_hub", "numpy", "soundfile" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
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

        device = self._resolve_device(self.config.device)
        model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=device,
            dtype=torch.bfloat16,
            trust_remote_code=True,
        )

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        if action.method == TextToSpeechActionMethod.GENERATE:
            return await QwenTextToSpeechGenerateTaskAction(action, self.model, self.device).run(context, loop)

        if action.method == TextToSpeechActionMethod.CLONE:
            return await QwenTextToSpeechCloneTaskAction(action, self.model, self.device).run(context, loop)

        if action.method == TextToSpeechActionMethod.DESIGN:
            return await QwenTextToSpeechDesignTaskAction(action, self.model, self.device).run(context, loop)

        raise ValueError(f"Unknown method: {action.method}")
