"""Tests for :class:`VoiceSegmenter`, the hysteresis state machine shared by
VAD backends. Deterministic — feeds crafted probability sequences without
loading any real model.
"""

from __future__ import annotations

import pytest

from mindor.core.component.services.model.tasks.voice_activity_detection.common import VoiceSegmenter


def _make_segmenter(
    threshold: float = 0.5,
    neg_threshold: float = 0.35,
    min_speech_samples: int = 100,
    min_silence_samples: int = 200,
    speech_pad_samples: int = 50,
) -> VoiceSegmenter:
    return VoiceSegmenter(
        threshold=threshold,
        neg_threshold=neg_threshold,
        min_speech_samples=min_speech_samples,
        min_silence_samples=min_silence_samples,
        speech_pad_samples=speech_pad_samples,
    )


class TestSpeechOnset:
    def test_no_speech_never_triggers(self):
        seg = _make_segmenter()
        for i in range(10):
            assert seg.feed(0.1, offset=i * 50) is None
        assert seg.flush(audio_length=500) is None

    def test_prob_above_threshold_starts_speech_but_no_emit_yet(self):
        seg = _make_segmenter()
        assert seg.feed(0.9, offset=0) is None
        assert seg.triggered is True
        assert seg.speech_start == 0

    def test_low_prob_between_neg_and_threshold_does_not_end(self):
        # prob in [neg_threshold, threshold) keeps state but does not arm temp_end
        seg = _make_segmenter(threshold=0.5, neg_threshold=0.35)
        assert seg.feed(0.9, offset=0) is None      # trigger
        assert seg.feed(0.4, offset=50) is None     # in [0.35, 0.5): neither trigger continuation nor silence
        assert seg.temp_end == 0                    # candidate silence NOT armed


class TestSegmentEmission:
    def test_confirmed_speech_then_silence_emits_segment(self):
        seg = _make_segmenter(min_speech_samples=100, min_silence_samples=200)
        # Speech from offset=0 to offset=500 (>= min_speech_samples)
        for offset in (0, 50, 100, 500):
            result = seg.feed(0.9, offset=offset)
            assert result is None
        # Enter silence at offset=550 (temp_end=550)
        assert seg.feed(0.1, offset=550) is None
        assert seg.temp_end == 550
        # Silence continues but not yet long enough (300 - 550 = -250? offsets go up)
        # Need offset - temp_end >= min_silence_samples (200)
        # temp_end=550, so need offset >= 750
        assert seg.feed(0.1, offset=650) is None    # 100 < 200
        # At offset=750, silence duration == 200 (== min_silence_samples): still not >=
        # Wait, code uses `< min_silence_samples`, so 200 satisfies... let's use 800 to be safe
        result = seg.feed(0.1, offset=800)
        assert result is not None, "segment should be confirmed"
        start, end, probs = result
        assert start == 0
        assert end == 550
        assert len(probs) > 0
        # After emission, state is reset
        assert seg.triggered is False
        assert seg.speech_start is None
        assert seg.temp_end == 0

    def test_short_speech_dropped(self):
        seg = _make_segmenter(min_speech_samples=1000, min_silence_samples=200)
        # Speech from 0..50 (way below min_speech_samples=1000)
        assert seg.feed(0.9, offset=0) is None
        # Long silence to confirm end
        assert seg.feed(0.1, offset=50) is None      # temp_end=50
        result = seg.feed(0.1, offset=1000)          # 950 > 200 → confirms end
        # Segment (0..50) has length 50 which is < 1000, so NOT emitted
        assert result is None
        # State should still reset
        assert seg.triggered is False

    def test_speech_resumes_cancels_pending_silence(self):
        seg = _make_segmenter(min_speech_samples=100, min_silence_samples=200)
        assert seg.feed(0.9, offset=0) is None       # trigger
        assert seg.feed(0.1, offset=100) is None     # candidate end (temp_end=100)
        assert seg.temp_end == 100
        # Speech resumes before silence is confirmed
        assert seg.feed(0.9, offset=150) is None
        assert seg.temp_end == 0, "candidate end should be cleared on speech resumption"
        assert seg.triggered is True


class TestFlush:
    def test_flush_empty_returns_none(self):
        seg = _make_segmenter()
        assert seg.flush(audio_length=1000) is None

    def test_flush_confirms_trailing_speech_if_long_enough(self):
        seg = _make_segmenter(min_speech_samples=100)
        assert seg.feed(0.9, offset=0) is None
        assert seg.feed(0.9, offset=50) is None
        # Speech ongoing when stream ends at length 500 (500 > min_speech_samples=100)
        result = seg.flush(audio_length=500)
        assert result is not None
        start, end, probs = result
        assert start == 0
        assert end == 500

    def test_flush_drops_trailing_too_short(self):
        seg = _make_segmenter(min_speech_samples=1000)
        assert seg.feed(0.9, offset=0) is None
        # Only 50 samples of speech when stream ends
        assert seg.flush(audio_length=50) is None


class TestHysteresis:
    def test_middle_prob_neither_triggers_nor_ends(self):
        # prob between neg_threshold and threshold: neutral zone
        seg = _make_segmenter(threshold=0.6, neg_threshold=0.3)
        for i in range(10):
            assert seg.feed(0.45, offset=i * 50) is None
        assert seg.triggered is False

    def test_temp_end_not_armed_in_neutral_zone(self):
        seg = _make_segmenter(threshold=0.6, neg_threshold=0.3)
        seg.feed(0.9, offset=0)                     # trigger
        seg.feed(0.45, offset=50)                   # neutral: no temp_end
        assert seg.temp_end == 0
        seg.feed(0.2, offset=100)                   # below neg_threshold: temp_end armed
        assert seg.temp_end == 100
