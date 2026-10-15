from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Dict, Optional, List, Any
from mindor.dsl.schema.component import ModelComponentConfig, GameMusicTranscriptionModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, GameMusicTranscriptionModelActionConfig
from mindor.core.foundation.package.onnxruntime import get_onnxruntime_distributions
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.url import download_to_file
from mindor.core.logger import logging
from ......base import ComponentActionContext
from ....base import ModelTaskDriver
from ..common import MusicTranscriptionTaskAction, MusicTranscriptNotes
from pathlib import Path
import os, io, json, shutil, tempfile, zipfile

if TYPE_CHECKING:
    import numpy as np
    import onnxruntime as ort
    import torch
    from pretty_midi import PrettyMIDI

# openvpi/GAME v1.0.3 release bundle URLs. Each zip expands to a flat directory
# with `config.json` and the five ONNX modules.
_GAME_BUNDLE_URLS: Dict[str, str] = {
    "small":  "https://github.com/openvpi/GAME/releases/download/v1.0.3/GAME-1.0.3-small-onnx.zip",
    "medium": "https://github.com/openvpi/GAME/releases/download/v1.0.3/GAME-1.0.3-medium-onnx.zip",
    "large":  "https://github.com/openvpi/GAME/releases/download/v1.0.3/GAME-1.0.3-large-onnx.zip",
}

_GAME_ONNX_FILES: Tuple[str, ...] = ("encoder.onnx", "segmenter.onnx", "estimator.onnx", "bd2dur.onnx", "dur2bd.onnx")

# GAME exposes no velocity output; emit a constant on each note so downstream
# MIDI writers see non-zero velocity.
_DEFAULT_VELOCITY = 1.0

# Reference defaults from the GameInfer C++ reference (GameModel.h); mirrored
# here so a bare action with no `params` matches the upstream behavior.
_DEFAULT_SEG_THRESHOLD = 0.2
_DEFAULT_SEG_RADIUS = 2
_DEFAULT_EST_THRESHOLD = 0.2
_DEFAULT_D3PM_STEPS = 5
_DEFAULT_D3PM_T0 = 0.1

# PrettyMIDI's default tempo is 120 BPM; keep the written MIDI consistent with
# that so note timings in seconds survive the ticks round-trip.
_MIDI_TEMPO = 120.0

class GameMusicTranscriptionTaskAction(MusicTranscriptionTaskAction):
    def __init__(
        self,
        config: GameMusicTranscriptionModelActionConfig,
        sessions: Dict[str, Any],
        model_config: Dict[str, Any],
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.config: GameMusicTranscriptionModelActionConfig = config
        self.sessions: Dict[str, Any] = sessions
        self.model_config: Dict[str, Any] = model_config

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        seg_threshold = await context.render_scalar(self.config.params.seg_threshold, float)
        seg_radius    = await context.render_scalar(self.config.params.seg_radius, int)
        est_threshold = await context.render_scalar(self.config.params.est_threshold, float)
        d3pm_steps    = await context.render_scalar(self.config.params.d3pm_steps, int)
        language      = await context.render_scalar(self.config.language, str)

        params.update({
            "seg_threshold": seg_threshold if seg_threshold is not None else _DEFAULT_SEG_THRESHOLD,
            "seg_radius":    seg_radius    if seg_radius    is not None else _DEFAULT_SEG_RADIUS,
            "est_threshold": est_threshold if est_threshold is not None else _DEFAULT_EST_THRESHOLD,
            "d3pm_steps":    d3pm_steps    if d3pm_steps    is not None else _DEFAULT_D3PM_STEPS,
            "language":      self._resolve_language_id(language) if language else 0,
        })

        return params

    def _resolve_language_id(self, language: str) -> int:
        languages = self.model_config.get("languages") or {}
        language_id = languages.get(language)

        if language_id is None:
            raise ValueError(f"Language '{language}' is not supported by this GAME model; available: {sorted(languages.keys())}")

        return int(language_id)

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
        sample_rate = int(self.model_config["samplerate"])

        for audio in audios:
            buffer = await AudioBufferStreamer(audio, sample_rate=sample_rate, channel="mono").collect()
            waveforms.append(buffer.waveform)

        return waveforms

    def _transcribe(self, waveform: np.ndarray, params: Dict[str, Any]) -> Dict[str, Any]:
        import numpy as np

        waveform = np.ascontiguousarray(waveform, dtype=np.float32)
        sample_rate = int(self.model_config["samplerate"])
        duration = float(waveform.shape[-1]) / sample_rate

        # x_seg and x_est share the time axis with maskT, so T comes back from
        # the encoder itself; no need to compute it from timestep manually.
        x_seg, x_est, mask_t = self._run_encoder(waveform, duration, params["language"])

        boundaries = self._run_segmenter(x_seg, mask_t, params)
        durations, mask_n = self._run_bd2dur(boundaries, mask_t)

        if durations.size == 0:
            return self._build_transcription_result([], duration, params)

        presence, scores = self._run_estimator(x_est, boundaries, mask_t, mask_n, params["est_threshold"])
        notes = self._assemble_notes(durations, presence, scores)

        return self._build_transcription_result(notes, duration, params)

    def _run_encoder(
        self,
        waveform: np.ndarray,
        duration: float,
        language_id: int,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        import numpy as np

        session = self.sessions["encoder"]
        feeds: Dict[str, np.ndarray] = {
            "waveform": waveform.reshape(1, -1),
            "duration": np.asarray([duration], dtype=np.float32),
        }

        if any(input.name == "language" for input in session.get_inputs()):
            feeds["language"] = np.asarray([language_id], dtype=np.int64)

        x_seg, x_est, mask_t = session.run(["x_seg", "x_est", "maskT"], feeds)

        return x_seg, x_est, mask_t

    def _run_segmenter(
        self,
        x_seg: np.ndarray,
        mask_t: np.ndarray,
        params: Dict[str, Any],
    ) -> np.ndarray:
        import numpy as np

        session = self.sessions["segmenter"]
        input_names = { input.name for input in session.get_inputs() }

        t_frames = x_seg.shape[1]
        known_boundaries = np.zeros((1, t_frames), dtype=bool)
        prev_boundaries = np.zeros((1, t_frames), dtype=bool)
        threshold = np.asarray(params["seg_threshold"], dtype=np.float32)
        radius = np.asarray(params["seg_radius"], dtype=np.int64)

        # Models exported with loop=true accept a scalar `t` and expect the
        # caller to iterate from near-zero toward one; models without the loop
        # take a single pass with the inputs it has.
        if self.model_config.get("loop") and "t" in input_names:
            d3pm_ts = self._generate_d3pm_ts(_DEFAULT_D3PM_T0, params["d3pm_steps"])
        else:
            d3pm_ts = [None]

        boundaries = prev_boundaries

        for t_value in d3pm_ts:
            feeds: Dict[str, np.ndarray] = {}

            for name in input_names:
                if name == "x_seg":
                    feeds[name] = x_seg
                    continue

                if name == "maskT":
                    feeds[name] = mask_t
                    continue

                if name == "known_boundaries":
                    feeds[name] = known_boundaries
                    continue

                if name == "prev_boundaries":
                    feeds[name] = boundaries
                    continue

                if name == "language":
                    feeds[name] = np.asarray([params["language"]], dtype=np.int64)
                    continue

                if name == "threshold":
                    feeds[name] = threshold
                    continue

                if name == "radius":
                    feeds[name] = radius
                    continue

                if name == "t":
                    feeds[name] = np.asarray([t_value], dtype=np.float32)
                    continue

                raise ValueError(f"Unknown segmenter input: {name}")

            boundaries = session.run(["boundaries"], feeds)[0]

        return boundaries

    def _run_bd2dur(
        self,
        boundaries: np.ndarray,
        mask_t: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        durations, mask_n = self.sessions["bd2dur"].run(
            ["durations", "maskN"],
            { "boundaries": boundaries, "maskT": mask_t },
        )

        return durations, mask_n

    def _run_estimator(
        self,
        x_est: np.ndarray,
        boundaries: np.ndarray,
        mask_t: np.ndarray,
        mask_n: np.ndarray,
        est_threshold: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        import numpy as np

        presence, scores = self.sessions["estimator"].run(
            ["presence", "scores"],
            {
                "x_est":      x_est,
                "boundaries": boundaries,
                "maskT":      mask_t,
                "maskN":      mask_n,
                "threshold":  np.asarray(est_threshold, dtype=np.float32),
            },
        )

        return presence, scores

    def _generate_d3pm_ts(self, t0: float, n_steps: int) -> List[float]:
        if n_steps <= 0:
            return []

        step = (1.0 - t0) / float(n_steps)

        return [ t0 + index * step for index in range(n_steps) ]

    def _assemble_notes(
        self,
        durations: np.ndarray,
        presence: np.ndarray,
        scores: np.ndarray,
    ) -> List[Dict[str, Any]]:
        notes: List[Dict[str, Any]] = []
        current_time = 0.0

        # Durations are a dense sequence across the whole clip; silent slots
        # carry presence=False but still advance the cursor so later voiced
        # notes land at the right time.
        for duration, voiced, pitch in zip(durations[0], presence[0], scores[0]):
            duration = float(duration)

            if bool(voiced):
                notes.append({
                    "start_time": round(current_time, 6),
                    "end_time":   round(current_time + duration, 6),
                    "pitch":      int(round(float(pitch))),
                    "velocity":   _DEFAULT_VELOCITY,
                })

            current_time += duration

        return notes

    def _build_transcription_result(
        self,
        notes: List[Dict[str, Any]],
        duration: float,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if params["return_midi"]:
            midi_bytes = self._encode_midi(notes)
            result["midi"] = BytesStreamResource(midi_bytes, content_type="audio/midi", filename="transcription.mid")

        if params["return_notes"]:
            result["notes"] = MusicTranscriptNotes(notes)

        if params["return_metadata"]:
            result["duration"] = duration

        return result

    def _encode_midi(self, notes: List[Dict[str, Any]]) -> bytes:
        from pretty_midi import PrettyMIDI, Instrument, Note

        midi = PrettyMIDI(initial_tempo=_MIDI_TEMPO)
        instrument = Instrument(program=0)

        for note in notes:
            instrument.notes.append(Note(
                velocity=int(round(float(note["velocity"]) * 127)),
                pitch=int(note["pitch"]),
                start=float(note["start_time"]),
                end=float(note["end_time"]),
            ))

        midi.instruments.append(instrument)

        buffer = io.BytesIO()
        midi.write(buffer)

        return buffer.getvalue()

class GameMusicTranscriptionTaskDriver(ModelTaskDriver):
    config: GameMusicTranscriptionModelComponentConfig

    def __init__(self, id: str, config: GameMusicTranscriptionModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.sessions: Dict[str, Any] = {}
        self.model_config: Dict[str, Any] = {}
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            ("onnxruntime", get_onnxruntime_distributions()),
            "numpy",
            "soxr",
            "pretty_midi",
        ]

    async def _load_model(self) -> None:
        import onnxruntime as ort

        model_path = await self._resolve_model_path()
        device = self._resolve_device(self.config.device)
        providers = self._resolve_providers(device)

        def _load() -> Tuple[Dict[str, Any], Dict[str, Any]]:
            sessions: Dict[str, Any] = {}

            for filename in _GAME_ONNX_FILES:
                key = filename.removesuffix(".onnx")
                sessions[key] = ort.InferenceSession(str(model_path / filename), providers=providers)

            with open(model_path / "config.json", "r", encoding="utf-8") as f:
                model_config = json.load(f)

            return sessions, model_config

        sessions, model_config = await self._run_in_executor(_load)

        self.sessions = sessions
        self.model_config = model_config
        self.device = device

    async def _unload_model(self) -> None:
        self.sessions = {}
        self.model_config = {}
        self.device = None

    async def _resolve_model_path(self) -> Path:
        model_name = self.config.model.name

        if model_name not in _GAME_BUNDLE_URLS:
            raise ValueError(f"Unknown GAME bundle '{model_name}'; available: {sorted(_GAME_BUNDLE_URLS.keys())}")

        cache_root = Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))) / "models"
        model_path = cache_root / "game" / model_name

        if all((model_path / filename).exists() for filename in ("config.json", *_GAME_ONNX_FILES)):
            return model_path

        url = _GAME_BUNDLE_URLS[model_name]

        logging.info(f"Downloading GAME bundle '{model_name}' from {url}")

        await self._download_and_extract_bundle(url, model_path)

        return model_path

    async def _download_and_extract_bundle(self, url: str, model_path: Path) -> None:
        model_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(suffix=".zip", dir=str(model_path.parent), delete=False) as tmp:
            archive_path = Path(tmp.name)

        staging_dir = Path(tempfile.mkdtemp(prefix=f".{model_path.name}.", dir=str(model_path.parent)))

        try:
            await download_to_file(url, archive_path)

            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(staging_dir)

            # Release zips wrap the files in a single top-level directory;
            # flatten so the cache layout is always `<model_path>/<file>`.
            extracted_root = self._find_bundle_root(staging_dir)

            if model_path.exists():
                shutil.rmtree(model_path)

            os.replace(extracted_root, model_path)
        except BaseException:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        finally:
            if archive_path.exists():
                archive_path.unlink()

    def _find_bundle_root(self, staging_dir: Path) -> Path:
        if (staging_dir / "config.json").exists():
            return staging_dir

        for child in staging_dir.iterdir():
            if child.is_dir() and (child / "config.json").exists():
                return child

        raise ValueError(f"GAME bundle does not contain config.json at {staging_dir}")

    def _resolve_providers(self, device: torch.device) -> List[str]:
        providers: List[str] = self.config.providers or []

        if not providers:
            if device.type == "cuda":
                providers.append("CUDAExecutionProvider")

            if device.type == "mps":
                providers.append("CoreMLExecutionProvider")

            providers.append("CPUExecutionProvider")

        return providers

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await GameMusicTranscriptionTaskAction(
            action,
            self.sessions,
            self.model_config,
            self.device,
        ).run(context)
