from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, BasicPitchMusicTranscriptionModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, BasicPitchMusicTranscriptionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.files import get_temporary_path
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import MusicTranscriptionTaskAction, MusicTranscriptNotes
import os, io

if TYPE_CHECKING:
    import numpy as np
    import torch
    from pretty_midi import PrettyMIDI

# Basic Pitch was trained on 22.05 kHz mono audio. Feeding it anything else forces
# an internal resample that both slows inference and can subtly shift note timing.
_BASIC_PITCH_SAMPLE_RATE = 22050

class BasicPitchMusicTranscriptionTaskAction(MusicTranscriptionTaskAction):
    def __init__(
        self,
        config: BasicPitchMusicTranscriptionModelActionConfig,
        model_path: str,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.config: BasicPitchMusicTranscriptionModelActionConfig = config
        self.model_path: str = model_path

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        minimum_note_length = await context.render_scalar(self.config.params.minimum_note_length, float)
        minimum_frequency   = await context.render_scalar(self.config.params.minimum_frequency, float)
        maximum_frequency   = await context.render_scalar(self.config.params.maximum_frequency, float)
        midi_tempo          = await context.render_scalar(self.config.params.midi_tempo, float)
        return_pitch_bends  = await context.render_scalar(self.config.return_pitch_bends, bool)

        params.update({
            "minimum_note_length": minimum_note_length,
            "minimum_frequency":   minimum_frequency,
            "maximum_frequency":   maximum_frequency,
            "midi_tempo":          midi_tempo,
            "return_pitch_bends":  return_pitch_bends,
        })

        return params

    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        waveforms = await self._preprocess_audio(audios)

        def _transcribe() -> List[Any]:
            return [ self._transcribe(waveform, params) for waveform in waveforms ]

        return await self._run_in_executor(_transcribe)

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            # Basic Pitch was trained at 22.05 kHz mono; downmix + resample here
            # so the library doesn't redo the same work at load time.
            buffer = await AudioBufferStreamer(audio, sample_rate=_BASIC_PITCH_SAMPLE_RATE, channel="mono").collect()
            waveforms.append(buffer.waveform)

        return waveforms

    def _transcribe(self, waveform: np.ndarray, params: Dict[str, Any]) -> Dict[str, Any]:
        from basic_pitch.inference import predict
        import soundfile as sf
        import numpy as np

        mono = np.ascontiguousarray(waveform, dtype=np.float32)

        if mono.ndim == 2:
            mono = mono.mean(axis=0)

        # basic_pitch.predict only accepts filesystem paths (it opens the file
        # with librosa internally). Spool the preprocessed waveform to a temp
        # wav so the library can pick it up.
        audio_path = get_temporary_path(extension="wav", reserve_file=True)

        try:
            sf.write(audio_path, mono, _BASIC_PITCH_SAMPLE_RATE, subtype="PCM_16")

            prediction_params: Dict[str, Any] = { "model_or_model_path": self.model_path }

            if params["onset_threshold"] is not None:
                prediction_params["onset_threshold"] = params["onset_threshold"]

            if params["frame_threshold"] is not None:
                prediction_params["frame_threshold"] = params["frame_threshold"]

            if params["minimum_note_length"] is not None:
                prediction_params["minimum_note_length"] = params["minimum_note_length"]

            if params["minimum_frequency"] is not None:
                prediction_params["minimum_frequency"] = params["minimum_frequency"]

            if params["maximum_frequency"] is not None:
                prediction_params["maximum_frequency"] = params["maximum_frequency"]

            if params["return_pitch_bends"] is not None:
                # basic_pitch names the flag `multiple_pitch_bends`; we expose it
                # as `return_pitch_bends` to match the project's return_* prefix
                # convention.
                prediction_params["multiple_pitch_bends"] = params["return_pitch_bends"]

            if params["midi_tempo"] is not None:
                prediction_params["midi_tempo"] = params["midi_tempo"]

            _, midi, note_events = predict(audio_path, **prediction_params)
        finally:
            try:
                os.remove(audio_path)
            except OSError:
                pass

        return self._build_transcription_result(midi, note_events, params["return_pitch_bends"])

    def _build_transcription_result(
        self,
        midi: PrettyMIDI,
        note_events: List[Tuple[Any]],
        return_pitch_bends: bool
    ) -> Dict[str, Any]:
        midi_bytes = self._encode_midi(midi)
        notes: List[Dict[str, Any]] = []

        for event in note_events:
            # basic_pitch always returns 5-tuples (start, end, pitch, amplitude,
            # pitch_bends). pitch_bends is a per-frame integer list even when the
            # `multiple_pitch_bends` flag is off — only surface it to callers who
            # asked for it, and cast np.int64 to native ints for JSON safety.
            start_time, end_time, pitch, amplitude = event[0], event[1], int(event[2]), float(event[3])
            note: Dict[str, Any] = {
                "start_time": float(start_time),
                "end_time":   float(end_time),
                "pitch":      pitch,
                "velocity":   amplitude,
            }

            if return_pitch_bends and len(event) >= 5 and event[4]:
                note["pitch_bends"] = [ int(bend) for bend in event[4] ]

            notes.append(note)

        return {
            "midi": BytesStreamResource(midi_bytes, content_type="audio/midi", filename="transcription.mid"),
            "notes": MusicTranscriptNotes(notes),
        }

    def _encode_midi(self, midi: PrettyMIDI) -> bytes:
        buffer = io.BytesIO()
        midi.write(buffer)

        return buffer.getvalue()

class BasicPitchMusicTranscriptionTaskService(ModelTaskService):
    config: BasicPitchMusicTranscriptionModelComponentConfig

    def __init__(self, id: str, config: BasicPitchMusicTranscriptionModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model_path: Optional[str] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        # basic-pitch ships four checkpoint formats (TF SavedModel, CoreML, TFLite,
        # ONNX). We target ONNX because onnxruntime installs cleanly on every
        # platform without pulling in a large TF/CoreML stack.
        return [ "basic-pitch", "onnxruntime", "soundfile", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.model_path, self.device = await self._resolve_model()

    async def _unload_model(self) -> None:
        self.model_path = None
        self.device = None

    async def _resolve_model(self) -> Tuple[str, torch.device]:
        from basic_pitch import build_icassp_2022_model_path, FilenameSuffix

        # basic_pitch dispatches to the runtime backend based on the file
        # extension. Force the ONNX variant so we don't accidentally depend on
        # TensorFlow (heavy, version-sensitive) or CoreML (macOS-only).
        model_path = build_icassp_2022_model_path(FilenameSuffix.onnx)
        device = self._resolve_device(self.config.device)

        return str(model_path), device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await BasicPitchMusicTranscriptionTaskAction(
            action,
            self.model_path,
            self.device,
        ).run(context)
