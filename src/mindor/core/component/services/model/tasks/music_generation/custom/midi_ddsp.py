from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.runtime import RuntimeType
from mindor.dsl.schema.action import (
    ModelActionConfig,
    MusicGenerationActionMethod,
    MidiDdspMusicGenerationModelGenerateActionConfig,
)
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ....base import ComponentActionContext, ModelTaskService
from ..common import MusicGenerationTaskAction
import os

if TYPE_CHECKING:
    from midi_ddsp.modules.get_synthesis_generator import SynthesisGenerator
    from midi_ddsp.modules.expression_generator import ExpressionGenerator
    from pretty_midi import PrettyMIDI

# URMP-trained MIDI-DDSP models emit 16 kHz mono audio; the frame rate is fixed
# at 250 Hz for the expression/synthesis parameter timelines.
_MIDI_DDSP_SAMPLE_RATE = 16000
_MIDI_DDSP_FRAME_RATE = 250

# The URMP checkpoints the upstream downloader ships. Users who train their own
# weights can point `model` at any directory laid out the same way; we default
# checkpoint filenames here so `model: <dir>` alone is enough for the shipped
# release.
_DEFAULT_SYNTHESIS_GENERATOR_STEP = "50000"
_DEFAULT_EXPRESSION_GENERATOR_STEP = "5000"

_EXPRESSION_CONTROL_KEYS = (
    "vibrato_extent",
    "vibrato_attack",
    "brightness",
    "attack_noise",
    "volume",
    "volume_fluctuation",
)

class MidiDdspMusicGenerationModelGenerateAction(MusicGenerationTaskAction):
    config: MidiDdspMusicGenerationModelGenerateActionConfig

    def __init__(
        self,
        config: MidiDdspMusicGenerationModelGenerateActionConfig,
        synthesis_generator: "SynthesisGenerator",
        expression_generator: "ExpressionGenerator",
    ):
        super().__init__(config)

        self.synthesis_generator  = synthesis_generator
        self.expression_generator = expression_generator

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        midi = await context.render_file(self.config.midi)

        is_single_input    = not isinstance(midi, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(midi, (StreamIterator, AsyncIterator))

        return (midi,), is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        instrument   = await context.render_variable(self.config.instrument)
        pitch_offset = await context.render_scalar(self.config.params.pitch_offset, int)
        speed_rate   = await context.render_scalar(self.config.params.speed_rate,   float)

        if instrument:
            instrument = instrument.replace("-", " ")

        expression_controls: Dict[str, Optional[float]] = {}

        for key in _EXPRESSION_CONTROL_KEYS:
            expression_controls[key] = await context.render_scalar(getattr(self.config.params, key), float)

        params.update({
            "instrument":   instrument,
            "pitch_offset": pitch_offset,
            "speed_rate":   speed_rate,
            **expression_controls,
        })

        return params

    async def _generate_batch(
        self,
        batch_input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        def _generate() -> List[PcmStreamResource]:
            results: List[PcmStreamResource] = []

            for (midi_path,) in batch_input:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break
                results.append(self._synthesize(midi_path, params))

            return results

        return await self._run_in_executor(_generate)

    def _synthesize(self, midi_path: str, params: Dict[str, Any]) -> PcmStreamResource:
        import numpy as np
        import pretty_midi
        import tensorflow as tf
        from midi_ddsp.data_handling.instrument_name_utils import INST_NAME_TO_ID_DICT
        from midi_ddsp.utils.midi_synthesis_utils import (
            note_list_to_sequence,
            expression_generator_output_to_conditioning_df,
            batch_conditioning_df_to_audio,
        )

        instrument_name = params["instrument"]

        if instrument_name not in INST_NAME_TO_ID_DICT:
            raise ValueError(f"Instrument '{instrument_name}' is not supported by MIDI-DDSP.")

        instrument_id = INST_NAME_TO_ID_DICT[instrument_name]

        midi = pretty_midi.PrettyMIDI(midi_path)
        self._ensure_monophonic_midi(midi)

        conditioning_dfs: List[Any] = []
        instrument_ids: List[Any] = []

        for instrument in midi.instruments:
            if not instrument.notes:
                continue

            note_sequence = note_list_to_sequence(
                instrument.notes,
                fs=_MIDI_DDSP_FRAME_RATE,
                pitch_offset=params["pitch_offset"],
                speed_rate=params["speed_rate"],
            )
            instrument_id_tensor = tf.constant([instrument_id])
            note_sequence["instrument_id"] = instrument_id_tensor

            expression_output = self.expression_generator(
                note_sequence,
                out=None,
                training=False,
            )
            conditioning_df = expression_generator_output_to_conditioning_df(
                expression_output["output"], note_sequence,
            )
            self._override_expression_controls(conditioning_df, params)

            conditioning_dfs.append(conditioning_df)
            instrument_ids.append(instrument_id_tensor)

        if not conditioning_dfs:
            raise ValueError(f"MIDI file '{midi_path}' contains no notes to synthesize.")

        midi_audio, _, _ = batch_conditioning_df_to_audio(
            self.synthesis_generator,
            conditioning_dfs,
            instrument_ids,
            display_progressbar=False,
        )

        # Mix all parts (each rendered as an independent monophonic voice) down
        # into a single waveform. `batch_conditioning_df_to_audio` right-pads
        # short parts with zeros, so a straight sum is safe.
        mix = tf.reduce_sum(midi_audio, axis=0).numpy().astype(np.float32)

        # Guard against clipping when multiple parts stack. Only attenuate when
        # the sum actually exceeds full scale; otherwise leave the model output
        # untouched so single-part renders keep their trained loudness.
        peak = float(np.max(np.abs(mix))) if mix.size else 0.0

        if peak > 1.0:
            mix = mix / peak

        frames, channels = encode_waveform_to_pcm(mix)

        return PcmStreamResource(frames, {
            "sample_rate": str(_MIDI_DDSP_SAMPLE_RATE),
            "channels":    str(channels),
            "bit_depth":   "16",
        })

    @staticmethod
    def _ensure_monophonic_midi(midi: "PrettyMIDI") -> None:
        for part_number, instrument in enumerate(midi.instruments):
            notes = sorted(instrument.notes, key=lambda n: n.start)
            for prev, current in zip(notes, notes[1:]):
                # Allow small floating-point overlap that MIDI editors emit at
                # note boundaries; only fail on genuine simultaneous notes.
                if current.start < prev.end - 1e-3:
                    raise ValueError(
                        f"MIDI part {part_number} contains overlapping notes at "
                        f"{current.start:.3f}s; MIDI-DDSP only supports monophonic input."
                    )

    @staticmethod
    def _override_expression_controls(conditioning_df: Any, params: Dict[str, Any]) -> None:
        for key in _EXPRESSION_CONTROL_KEYS:
            value = params.get(key)
            if value is not None and key in conditioning_df.columns:
                conditioning_df[key] = float(value)

class MidiDdspMusicGenerationTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # Reject unsupported runtimes before setup runs.
        self._require_isolated_runtime()

        self.synthesis_generator: Optional["SynthesisGenerator"] = None
        self.expression_generator: Optional["ExpressionGenerator"] = None

    def _require_isolated_runtime(self) -> None:
        # MIDI-DDSP's TF 2.7-era pin collides with the host mindor stack
        # (torch 2.10 / TF-free). Refuse runtimes that share the host
        # interpreter or a plain subprocess of it.
        runtime_type = self.config.runtime.type

        if runtime_type in (RuntimeType.NATIVE, RuntimeType.EMBEDDED, RuntimeType.PROCESS):
            raise RuntimeError(
                f"MIDI-DDSP requires an isolated runtime (virtualenv, docker, or apple-container) "
                f"because it pins TensorFlow 2.11 and cannot coexist with the host interpreter. "
                f"Got runtime.type = '{runtime_type.value}'."
            )

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            "midi-ddsp",
            "tensorflow>=2.7,<=2.11",
            "protobuf<=3.20",
            "numpy<1.24",
            "pretty_midi",
        ]

    async def _load_model(self) -> None:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            raise ValueError("MIDI-DDSP does not support HuggingFace Hub models. Provide a local model directory instead.")

        model_path = await self._provision_model(self.config.model, prefetch=True)
        self.synthesis_generator, self.expression_generator = await self._load_generators(model_path)

    async def _unload_model(self) -> None:
        self.synthesis_generator = None
        self.expression_generator = None

    async def _load_generators(self, model_path: str) -> Tuple["SynthesisGenerator", "ExpressionGenerator"]:
        from midi_ddsp.hparams_synthesis_generator import hparams as hp
        from midi_ddsp.modules.get_synthesis_generator import (
            get_synthesis_generator,
            get_fake_data_synthesis_generator,
        )
        from midi_ddsp.modules.expression_generator import (
            ExpressionGenerator,
            get_fake_data_expression_generator,
        )
        from midi_ddsp.utils.training_utils import get_hp

        synthesis_generator_path, expression_generator_path = self._resolve_checkpoint_paths(model_path)

        # Upstream stores training hyperparameters next to the checkpoint as
        # `train.log`. Missing it means the caller pointed us at a directory
        # that isn't a MIDI-DDSP release layout.
        train_log_path = os.path.join(os.path.dirname(synthesis_generator_path), "train.log")

        if not os.path.isfile(train_log_path):
            raise FileNotFoundError(
                f"Synthesis generator train.log not found at '{train_log_path}'. "
                f"MIDI-DDSP requires the URMP release layout with a train.log alongside the checkpoint."
            )

        for key, value in get_hp(train_log_path).items():
            setattr(hp, key, value)

        synthesis_generator = get_synthesis_generator(hp)
        synthesis_generator._build(get_fake_data_synthesis_generator(hp))
        synthesis_generator.load_weights(synthesis_generator_path).expect_partial()

        expression_generator = ExpressionGenerator(n_out=6, nhid=128)
        fake_data = get_fake_data_expression_generator(6)
        _ = expression_generator(fake_data["cond"], out=fake_data["target"], training=True)
        expression_generator.load_weights(expression_generator_path).expect_partial()

        return synthesis_generator, expression_generator

    def _resolve_checkpoint_paths(self, model_path: str) -> Tuple[str, str]:
        synthesis_generator_path = os.path.join(model_path, "synthesis_generator", _DEFAULT_SYNTHESIS_GENERATOR_STEP)
        expression_generator_path = self.config.expression_generator_weights

        if expression_generator_path:
            if not os.path.isabs(expression_generator_path):
                expression_generator_path = os.path.join(model_path, expression_generator_path)
        else:
            expression_generator_path = os.path.join(model_path, "expression_generator", _DEFAULT_EXPRESSION_GENERATOR_STEP)

        return synthesis_generator_path, expression_generator_path

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == MusicGenerationActionMethod.GENERATE:
            return await MidiDdspMusicGenerationModelGenerateAction(
                action, self.synthesis_generator, self.expression_generator,
            ).run(context)

        raise ValueError(f"Unknown method: {action.method}")
