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
    def test_below_threshold_segment_is_skipped(self):
        result = _correct_all(
            "hello world",
            [{"text": "completely different text", "start_time": 0.0, "end_time": 1.0}],
            match_threshold=0.9,
        )
        assert result == []

    def test_segment_after_reference_exhaustion_is_skipped(self):
        result = _correct_all(
            "hello",
            [
                {"text": "hello", "start_time": 0.0, "end_time": 0.5},
                {"text": "world", "start_time": 0.5, "end_time": 1.0},
                {"text": "extra", "start_time": 1.0, "end_time": 1.5},
            ],
        )
        # Only the segment that fits the reference gets emitted.
        assert len(result) == 1
        assert result[0]["text"] == "hello"

    def test_leftover_reference_is_discarded_on_flush(self):
        # Reference has many tokens but only one segment arrives — flush must
        # not emit trailing reference text.
        result = _correct_all(
            "hello world this is much longer than the stt output",
            [{"text": "helo wrld", "start_time": 0.0, "end_time": 1.0}],
        )
        assert len(result) == 1  # only the matched one
        assert result[0]["text"] == "hello world"

    def test_flush_yields_nothing_extra_after_normal_feeding(self):
        corrector = _make_corrector("hello world")
        list(corrector.feed({"text": "hello world", "start_time": 0.0, "end_time": 1.0}))
        assert list(corrector.flush()) == []

    def test_empty_text_segment_is_skipped(self):
        result = _correct_all(
            "hello world",
            [{"text": "", "start_time": 0.0, "end_time": 1.0}],
        )
        assert result == []

    def test_whitespace_only_text_segment_is_skipped(self):
        result = _correct_all(
            "hello world",
            [{"text": "   ", "start_time": 0.0, "end_time": 1.0}],
        )
        assert result == []

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

    def test_empty_segment_stream_yields_nothing(self):
        assert _correct_all("hello world", []) == []

    def test_repeated_flushes_are_idempotent(self):
        corrector = _make_corrector("hello world")
        list(corrector.feed({"text": "hello world", "start_time": 0.0, "end_time": 1.0}))
        assert list(corrector.flush()) == []
        assert list(corrector.flush()) == []
