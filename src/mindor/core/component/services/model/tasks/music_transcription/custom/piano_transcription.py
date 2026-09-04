from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, PianoTranscriptionMusicTranscriptionModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, PianoTranscriptionMusicTranscriptionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.files import get_temporary_path
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import MusicTranscriptionTaskAction, MusicTranscriptNotes
import os

if TYPE_CHECKING:
    from piano_transcription_inference import PianoTranscription
    import numpy as np
    import torch

# ByteDance's model was trained on 16 kHz mono piano recordings; feeding anything
# else silently degrades note recall.
_PIANO_TRANSCRIPTION_SAMPLE_RATE = 16000

class PianoTranscriptionTaskActionImpl(MusicTranscriptionTaskAction):
    def __init__(
        self,
        config: PianoTranscriptionMusicTranscriptionModelActionConfig,
        transcriptor: PianoTranscription,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.config: PianoTranscriptionMusicTranscriptionModelActionConfig = config
        self.transcriptor: PianoTranscription = transcriptor

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        offset_threshold       = await context.render_scalar(self.config.params.offset_threshold, float)
        pedal_offset_threshold = await context.render_scalar(self.config.params.pedal_offset_threshold, float)

        params.update({
            "offset_threshold":       offset_threshold,
            "pedal_offset_threshold": pedal_offset_threshold,
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
            buffer = await AudioBufferStreamer(audio, sample_rate=_PIANO_TRANSCRIPTION_SAMPLE_RATE, channel="mono").collect()
            waveforms.append(buffer.waveform)

        return waveforms

    def _transcribe(self, waveform: np.ndarray, params: Dict[str, Any]) -> Dict[str, Any]:
        import numpy as np

        mono = np.ascontiguousarray(waveform, dtype=np.float32)

        if mono.ndim == 2:
            mono = mono.mean(axis=0)

        # PianoTranscription stashes thresholds as instance attributes and reads
        # them fresh at each transcribe() call, so pushing per-request overrides
        # here works without rebuilding the model. Restore the previous values
        # after the call so concurrent requests aren't affected.
        # Note: upstream misspells `offset_threshold` as `offset_threshod`.
        threshold_overrides = {
            "onset_threshold":        params["onset_threshold"],
            "offset_threshod":        params["offset_threshold"],
            "frame_threshold":        params["frame_threshold"],
            "pedal_offset_threshold": params["pedal_offset_threshold"],
        }
        saved_thresholds: Dict[str, Any] = {}

        for name, value in threshold_overrides.items():
            if value is not None and hasattr(self.transcriptor, name):
                saved_thresholds[name] = getattr(self.transcriptor, name)
                setattr(self.transcriptor, name, value)

        # piano_transcription_inference writes MIDI to a file path (no in-memory
        # API). Spool to a temp file, then read the bytes back into a stream
        # resource that matches the basic_pitch backend's output shape.
        midi_path = get_temporary_path(extension="mid", reserve_file=True)

        try:
            # piano_transcription_inference returns a dict of
            # { output_dict, est_note_events, est_pedal_events }. We only need
            # the note events; pedal events are baked into the MIDI file the
            # library writes.
            result = self.transcriptor.transcribe(mono, midi_path)
            note_events = result.get("est_note_events") or []

            with open(midi_path, "rb") as f:
                midi_bytes = f.read()
        finally:
            for name, value in saved_thresholds.items():
                setattr(self.transcriptor, name, value)

            try:
                os.remove(midi_path)
            except OSError:
                pass

        return self._build_transcription_result(midi_bytes, note_events)

    def _build_transcription_result(self, midi_bytes: bytes, note_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        notes: List[Dict[str, Any]] = []

        for event in note_events:
            notes.append({
                "start_time": float(event.get("onset_time", 0.0)),
                "end_time":   float(event.get("offset_time", 0.0)),
                "pitch":      int(event.get("midi_note", 0)),
                "velocity":   float(event.get("velocity", 0.0)) / 128.0,
            })

        return {
            "midi": BytesStreamResource(midi_bytes, content_type="audio/midi", filename="transcription.mid"),
            "notes": MusicTranscriptNotes(notes),
        }

class PianoTranscriptionMusicTranscriptionTaskService(ModelTaskService):
    config: PianoTranscriptionMusicTranscriptionModelComponentConfig

    def __init__(self, id: str, config: PianoTranscriptionMusicTranscriptionModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.transcriptor: Optional[PianoTranscription] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "piano_transcription_inference", "torch", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.transcriptor, self.device = await self._load_transcriptor()

    async def _unload_model(self) -> None:
        self.transcriptor = None
        self.device = None

    async def _load_transcriptor(self) -> Tuple[PianoTranscription, torch.device]:
        from piano_transcription_inference import PianoTranscription

        device = self._resolve_device(self.config.device)

        # PianoTranscription auto-downloads its default checkpoint on first use
        # when checkpoint_path is None. The schema stamps a sentinel name so the
        # discriminator has something to compare, but we only forward it when
        # it's an actual filesystem path — otherwise let the library resolve
        # its default.
        checkpoint_path = self.config.model.name

        if not checkpoint_path or not os.path.isfile(checkpoint_path):
            checkpoint_path = None

        transcriptor = PianoTranscription(device=str(device), checkpoint_path=checkpoint_path)

        return transcriptor, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await PianoTranscriptionTaskActionImpl(
            action,
            self.transcriptor,
            self.device,
        ).run(context)
