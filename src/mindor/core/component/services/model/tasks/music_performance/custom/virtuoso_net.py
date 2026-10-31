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
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import MusicPerformanceTaskAction
from pathlib import Path
import os, tempfile

if TYPE_CHECKING:
    from virtuoso.inference import InferenceModel
    import torch

_VIRTUOSO_NET_CHECKPOINT_FILENAME = "checkpoint_best.pt"

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
        from virtuoso.inference import save_model_output_as_midi

        # Follow the module-level CLI path (`python -m virtuoso --session_mode=inference`),
        # not InferenceModel.infer_xml(). The bound-method `model_prediction_to_feature`
        # applies an inverse sigmoid to pedal features that NaNs out on the
        # public `dasaem/virtuosonet` checkpoint — its pedal predictions are
        # already on the MIDI scale, so `127/(x+0.04)-1` goes negative and
        # np.log explodes. The module-level `model_prediction_to_feature` used
        # by `save_model_output_as_midi` is a plain column→key map, matching
        # what the upstream CLI ships.
        with tempfile.TemporaryDirectory(prefix="virtuoso-net-") as output_dir:
            save_path = Path(output_dir) / f"{Path(score_path).stem}.mid"

            if params["seed"] is not None:
                torch.manual_seed(params["seed"])

            score, model_input, edges, note_locations = self.inference_model.get_input_from_xml(
                xml_path=score_path,
                composer=params["composer"],
                qpm_primo=params["qpm_primo"],
            )

            model = self.inference_model.model

            with torch.no_grad():
                outputs, _, _, _ = model(model_input, None, edges, note_locations, initial_z="zero")

            save_model_output_as_midi(
                outputs, save_path, score,
                model.stats["output_keys"], model.stats["stats"], note_locations,
                velocity_multiplier=params["velocity_multiplier"],
                multi_instruments=params["multi_instruments"],
                tempo_clock=params["tempo_clock"],
                bool_pedal=params["bool_pedal"],
                disklavier=params["disklavier"],
                clock_interval_in_16th=params["clock_interval_in_16th"],
            )

            with open(save_path, "rb") as f:
                midi_bytes = f.read()

        return BytesStreamResource(midi_bytes, content_type="audio/midi", filename=save_path.name)

class VirtuosoNetMusicPerformanceTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._require_isolated_runtime()

        self.inference_model: Optional[InferenceModel] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            # torch<2.6: InferenceModel's torch.load() has no weights_only kwarg,
            # and checkpoint_best.pt holds NumPy scalars that trip 2.6+'s default.
            *torch_requirements("torch<2.6"),
            "omegaconf",
            "pyyaml",
            # numpy<2: VirtuosoNet imports numpy.lib.npyio.save and
            # numpy.lib.arraysetops.isin, both removed in NumPy 2.
            "numpy<2",
            "scikit-learn",
            "pretty_midi",
            "music21",
            "mido",
            "pandas<3",
            "matplotlib",
            "plotly",
            "six",
            "tqdm",
            "wandb",
            "huggingface_hub",
        ]

    async def _setup(self) -> None:
        if not is_package_installed("virtuoso"):
            # jdasam/virtuosoNet ships the `virtuoso/` package at the repo root
            # without `setup.py`/`pyproject.toml`, so pip-install isn't an
            # option — drop the directory next to `mindor` as a top-level
            # `virtuoso` package. Internal imports are already relative
            # (`from .inference import ...`), so no path rewriting is needed.
            await install_package_from_github(
                module_name="virtuoso",
                repo_url="https://github.com/jdasam/virtuosoNet.git",
                revision="f20e5b0",
                subdirs=[ "virtuoso" ],
            )

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
            # output_path and midi_decode_options are required by the upstream
            # ctor but go unused: _render follows the module-level CLI path and
            # drives save_model_output_as_midi directly rather than the
            # per-instance midi_decoder / output_path.
            return InferenceModel(
                checkpoint_path=checkpoint_path,
                device=str(device),
                output_path=tempfile.gettempdir(),
                midi_decode_options={},
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
