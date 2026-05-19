from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, AceStepMusicGenerationModelActionConfig
from mindor.core.logger import logging
from ...base import ComponentActionContext
from .common import MusicGenerationTaskService, MusicGenerationTaskAction
import asyncio, io

if TYPE_CHECKING:
    from acestep.handler import AceStepHandler

class AceStepMusicGenerationTaskAction(MusicGenerationTaskAction):
    def __init__(self, config: AceStepMusicGenerationModelActionConfig, handler: AceStepHandler):
        super().__init__(config)

        self.config: AceStepMusicGenerationModelActionConfig = config
        self.handler: AceStepHandler = handler

    async def _generate(self, prompt: str, lyrics: Optional[str], params: Dict[str, Any]) -> bytes:
        from acestep.inference import generate_music, GenerationParams, GenerationConfig
        import soundfile as sf

        generation_params = GenerationParams(
            caption=prompt,
            lyrics=lyrics or "",
            duration=int(params["duration"]),
            bpm=int(params["bpm"]),
            key_scale=params["key_scale"],
            time_signature=params["time_signature"],
            inference_steps=int(params["inference_steps"]),
            guidance_scale=float(params["guidance_scale"]),
            seed=int(params["seed"]) if params["seed"] is not None else None,
        )

        generation_config = GenerationConfig(
            batch_size=1,
            audio_format="wav",
        )

        result = generate_music(
            dit_handler=self.handler,
            llm_handler=None,
            params=generation_params,
            config=generation_config,
        )

        if not result.success:
            raise RuntimeError(f"Music generation failed: {result.error}")

        audio_tensor = result.audios[0]["tensor"]
        sample_rate = result.audios[0].get("sample_rate", 48000)

        buffer = io.BytesIO()
        sf.write(buffer, audio_tensor, sample_rate, format="WAV")

        return buffer.getvalue()

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_generation_params(context)

        params["time_signature" ] = await context.render_variable(self.config.params.time_signature)
        params["inference_steps"] = await context.render_variable(self.config.params.inference_steps)
        params["guidance_scale" ] = await context.render_variable(self.config.params.guidance_scale)
        params["seed"           ] = await context.render_variable(self.config.params.seed)

        return params

class AceStepMusicGenerationTaskService(MusicGenerationTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.handler: Optional[AceStepHandler] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "ace-step@git+https://github.com/ace-step/ACE-Step-1.5.git", "soundfile" ]

    def _load_model(self) -> None:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            raise ValueError("ACE-Step does not support HuggingFace Hub models. Use a local model path instead.")

        self.handler = self._load_generation_handler()

    def _unload_model(self) -> None:
        self.handler = None

    def _load_generation_handler(self) -> AceStepHandler:
        from acestep.handler import AceStepHandler

        handler = AceStepHandler()
        handler.initialize_service(
            project_root=self._get_model_path(),
            config_path=self.config.preset,
            device=str(self.config.device),
        )

        return handler

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await AceStepMusicGenerationTaskAction(action, self.handler).run(context)
