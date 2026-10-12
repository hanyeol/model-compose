"""Unit tests for the stateless pitch-correction helpers.

Scale snap, filter coefficient, median filter — the pieces that encode the
component's musical and signal-processing assumptions. These tests pin down
the behavior so a change here is caught immediately rather than through an
integration test's downstream drift.
"""

import math
import numpy as np
import pytest

from mindor.core.component.services.music_pitch_corrector.drivers.planner import (
    MusicPitchCorrectionPlanner,
)

_planner = MusicPitchCorrectionPlanner(frame_period=0.005)
_key_to_pitch_class             = _planner._key_to_pitch_class
_snap_to_pitch_classes                  = _planner._snap_to_pitch_classes
_retune_filter_alpha            = _planner._retune_filter_alpha
_median_filter_1d               = _planner._median_filter_1d


class TestKeyParsing:
    def test_natural_keys(self):
        assert _key_to_pitch_class("C") == 0
        assert _key_to_pitch_class("A") == 9

    def test_sharps_and_flats(self):
        assert _key_to_pitch_class("F#") == 6
        assert _key_to_pitch_class("Gb") == 6
        assert _key_to_pitch_class("C#") == 1
        assert _key_to_pitch_class("Db") == 1

    def test_rejects_garbage(self):
        with pytest.raises(ValueError):
            _key_to_pitch_class("H")
        with pytest.raises(ValueError):
            _key_to_pitch_class("Ax")


_A_MINOR_PITCH_CLASSES = (0, 2, 4, 5, 7, 9, 11)  # A natural minor: A B C D E F G


class TestSnapToPitchClasses:
    def test_sharp_a_snaps_down_to_a(self):
        # 35 cents above MIDI 57 (A3) → should snap back to 57
        assert _snap_to_pitch_classes(57.35, _A_MINOR_PITCH_CLASSES) == 57.0

    def test_flat_a_snaps_up_to_a(self):
        assert _snap_to_pitch_classes(56.6, _A_MINOR_PITCH_CLASSES) == 57.0

    def test_prefers_closest_allowed(self):
        # In A minor, note 10 (A#) is not allowed, but 9 (A) and 11 (B) are.
        # 69.3 → closer to A4 (69) than B4 (71), both allowed
        assert _snap_to_pitch_classes(69.3, _A_MINOR_PITCH_CLASSES) == 69.0
        # 70.7 → closer to B4 (71) than A4 (69)
        assert _snap_to_pitch_classes(70.7, _A_MINOR_PITCH_CLASSES) == 71.0


class TestRetuneFilterAlpha:
    def test_fast_retune_has_large_alpha(self):
        fast = _retune_filter_alpha(tau=0.005, frame_period=0.005)
        slow = _retune_filter_alpha(tau=0.2, frame_period=0.005)
        assert fast > slow
        assert 0.0 < slow < 1.0
        assert 0.0 < fast <= 1.0 - math.exp(-1.0)  # clamped at tau >= one frame

    def test_zero_tau_clamps_to_one_frame(self):
        """A zero retune_speed shouldn't blow up — it should degenerate to the
        tightest filter the frame rate allows.
        """
        alpha = _retune_filter_alpha(tau=0.0, frame_period=0.005)
        assert alpha == pytest.approx(1.0 - math.exp(-1.0), rel=1e-6)

    def test_invalid_frame_period(self):
        with pytest.raises(ValueError):
            _retune_filter_alpha(0.04, 0.0)


class TestMedianFilter:
    def test_removes_single_spike(self):
        signal = np.array([60.0, 60.0, 72.0, 60.0, 60.0], dtype=np.float32)
        out = _median_filter_1d(signal, window=3)
        assert out[2] == 60.0

    def test_passthrough_when_shorter_than_window(self):
        signal = np.array([60.0, 61.0], dtype=np.float32)
        out = _median_filter_1d(signal, window=3)
        np.testing.assert_array_equal(out, signal)
