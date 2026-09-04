from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union, Tuple, Dict, List, Any
from mindor.dsl.schema.component import MusicAnalyzerComponentConfig
from mindor.dsl.schema.action import MusicAnalyzerActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.soundfile.audio import load_pcm_samples
from ....action.media import MediaInputPathResolver
from ..base import MusicAnalyzerService, MusicAnalyzerDriver, register_music_analyzer_service
from ..base import ComponentActionContext
from .common import (
    MusicAnalyzerAction,
    MusicBeats,
    MusicOnsets,
    MusicTempogram,
    MusicActivity,
    MusicChroma,
    MusicTonnetz,
    MusicBrightness,
    MusicFlatness,
)
import os

if TYPE_CHECKING:
    import numpy as np

# Number of decimals kept in emitted time/BPM/level values. Anything finer than
# 3 decimals (1ms / 0.001) is below librosa's frame-grid precision at the
# default hop, so trimming here keeps output stable without losing information.
_OUTPUT_DECIMALS = 3

# Default STFT hop for frame-based features. Matches librosa's own default
# across beat/onset/spectral APIs so consumers get a consistent time grid.
_DEFAULT_HOP_LENGTH = 512

# Krumhansl-Schmuckler key profiles (major and minor). Correlating a normalized
# chroma vector against every rotation of these two profiles picks the most
# likely tonal centre and mode.
_KRUMHANSL_MAJOR = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
_KRUMHANSL_MINOR = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)

_PITCH_CLASS_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# Chroma frames get folded to this many rows for a compact JSON payload. 12 is
# the natural pitch-class count so no lossy downsampling is needed for chroma
# itself; kept as a name for parity with tonnetz which uses a different width.
_CHROMA_ROWS = 12
_TONNETZ_ROWS = 6

class NativeMusicAnalyzerAction(MusicAnalyzerAction):
    async def _analyze_beats(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        envelope, sample_rate, hop_length = await self._prepare_onset_envelope(source, params)

        def _analyze() -> Dict[str, Any]:
            import numpy as np
            import librosa

            tempo_bpm, beat_frames = librosa.beat.beat_track(
                onset_envelope=envelope,
                sr=sample_rate,
                hop_length=hop_length,
                bpm=None,
                start_bpm=(float(params["min_bpm"]) + float(params["max_bpm"])) / 2.0,
            )

            beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate, hop_length=hop_length)

            return MusicBeats({
                "bpm":        round(float(np.atleast_1d(tempo_bpm)[0]), _OUTPUT_DECIMALS),
                "confidence": self._autocorrelation_confidence(envelope, sample_rate, hop_length, params),
                "beats":      [ { "time": round(float(t), _OUTPUT_DECIMALS) } for t in beat_times ],
            })

        return await self._run_in_executor(_analyze)

    async def _analyze_onsets(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        envelope, sample_rate, hop_length = await self._prepare_onset_envelope(source, params)

        def _analyze() -> Dict[str, Any]:
            import numpy as np
            import librosa

            frames_per_second = sample_rate / hop_length
            wait = max(1, int(round(float(params["min_gap"]) * frames_per_second)))

            onset_frames = librosa.onset.onset_detect(
                onset_envelope=envelope, sr=sample_rate, hop_length=hop_length, wait=wait,
            )

            if onset_frames.size == 0:
                return MusicOnsets({ "onsets": [] })

            times = librosa.frames_to_time(onset_frames, sr=sample_rate, hop_length=hop_length)
            raw = envelope[onset_frames]
            # Normalize by the 95th percentile of picked-onset strengths so the
            # scale matches the [analyzer/] convention: robust to a single very
            # loud transient, comparable across songs. Falls back to 1.0 for
            # degenerate inputs.
            ceiling = float(np.percentile(raw, 95.0)) if raw.size else 0.0
            strengths = raw / ceiling if ceiling > 0.0 else np.zeros_like(raw)
            strengths = np.clip(strengths, 0.0, 1.0)

            return MusicOnsets({
                "onsets": [
                    {
                        "time":     round(float(t), _OUTPUT_DECIMALS),
                        "strength": round(float(s), _OUTPUT_DECIMALS),
                    }
                    for t, s in zip(times, strengths)
                ],
            })

        return await self._run_in_executor(_analyze)

    async def _analyze_tempogram(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        envelope, sample_rate, hop_length = await self._prepare_onset_envelope(source, params)

        def _analyze() -> Dict[str, Any]:
            import numpy as np
            import librosa

            # librosa.feature.tempogram returns (win_length, n_frames); rows are
            # lag indices convertible to BPM via tempo_frequencies.
            tg = librosa.feature.tempogram(
                onset_envelope=envelope, sr=sample_rate, hop_length=hop_length,
            )
            bpms = librosa.tempo_frequencies(tg.shape[0], sr=sample_rate, hop_length=hop_length)

            # Clip to the requested BPM band and rearrange so rows go from low
            # to high BPM. tempo_frequencies returns descending BPM with a
            # sentinel `+inf` at row 0 (lag 0), which we always drop.
            min_bpm = float(params["min_bpm"])
            max_bpm = float(params["max_bpm"])
            keep = np.where((bpms >= min_bpm) & (bpms <= max_bpm))[0]
            keep = keep[np.argsort(bpms[keep])]

            frames = tg[keep, :].T.astype(np.float32)  # (n_frames, n_bpm_bins)
            fps = sample_rate / hop_length

            return MusicTempogram({
                "frames":      [ [ round(float(v), _OUTPUT_DECIMALS) for v in row ] for row in frames ],
                "bpm_axis":    [ round(float(b), _OUTPUT_DECIMALS) for b in bpms[keep] ],
                "fps":         round(float(fps), _OUTPUT_DECIMALS),
                "sample_rate": int(sample_rate),
            })

        return await self._run_in_executor(_analyze)

    async def _analyze_activity(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """Active regions where the song is louder than its own quiet-to-loud
        threshold. Port of analyzer/sustain.py, kept in pure numpy — no librosa
        equivalent exists.
        """
        energy, sample_rate, hop_length = await self._prepare_energy_envelope(source, params)

        def _analyze() -> Dict[str, Any]:
            import numpy as np

            if energy.size == 0:
                return MusicActivity({ "activity": [] })

            quiet = float(np.percentile(energy, 5.0))
            loud = float(np.percentile(energy, 95.0))

            # Songs with no dynamic range (silence, constant tone) give us no
            # basis to separate active from quiet — return nothing rather than
            # marking the whole track as one big active region.
            if loud <= quiet:
                return MusicActivity({ "activity": [] })

            level = float(params["level"])
            threshold = quiet + level * (loud - quiet)
            active = energy >= threshold

            frames_per_second = sample_rate / hop_length
            min_frames = max(1, int(round(float(params["min_duration"]) * frames_per_second)))

            # Walk the boolean mask, emitting (start, end) frame pairs for each
            # contiguous run of `active` frames. Runs shorter than `min_frames`
            # are dropped as noise.
            regions: List[Dict[str, float]] = []
            start: Optional[int] = None
            for index, on in enumerate(active):
                if on and start is None:
                    start = index
                elif not on and start is not None:
                    if index - start >= min_frames:
                        regions.append({
                            "start_time": round(start / frames_per_second, _OUTPUT_DECIMALS),
                            "end_time":   round(index / frames_per_second, _OUTPUT_DECIMALS),
                        })
                    start = None
            if start is not None and len(active) - start >= min_frames:
                regions.append({
                    "start_time": round(start / frames_per_second, _OUTPUT_DECIMALS),
                    "end_time":   round(len(active) / frames_per_second, _OUTPUT_DECIMALS),
                })

            return MusicActivity({ "activity": regions })

        return await self._run_in_executor(_analyze)

    async def _analyze_key(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """Estimate key by correlating an averaged CENS chroma against every
        rotation of the Krumhansl-Schmuckler major and minor profiles.
        `confidence` is the winning correlation minus the second-place, so a
        song with a clear tonal centre reports high confidence and an
        ambiguous one reports low.
        """
        samples, sample_rate = await self._prepare_pcm_samples(source, params)

        def _analyze() -> Dict[str, Any]:
            import numpy as np
            import librosa

            chroma = librosa.feature.chroma_cens(y=samples, sr=sample_rate, hop_length=_DEFAULT_HOP_LENGTH)
            mean = chroma.mean(axis=1)
            norm = np.linalg.norm(mean) or 1.0
            mean = mean / norm

            major = np.asarray(_KRUMHANSL_MAJOR, dtype=np.float32)
            minor = np.asarray(_KRUMHANSL_MINOR, dtype=np.float32)
            scores: List[Tuple[float, str, str]] = []

            for tonic in range(12):
                scores.append((float(np.corrcoef(mean, np.roll(major, tonic))[0, 1]), _PITCH_CLASS_NAMES[tonic], "major"))
                scores.append((float(np.corrcoef(mean, np.roll(minor, tonic))[0, 1]), _PITCH_CLASS_NAMES[tonic], "minor"))

            scores.sort(key=lambda item: item[0], reverse=True)
            best_score, key, mode = scores[0]
            runner_up = scores[1][0]

            return {
                "key":        key,
                "mode":       mode,
                "confidence": round(max(0.0, best_score - runner_up), _OUTPUT_DECIMALS),
            }

        return await self._run_in_executor(_analyze)

    async def _analyze_chroma(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        samples, sample_rate = await self._prepare_pcm_samples(source, params)

        def _analyze() -> Dict[str, Any]:
            import librosa

            chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate, hop_length=_DEFAULT_HOP_LENGTH)
            series = self._build_time_series(
                chroma,
                sample_rate,
                _DEFAULT_HOP_LENGTH,
                "chroma",
                expected_rows=_CHROMA_ROWS,
            )

            return MusicChroma(series)

        return await self._run_in_executor(_analyze)

    async def _analyze_tonnetz(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        samples, sample_rate = await self._prepare_pcm_samples(source, params)

        def _analyze() -> Dict[str, Any]:
            import librosa

            # tonnetz reads chroma internally; passing y+sr keeps it consistent
            # with our other tonal metrics rather than requiring the caller to
            # thread a chroma matrix through separately.
            tonnetz = librosa.feature.tonnetz(y=samples, sr=sample_rate)
            # librosa.feature.tonnetz uses its own default hop; recompute from
            # its output shape so downstream fps is not a lie.
            hop_length = max(1, len(samples) // max(1, tonnetz.shape[1]))
            series = self._build_time_series(
                tonnetz,
                sample_rate,
                hop_length,
                "tonnetz",
                expected_rows=_TONNETZ_ROWS,
            )

            return MusicTonnetz(series)

        return await self._run_in_executor(_analyze)

    async def _analyze_brightness(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        samples, sample_rate = await self._prepare_pcm_samples(source, params)

        def _analyze() -> Dict[str, Any]:
            import librosa

            centroid = librosa.feature.spectral_centroid(
                y=samples, sr=sample_rate, hop_length=_DEFAULT_HOP_LENGTH,
            )[0]
            fps = sample_rate / _DEFAULT_HOP_LENGTH

            return MusicBrightness({
                "brightness_hz": round(float(centroid.mean()), _OUTPUT_DECIMALS),
                "frames":        [ round(float(frame), _OUTPUT_DECIMALS) for frame in centroid ],
                "fps":           round(float(fps), _OUTPUT_DECIMALS),
                "sample_rate":   int(sample_rate),
            })

        return await self._run_in_executor(_analyze)

    async def _analyze_flatness(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        samples, sample_rate = await self._prepare_pcm_samples(source, params)

        def _analyze() -> Dict[str, Any]:
            import librosa

            flatness = librosa.feature.spectral_flatness(y=samples, hop_length=_DEFAULT_HOP_LENGTH)[0]
            fps = sample_rate / _DEFAULT_HOP_LENGTH

            return MusicFlatness({
                "flatness":    round(float(flatness.mean()), _OUTPUT_DECIMALS),
                "frames":      [ round(float(frame), _OUTPUT_DECIMALS) for frame in flatness ],
                "fps":         round(float(fps), _OUTPUT_DECIMALS),
                "sample_rate": int(sample_rate),
            })

        return await self._run_in_executor(_analyze)

    async def _analyze_harmonicity(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        samples, _ = await self._prepare_pcm_samples(source, params)

        def _analyze() -> Dict[str, Any]:
            import numpy as np
            import librosa

            harmonic, percussive = librosa.effects.hpss(samples)
            harmonic_energy = float(np.sum(harmonic.astype(np.float64) ** 2))
            percussive_energy = float(np.sum(percussive.astype(np.float64) ** 2))
            total = harmonic_energy + percussive_energy

            if total <= 0.0:
                return { "harmonicity": 0.0, "percussivity": 0.0 }

            harmonicity = harmonic_energy / total

            return {
                "harmonicity":  round(harmonicity, _OUTPUT_DECIMALS),
                "percussivity": round(1.0 - harmonicity, _OUTPUT_DECIMALS),
            }

        return await self._run_in_executor(_analyze)

    async def _prepare_onset_envelope(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Tuple[np.ndarray, int, int]:
        if isinstance(source, dict):
            return await self._run_in_executor(self._onset_envelope_from_spectrum, source)

        samples, sample_rate = await self._load_pcm_samples(source, params["sample_rate"])

        return await self._run_in_executor(self._onset_envelope_from_audio, samples, sample_rate)

    async def _prepare_energy_envelope(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Tuple[np.ndarray, int, int]:
        """Per-frame total energy — envelope for activity detection. Unlike the
        onset envelope (which only keeps energy *increases*), this keeps the
        raw sum so silences read as low and sustained tones read as high.
        """
        if isinstance(source, dict):
            return await self._run_in_executor(self._energy_envelope_from_spectrum, source)

        samples, sample_rate = await self._load_pcm_samples(source, params["sample_rate"])

        return await self._run_in_executor(self._energy_envelope_from_audio, samples, sample_rate)

    async def _prepare_pcm_samples(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Tuple[np.ndarray, int]:
        """Raw waveform + sample rate. Metrics that need chroma, tonnetz,
        HPSS, or full spectral features go through here; a pre-computed
        spectrum cannot substitute because those functions need phase or a
        different band layout than audio-feature-extractor produces.
        """
        if isinstance(source, dict):
            raise ValueError(
                f"Metric requires raw audio; a pre-computed spectrum is not sufficient. "
                f"Provide `audio: ...` instead of `spectrum: ...` for this metric."
            )

        return await self._load_pcm_samples(source, params["sample_rate"])

    async def _load_pcm_samples(self, source: MediaSource, sample_rate: Optional[int]) -> Tuple[np.ndarray, int]:
        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "audio" ])

        if input_path is None:
            raise ValueError("Native music analyzer requires a file-based audio source.")

        try:
            return await self._run_in_executor(load_pcm_samples, input_path, sample_rate)
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

    @staticmethod
    def _onset_envelope_from_audio(samples: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, int, int]:
        import librosa

        envelope = librosa.onset.onset_strength(y=samples, sr=sample_rate, hop_length=_DEFAULT_HOP_LENGTH)
        return envelope, sample_rate, _DEFAULT_HOP_LENGTH

    @staticmethod
    def _onset_envelope_from_spectrum(spectrum: Dict[str, Any]) -> Tuple[np.ndarray, int, int]:
        """Adapt an audio-feature-extractor spectrum dict into a librosa-shaped
        onset envelope.

        audio-feature-extractor emits `frames` shaped (n_frames, n_bands) after a
        peak-percentile `sqrt(magnitude)` normalization. librosa's
        `onset_strength(S=...)` expects (n_bands, n_frames) power in dB, so we
        transpose, undo the sqrt to recover a magnitude-proportional value, and
        convert to dB. The absolute scale is irrelevant — onset_strength only
        looks at frame-to-frame differences.
        """
        import librosa
        import numpy as np

        frames = np.asarray(spectrum["frames"], dtype=np.float32).T  # (bands, frames)
        sample_rate = int(spectrum["sample_rate"])
        hop_length = max(1, sample_rate // int(spectrum["fps"]))

        if frames.size == 0:
            return np.zeros(0, dtype=np.float32), sample_rate, hop_length

        power = np.square(frames)
        envelope = librosa.onset.onset_strength(
            S=librosa.power_to_db(power, ref=np.max),
            sr=sample_rate,
            hop_length=hop_length,
        )
        return envelope, sample_rate, hop_length

    @staticmethod
    def _energy_envelope_from_audio(samples: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, int, int]:
        import librosa

        # RMS gives a smooth per-frame magnitude that mirrors what
        # analyzer/sustain.py used (sum of log-compressed band energies). We
        # pass frame_length so window size and hop stay in step.
        rms = librosa.feature.rms(y=samples, frame_length=_DEFAULT_HOP_LENGTH * 2, hop_length=_DEFAULT_HOP_LENGTH)[0]

        return rms, sample_rate, _DEFAULT_HOP_LENGTH

    @staticmethod
    def _energy_envelope_from_spectrum(spectrum: Dict[str, Any]) -> Tuple[np.ndarray, int, int]:
        import numpy as np

        frames = np.asarray(spectrum["frames"], dtype=np.float32)  # (n_frames, n_bands)
        sample_rate = int(spectrum["sample_rate"])
        hop_length = max(1, sample_rate // int(spectrum["fps"]))

        if frames.size == 0:
            return np.zeros(0, dtype=np.float32), sample_rate, hop_length

        # Sum of log1p-compressed band magnitudes — matches
        # analyzer/sustain.py:energy_envelope, which is what the percentile
        # threshold in _analyze_activity was tuned against.
        energy = np.sum(np.log1p(frames), axis=1)

        return energy.astype(np.float32), sample_rate, hop_length

    @staticmethod
    def _autocorrelation_confidence(envelope: np.ndarray, sample_rate: int, hop_length: int, params: Dict[str, Any]) -> float:
        """Ratio of the tempo-band autocorrelation peak to its band mean.

        librosa's beat tracker returns a BPM even for arrhythmic input, so this
        gives a downstream signal for gating. A value near 1 means "no dominant
        period in the tempo band"; typical music sits at 3+.
        """
        import librosa
        import numpy as np

        if envelope.size < 2:
            return 0.0

        ac = librosa.autocorrelate(envelope)
        frames_per_second = sample_rate / hop_length
        low = max(1, int(frames_per_second * 60.0 / float(params["max_bpm"])))
        high = min(ac.size, int(frames_per_second * 60.0 / float(params["min_bpm"])) + 1)

        if high <= low:
            return 0.0

        band = ac[low:high]
        mean = float(band.mean())

        if mean <= 0.0:
            return 0.0

        return round(float(band.max() / mean), _OUTPUT_DECIMALS)

    @staticmethod
    def _build_time_series(
        matrix: np.ndarray,
        sample_rate: int,
        hop_length: int,
        label: str,
        expected_rows: int,
    ) -> Dict[str, Any]:
        """Serialize a (rows, n_frames) librosa feature matrix to the shape
        this component publishes: (n_frames, rows), fps, sample_rate.

        `expected_rows` is checked defensively so a librosa version change that
        alters chroma/tonnetz row counts surfaces here instead of silently
        propagating an off-shape array to consumers.
        """
        import numpy as np

        if matrix.ndim != 2 or matrix.shape[0] != expected_rows:
            raise ValueError(
                f"Expected {label} matrix of shape ({expected_rows}, n_frames); "
                f"got {matrix.shape}."
            )

        frames = matrix.T.astype(np.float32)
        fps = sample_rate / hop_length

        return {
            "frames":      [ [ round(float(v), _OUTPUT_DECIMALS) for v in row ] for row in frames ],
            "fps":         round(float(fps), _OUTPUT_DECIMALS),
            "sample_rate": int(sample_rate),
        }

@register_music_analyzer_service(MusicAnalyzerDriver.NATIVE)
class NativeMusicAnalyzerService(MusicAnalyzerService):
    def __init__(self, id: str, config: MusicAnalyzerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "librosa", "numpy", "soundfile" ]

    async def _run(
        self,
        action: MusicAnalyzerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await NativeMusicAnalyzerAction(action).run(context)
