from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.core.logger import logging
from ...base import ComponentActionContext
from .common import TextToSpeechTaskService, TextToSpeechTaskAction
import asyncio
import io

if TYPE_CHECKING:
    import torch

class QwenTextToSpeechTaskAction(TextToSpeechTaskAction):
    def __init__(self, config: ModelActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, device)

        self.model = model

    async def _synthesize(self, text: str, context: ComponentActionContext) -> bytes:
        import soundfile as sf

        language = await context.render_variable(self.config.language)

        if self.config.method == TextToSpeechActionMethod.GENERATE:
            voice        = await context.render_variable(self.config.voice)
            instructions = await context.render_variable(self.config.instructions)

            wavs, sr = self.model.generate_custom_voice(
                text=text, language=language, speaker=voice, instruct=instructions,
            )
        elif self.config.method == TextToSpeechActionMethod.CLONE:
            ref_audio = await context.render_variable(self.config.ref_audio)
            ref_text  = await context.render_variable(self.config.ref_text)

            ref_audio = await self._resolve_audio_path(ref_audio)

            wavs, sr = self.model.generate_voice_clone(
                text=text, language=language, ref_audio=ref_audio, ref_text=ref_text,
            )
        elif self.config.method == TextToSpeechActionMethod.DESIGN:
            instructions = await context.render_variable(self.config.instructions)

            wavs, sr = self.model.generate_voice_design(
                text=text, language=language, instruct=instructions,
            )
        else:
            raise ValueError(f"Unknown method: {self.config.method}")

        buffer = io.BytesIO()
        sf.write(buffer, wavs[0], sr, format="WAV")
        audio_bytes = buffer.getvalue()

        return audio_bytes

    async def _resolve_audio_path(self, value: Any) -> str:
        from starlette.datastructures import UploadFile
        from tempfile import NamedTemporaryFile
        import base64, os

        if isinstance(value, UploadFile):
            tmp = NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(await value.read())
            tmp.flush()
            tmp.close()
            return tmp.name

        if isinstance(value, bytes):
            tmp = NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(value)
            tmp.flush()
            tmp.close()
            return tmp.name

        if isinstance(value, str):
            if os.path.isfile(value):
                return value

            # Assume base64-encoded audio data
            tmp = NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(base64.b64decode(value))
            tmp.flush()
            tmp.close()
            return tmp.name

        return value

class QwenTextToSpeechTaskService(TextToSpeechTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "torch", "transformers", "qwen_tts", "soundfile" ]

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
        import torch
        from qwen_tts import Qwen3TTSModel
        from mindor.dsl.schema.component import HuggingfaceModelConfig

        device = self._resolve_device()

        # qwen_tts handles model downloading internally via from_pretrained(),
        # so pass the repo ID directly instead of a snapshot_download() path.
        if isinstance(self.config.model, HuggingfaceModelConfig):
            model_id = self.config.model.repository
        else:
            model_id = self._get_model_path()

        model = Qwen3TTSModel.from_pretrained(
            model_id,
            device_map=device,
            dtype=torch.bfloat16,
            trust_remote_code=True,
        )

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await QwenTextToSpeechTaskAction(action, self.model, self.device).run(context)
