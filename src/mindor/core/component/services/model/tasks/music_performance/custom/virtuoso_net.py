from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import (
    ModelActionConfig,
    MusicPerformanceActionMethod,
    VirtuosoNetComposer,
    VirtuosoNetMusicPerformanceModelRenderActionConfig,
)
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import MusicPerformanceTaskAction
import os, glob, shutil, tempfile

if TYPE_CHECKING:
    from virtuoso.inference import InferenceModel
    import torch

# dasaem/virtuosonet publishes a single canonical pair. We only need the
# weights + yml; .gitattributes and README are skipped to keep the snapshot
# small when the user points `model` at the repo id.
_VIRTUOSO_NET_CHECKPOINT_FILENAME = "checkpoint_best.pt"
_VIRTUOSO_NET_CONFIG_FILENAME = "han_measnote_gru.yml"
_VIRTUOSO_NET_ALLOW_PATTERNS = [ _VIRTUOSO_NET_CHECKPOINT_FILENAME, _VIRTUOSO_NET_CONFIG_FILENAME ]

class VirtuosoNetMusicPerformanceModelRenderAction(MusicPerformanceTaskAction):
    config: VirtuosoNetMusicPerformanceModelRenderActionConfig

    def __init__(
        self,
        config: VirtuosoNetMusicPerformanceModelRenderActionConfig,
        inference_model: InferenceModel,
    ):
        super().__init__(config)

        self.inference_model: InferenceModel = inference_model

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        score = await context.render_file(self.config.score)

        primary_input      = score if isinstance(score, (StreamIterator, AsyncIterator)) else None
        is_single_input    = not isinstance(score, (list, StreamIterator, AsyncIterator))
        is_streaming_input = primary_input is not None

        return (score,), primary_input, is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        composer               = await context.render_scalar(self.config.composer, str)
        qpm_primo              = await context.render_scalar(self.config.params.qpm_primo, float)
        bool_pedal             = await context.render_scalar(self.config.params.bool_pedal, bool)
        disklavier             = await context.render_scalar(self.config.params.disklavier, bool)
        multi_instruments      = await context.render_scalar(self.config.params.multi_instruments, bool)
        tempo_clock            = await context.render_scalar(self.config.params.tempo_clock, bool)
        clock_interval_in_16th = await context.render_scalar(self.config.params.clock_interval_in_16th, int)
        velocity_multiplier    = await context.render_scalar(self.config.params.velocity_multiplier, float)

        try:
            composer = VirtuosoNetComposer(composer)
        except ValueError:
            raise ValueError(f"Invalid composer: {composer}")

        params.update({
            "composer":               composer.value,
            "qpm_primo":              qpm_primo,
            "bool_pedal":             bool_pedal,
            "disklavier":             disklavier,
            "multi_instruments":      multi_instruments,
            "tempo_clock":            tempo_clock,
            "clock_interval_in_16th": clock_interval_in_16th,
            "velocity_multiplier":    velocity_multiplier,
        })

        return params

    async def _render_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        def _render() -> List[BytesStreamResource]:
            results: List[BytesStreamResource] = []

            for (score_path,) in inputs:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                results.append(self._render(score_path, params))

            return results

        return await self._run_in_executor(_render)

    def _render(self, score_path: str, params: Dict[str, Any]) -> BytesStreamResource:
        import torch

        decode_overrides = {
            "bool_pedal":            params["bool_pedal"],
            "for_disklavier":        params["disklavier"],
            "multi_instruments":     params["multi_instruments"],
            "tempo_clock":           params["tempo_clock"],
            "clock_interval_in_16th": params["clock_interval_in_16th"],
            "velocity_multiplier":   params["velocity_multiplier"],
        }

        # InferenceModel reads midi_decode_options and output_path fresh at each
        # infer_xml() call, so pushing per-request overrides here works without
        # rebuilding the model. Restore the previous values after the call so
        # concurrent requests aren't affected.
        saved_options = dict(self.inference_model.midi_decode_options)
        saved_output_path = self.inference_model.output_path

        output_dir = tempfile.mkdtemp(prefix="virtuoso-net-")

        try:
            self.inference_model.midi_decode_options.update(decode_overrides)
            self.inference_model.output_path = output_dir

            if params["seed"] is not None:
                torch.manual_seed(params["seed"])

            self.inference_model.infer_xml(
                xml_path=score_path,
                composer_name=params["composer"],
                qpm_primo=params["qpm_primo"],
            )

            midi_paths = glob.glob(os.path.join(output_dir, "*.mid"))

            if not midi_paths:
                raise RuntimeError(f"VirtuosoNet produced no MIDI output for score '{score_path}'.")

            # infer_xml writes exactly one MIDI per call; take the first match
            # defensively in case upstream ever adds auxiliary files.
            midi_path = midi_paths[0]
            midi_filename = os.path.basename(midi_path)

            with open(midi_path, "rb") as f:
                midi_bytes = f.read()
        finally:
            self.inference_model.midi_decode_options.clear()
            self.inference_model.midi_decode_options.update(saved_options)
            self.inference_model.output_path = saved_output_path

            shutil.rmtree(output_dir, ignore_errors=True)

        return BytesStreamResource(midi_bytes, content_type="audio/midi", filename=midi_filename)

class VirtuosoNetMusicPerformanceTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._require_isolated_runtime()

        self.inference_model: Optional[InferenceModel] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch"),
            "virtuosonet",
            "omegaconf",
            "pyyaml",
            "numpy",
            "scikit-learn",
            "pretty_midi",
            "music21",
            "mido",
        ]

    async def _load_model(self) -> None:
        self.inference_model = await self._load_inference_model()

    async def _unload_model(self) -> None:
        self.inference_model = None

    async def _load_inference_model(self) -> InferenceModel:
        from virtuoso.inference import InferenceModel

        model_path = await self._provision_model(self.config.model, prefetch=True)
        checkpoint_path = self._resolve_checkpoint_path(model_path)
        device = self._resolve_device(self.config.device)

        def _load() -> InferenceModel:
            return InferenceModel(
                checkpoint_path=checkpoint_path,
                device=str(device),
                output_path=tempfile.gettempdir(),
                midi_decode_options={
                    "bool_pedal":            False,
                    "for_disklavier":        False,
                    "multi_instruments":     False,
                    "tempo_clock":           False,
                    "clock_interval_in_16th": 4,
                    "velocity_multiplier":   1.0,
                },
            )

        return await self._run_in_executor(_load)

    def _resolve_checkpoint_path(self, model_path: str) -> str:
        # HuggingFace repos resolve to a snapshot directory; local repos point
        # straight at the checkpoint file or its parent directory.
        if os.path.isfile(model_path):
            return model_path

        candidate = os.path.join(model_path, _VIRTUOSO_NET_CHECKPOINT_FILENAME)

        if not os.path.isfile(candidate):
            raise FileNotFoundError(
                f"VirtuosoNet checkpoint '{_VIRTUOSO_NET_CHECKPOINT_FILENAME}' not found under '{model_path}'."
            )

        return candidate

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == MusicPerformanceActionMethod.RENDER:
            return await VirtuosoNetMusicPerformanceModelRenderAction(
                action, self.inference_model,
            ).run(context)

        raise ValueError(f"Unknown method: {action.method}")
