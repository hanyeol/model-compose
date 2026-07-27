from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Callable, Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.dsl.schema.action import KokoroTextToSpeechModelGenerateActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ......base import ComponentActionContext
from ..common import TextToSpeechTaskService, TextToSpeechTaskAction

if TYPE_CHECKING:
    import torch

# ISO 639-1 → Kokoro `KPipeline` lang_code. Kokoro uses single-letter codes
# from misaki's g2p namespace; see https://github.com/hexgrad/kokoro for the
# authoritative list. Regional variants ("en-gb", "pt-br") can be selected
# via the mapping below; bare "en"/"pt" fall through to the general default.
_KOKORO_LANG_CODE_MAP: Dict[str, str] = {
    "en":    "a",  # American English (default for bare "en")
    "en-us": "a",
    "en-gb": "b",  # British English
    "ja":    "j",  # Japanese
    "zh":    "z",  # Mandarin Chinese
    "es":    "e",  # Spanish
    "fr":    "f",  # French
    "hi":    "h",  # Hindi
    "it":    "i",  # Italian
    "pt":    "p",  # Brazilian Portuguese
    "pt-br": "p",
}

_KOKORO_DEFAULT_LANG_CODE = "a"

class KokoroTextToSpeechGenerateTaskAction(TextToSpeechTaskAction):
    config: KokoroTextToSpeechModelGenerateActionConfig

    def __init__(
        self,
        config: KokoroTextToSpeechModelGenerateActionConfig,
        pipeline_provider: Callable[[str], Any],
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.pipeline_provider = pipeline_provider

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        voice    = await context.render_variable(self.config.voice)
        speed    = await context.render_variable(self.config.speed)
        language = await context.render_variable(self.config.language)

        params.update({
            "voice":     voice or "af_heart",
            "speed":     float(speed) if speed is not None else 1.0,
            "lang_code": self._resolve_lang_code(language),
        })

        return params

    async def _generate(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[StreamResource]:
        def _generate() -> List[StreamResource]:
            pipeline = self.pipeline_provider(params["lang_code"])
            results: List[StreamResource] = []

            for text in texts:
                samples, sample_rate = self._synthesize(pipeline, text, params["voice"], params["speed"])
                frames, channels = encode_waveform_to_pcm(samples)

                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(sample_rate),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

    def _synthesize(self, pipeline: Any, text: str, voice: str, speed: float) -> Tuple[Any, int]:
        import numpy as np

        chunks = []
        for _, _, audio in pipeline(text, voice=voice, speed=speed):
            chunks.append(audio)

        samples = np.concatenate(chunks, axis=0) if len(chunks) > 1 else chunks[0]

        return samples, 24000

    def _resolve_lang_code(self, language: Optional[str]) -> str:
        if language:
            language = language.lower().replace("_", "-")
            primary_language = language.split("-")[0]

            for language in (language, primary_language):
                if language in _KOKORO_LANG_CODE_MAP:
                    return _KOKORO_LANG_CODE_MAP[language]

        return _KOKORO_DEFAULT_LANG_CODE

class KokoroTextToSpeechTaskService(TextToSpeechTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # One pipeline per Kokoro lang_code. Loaded lazily on first request
        # for that language and cached for the lifetime of the service, since
        # each pipeline pulls in language-specific g2p resources.
        self.pipelines: Dict[str, Any] = {}
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "kokoro", "torch", "numpy", "soundfile" ]

    async def _load_model(self) -> None:
        self.device = self._resolve_device(self.config.device)
        self._get_or_create_pipeline(_KOKORO_DEFAULT_LANG_CODE)

    async def _unload_model(self) -> None:
        self.pipelines = {}
        self.device = None

    def _get_or_create_pipeline(self, lang_code: str) -> Any:
        pipeline = self.pipelines.get(lang_code)

        if pipeline is None:
            from kokoro import KPipeline
            pipeline = KPipeline(lang_code=lang_code, device=str(self.device))
            self.pipelines[lang_code] = pipeline

        return pipeline

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == TextToSpeechActionMethod.GENERATE:
            return await KokoroTextToSpeechGenerateTaskAction(action, self._get_or_create_pipeline, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
