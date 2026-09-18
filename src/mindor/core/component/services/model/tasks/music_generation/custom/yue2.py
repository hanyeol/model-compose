from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import (
    ModelActionConfig,
    MusicGenerationActionMethod,
    CommonYue2MusicGenerationModelActionConfig,
    Yue2MusicGenerationModelGenerateActionConfig,
    Yue2MusicGenerationModelCoverActionConfig,
    Yue2MusicGenerationModelScoreActionConfig,
)
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.utils.audio import encode_waveform_to_pcm
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import MusicGenerationTaskAction

if TYPE_CHECKING:
    from yue2 import YuE2Pipeline

# YuE2 renders 48 kHz stereo audio.
_YUE2_SAMPLE_RATE = 48000

class Yue2MusicGenerationTaskAction(MusicGenerationTaskAction):
    config: CommonYue2MusicGenerationModelActionConfig

    def __init__(self, config: CommonYue2MusicGenerationModelActionConfig, pipeline: "YuE2Pipeline"):
        super().__init__(config)

        self.pipeline: YuE2Pipeline = pipeline

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        cot_mode          = await context.render_variable(self.config.params.cot_mode)
        cot_mode          = cot_mode.value if hasattr(cot_mode, "value") else cot_mode
        cfg_scale         = await context.render_scalar(self.config.params.cfg_scale, float) if self.config.params.cfg_scale is not None else None
        abc_sampling      = await self._resolve_sampling(context, self.config.params.abc_sampling) if self.config.params.abc_sampling is not None else None
        semantic_sampling = await self._resolve_sampling(context, self.config.params.semantic_sampling) if self.config.params.semantic_sampling is not None else None

        params.update({
            "cot_mode":          cot_mode,
            "cfg_scale":         cfg_scale,
            "abc_sampling":      abc_sampling,
            "semantic_sampling": semantic_sampling,
        })

        return params

    async def _resolve_sampling(self, context: ComponentActionContext, sampling: Any) -> Dict[str, Any]:
        temperature        = await context.render_scalar(sampling.temperature, float) if sampling.temperature is not None else None
        top_p              = await context.render_scalar(sampling.top_p, float) if sampling.top_p is not None else None
        top_k              = await context.render_scalar(sampling.top_k, int) if sampling.top_k is not None else None
        repetition_penalty = await context.render_scalar(sampling.repetition_penalty, float) if sampling.repetition_penalty is not None else None
        penalty_window     = await context.render_scalar(sampling.penalty_window, int) if sampling.penalty_window is not None else None
        min_tokens         = await context.render_scalar(sampling.min_tokens, int) if sampling.min_tokens is not None else None
        max_tokens         = await context.render_scalar(sampling.max_tokens, int) if sampling.max_tokens is not None else None

        return {
            "temperature":        temperature,
            "top_p":              top_p,
            "top_k":              top_k,
            "repetition_penalty": repetition_penalty,
            "penalty_window":     penalty_window,
            "min_tokens":         min_tokens,
            "max_tokens":         max_tokens,
        }

    def _build_pipeline_params(self, style: str, lyrics: str, params: Dict[str, Any], abc: Optional[str] = None) -> Dict[str, Any]:
        pipeline_params: Dict[str, Any] = {
            "style":  style,
            "lyrics": lyrics,
            "cot":    params["cot_mode"],
        }

        if params.get("cfg_scale") is not None:
            pipeline_params["cfg_scale"] = float(params["cfg_scale"])

        if params.get("seed") is not None:
            pipeline_params["seed"] = int(params["seed"])

        if abc is not None:
            pipeline_params["abc"] = abc

        return pipeline_params

class Yue2MusicGenerationModelGenerateAction(Yue2MusicGenerationTaskAction):
    config: Yue2MusicGenerationModelGenerateActionConfig

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        style  = await context.render_text(self.config.style)
        lyrics = await context.render_text(self.config.lyrics)

        is_single_input    = not isinstance(style, (list, StreamIterator, AsyncIterator))
        is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (style, lyrics))

        return (style, lyrics), is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        def _generate() -> List[PcmStreamResource]:
            results: List[PcmStreamResource] = []

            for style, lyrics in inputs:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                pipeline_params = self._build_pipeline_params(style, lyrics, params)
                result = self.pipeline(
                    abc_sampling=params.get("abc_sampling"),
                    semantic_sampling=params.get("semantic_sampling"),
                    cancelled=(cancellation_token.is_cancelled if cancellation_token is not None else None),
                    **pipeline_params,
                )
                frames, channels = encode_waveform_to_pcm(result.audio)
                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(_YUE2_SAMPLE_RATE),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

class Yue2MusicGenerationModelCoverAction(Yue2MusicGenerationTaskAction):
    config: Yue2MusicGenerationModelCoverActionConfig

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        style  = await context.render_text(self.config.style)
        lyrics = await context.render_text(self.config.lyrics)
        abc    = await context.render_text(self.config.abc)

        is_single_input    = not isinstance(style, (list, StreamIterator, AsyncIterator))
        is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (style, lyrics, abc))

        return (style, lyrics, abc), is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        # Covers rely on a supplied ABC score, so force cot_mode to melody if the caller left it at the default.
        cot_mode = params.get("cot_mode") or "melody"
        if cot_mode == "off":
            raise ValueError("YuE2 cover action requires cot_mode='melody' or cot_mode='full' (cot_mode='off' cannot use an external ABC).")

        def _generate() -> List[PcmStreamResource]:
            results: List[PcmStreamResource] = []

            for style, lyrics, abc in inputs:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                pipeline_params = self._build_pipeline_params(style, lyrics, {**params, "cot_mode": cot_mode}, abc=abc)
                result = self.pipeline(
                    abc_sampling=params.get("abc_sampling"),
                    semantic_sampling=params.get("semantic_sampling"),
                    cancelled=(cancellation_token.is_cancelled if cancellation_token is not None else None),
                    **pipeline_params,
                )
                frames, channels = encode_waveform_to_pcm(result.audio)
                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(_YUE2_SAMPLE_RATE),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

class Yue2MusicGenerationModelScoreAction(Yue2MusicGenerationTaskAction):
    config: Yue2MusicGenerationModelScoreActionConfig

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        style  = await context.render_text(self.config.style)
        lyrics = await context.render_text(self.config.lyrics)

        is_single_input    = not isinstance(style, (list, StreamIterator, AsyncIterator))
        is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (style, lyrics))

        return (style, lyrics), is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        cot_mode = params.get("cot_mode") or "full"

        if cot_mode == "off":
            raise ValueError("YuE2 score action requires cot_mode='melody' or cot_mode='full' (cot_mode='off' does not produce an ABC score).")

        def _generate() -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []

            for style, lyrics in inputs:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                pipeline_params = self._build_pipeline_params(style, lyrics, {**params, "cot_mode": cot_mode})
                result = self.pipeline.plan(
                    abc_sampling=params.get("abc_sampling"),
                    cancelled=(cancellation_token.is_cancelled if cancellation_token is not None else None),
                    **pipeline_params,
                )
                results.append({
                    "abc":       result.abc,
                    "truncated": bool(getattr(result, "truncated", False)),
                })

            return results

        return await self._run_in_executor(_generate)

class Yue2MusicGenerationTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[YuE2Pipeline] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        # YuE2 pins torch==2.10.0 (see YuE/pyproject.toml); install a matching torch
        # ahead of the wheel so uv/pip doesn't drift the resolved version.
        return [
            *torch_requirements("torch==2.10.0"),
            "yue2-infer@https://github.com/multimodal-art-projection/YuE/releases/download/yue2-v0.1.6/yue2_infer-0.1.6-py3-none-any.whl",
        ]

    async def _load_model(self) -> None:
        model_path     = await self._provision_model(self.config.model, prefetch=True)
        vae_model_path = await self._provision_model(self.config.vae.model, prefetch=True)

        self.pipeline = await self._load_pipeline(model_path, vae_model_path)

    async def _unload_model(self) -> None:
        if self.pipeline is not None:
            self.pipeline.close()
            self.pipeline = None

    async def _load_pipeline(self, model_path: str, vae_model_path: str) -> "YuE2Pipeline":
        from yue2 import YuE2Pipeline

        def _load() -> "YuE2Pipeline":
            memory_budget_gib = float(self.config.memory_budget_gib)
            vae_core_frames = int(self.config.vae.tile_size) if self.config.vae.tile_size is not None else None

            return YuE2Pipeline.from_pretrained(
                model=model_path,
                vae=vae_model_path,
                device=str(self._resolve_device(self.config.device)),
                backend=self.config.backend.value,
                quantization=self.config.quantization.type.value if self.config.quantization is not None else "none",
                memory_budget_gib=memory_budget_gib,
                vae_core_frames=vae_core_frames,
                offload_ar=bool(self.config.offload_ar),
                verify_hashes=bool(self.config.verify_hashes),
                progress=False,
            )

        return await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == MusicGenerationActionMethod.GENERATE:
            return await Yue2MusicGenerationModelGenerateAction(action, self.pipeline).run(context)

        if action.method == MusicGenerationActionMethod.COVER:
            return await Yue2MusicGenerationModelCoverAction(action, self.pipeline).run(context)

        if action.method == MusicGenerationActionMethod.SCORE:
            return await Yue2MusicGenerationModelScoreAction(action, self.pipeline).run(context)

        raise ValueError(f"Unknown method: {action.method}")
