from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Callable, Dict, Optional, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.dsl.schema.action import SupertonicTextToSpeechModelGenerateActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ......base import ComponentActionContext
from ....base import ModelTaskDriver
from ..common import TextToSpeechTaskAction

if TYPE_CHECKING:
    import torch

# Supertonic 3 renders at 44.1 kHz for every voice/language combo.
_SUPERTONIC_SAMPLE_RATE = 44100

# ISO 639-1 codes Supertonic 3 handles natively; `na` is its language-agnostic
# fallback for inputs outside this set. See https://pypi.org/project/supertonic/.
_SUPERTONIC_SUPPORTED_LANGUAGES = {
    "ar", "bg", "cs", "da", "de", "el", "en", "es", "et", "fi",
    "fr", "hi", "hr", "hu", "id", "it", "ja", "ko", "lt", "lv",
    "nl", "pl", "pt", "ro", "ru", "sk", "sl", "sv", "tr", "uk",
    "vi",
}

_SUPERTONIC_DEFAULT_LANGUAGE = "en"

class SupertonicTextToSpeechGenerateTaskAction(TextToSpeechTaskAction):
    config: SupertonicTextToSpeechModelGenerateActionConfig

    def __init__(
        self,
        config: SupertonicTextToSpeechModelGenerateActionConfig,
        model: Any,
        voice_style_resolver: Callable[[str], Any],
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model = model
        self.voice_style_resolver = voice_style_resolver

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        voice            = await context.render_variable(self.config.voice)
        speed            = await context.render_scalar(self.config.speed, float)
        total_steps      = await context.render_scalar(self.config.total_steps, int)
        max_chunk_length = await context.render_scalar(self.config.max_chunk_length, int)
        silence_duration = await context.render_scalar(self.config.silence_duration, float)
        language         = self._resolve_language(await context.render_variable(self.config.language))

        params.update({
            "voice":            voice or "F1",
            "speed":            speed,
            "total_steps":      total_steps,
            "max_chunk_length": max_chunk_length,
            "silence_duration": silence_duration,
            "language":         language,
        })

        return params

    async def _generate_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[StreamResource]:
        def _generate() -> List[StreamResource]:
            results: List[StreamResource] = []

            # Pass only the synthesize_params the caller set; leave the rest to the
            # library's own defaults (total_steps=8, speed=1.05, etc).
            synthesize_params: Dict[str, Any] = {
                "voice_style": self.voice_style_resolver(params["voice"]),
                "lang":        params["language"],
            }

            for key in ("speed", "total_steps", "max_chunk_length", "silence_duration"):
                if params[key] is not None:
                    synthesize_params[key] = params[key]

            for text in texts:
                # synthesize() returns (wav[(1, num_samples) float32], duration).
                # Drop the batch dim so encode_waveform_to_pcm treats it as mono.
                wav, _ = self.model.synthesize(text=text, **synthesize_params)
                frames, channels = encode_waveform_to_pcm(wav[0])

                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(_SUPERTONIC_SAMPLE_RATE),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

    def _resolve_language(self, language: Optional[str]) -> str:
        if language:
            language = language.lower().replace("_", "-").split("-")[0]
            if language in _SUPERTONIC_SUPPORTED_LANGUAGES:
                return language
            # `na` is Supertonic's language-agnostic fallback for codes it
            # doesn't model directly; preferable to silently defaulting to en.
            return "na"

        return _SUPERTONIC_DEFAULT_LANGUAGE

class SupertonicTextToSpeechTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.voice_styles: Dict[str, Any] = {}
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            "supertonic",
            "numpy",
            "soundfile",
        ]

    async def _load_model(self) -> None:
        from supertonic import TTS

        # supertonic ships its own HF-hub fetch, but we route the download
        # through _provision_model so revision pinning, cache_dir, etc. come
        # from the component config. The returned path is a complete snapshot
        # dir; auto_download=False keeps the library from re-fetching.
        model_dir = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        def _load() -> Any:
            return TTS(model_dir=model_dir, auto_download=False)

        self.model, self.device = await self._run_in_executor(_load), device

    async def _unload_model(self) -> None:
        self.model = None
        self.voice_styles = {}
        self.device = None

    def _resolve_voice_style(self, voice: str) -> Any:
        voice_style = self.voice_styles.get(voice)

        if voice_style is None:
            # Treat any value with a path separator or a .json suffix as a
            # custom Voice Builder export; everything else is a built-in ID
            # (M1-M5, F1-F5).
            if "/" in voice or voice.lower().endswith(".json"):
                voice_style = self.model.get_voice_style_from_path(voice)
            else:
                voice_style = self.model.get_voice_style(voice_name=voice)

            self.voice_styles[voice] = voice_style

        return voice_style

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == TextToSpeechActionMethod.GENERATE:
            return await SupertonicTextToSpeechGenerateTaskAction(
                action,
                self.model,
                self._resolve_voice_style,
                self.device
            ).run(context)

        raise ValueError(f"Unknown method: {action.method}")
