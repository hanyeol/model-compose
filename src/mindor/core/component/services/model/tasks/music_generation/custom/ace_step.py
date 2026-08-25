from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import (
    ModelActionConfig,
    MusicGenerationActionMethod,
    AceStepMusicGenerationModelGenerateActionConfig,
    AceStepMusicGenerationModelCoverActionConfig,
    AceStepMusicGenerationModelRewriteActionConfig,
    AceStepMusicGenerationModelExtendActionConfig,
    AceStepMusicGenerationModelLayerActionConfig,
    AceStepMusicGenerationModelAccompanyActionConfig,
)
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from mindor.core.logger import logging
from ....base import ComponentActionContext, ModelTaskService
from ..common import MusicGenerationTaskAction

if TYPE_CHECKING:
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler

class AceStepMusicGenerationTaskAction(MusicGenerationTaskAction):
    def __init__(self, config: Any, handler: AceStepHandler, llm_handler: Optional[LLMHandler], thinking_scope: List[str]):
        super().__init__(config)

        self.handler: AceStepHandler = handler
        self.llm_handler: Optional[LLMHandler] = llm_handler
        self.thinking_scope: List[str] = thinking_scope

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        time_signature  = await context.render_variable(self.config.params.time_signature)
        inference_steps = await context.render_variable(self.config.params.inference_steps)
        guidance_scale  = await context.render_variable(self.config.params.guidance_scale)

        params.update({
            "time_signature":  time_signature,
            "inference_steps": inference_steps,
            "guidance_scale":  guidance_scale,
        })

        return params

class AceStepMusicGenerationModelGenerateAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelGenerateActionConfig

    def __init__(self, config: AceStepMusicGenerationModelGenerateActionConfig, handler: AceStepHandler, llm_handler: Optional[LLMHandler], thinking_scope: List[str]):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        prompt = await context.render_text(self.config.prompt)
        lyrics = await context.render_text(self.config.lyrics) if self.config.lyrics is not None else None

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator)) or isinstance(lyrics, (StreamIterator, AsyncIterator))

        return (prompt, lyrics), is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        def _generate() -> List[Any]:
            from acestep.inference import generate_music, GenerationParams, GenerationConfig

            generation_config = GenerationConfig(
                batch_size=1,
                audio_format="wav",
            )

            results: List[Any] = []

            for prompt, song_lyrics in batch_input:
                generation_params = GenerationParams(
                    caption=prompt,
                    lyrics=song_lyrics or "",
                    duration=int(params["duration"]),
                    bpm=int(params["bpm"]),
                    keyscale=params["key_scale"] or "",
                    timesignature=params["time_signature"] or "",
                    inference_steps=int(params["inference_steps"]),
                    guidance_scale=float(params["guidance_scale"]),
                    seed=int(params["seed"]) if params["seed"] is not None else -1,
                    thinking="codes" in self.thinking_scope,
                    use_cot_metas="metas" in self.thinking_scope,
                    use_cot_caption="caption" in self.thinking_scope,
                    use_cot_language="language" in self.thinking_scope,
                )

                result = generate_music(
                    dit_handler=self.handler,
                    llm_handler=self.llm_handler,
                    params=generation_params,
                    config=generation_config,
                )

                if not result.success:
                    raise RuntimeError(f"Music generation failed: {result.error}")

                frames, channels = encode_waveform_to_pcm(result.audios[0]["tensor"])
                sample_rate = result.audios[0].get("sample_rate", 48000)

                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(sample_rate),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

class AceStepMusicGenerationModelCoverAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelCoverActionConfig

    def __init__(self, config: AceStepMusicGenerationModelCoverActionConfig, handler: AceStepHandler, llm_handler: Optional[LLMHandler], thinking_scope: List[str]):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        raise NotImplementedError("ACE-Step cover generation is not implemented yet.")

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        raise NotImplementedError("ACE-Step cover generation is not implemented yet.")

class AceStepMusicGenerationModelRewriteAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelRewriteActionConfig

    def __init__(self, config: AceStepMusicGenerationModelRewriteActionConfig, handler: AceStepHandler, llm_handler: Optional[LLMHandler], thinking_scope: List[str]):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        raise NotImplementedError("ACE-Step rewrite is not implemented yet.")

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        raise NotImplementedError("ACE-Step rewrite is not implemented yet.")

class AceStepMusicGenerationModelExtendAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelExtendActionConfig

    def __init__(self, config: AceStepMusicGenerationModelExtendActionConfig, handler: AceStepHandler, llm_handler: Optional[LLMHandler], thinking_scope: List[str]):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        raise NotImplementedError("ACE-Step extend is not implemented yet.")

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        raise NotImplementedError("ACE-Step extend is not implemented yet.")

class AceStepMusicGenerationModelLayerAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelLayerActionConfig

    def __init__(self, config: AceStepMusicGenerationModelLayerActionConfig, handler: AceStepHandler, llm_handler: Optional[LLMHandler], thinking_scope: List[str]):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        raise NotImplementedError("ACE-Step layer generation is not implemented yet.")

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        raise NotImplementedError("ACE-Step layer generation is not implemented yet.")

class AceStepMusicGenerationModelAccompanyAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelAccompanyActionConfig

    def __init__(self, config: AceStepMusicGenerationModelAccompanyActionConfig, handler: AceStepHandler, llm_handler: Optional[LLMHandler], thinking_scope: List[str]):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        raise NotImplementedError("ACE-Step accompany (vocal-to-BGM) is not implemented yet.")

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        raise NotImplementedError("ACE-Step accompany (vocal-to-BGM) is not implemented yet.")

class AceStepMusicGenerationTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.handler: Optional[AceStepHandler] = None
        self.llm_handler: Optional[LLMHandler] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            "torch==2.10.0+cu128@https://download.pytorch.org/whl/cu128",
            "torchaudio==2.10.0+cu128@https://download.pytorch.org/whl/cu128",
            "torchvision==0.25.0+cu128@https://download.pytorch.org/whl/cu128",
            "flash-attn==2.8.1@https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.1/flash_attn-2.8.1+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl",
            "nano-vllm@git+https://github.com/GeeeekExplorer/nano-vllm.git",
            "ace-step@git+https://github.com/ace-step/ACE-Step-1.5.git",
            "numpy",
            "soundfile"
        ]

    async def _load_model(self) -> None:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            raise ValueError("ACE-Step does not support HuggingFace Hub models. Use a local model path instead.")

        model_path = await self._provision_model(self.config.model, prefetch=True)
        self.handler = await self._load_generation_handler(model_path)

        if self.config.thinking_model:
            self.llm_handler = await self._load_llm_handler(model_path)

    async def _unload_model(self) -> None:
        if self.llm_handler is not None:
            self.llm_handler.unload()
            self.llm_handler = None

        self.handler = None

    async def _load_generation_handler(self, model_path: str) -> AceStepHandler:
        from acestep.handler import AceStepHandler
        import torch

        handler = AceStepHandler()
        handler.initialize_service(
            project_root=model_path,
            config_path=self.config.preset,
            device=self._resolve_device(self.config.device).type,
        )

        if self.config.precision is not None:
            handler.dtype = getattr(torch, self.config.precision.value)

        return handler

    async def _load_llm_handler(self, model_path: str) -> LLMHandler:
        from acestep.llm_inference import LLMHandler
        import os, torch

        dtype = getattr(torch, self.config.precision.value) if self.config.precision is not None else None

        handler = LLMHandler()
        status, success = handler.initialize(
            checkpoint_dir=os.path.dirname(model_path),
            lm_model_path=self.config.thinking_model,
            device=self._resolve_device(self.config.device).type,
            dtype=dtype,
        )

        if not success:
            raise RuntimeError(f"Failed to initialize 5Hz LM: {status}")

        return handler

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        thinking_scope = list(self.config.thinking_scope) if self.llm_handler is not None else []

        if action.method == MusicGenerationActionMethod.GENERATE:
            return await AceStepMusicGenerationModelGenerateAction(action, self.handler, self.llm_handler, thinking_scope).run(context)

        if action.method == MusicGenerationActionMethod.COVER:
            return await AceStepMusicGenerationModelCoverAction(action, self.handler, self.llm_handler, thinking_scope).run(context)

        if action.method == MusicGenerationActionMethod.REWRITE:
            return await AceStepMusicGenerationModelRewriteAction(action, self.handler, self.llm_handler, thinking_scope).run(context)

        if action.method == MusicGenerationActionMethod.EXTEND:
            return await AceStepMusicGenerationModelExtendAction(action, self.handler, self.llm_handler, thinking_scope).run(context)

        if action.method == MusicGenerationActionMethod.LAYER:
            return await AceStepMusicGenerationModelLayerAction(action, self.handler, self.llm_handler, thinking_scope).run(context)

        if action.method == MusicGenerationActionMethod.ACCOMPANY:
            return await AceStepMusicGenerationModelAccompanyAction(action, self.handler, self.llm_handler, thinking_scope).run(context)

        raise ValueError(f"Unknown method: {action.method}")
