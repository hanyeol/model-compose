from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Any, Tuple
from mindor.dsl.schema.component import MusicPitchCorrectorComponentConfig
from mindor.dsl.schema.action import MusicPitchCorrectorActionConfig
from mindor.core.foundation.variable.time import parse_time
from ..base import MusicPitchCorrectorDriver, MusicPitchCorrectorDriverType, register_music_pitch_corrector_driver
from ..base import ComponentActionContext
from mindor.dsl.schema.action.impl.music_pitch_corrector.impl.common import MusicPitchCorrectorActionMethod
from .common import MusicPitchCorrectorAction

if TYPE_CHECKING:
    import numpy as np

class WorldMusicPitchCorrectorAction(MusicPitchCorrectorAction):
    def __init__(
        self,
        config: MusicPitchCorrectorActionConfig,
        frame_period: float,
        f0_estimator: str,
    ):
        super().__init__(config, frame_period=frame_period)

        self.f0_estimator: str = f0_estimator

    async def _resolve_params(self, method: MusicPitchCorrectorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(method, context)

        if method in (MusicPitchCorrectorActionMethod.APPLY, MusicPitchCorrectorActionMethod.CORRECT):
            formant_shift = await context.render_scalar(self.config.formant_shift, float, 0.0)

            params.update({
                "formant_shift": formant_shift,
            })

        return params

    async def _apply_curve(
        self,
        samples: np.ndarray,
        sample_rate: int,
        curve: Dict[str, Any],
        params: Dict[str, Any],
    ) -> np.ndarray:
        def _synthesize() -> np.ndarray:
            import pyworld as pw
            import numpy as np

            waveform = samples.astype(np.float64)

            # pyworld's dio/harvest/cheaptrick/synthesize take frame_period in milliseconds.
            frame_period_ms = self.frame_period * 1000.0

            if self.f0_estimator == "harvest":
                f0, t = pw.harvest(waveform, sample_rate, frame_period=frame_period_ms)
            else:
                f0, t = pw.dio(waveform, sample_rate, frame_period=frame_period_ms)
                f0 = pw.stonemask(waveform, f0, t, sample_rate)

            spectrogram = pw.cheaptrick(waveform, f0, t, sample_rate)
            aperiodicity = pw.d4c(waveform, f0, t, sample_rate)

            shift_cents = self._interpolate_shift_cents(curve, t)
            f0_shifted = self._apply_shift(f0, shift_cents)

            if params["formant_shift"] != 0.0:
                spectrogram = self._shift_formants(spectrogram, params["formant_shift"])

            waveform = pw.synthesize(f0_shifted, spectrogram, aperiodicity, sample_rate, frame_period_ms)

            if params.get("sample_rate") is not None and params["sample_rate"] != sample_rate:
                import soxr

                waveform = soxr.resample(waveform.astype(np.float32), sample_rate, params["sample_rate"])

            return waveform.astype(np.float32)

        return await self._run_in_executor(_synthesize)

    def _interpolate_shift_cents(self, curve: Dict[str, Any], analysis_times: np.ndarray) -> np.ndarray:
        import numpy as np

        frames = curve.get("frames") or {}
        curve_times = np.asarray(frames.get("time", []), dtype=np.float64)
        curve_shifts = np.asarray(frames.get("shift_cents", []), dtype=np.float64)

        if curve_times.size == 0:
            return self._shift_cents_from_notes_only(curve, analysis_times)

        return np.interp(analysis_times, curve_times, curve_shifts, left=curve_shifts[0], right=curve_shifts[-1])

    @staticmethod
    def _shift_cents_from_notes_only(curve: Dict[str, Any], analysis_times: np.ndarray) -> np.ndarray:
        """Fallback when the user stripped `frames` from the curve. Reconstruct a
        per-frame step from the notes alone — coarser than a filtered curve but
        enough for a user who only kept the notes list.
        """
        import numpy as np

        shift_cents = np.zeros_like(analysis_times, dtype=np.float64)

        for note in curve.get("notes", []):
            if note.get("target_pitch") is None:
                continue

            shift = (note["target_pitch"] - note["sung_pitch"]) * 100.0
            mask = (analysis_times >= note["start_time"]) & (analysis_times < note["end_time"])
            shift_cents[mask] = shift

        return shift_cents

    @staticmethod
    def _apply_shift(f0: np.ndarray, shift_cents: np.ndarray) -> np.ndarray:
        import numpy as np

        voiced_mask = f0 > 0.0
        shifted_f0 = np.where(voiced_mask, f0 * np.power(2.0, shift_cents / 1200.0), 0.0)

        return shifted_f0.astype(np.float64)

    @staticmethod
    def _shift_formants(spectrogram: np.ndarray, semitones: float) -> np.ndarray:
        """Scale the spectral envelope along the frequency axis. Positive values
        stretch toward higher frequencies (shorter vocal tract), negative values
        compress toward lower.
        """
        import numpy as np

        ratio = float(2.0 ** (semitones / 12.0))
        _, n_bins = spectrogram.shape
        source_bins = np.arange(n_bins, dtype=np.float64) / ratio

        low = np.clip(np.floor(source_bins).astype(np.int64), 0, n_bins - 1)
        high = np.clip(low + 1, 0, n_bins - 1)
        frac = source_bins - low

        return spectrogram[:, low] * (1.0 - frac) + spectrogram[:, high] * frac

@register_music_pitch_corrector_driver(MusicPitchCorrectorDriverType.WORLD)
class WorldMusicPitchCorrectorService(MusicPitchCorrectorDriver):
    def __init__(self, id: str, config: MusicPitchCorrectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.frame_period: float = parse_time(self.config.frame_period)
        self.f0_estimator: str = str(self.config.f0_estimator)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "pyworld", "numpy", "soxr", "soundfile", "librosa" ]

    async def _run(self, action: MusicPitchCorrectorActionConfig, context: ComponentActionContext) -> Any:
        return await WorldMusicPitchCorrectorAction(action, self.frame_period, self.f0_estimator).run(context)
