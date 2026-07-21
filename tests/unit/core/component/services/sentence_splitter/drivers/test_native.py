"""Unit tests for ``NativeStreamingSentenceSplitter``.

Focus areas:
- Terminator detection across Latin, CJK, and ellipsis punctuation.
- Runs of consecutive terminators stay attached (``!!``, ``?!``, ``...``).
- ``min_chunk_length`` merges short sentences into a single emitted chunk.
- ``max_chunk_length`` force-splits terminator-less runs at whitespace.
- Streaming behavior across ``feed`` calls (state carried in the pending buffer).
- ``flush`` emits residual pending text and residual chunk buffer.
"""

from typing import Iterator, List, Optional

import pytest

from mindor.core.component.services.sentence_splitter.drivers.native import (
    NativeStreamingSentenceSplitter,
)


def _drain(it: Iterator[str]) -> List[str]:
    return list(it)


def _split_all(
    text: str,
    min_chunk_length: int = 0,
    max_chunk_length: Optional[int] = None,
) -> List[str]:
    """Feed the whole string at once, then flush. Convenience for non-streaming
    scenarios where we only care about the final chunk sequence."""
    splitter = NativeStreamingSentenceSplitter(min_chunk_length, max_chunk_length)
    out: List[str] = []
    out.extend(_drain(splitter.feed(text)))
    out.extend(_drain(splitter.flush()))
    return out


class TestTerminatorDetection:
    def test_period_terminator(self):
        assert _split_all("Hello world.") == ["Hello world."]

    def test_question_mark_terminator(self):
        assert _split_all("Really?") == ["Really?"]

    def test_exclamation_terminator(self):
        assert _split_all("Wow!") == ["Wow!"]

    def test_newline_acts_as_terminator(self):
        # Newline is in _TERMINATORS; each newline closes a sentence.
        assert _split_all("line one\nline two\n") == ["line one", "line two"]

    def test_cjk_period(self):
        assert _split_all("你好世界。") == ["你好世界。"]

    def test_cjk_question_and_exclamation(self):
        assert _split_all("真的吗？太好了！") == ["真的吗？", "太好了！"]

    def test_ellipsis_single_character(self):
        # U+2026 HORIZONTAL ELLIPSIS is a single-character terminator.
        assert _split_all("Well…") == ["Well…"]

    def test_no_terminator_no_output_until_flush(self):
        splitter = NativeStreamingSentenceSplitter(0, None)
        assert _drain(splitter.feed("no terminator here")) == []
        assert _drain(splitter.flush()) == ["no terminator here"]


class TestTerminatorRuns:
    def test_double_exclamation_stays_attached(self):
        assert _split_all("Really!!") == ["Really!!"]

    def test_interrobang_stays_attached(self):
        assert _split_all("What?!") == ["What?!"]

    def test_three_dots_stay_attached(self):
        assert _split_all("Wait...") == ["Wait..."]

    def test_run_across_sentences(self):
        assert _split_all("A!! B?") == ["A!!", "B?"]

    def test_mixed_run_holds_until_next_char(self):
        # Runs are greedy: everything terminator-y collapses into one boundary.
        assert _split_all("Huh?!?! Really.") == ["Huh?!?!", "Really."]


class TestStreamingFeedBehavior:
    def test_incremental_feed_emits_when_boundary_seen(self):
        splitter = NativeStreamingSentenceSplitter(0, None)
        assert _drain(splitter.feed("Hello")) == []
        assert _drain(splitter.feed(" world")) == []
        assert _drain(splitter.feed(".")) == []
        # The terminator run may still grow — emission waits for a following char.
        assert _drain(splitter.feed(" Next")) == ["Hello world."]
        assert _drain(splitter.flush()) == ["Next"]

    def test_terminator_arriving_char_by_char(self):
        splitter = NativeStreamingSentenceSplitter(0, None)
        assert _drain(splitter.feed("Wait")) == []
        assert _drain(splitter.feed(".")) == []
        assert _drain(splitter.feed(".")) == []
        assert _drain(splitter.feed(".")) == []
        # Nothing emitted mid-run — we don't know if more dots are coming.
        assert _drain(splitter.feed(" done.")) == ["Wait..."]
        assert _drain(splitter.flush()) == ["done."]

    def test_flush_emits_remaining_pending_without_terminator(self):
        splitter = NativeStreamingSentenceSplitter(0, None)
        _drain(splitter.feed("partial fragment"))
        assert _drain(splitter.flush()) == ["partial fragment"]

    def test_empty_feed_yields_nothing(self):
        splitter = NativeStreamingSentenceSplitter(0, None)
        assert _drain(splitter.feed("")) == []
        assert _drain(splitter.flush()) == []


class TestMinChunkLengthMerging:
    def test_short_sentences_merge_until_threshold(self):
        # Each sentence is short; merge until combined length >= 10.
        # "Hi." + " " + "You?" = 8 chars → still under; add "Ok." → 12 → emit.
        assert _split_all("Hi. You? Ok. Bye.", min_chunk_length=10) == [
            "Hi. You? Ok.",
            "Bye.",
        ]

    def test_single_long_sentence_passes_through(self):
        text = "This sentence is definitely long enough to exceed the threshold."
        assert _split_all(text, min_chunk_length=10) == [text]

    def test_zero_threshold_emits_each_sentence(self):
        assert _split_all("A. B. C.", min_chunk_length=0) == ["A.", "B.", "C."]

    def test_flush_emits_undersized_tail(self):
        # "Bye." alone is under 10, but flush emits it anyway because the
        # stream is over.
        assert _split_all("Bye.", min_chunk_length=10) == ["Bye."]

    def test_exact_threshold_emits(self):
        # "Hello." is 6 chars; threshold 6 → should emit on the boundary.
        assert _split_all("Hello. Next.", min_chunk_length=6) == ["Hello.", "Next."]


class TestMaxChunkLengthForceSplit:
    def test_oversize_run_splits_at_whitespace(self):
        # No terminators; force-split when pending crosses max=20.
        # "aaaa bbbb cccc dddd eeee" — length 24. Split prefers last whitespace
        # within limit 20 → index 19 (before "eeee").
        result = _split_all("aaaa bbbb cccc dddd eeee", max_chunk_length=20)
        assert result == ["aaaa bbbb cccc dddd", "eeee"]

    def test_oversize_no_whitespace_falls_back_to_limit(self):
        # A single unbroken token longer than the limit → hard cut at limit.
        result = _split_all("a" * 30, max_chunk_length=10)
        # First 10 chars, then next 10, then the remaining 10 (flushed).
        assert result == ["a" * 10, "a" * 10, "a" * 10]

    def test_terminator_wins_over_max_limit(self):
        # If a terminator arrives before max is hit, sentence closes normally.
        result = _split_all("short. and more text here without terminator",
                            max_chunk_length=100)
        assert result == ["short.", "and more text here without terminator"]

    def test_terminator_in_buffer_disables_max_split(self):
        # ``max_chunk_length`` only fires when the pending buffer holds no
        # terminator at all. Once a terminator is present, the scanner closes
        # the sentence there regardless of the max — the first "sentence" here
        # is 20 chars even though max is 10.
        result = _split_all("aaaa bbbb cccc dddd. next.", max_chunk_length=10)
        assert result == ["aaaa bbbb cccc dddd.", "next."]


class TestChunkAggregationWithMaxSplit:
    def test_max_split_pieces_participate_in_min_merge(self):
        # A force-split piece is treated like a sentence and can be merged
        # with following ones under min_chunk_length.
        result = _split_all(
            "aaaa bbbb. cc.",
            min_chunk_length=15,
            max_chunk_length=100,
        )
        # "aaaa bbbb." (10) < 15, wait; + " cc." (14) < 15, flush emits.
        assert result == ["aaaa bbbb. cc."]


class TestWhitespaceAndEdgeCases:
    def test_leading_whitespace_before_terminator_is_skipped(self):
        # "   ." strips to "" → skipped as terminator-only fragment.
        assert _split_all("   . Real.") == ["Real."]

    def test_only_whitespace_input(self):
        assert _split_all("   \t  ") == []

    def test_only_terminators_input(self):
        # All terminators, no substantive text. Nothing emitted.
        assert _split_all("...") == []

    def test_mixed_terminators_and_content(self):
        assert _split_all("First. Second! Third?") == [
            "First.",
            "Second!",
            "Third?",
        ]

    def test_multiple_flushes_are_idempotent(self):
        splitter = NativeStreamingSentenceSplitter(0, None)
        _drain(splitter.feed("Hello."))
        first = _drain(splitter.flush())
        second = _drain(splitter.flush())
        assert first == ["Hello."]
        assert second == []


class TestRegressionScenarios:
    def test_realistic_paragraph(self):
        text = (
            "The quick brown fox jumps over the lazy dog. "
            "Then it runs away! Does it come back? Maybe..."
        )
        assert _split_all(text) == [
            "The quick brown fox jumps over the lazy dog.",
            "Then it runs away!",
            "Does it come back?",
            "Maybe...",
        ]

    def test_streaming_chunks_match_bulk_split(self):
        # Feeding character-by-character must produce the same output as
        # feeding the whole string at once.
        text = "One. Two! Three? Four... Five."
        bulk = _split_all(text)

        splitter = NativeStreamingSentenceSplitter(0, None)
        streamed: List[str] = []
        for ch in text:
            streamed.extend(splitter.feed(ch))
        streamed.extend(splitter.flush())

        assert streamed == bulk

    def test_streaming_random_chunking_matches_bulk(self):
        # Split the input at arbitrary boundaries and verify identical output.
        text = "Alpha. Beta! Gamma? Delta... Epsilon."
        bulk = _split_all(text)

        # Feed in irregular pieces.
        pieces = ["Alph", "a. Beta! ", "Gamm", "a? De", "lta..", ". Epsi", "lon."]
        assert "".join(pieces) == text  # sanity: pieces reassemble to text

        splitter = NativeStreamingSentenceSplitter(0, None)
        streamed: List[str] = []
        for p in pieces:
            streamed.extend(splitter.feed(p))
        streamed.extend(splitter.flush())

        assert streamed == bulk
