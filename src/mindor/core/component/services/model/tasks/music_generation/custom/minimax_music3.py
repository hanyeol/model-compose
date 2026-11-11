from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import (
    ModelActionConfig,
    MusicGenerationActionMethod,
    CommonMinimaxMusic3MusicGenerationModelActionConfig,
    MinimaxMusic3MusicGenerationModelGenerateActionConfig,
)
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import MusicGenerationTaskAction

if TYPE_CHECKING:
    from diffusers import MiniMaxMusic3ModularPipeline
    import torch

class MinimaxMusic3MusicGenerationTaskAction(MusicGenerationTaskAction):
    config: CommonMinimaxMusic3MusicGenerationModelActionConfig

    def __init__(self, config: CommonMinimaxMusic3MusicGenerationModelActionConfig, pipeline: MiniMaxMusic3ModularPipeline, device: torch.device, sampling_rate: int):
        super().__init__(config)

        self.pipeline: MiniMaxMusic3ModularPipeline = pipeline
        self.device: torch.device = device
        self.sampling_rate: int = sampling_rate

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        duration = await context.render_scalar(self.config.params.duration, float)

        params.update({
            "duration": duration,
        })

        return params

class MinimaxMusic3MusicGenerationModelGenerateAction(MinimaxMusic3MusicGenerationTaskAction):
    config: MinimaxMusic3MusicGenerationModelGenerateActionConfig

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        prompt = await context.render_text(self.config.prompt)
        lyrics = await context.render_text(self.config.lyrics) if self.config.lyrics is not None else None

        primary_input      = next((value for value in (prompt, lyrics) if isinstance(value, (StreamIterator, AsyncIterator))), None)
        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = primary_input is not None

        return (prompt, lyrics), primary_input, is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        import torch

        def _generate() -> List[PcmStreamResource]:
            results: List[PcmStreamResource] = []

            for prompt, lyrics in inputs:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                pipeline_params: Dict[str, Any] = {
                    "prompt":         prompt,
                    "lyrics":         lyrics or "",
                    "audio_duration": params["duration"],
                    "output":         "audios",
                }

                if params["seed"] is not None:
                    pipeline_params["generator"] = torch.Generator(self.device).manual_seed(params["seed"])

                audios = self.pipeline(**pipeline_params)
                audio = audios[0]

                frames, channels = encode_waveform_to_pcm(audio)
                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(self.sampling_rate),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

class MinimaxMusic3MusicGenerationTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipeline: Optional[MiniMaxMusic3ModularPipeline] = None
        self.device: Optional[torch.device] = None
        self.sampling_rate: int = 44100

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch", "torchaudio"),
            "diffusers>=0.40.0",
            "transformers",
            "accelerate",
            "soundfile",
        ]

    async def _load_model(self) -> None:
        model_path = await self._provision_model(self.config.model, prefetch=True)
        self.pipeline, self.device = await self._load_pipeline(model_path)
        self.sampling_rate = int(getattr(self.pipeline, "sampling_rate", 44100))

    async def _unload_model(self) -> None:
        self.pipeline = None

    async def _load_pipeline(self, model_path: str) -> Tuple[MiniMaxMusic3ModularPipeline, torch.device]:
        from diffusers import MiniMaxMusic3ModularPipeline
        import torch

        device = str(self._resolve_device(self.config.device))

        if self.config.precision is not None:
            dtype = self._resolve_torch_dtype(self.config.precision)
        else:
            dtype = torch.bfloat16

        def _load() -> MiniMaxMusic3ModularPipeline:
            pipeline = MiniMaxMusic3ModularPipeline.from_pretrained(model_path)
            pipeline.load_components(dtype=dtype)
            pipeline.to(device)

            return pipeline

        pipeline = await self._run_in_executor(_load)

        return pipeline, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == MusicGenerationActionMethod.GENERATE:
            return await MinimaxMusic3MusicGenerationModelGenerateAction(action, self.pipeline, self.pipeline.device, self.sampling_rate).run(context)

        raise ValueError(f"Unknown method: {action.method}")
