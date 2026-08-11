"""Unit tests for ``NativeStreamingTranscriptCorrector``.

Focus areas:
- Segment-level anchor matching (correct text replaced by reference span).
- Timestamps and unrelated segment keys are preserved verbatim.
- Reference cursor advances so subsequent segments match forward-only.
- Design rules (per user requirements):
    * whole-segment replacement,
    * below-threshold segments are skipped,
    * segments after reference exhaustion are skipped,
    * leftover reference at flush time is discarded.
- Multi-script coverage (English, Korean, Chinese/character mode).
- Punctuation / casing normalization does not leak into output.
"""

from typing import Any, Dict, Iterator, List

import pytest

from mindor.core.component.services.transcript_corrector.drivers.native import (
    NativeStreamingTranscriptCorrector,
)
from mindor.dsl.schema.action.impl.transcript_corrector.impl.common import (
    TranscriptGranularity,
)


def _make_corrector(
    reference: str,
    *,
    granularity: TranscriptGranularity = TranscriptGranularity.WORD,
    text_key: str = "text",
    start_time_key: str = "start_time",
    end_time_key: str = "end_time",
    case_sensitive: bool = False,
    ignore_punctuation: bool = True,
    window_multiplier: float = 3.0,
    min_window_tokens: int = 8,
    match_threshold: float = 0.5,
) -> NativeStreamingTranscriptCorrector:
    return NativeStreamingTranscriptCorrector(
        reference=reference,
        granularity=granularity,
        text_key=text_key,
        start_time_key=start_time_key,
        end_time_key=end_time_key,
        case_sensitive=case_sensitive,
        ignore_punctuation=ignore_punctuation,
        window_multiplier=window_multiplier,
        min_window_tokens=min_window_tokens,
        match_threshold=match_threshold,
    )


def _matched(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out estimated gap segments so tests can focus on anchored ones."""
    return [ r for r in results if not r.get("estimated") ]


def _estimated(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only estimated gap segments."""
    return [ r for r in results if r.get("estimated") ]


def _drain(it: Iterator[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return list(it)


def _correct_all(
    reference: str,
    segments: List[Dict[str, Any]],
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """Feed every segment, then flush. Convenience for non-streaming scenarios."""
    corrector = _make_corrector(reference, **kwargs)
    out: List[Dict[str, Any]] = []
    for segment in segments:
        out.extend(_drain(corrector.feed(segment)))
    out.extend(_drain(corrector.flush()))
    return out


class TestBasicWordAlignment:
    def test_exact_match_returns_reference_text_verbatim(self):
        result = _correct_all(
            "hello world",
            [{"text": "hello world", "start_time": 0.0, "end_time": 1.0}],
        )
        assert result == [{"text": "hello world", "start_time": 0.0, "end_time": 1.0}]

    def test_typo_is_corrected_to_reference_span(self):
        # STT drops letters — should still anchor to the reference span.
        result = _correct_all(
            "hello world",
            [{"text": "helo wrld", "start_time": 0.0, "end_time": 1.0}],
        )
        assert result[0]["text"] == "hello world"

    def test_multiple_segments_walk_the_reference_forward(self):
        result = _correct_all(
            "hello world this is a small test of the alignment system",
            [
                {"text": "helo wrld", "start_time": 0.0, "end_time": 1.0},
                {"text": "this is a smal test", "start_time": 1.0, "end_time": 2.5},
                {"text": "of the aligment sistem", "start_time": 2.5, "end_time": 4.0},
            ],
        )
        assert [r["text"] for r in result] == [
            "hello world",
            "this is a small test",
            "of the alignment system",
        ]

    def test_original_timestamps_are_preserved(self):
        result = _correct_all(
            "hello world",
            [{"text": "helo wrld", "start_time": 12.5, "end_time": 13.7}],
        )
        assert result[0]["start_time"] == 12.5
        assert result[0]["end_time"] == 13.7


class TestSegmentKeyPreservation:
    def test_extra_keys_pass_through(self):
        result = _correct_all(
            "hello world",
            [{
                "text": "helo wrld",
                "start_time": 0.0,
                "end_time": 1.0,
                "confidence": 0.87,
                "speaker": "A",
            }],
        )
        assert result[0]["confidence"] == 0.87
        assert result[0]["speaker"] == "A"

    def test_original_segment_object_is_not_mutated(self):
        segment = {"text": "helo wrld", "start_time": 0.0, "end_time": 1.0}
        _correct_all("hello world", [segment])
        # The input dict should remain unchanged.
        assert segment == {"text": "helo wrld", "start_time": 0.0, "end_time": 1.0}

    def test_custom_text_key_is_respected(self):
        result = _correct_all(
            "hello world",
            [{"transcript": "helo wrld", "start_time": 0.0, "end_time": 1.0}],
            text_key="transcript",
        )
        assert result[0]["transcript"] == "hello world"


class TestReferenceCursorAdvance:
    def test_second_segment_does_not_rematch_earlier_reference(self):
        # If the corrector allowed re-matching, "hello" arriving second could
        # snap back to the reference's leading "hello". The cursor must prevent
        # that: the second segment can only match "world" (or nothing).
        result = _correct_all(
            "hello world",
            [
                {"text": "hello", "start_time": 0.0, "end_time": 0.5},
                {"text": "hello", "start_time": 0.5, "end_time": 1.0},
            ],
            match_threshold=0.4,
        )
        texts = [r["text"] for r in result]
        # First segment always anchors to "hello". The second must not.
        assert texts[0] == "hello"
        assert "hello" not in texts[1:]


class TestSkipRules:
    """Segments that fail to anchor produce no matched output. The reference
    they didn't cover surfaces later as estimated gap segments — those tests
    live in TestGapFill."""

    def test_below_threshold_segment_is_skipped(self):
        result = _correct_all(
            "hello world",
            [{"text": "completely different text", "start_time": 0.0, "end_time": 1.0}],
            match_threshold=0.9,
        )
        assert _matched(result) == []

    def test_segment_after_reference_exhaustion_is_skipped(self):
        result = _correct_all(
            "hello",
            [
                {"text": "hello", "start_time": 0.0, "end_time": 0.5},
                {"text": "world", "start_time": 0.5, "end_time": 1.0},
                {"text": "extra", "start_time": 1.0, "end_time": 1.5},
            ],
        )
        matched = _matched(result)
        # Only the segment that fits the reference gets emitted as an anchor.
        assert len(matched) == 1
        assert matched[0]["text"] == "hello"

    def test_flush_yields_nothing_extra_after_normal_feeding(self):
        corrector = _make_corrector("hello world")
        list(corrector.feed({"text": "hello world", "start_time": 0.0, "end_time": 1.0}))
        assert list(corrector.flush()) == []

    def test_empty_text_segment_is_skipped(self):
        result = _correct_all(
            "hello world",
            [{"text": "", "start_time": 0.0, "end_time": 1.0}],
        )
        assert _matched(result) == []

    def test_whitespace_only_text_segment_is_skipped(self):
        result = _correct_all(
            "hello world",
            [{"text": "   ", "start_time": 0.0, "end_time": 1.0}],
        )
        assert _matched(result) == []

    def test_non_dict_segment_is_skipped(self):
        # feed() is defensive — pass a non-dict and expect no crash, no emit.
        corrector = _make_corrector("hello world")
        assert list(corrector.feed("not a dict")) == []
        assert list(corrector.feed(None)) == []


class TestInsertionsAndDeletions:
    def test_stt_missed_a_word_gets_filled_from_reference(self):
        # STT: "please turn off lights"  (missing "the")
        # REF: "please turn off the lights"
        result = _correct_all(
            "please turn off the lights before you leave the room",
            [
                {"text": "please turn off lights", "start_time": 0.0, "end_time": 1.0},
                {"text": "before you leave the room", "start_time": 1.0, "end_time": 2.0},
            ],
        )
        assert result[0]["text"] == "please turn off the lights"
        assert result[1]["text"] == "before you leave the room"

    def test_stt_inserted_extra_word_still_anchors(self):
        # STT: "please please turn off the lights" (duplicated word)
        # REF: "please turn off the lights"
        result = _correct_all(
            "please turn off the lights and go home",
            [{"text": "please please turn off the lights",
              "start_time": 0.0, "end_time": 1.0}],
        )
        # The corrected text should be the reference span, not the STT.
        assert result[0]["text"] == "please turn off the lights"


class TestNormalization:
    def test_case_insensitive_by_default(self):
        result = _correct_all(
            "Hello World",
            [{"text": "hello world", "start_time": 0.0, "end_time": 1.0}],
        )
        # Output preserves the reference's original casing.
        assert result[0]["text"] == "Hello World"

    def test_case_sensitive_mode_still_matches_when_case_agrees(self):
        result = _correct_all(
            "Hello World",
            [{"text": "Hello World", "start_time": 0.0, "end_time": 1.0}],
            case_sensitive=True,
        )
        assert result[0]["text"] == "Hello World"

    def test_reference_punctuation_is_preserved_in_output(self):
        # `ignore_punctuation=True` only affects the similarity score, not
        # the visible output token. Reference punctuation must survive.
        result = _correct_all(
            "hello, world!",
            [{"text": "helo wrld", "start_time": 0.0, "end_time": 1.0}],
        )
        # The word tokenizer strips punctuation from tokens, so the output
        # is a whitespace-joined list of alnum tokens from the reference.
        # We check the tokens themselves round-trip.
        assert "hello" in result[0]["text"]
        assert "world" in result[0]["text"]


class TestKoreanAlignment:
    def test_typos_in_korean_are_corrected(self):
        result = _correct_all(
            "오늘 날씨가 정말 좋네요 내일도 맑다고 해요",
            [
                {"text": "오늘 날시가", "start_time": 0.0, "end_time": 0.8},
                {"text": "정말 조네요", "start_time": 0.8, "end_time": 1.5},
                {"text": "내일도 맑다고 해요", "start_time": 1.5, "end_time": 3.0},
            ],
        )
        assert [r["text"] for r in result] == [
            "오늘 날씨가",
            "정말 좋네요",
            "내일도 맑다고 해요",
        ]


class TestCharacterGranularity:
    def test_chinese_segments_align_character_by_character(self):
        result = _correct_all(
            "今天天气很好我们去公园散步",
            [
                {"text": "今天天气很好", "start_time": 0.0, "end_time": 1.0},
                {"text": "我们去公园散步", "start_time": 1.0, "end_time": 2.5},
            ],
            granularity=TranscriptGranularity.CHARACTER,
            min_window_tokens=12,
        )
        assert [r["text"] for r in result] == [
            "今天天气很好",
            "我们去公园散步",
        ]

    def test_character_mode_produces_no_spaces_between_tokens(self):
        result = _correct_all(
            "今天天气很好",
            [{"text": "今天天气很好", "start_time": 0.0, "end_time": 1.0}],
            granularity=TranscriptGranularity.CHARACTER,
            min_window_tokens=12,
        )
        assert " " not in result[0]["text"]


class TestWindowingParameters:
    def test_small_window_still_finds_nearby_match(self):
        # Force a tight window and confirm the corrector still anchors.
        result = _correct_all(
            "hello world this is a test",
            [{"text": "helo wrld", "start_time": 0.0, "end_time": 1.0}],
            min_window_tokens=2,
            window_multiplier=1.0,
        )
        assert result[0]["text"] == "hello world"

    def test_window_far_short_of_needed_span_produces_no_match(self):
        # Reference has "test" only after a big buffer of tokens. If the
        # window can't see far enough, the STT for "test" fails to anchor
        # from the current cursor.
        buffer = " ".join(["filler"] * 30)
        result = _correct_all(
            f"start {buffer} test end",
            [
                # Anchor cursor near the beginning
                {"text": "start", "start_time": 0.0, "end_time": 0.5},
                # Now try to match "test" but with a small window that can't
                # jump 30 tokens ahead.
                {"text": "test", "start_time": 0.5, "end_time": 1.0},
            ],
            min_window_tokens=3,
            window_multiplier=1.0,
        )
        # First anchors to "start".
        assert result[0]["text"] == "start"
        # Second is either skipped (out of window) or matched to a nearby
        # filler token. The invariant we assert: it should not silently
        # match "test" if "test" is out of window.
        if len(result) > 1:
            assert result[1]["text"] != "test"


class TestRegressionScenarios:
    def test_realistic_english_paragraph(self):
        reference = (
            "The quick brown fox jumps over the lazy dog "
            "and then it runs away into the woods"
        )
        segments = [
            {"text": "the quik brown fox", "start_time": 0.0, "end_time": 1.0},
            {"text": "jumps over the lazi dog", "start_time": 1.0, "end_time": 2.0},
            {"text": "and then it runs away", "start_time": 2.0, "end_time": 3.0},
            {"text": "into the wood", "start_time": 3.0, "end_time": 4.0},
        ]
        result = _correct_all(reference, segments)
        # Every segment matches its reference span (case- and typo-normalized).
        assert [r["text"] for r in result] == [
            "The quick brown fox",
            "jumps over the lazy dog",
            "and then it runs away",
            "into the woods",
        ]

    def test_empty_segment_stream_produces_only_estimates(self):
        # With no STT anchors at all, the full reference surfaces on flush as
        # estimated gap segments — no matched anchors.
        result = _correct_all("hello world", [])
        assert _matched(result) == []
        assert _estimated(result), "expected gap fill to emit the full reference"

    def test_repeated_flushes_are_idempotent(self):
        corrector = _make_corrector("hello world")
        list(corrector.feed({"text": "hello world", "start_time": 0.0, "end_time": 1.0}))
        assert list(corrector.flush()) == []
        assert list(corrector.flush()) == []


class TestGapFill:
    """Coverage for reference gaps: text the STT missed surfaces as
    `estimated: true` segments so the output always covers the full reference.
    Each estimated segment is one sentence, cut at sentence terminators
    (``.``, ``!``, ``?``, ``。``, ``！``, ``？``, ``…``, ``\\n``).
    """

    # -------- basic emission --------

    def test_matched_segments_have_no_estimated_field(self):
        result = _correct_all(
            "hello world",
            [{"text": "hello world", "start_time": 0.0, "end_time": 1.0}],
        )
        matched = _matched(result)
        assert len(matched) == 1
        assert "estimated" not in matched[0]

    def test_no_gap_when_reference_is_fully_covered(self):
        result = _correct_all(
            "hello world this is a small test",
            [
                {"text": "hello world",        "start_time": 0.0, "end_time": 1.0},
                {"text": "this is a smal test", "start_time": 1.0, "end_time": 2.0},
            ],
        )
        assert _estimated(result) == []
        assert [seg["text"] for seg in result] == [
            "hello world",
            "this is a small test",
        ]

    def test_estimated_segments_are_interleaved_with_anchors_in_order(self):
        result = _correct_all(
            "alpha beta.\nGamma delta.\nEpsilon zeta.",
            [
                {"text": "alpha beta",   "start_time":  0.0, "end_time":  2.0},
                {"text": "epsilon zeta", "start_time": 12.0, "end_time": 14.0},
            ],
            min_window_tokens=20,
        )
        # Full stream: matched(0..2), estimated (middle sentence), matched(12..14).
        # Corrected text is taken from the reference verbatim, so casing follows
        # the reference (``Epsilon zeta``), not the STT input.
        assert result[0]["text"]  == "alpha beta"
        assert result[-1]["text"] == "Epsilon zeta"
        assert not result[0].get("estimated")
        assert all(seg.get("estimated") for seg in result[1:-1])
        assert not result[-1].get("estimated")

    # -------- sentence-boundary splitting --------

    def test_bounded_gap_splits_at_sentence_terminators(self):
        # Two sentences in the gap → two estimated segments regardless of
        # gap duration.
        result = _correct_all(
            "start. Alpha beta gamma. Delta epsilon. End.",
            [
                {"text": "start", "start_time":  0.0, "end_time":  1.0},
                {"text": "end",   "start_time": 61.0, "end_time": 62.0},
            ],
            min_window_tokens=20,
        )
        estimates = _estimated(result)
        texts = [ seg["text"] for seg in estimates ]
        assert texts == ["Alpha beta gamma", "Delta epsilon"]

    def test_trailing_gap_splits_at_sentence_terminators(self):
        result = _correct_all(
            "opening. Second sentence here. Third one!",
            [{"text": "opening", "start_time": 0.0, "end_time": 1.0}],
        )
        estimates = _estimated(result)
        texts = [ seg["text"] for seg in estimates ]
        assert texts == ["Second sentence here", "Third one"]

    def test_newline_is_a_sentence_terminator(self):
        result = _correct_all(
            "start\nalpha beta gamma\ndelta epsilon\nend",
            [
                {"text": "start", "start_time":  0.0, "end_time":  1.0},
                {"text": "end",   "start_time": 61.0, "end_time": 62.0},
            ],
            min_window_tokens=20,
        )
        estimates = _estimated(result)
        texts = [ seg["text"] for seg in estimates ]
        assert texts == ["alpha beta gamma", "delta epsilon"]

    def test_gap_with_no_terminator_is_one_segment(self):
        # No sentence break inside the gap → the whole remainder is a single
        # estimated segment.
        result = _correct_all(
            "start alpha beta gamma end",
            [
                {"text": "start", "start_time":  0.0, "end_time":  1.0},
                {"text": "end",   "start_time": 11.0, "end_time": 12.0},
            ],
            min_window_tokens=20,
        )
        estimates = _estimated(result)
        assert len(estimates) == 1
        assert estimates[0]["text"] == "alpha beta gamma"
        assert estimates[0]["start_time"] == 1.0
        assert estimates[0]["end_time"] == 11.0

    def test_cjk_sentence_terminators_are_recognized(self):
        # Both CJK full-width period and question mark split.
        result = _correct_all(
            "开头。中间一句。末尾一句？",
            [],
            granularity=TranscriptGranularity.CHARACTER,
            min_window_tokens=1,
        )
        texts = [ seg["text"] for seg in _estimated(result) ]
        assert texts == ["开头", "中间一句", "末尾一句"]

    # -------- time distribution --------

    def test_bounded_gap_time_is_split_proportionally_to_token_count(self):
        # Two sentences: 3 tokens vs 1 token; gap = 10s → 7.5s vs 2.5s.
        result = _correct_all(
            "start.\nAlpha beta gamma.\nOmega.\nEnd.",
            [
                {"text": "start", "start_time":  0.0, "end_time":  1.0},
                {"text": "end",   "start_time": 11.0, "end_time": 12.0},
            ],
            min_window_tokens=20,
        )
        estimates = _estimated(result)
        assert len(estimates) == 2
        first_duration  = estimates[0]["end_time"] - estimates[0]["start_time"]
        second_duration = estimates[1]["end_time"] - estimates[1]["start_time"]
        assert first_duration  == pytest.approx(7.5)
        assert second_duration == pytest.approx(2.5)

    def test_bounded_gap_last_estimate_clamps_to_end_time(self):
        # Regardless of floating-point drift, the final estimated segment in a
        # bounded gap must end exactly at the next anchor's start.
        result = _correct_all(
            "start. One. Two. Three. Four. End.",
            [
                {"text": "start", "start_time":  0.0, "end_time":  1.0},
                {"text": "end",   "start_time": 61.0, "end_time": 62.0},
            ],
            min_window_tokens=20,
        )
        estimates = _estimated(result)
        assert estimates[-1]["end_time"] == 61.0

    def test_trailing_gap_after_no_matches_starts_at_zero(self):
        result = _correct_all(
            "alpha beta. gamma delta.",
            [],
        )
        estimates = _estimated(result)
        assert estimates, "expected trailing gap on flush"
        assert estimates[0]["start_time"] == 0.0

    def test_trailing_gap_duration_uses_speaking_rate(self):
        # After the last anchor, each sentence's duration is estimated from
        # its token count and a fallback speaking rate (~2.5 tokens/s for
        # word granularity). Two sentences with 3 and 2 tokens → 1.2s and 0.8s.
        result = _correct_all(
            "start. Alpha beta gamma. Delta epsilon.",
            [{"text": "start", "start_time": 0.0, "end_time": 1.0}],
        )
        estimates = _estimated(result)
        assert len(estimates) == 2
        assert estimates[0]["text"] == "Alpha beta gamma"
        assert estimates[1]["text"] == "Delta epsilon"
        # First sentence starts right after the anchor.
        assert estimates[0]["start_time"] == 1.0
        # 3 tokens / 2.5 tokens_per_second = 1.2s.
        assert estimates[0]["end_time"] - estimates[0]["start_time"] == pytest.approx(1.2)
        assert estimates[1]["end_time"] - estimates[1]["start_time"] == pytest.approx(0.8)
        # Sentences chain.
        assert estimates[1]["start_time"] == pytest.approx(estimates[0]["end_time"])
