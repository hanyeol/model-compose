from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import (
    ModelActionConfig,
    MusicGenerationActionMethod,
    CommonAceStepMusicGenerationModelActionConfig,
    AceStepMusicGenerationModelGenerateActionConfig,
    AceStepMusicGenerationModelCoverActionConfig,
    AceStepMusicGenerationModelRewriteActionConfig,
    AceStepMusicGenerationModelExtendActionConfig,
    AceStepMusicGenerationModelLayerActionConfig,
    AceStepMusicGenerationModelAccompanyActionConfig,
)
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ......action.media import MediaInputPathResolver
from ....base import ComponentActionContext, ModelTaskService
from ..common import MusicGenerationTaskAction
import os

if TYPE_CHECKING:
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler

class AceStepMusicGenerationTaskAction(MusicGenerationTaskAction):
    config: CommonAceStepMusicGenerationModelActionConfig

    def __init__(
        self,
        config: CommonAceStepMusicGenerationModelActionConfig,
        handler: AceStepHandler,
        llm_handler: Optional[LLMHandler],
        thinking_scope: List[str],
    ):
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

    async def _resolve_source_paths(self, sources: List[MediaSource]) -> List[Tuple[str, bool]]:
        paths: List[Tuple[str, bool]] = []

        for source in sources:
            path, spooled = await MediaInputPathResolver().resolve(source)
            paths.append((path, spooled))

        return paths

    def _build_generation_params(
        self,
        prompt: Optional[str],
        lyrics: Optional[str],
        params: Dict[str, Any],
        task_type: str,
        src_audio: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Any:
        from acestep.inference import GenerationParams

        generation_params = GenerationParams(
            task_type=task_type,
            caption=prompt or "",
            lyrics=lyrics or "",
            duration=int(params["duration"]),
            bpm=int(params["bpm"]),
            keyscale=params["key_scale"] or "",
            timesignature=params["time_signature"] or "",
            inference_steps=int(params["inference_steps"]),
            guidance_scale=float(params["guidance_scale"]),
            src_audio=src_audio or None,
            thinking="codes" in self.thinking_scope,
            use_cot_metas="metas" in self.thinking_scope,
            use_cot_caption="caption" in self.thinking_scope,
            use_cot_language="language" in self.thinking_scope,
        )

        for name, value in (extra or {}).items():
            setattr(generation_params, name, value)

        return generation_params

    def _generate_music(self, generation_params: Any, seed: Optional[int] = None) -> "PcmStreamResource":
        from acestep.inference import generate_music, GenerationConfig

        result = generate_music(
            dit_handler=self.handler,
            llm_handler=self.llm_handler,
            params=generation_params,
            config=GenerationConfig(
                batch_size=1,
                audio_format="wav",
                seeds=[ seed ] if seed is not None else None,
                use_random_seed=bool(seed is None),
            ),
        )

        if not result.success:
            raise RuntimeError(f"Music generation failed: {result.error}")

        frames, channels = encode_waveform_to_pcm(result.audios[0]["tensor"])
        sample_rate = result.audios[0].get("sample_rate", 48000)

        return PcmStreamResource(frames, {
            "sample_rate": str(sample_rate),
            "channels":    str(channels),
            "bit_depth":   "16",
        })

    @staticmethod
    def _cleanup_source_paths(source_paths: List[Tuple[str, bool]]) -> None:
        for path, spooled in source_paths:
            if spooled:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

class AceStepMusicGenerationModelGenerateAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelGenerateActionConfig

    def __init__(
        self,
        config: AceStepMusicGenerationModelGenerateActionConfig,
        handler: AceStepHandler,
        llm_handler: Optional[LLMHandler],
        thinking_scope: List[str],
    ):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        prompt = await context.render_text(self.config.prompt)
        lyrics = await context.render_text(self.config.lyrics) if self.config.lyrics is not None else None

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (prompt, lyrics))

        return (prompt, lyrics), is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        def _generate() -> List[Any]:
            results: List[PcmStreamResource] = []

            for prompt, lyrics in batch_input:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break
                generation_params = self._build_generation_params(prompt, lyrics, params, task_type="text2music")
                results.append(self._generate_music(generation_params, seed=params["seed"]))

            return results

        return await self._run_in_executor(_generate)

class AceStepMusicGenerationModelCoverAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelCoverActionConfig

    def __init__(
        self,
        config: AceStepMusicGenerationModelCoverActionConfig,
        handler: AceStepHandler,
        llm_handler: Optional[LLMHandler],
        thinking_scope: List[str],
    ):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        source = await context.render_audio(self.config.source)
        prompt = await context.render_text(self.config.prompt)
        lyrics = await context.render_text(self.config.lyrics) if self.config.lyrics is not None else None

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (source, prompt, lyrics))

        return (source, prompt, lyrics), is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        sources: List[MediaSource] = [ source for source, _, _ in batch_input ]
        source_paths = await self._resolve_source_paths(sources)

        def _generate() -> List[PcmStreamResource]:
            results: List[PcmStreamResource] = []

            for (_, prompt, lyrics), (src_path, _) in zip(batch_input, source_paths):
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break
                generation_params = self._build_generation_params(
                    prompt, lyrics, params,
                    task_type="cover",
                    src_audio=src_path,
                )
                results.append(self._generate_music(generation_params, seed=params["seed"]))

            return results

        try:
            return await self._run_in_executor(_generate)
        finally:
            self._cleanup_source_paths(source_paths)

class AceStepMusicGenerationModelRewriteAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelRewriteActionConfig

    def __init__(
        self,
        config: AceStepMusicGenerationModelRewriteActionConfig,
        handler: AceStepHandler,
        llm_handler: Optional[LLMHandler],
        thinking_scope: List[str],
    ):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        source = await context.render_audio(self.config.source)
        prompt = await context.render_text(self.config.prompt)
        lyrics = await context.render_text(self.config.lyrics) if self.config.lyrics is not None else None

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (source, prompt, lyrics))

        return (source, prompt, lyrics), is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        params["start_time"] = await context.render_scalar(self.config.start_time, "time")
        params["end_time"]   = await context.render_scalar(self.config.end_time,   "time")

        return params

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        sources: List[MediaSource] = [ source for source, _, _ in batch_input ]
        source_paths = await self._resolve_source_paths(sources)

        def _generate() -> List[PcmStreamResource]:
            results: List[PcmStreamResource] = []

            for (_, prompt, lyrics), (src_path, _) in zip(batch_input, source_paths):
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break
                generation_params = self._build_generation_params(
                    prompt, lyrics, params,
                    task_type="repaint",
                    src_audio=src_path,
                    extra={
                        "repainting_start": float(params["start_time"]),
                        "repainting_end":   float(params["end_time"]),
                    },
                )
                results.append(self._generate_music(generation_params, seed=params["seed"]))

            return results

        try:
            return await self._run_in_executor(_generate)
        finally:
            self._cleanup_source_paths(source_paths)

class AceStepMusicGenerationModelExtendAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelExtendActionConfig

    def __init__(
        self,
        config: AceStepMusicGenerationModelExtendActionConfig,
        handler: AceStepHandler,
        llm_handler: Optional[LLMHandler],
        thinking_scope: List[str],
    ):
        super().__init__(config, handler, llm_handler, thinking_scope)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        source = await context.render_audio(self.config.source)
        prompt = await context.render_text(self.config.prompt)
        lyrics = await context.render_text(self.config.lyrics) if self.config.lyrics is not None else None

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (source, prompt, lyrics))

        return (source, prompt, lyrics), is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        sources: List[MediaSource] = [ source for source, _, _ in batch_input ]
        source_paths = await self._resolve_source_paths(sources)

        def _generate() -> List[PcmStreamResource]:
            results: List[PcmStreamResource] = []

            for (_, prompt, lyrics), (src_path, _) in zip(batch_input, source_paths):
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break
                generation_params = self._build_generation_params(
                    prompt, lyrics, params,
                    task_type="complete",
                    src_audio=src_path,
                )
                results.append(self._generate_music(generation_params, seed=params["seed"]))

            return results

        try:
            return await self._run_in_executor(_generate)
        finally:
            self._cleanup_source_paths(source_paths)

class AceStepMusicGenerationModelLayerAction(AceStepMusicGenerationTaskAction):
    config: AceStepMusicGenerationModelLayerActionConfig

    def __init__(
        self,
        config: AceStepMusicGenerationModelLayerActionConfig,
        handler: AceStepHandler,
        llm_handler: Optional[LLMHandler],
        thinking_scope: List[str],
    ):
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

    def __init__(
        self,
        config: AceStepMusicGenerationModelAccompanyActionConfig,
        handler: AceStepHandler,
        llm_handler: Optional[LLMHandler],
        thinking_scope: List[str],
    ):
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
        requirements = [
            "torch==2.10.0+cu128@https://download.pytorch.org/whl/cu128",
            "torchaudio==2.10.0+cu128@https://download.pytorch.org/whl/cu128",
            "torchvision==0.25.0+cu128@https://download.pytorch.org/whl/cu128",
            "ace-step@git+https://github.com/ace-step/ACE-Step-1.5.git",
            "numpy",
            "soundfile",
        ]

        if self.config.thinking_model:
            # nano-vllm powers the 5Hz thinking LM. Install ACE-Step's vendored fork, not
            # upstream nano-vllm: the 5Hz LM checkpoint stores flat Qwen3Model weight names
            # (embed_tokens.weight, layers.*, norm.weight) and only the fork's loader maps
            # them onto Qwen3ForCausalLM — upstream fails with
            # "Qwen3ForCausalLM has no attribute `embed_tokens`". It must be installed after
            # ace-step, whose own `nano-vllm` dependency would otherwise pull in upstream.
            # flash-attn is intentionally omitted: its wheel is pinned to
            # cu128/torch2.10/cp312/linux_x86_64, and nano-vllm falls back to SDPA when it
            # isn't installed.
            requirements.append("nano-vllm@git+https://github.com/ace-step/ACE-Step-1.5.git#subdirectory=acestep/third_parts/nano-vllm")

        return requirements

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
            device=str(self._resolve_device(self.config.device)),
        )

        if self.config.precision is not None:
            handler.dtype = getattr(torch, self.config.precision.value)

        return handler

    async def _load_llm_handler(self, model_path: str) -> LLMHandler:
        from acestep.llm_inference import LLMHandler
        import torch

        dtype = getattr(torch, self.config.precision.value) if self.config.precision is not None else None

        handler = LLMHandler()
        status, success = handler.initialize(
            # Mirror the DiT handler's convention: project_root=<model_path>, so the LM
            # checkpoint lives under <model_path>/checkpoints/<thinking_model>.
            checkpoint_dir=os.path.join(model_path, "checkpoints"),
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
