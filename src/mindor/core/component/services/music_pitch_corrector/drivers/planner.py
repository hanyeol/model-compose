from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.action.impl.music_pitch_corrector.impl.common import (
    MusicPitchCorrectionMode,
    MusicPitchCorrectionOutOfRangeMode,
)
from bisect import bisect_right

if TYPE_CHECKING:
    import numpy as np

# Decimal places kept in emitted numbers. 3 is below the perceptible pitch
# resolution (~5 cents ≈ 0.003 semitones) and matches other music-* components.
_RESULT_DECIMALS = 3

# Window for the median filter that removes octave jumps during preprocessing.
# 3 frames at 5ms hop = 15ms, short enough to leave vibrato intact.
_MEDIAN_WINDOW = 3

# Guard for the smoothing LPF: τ ≥ one frame period, so a 0ms retune_speed
# collapses to a one-frame step instead of a divide-by-zero.
_MIN_TAU_FRAMES = 1.0

_KEY_PITCH_CLASS_MAP: Dict[str, int] = {
    "C":  0, "C#": 1,  "Db": 1,
    "D":  2, "D#": 3,  "Eb": 3,
    "E":  4,
    "F":  5, "F#": 6,  "Gb": 6,
    "G":  7, "G#": 8,  "Ab": 8,
    "A":  9, "A#": 10, "Bb": 10,
    "B": 11,
}

class MusicPitchCorrectionPlanner:
    """Pure CPU-bound planner. Produces a correction curve + report (both as
    plain dicts) from a pre-decoded pitch track. Steps 1-6 of the planning
    algorithm are driven from ``plan``: preprocess → note split → representative
    pitch → target → per-note shift → frame-level smoothed shift.
    """
    def __init__(self, frame_period: float):
        self.frame_period: float = frame_period

    def plan(
        self,
        f0_semitones: np.ndarray,
        confidence: np.ndarray,
        time_axis: np.ndarray,
        voiced_mask: np.ndarray,
        key: Optional[str],
        scale: List[int],
        melody: Any,
        melody_offset: float,
        params: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        import numpy as np

        warnings: List[str] = []

        # Step 1 — preprocess: zero low-confidence and unvoiced frames, median-filter.
        masked_pitch = f0_semitones.copy()
        masked_pitch[~voiced_mask] = np.nan
        masked_pitch[confidence < params["min_confidence"]] = np.nan

        pitch_finites = np.isfinite(masked_pitch)
        voiced_ratio = float(pitch_finites.mean()) if masked_pitch.size else 0.0

        if voiced_ratio == 0.0:
            raise ValueError("Input has no voiced frames above the confidence floor; cannot plan correction.")

        if voiced_ratio < 0.2:
            warnings.append(f"low voiced ratio ({voiced_ratio:.2f})")

        # Fill NaNs for the median filter (they persist in `voiced_mask`).
        filled_pitch = masked_pitch.copy()

        if pitch_finites.any():
            filled_pitch = np.where(pitch_finites, filled_pitch, np.nan)
            last_valid = np.nan

            for index in range(filled_pitch.size):
                if np.isnan(filled_pitch[index]):
                    filled_pitch[index] = last_valid if not np.isnan(last_valid) else 0.0
                else:
                    last_valid = filled_pitch[index]

        smoothed_pitch = self._median_filter_1d(filled_pitch, _MEDIAN_WINDOW)

        # Step 2 — split into notes.
        sung_notes = self._split_pitch_into_notes(smoothed_pitch, pitch_finites, time_axis, params)

        # Steps 3-5 setup — resolve scale pitch classes or normalize the melody notes.
        if params["mode"] == MusicPitchCorrectionMode.SCALE and key is not None:
            allowed_pitch_classes = tuple(sorted({
                (self._key_to_pitch_class(key) + int(offset)) % 12 for offset in scale
            }))
        else:
            allowed_pitch_classes = None

        if params["mode"] == MusicPitchCorrectionMode.MELODY and melody is not None:
            melody_notes = self._resolve_melody_notes(melody)
        else:
            melody_notes = None

        # Steps 3-5 — target choice, correction decision, per-note shift
        # (center semitone move, vibrato left in place).
        for note in sung_notes:
            if params["mode"] == MusicPitchCorrectionMode.SCALE and allowed_pitch_classes is not None:
                target_pitch = self._snap_to_pitch_classes(note["sung_pitch"], allowed_pitch_classes)
            elif params["mode"] == MusicPitchCorrectionMode.MELODY and melody_notes:
                target_pitch = self._lookup_melody_pitch(note, melody_notes, melody_offset)
            else:
                target_pitch = None

            target_pitch, status, correction_cents = self._decide_note_correction(
                note["sung_pitch"],
                target_pitch,
                params,
                allowed_pitch_classes
            )

            if target_pitch is not None:
                shift_semitones = (target_pitch - note["sung_pitch"]) * params["strength"]
            else:
                shift_semitones = 0.0

            note.update({
                "target_pitch":     target_pitch,
                "status":           status,
                "correction_cents": correction_cents,
                "shift_semitones":  shift_semitones,
            })

        # Step 6 — assemble per-frame shift and smooth with a 1st-order filter run
        # both directions (zero-phase) so the curve starts moving slightly before
        # each note boundary. A real-time engine would run the same α single-pass.
        if params["return_frames"]:
            frames = self._smooth_note_shifts_to_frames(smoothed_pitch, pitch_finites, time_axis, sung_notes, params)
        else:
            frames = None

        report = self._build_plan_report(sung_notes, voiced_ratio, warnings)

        curve: Dict[str, Any] = {
            "reference_pitch": round(params["reference_pitch"], _RESULT_DECIMALS),
            "frame_period":    round(params["frame_period"], 4),
            "settings":        {
                "mode":         params["mode"].value,
                "key":          key,
                "scale":        list(scale),
                "strength":     round(params["strength"], _RESULT_DECIMALS),
                "retune_speed": round(params["retune_speed"], 4),
            },
            "notes":  [ self._serialize_note(note) for note in sung_notes ],
        }

        if frames is not None:
            curve["frames"] = frames

        return curve, report

    def _decide_note_correction(
        self,
        sung_pitch: float,
        target_pitch: Optional[float],
        params: Dict[str, Any],
        allowed_pitch_classes: Optional[Tuple[int, ...]],
    ) -> Tuple[Optional[float], str, float]:
        """Decide the final (target_pitch, status, correction_cents) for a note
        given a candidate ``target_pitch``. The caller passes the scale-snap or
        melody lookup result; ``None`` means the note has no in-range target.
        """
        tolerance_semitones = params["tolerance_cents"] / 100.0
        max_correction_semitones = params["max_correction_cents"] / 100.0

        if target_pitch is None:
            if params["out_of_range"] == MusicPitchCorrectionOutOfRangeMode.SNAP and allowed_pitch_classes is not None:
                return self._snap_to_pitch_classes(sung_pitch, allowed_pitch_classes), "corrected", 0.0

            return None, "out_of_range", 0.0

        distance = target_pitch - sung_pitch

        if abs(distance) < tolerance_semitones:
            return target_pitch, "within_tolerance", 0.0

        if abs(distance) > max_correction_semitones:
            if params["out_of_range"] != MusicPitchCorrectionOutOfRangeMode.SNAP:
                return None, "out_of_range", 0.0

        return target_pitch, "corrected", (target_pitch - sung_pitch) * 100.0

    def _smooth_note_shifts_to_frames(
        self,
        smoothed_pitch: np.ndarray,
        voiced_mask: np.ndarray,
        time_axis: np.ndarray,
        sung_notes: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        import numpy as np

        shift_cents_step = np.zeros(smoothed_pitch.size, dtype=np.float32)

        for note in sung_notes:
            shift_cents_step[note["frame_start"] : note["frame_end"] + 1] = note["shift_semitones"] * 100.0

        alpha = self._retune_filter_alpha(params["retune_speed"], params["frame_period"])
        smoothed_shift = self._bidirectional_lpf(shift_cents_step, alpha)

        # Suppress correction on unvoiced frames — WORLD will reproduce them as-is.
        smoothed_shift = np.where(voiced_mask, smoothed_shift, 0.0)

        return {
            "time":        [ round(float(t), _RESULT_DECIMALS) for t in time_axis ],
            "f0":          [ round(float(f), _RESULT_DECIMALS) if np.isfinite(f) else 0.0 for f in smoothed_pitch ],
            "shift_cents": [ round(float(s), _RESULT_DECIMALS) for s in smoothed_shift ],
        }

    def _key_to_pitch_class(self, key: str) -> int:
        """Map a key spelling (``A``, ``F#``, ``Bb``, ``Db``) to a 0-11 pitch
        class. Accepts flats so music-analyzer output can be fed through
        unchanged even though its canonical names are sharps; unicode
        accidentals (``♯``/``♭``) are normalized to ASCII first.
        """
        normalized_key = key.replace("♯", "#").replace("♭", "b")

        try:
            return _KEY_PITCH_CLASS_MAP[normalized_key]
        except KeyError:
            raise ValueError(f"Invalid key: {key!r}")

    def _snap_to_pitch_classes(self, sung_pitch: float, allowed_pitch_classes: Tuple[int, ...]) -> float:
        """Return the MIDI note nearest to ``sung_pitch`` whose pitch class is
        in ``allowed_pitch_classes``.
        """
        # Walk the two semitones on either side of the rounded note and pick
        # the closest one that lands on an allowed pitch class. ±2 is enough:
        # for any chromatic input, the nearest allowed class is at most 1
        # semitone away in the worst case (adjacent pitch classes), so a
        # window of 2 is safe.
        center = int(round(sung_pitch))
        best_note: Optional[int] = None
        best_distance = float("inf")

        for candidate in range(center - 2, center + 3):
            if candidate % 12 in allowed_pitch_classes:
                distance = abs(candidate - sung_pitch)

                if distance < best_distance:
                    best_distance = distance
                    best_note = candidate

        if best_note is None:
            raise ValueError("No allowed pitch class within ±2 semitones.")

        return float(best_note)

    def _split_pitch_into_notes(
        self,
        smoothed_pitch: np.ndarray,
        voiced_mask: np.ndarray,
        time_axis: np.ndarray,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Walk voiced frames, cutting at step-like semitone jumps >= 50 cents.
        Fragments shorter than ``min_note_duration`` are merged back into the
        neighbour with the smaller pitch distance.
        """
        import numpy as np

        frame_period = params["frame_period"]
        min_frames = max(1, round(params["min_note_duration"] / frame_period))

        segments: List[List[int]] = []
        current: List[int] = []
        previous_pitch: Optional[float] = None

        for index in range(smoothed_pitch.size):
            if not voiced_mask[index]:
                if current:
                    segments.append(current)
                    current = []

                previous_pitch = None

                continue

            if previous_pitch is not None and abs(smoothed_pitch[index] - previous_pitch) >= 0.5:
                if current:
                    segments.append(current)
                current = [index]
            else:
                current.append(index)

            previous_pitch = smoothed_pitch[index]

        if current:
            segments.append(current)

        # Merge short fragments into the neighbour with the closer median pitch.
        merged_segments: List[List[int]] = []

        for segment in segments:
            if len(segment) < min_frames and merged_segments:
                merged_segments[-1].extend(segment)
            else:
                merged_segments.append(segment)

        notes: List[Dict[str, Any]] = []
        transition_frames = max(1, round(params["transition"] / frame_period))

        for index, segment in enumerate(merged_segments):
            start_index, end_index = segment[0], segment[-1]
            stable_start_index = min(start_index + transition_frames, end_index)
            stable_end_index = max(end_index - transition_frames, stable_start_index)
            stable_slice = smoothed_pitch[stable_start_index : stable_end_index + 1]

            if stable_slice.size == 0:
                stable_slice = smoothed_pitch[start_index : end_index + 1]

            sung_pitch = float(np.median(stable_slice))
            notes.append({
                "index":          index,
                "frame_start":    start_index,
                "frame_end":      end_index,
                "start_time":     float(time_axis[start_index]),
                "end_time":       float(time_axis[end_index]) + frame_period,
                "sung_pitch":     sung_pitch,
                "target_pitch":   None,
                "correction_cents": 0.0,
                "status":         "corrected",
                "shift_semitones": 0.0,
            })

        return notes

    def _resolve_melody_notes(self, melody: Any) -> List[Dict[str, Any]]:
        if isinstance(melody, list):
            notes: List[Dict[str, Any]] = []

            for note in melody:
                if not isinstance(note, dict):
                    raise ValueError("Each melody entry must be an object with start_time/end_time/pitch.")

                notes.append({
                    "start_time": float(note["start_time"]),
                    "end_time":   float(note["end_time"]),
                    "pitch":      float(note["pitch"]),
                })

            return sorted(notes, key=lambda note: note["start_time"])

        raise ValueError("`melody` must be a list of note objects.")

    def _lookup_melody_pitch(
        self,
        sung_note: Dict[str, Any],
        melody_notes: List[Dict[str, Any]],
        offset: float,
    ) -> Optional[float]:
        center_in_melody = 0.5 * (sung_note["start_time"] + sung_note["end_time"]) - offset
        index = bisect_right(melody_notes, center_in_melody, key=lambda note: note["start_time"]) - 1

        if index >= 0 and melody_notes[index]["end_time"] >= center_in_melody:
            return melody_notes[index]["pitch"]

        return None

    def _median_filter_1d(self, signal: np.ndarray, window: int = _MEDIAN_WINDOW) -> np.ndarray:
        import numpy as np

        if window < 2 or signal.size < window:
            return signal

        half_window = window // 2
        padded_signal = np.pad(signal, (half_window, half_window), mode="edge")
        filtered_signal = np.empty_like(signal)

        for index in range(signal.size):
            filtered_signal[index] = np.median(padded_signal[index : index + window])

        return filtered_signal

    def _retune_filter_alpha(self, tau: float, frame_period: float) -> float:
        """Smoothing coefficient for a one-pole LPF whose step response reaches
        ~63% in ``tau``. ``alpha = 1 - exp(-dt/tau)``.
        """
        import math

        if frame_period <= 0.0:
            raise ValueError("frame_period must be positive.")

        tau_frames = max(_MIN_TAU_FRAMES, tau / frame_period)

        return 1.0 - math.exp(-1.0 / tau_frames)

    def _bidirectional_lpf(self, signal: np.ndarray, alpha: float) -> np.ndarray:
        """Zero-phase one-pole LPF: forward pass then backward pass. The
        equivalent single-pass filter is what a real-time engine would run.
        """
        import numpy as np

        if alpha >= 1.0:
            return signal.astype(np.float32)

        # Initialize each pass to the first sample it will see so a steady DC
        # input passes through unchanged — otherwise the filter would spend
        # ~1/α frames climbing out of zero at both ends.
        forward = np.empty_like(signal, dtype=np.float32)
        state = float(signal[0]) if signal.size else 0.0

        for index in range(signal.size):
            state = state + alpha * (signal[index] - state)
            forward[index] = state

        backward = np.empty_like(forward)
        state = float(forward[-1]) if forward.size else 0.0

        for index in range(forward.size - 1, -1, -1):
            state = state + alpha * (forward[index] - state)
            backward[index] = state

        return backward

    def _build_plan_report(
        self,
        sung_notes: List[Dict[str, Any]],
        voiced_ratio: float,
        warnings: List[str],
    ) -> Dict[str, Any]:
        import numpy as np

        status_counts: Dict[str, int] = {}
        corrected_shifts: List[float] = []

        for note in sung_notes:
            status_counts[note["status"]] = status_counts.get(note["status"], 0) + 1

            if note["status"] == "corrected" and note["target_pitch"] is not None:
                corrected_shifts.append(abs(note["correction_cents"]))

        out_of_range_count = status_counts.get("out_of_range", 0)

        if sung_notes and out_of_range_count / len(sung_notes) > 0.3:
            warnings.append(f"{out_of_range_count}/{len(sung_notes)} notes out of range — check the key input")

        if corrected_shifts == [] and sung_notes:
            warnings.append("no notes required correction")

        return {
            "notes_total":               len(sung_notes),
            "notes_corrected":           len(corrected_shifts),
            "notes_within_tolerance":    status_counts.get("within_tolerance", 0),
            "notes_out_of_range":        out_of_range_count,
            "voiced_ratio":              round(voiced_ratio, _RESULT_DECIMALS),
            "mean_abs_correction_cents": round(float(np.mean(corrected_shifts)), _RESULT_DECIMALS) if corrected_shifts else 0.0,
            "max_correction_cents":      round(float(max(corrected_shifts)), _RESULT_DECIMALS) if corrected_shifts else 0.0,
            "warnings":                  warnings,
        }

    def _serialize_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "index":            note["index"],
            "start_time":       round(note["start_time"], _RESULT_DECIMALS),
            "end_time":         round(note["end_time"], _RESULT_DECIMALS),
            "sung_pitch":       round(note["sung_pitch"], _RESULT_DECIMALS),
            "target_pitch":     None if note["target_pitch"] is None else round(note["target_pitch"], _RESULT_DECIMALS),
            "correction_cents": round(note["correction_cents"], _RESULT_DECIMALS),
            "status":           note["status"],
        }

