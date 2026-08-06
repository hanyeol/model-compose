from __future__ import annotations

from typing import Optional, Dict, List, Set, Iterator, Tuple, Any
from mindor.dsl.schema.component import TranscriptCorrectorComponentConfig, TranscriptCorrectorDriver
from mindor.dsl.schema.action import TranscriptCorrectorActionConfig
from mindor.dsl.schema.action.impl.transcript_corrector.impl.common import TranscriptGranularity
from mindor.core.foundation.cancellation import CancellationToken
from ..base import TranscriptCorrectorService, register_transcript_corrector_service
from ..base import ComponentActionContext
from .common import StreamingTranscriptCorrector, TranscriptCorrectorAction
import regex, unicodedata

# Unicode letter+mark runs, optionally with connector marks. Used for word-level
# tokenization across scripts that use whitespace between words.
_WORD_PATTERN = regex.compile(r"[\p{L}\p{M}\p{N}]+", flags=regex.UNICODE)

# Sentence terminators covering common Latin, CJK, and ellipsis punctuation,
# plus newline. Used to detect sentence boundaries when estimating gaps so
# each emitted gap segment is one sentence.
_SENTENCE_TERMINATORS: frozenset = frozenset(".!?。！？…\n")

# Fallback speaking rates used when the flush gap has no known duration.
# Word granularity: ~2.5 words/second. Character granularity: ~10 chars/second.
_ESTIMATED_TOKENS_PER_SECOND_WORD: float = 2.5
_ESTIMATED_TOKENS_PER_SECOND_CHAR: float = 10.0

class NativeStreamingTranscriptCorrector(StreamingTranscriptCorrector):
    """Segment-level streaming corrector.

    Each STT segment is confirmed on arrival: we search a sliding window of the
    reference for the best-matching contiguous span (Ratcliff-Obershelp / partial
    ratio), and if similarity >= ``match_threshold``, emit one corrected segment
    whose text is the reference span verbatim and whose timestamps are the STT
    segment's own. The reference cursor advances past the matched span.

    Gap coverage: reference text that sits between two consecutive matched
    anchors (or before the first / after the last anchor) is emitted as
    additional segments marked ``estimated: true``, so callers get complete
    coverage of the reference even where the STT missed. Each estimated
    segment is one sentence, cut at sentence terminators (``.``, ``!``,
    ``?``, ``。``, ``！``, ``？``, ``…``, ``\\n``) in the reference source.
    Time is split across the gap in proportion to each sentence's token count.

    Design choices per user requirements:
    - Whole-segment replacement (matched STT text is replaced by the reference span).
    - Segments below threshold are skipped (not emitted, not fallback-passed-through).
    - Reference gaps are filled with `estimated: true` segments so the full
      reference is always present in the output.
    """
    def __init__(
        self,
        reference: str,
        granularity: TranscriptGranularity,
        text_key: str,
        start_time_key: str,
        end_time_key: str,
        case_sensitive: bool,
        ignore_punctuation: bool,
        window_multiplier: float,
        min_window_tokens: int,
        match_threshold: float,
    ):
        self.text_key: str = text_key
        self.start_time_key: str = start_time_key
        self.end_time_key: str = end_time_key
        self.case_sensitive: bool = case_sensitive
        self.ignore_punctuation: bool = ignore_punctuation
        self.window_multiplier: float = window_multiplier
        self.min_window_tokens: int = min_window_tokens
        self.match_threshold: float = match_threshold

        self._granularity: TranscriptGranularity = granularity

        # Reference is tokenized once. We keep two parallel views:
        # - ``_display_tokens[i]``: the original token verbatim (for the corrected output)
        # - ``_match_tokens[i]``: normalized form used only for similarity scoring
        # ``_sentence_break_after`` records token indices that end a sentence in the
        # reference — used as gap segment boundaries so each estimated segment is
        # exactly one sentence.
        self._display_tokens: List[str]
        self._sentence_break_after: Set[int]
        self._display_tokens, self._sentence_break_after = self._tokenize_with_sentence_breaks(reference)
        self._match_tokens: List[str] = [ self._normalize_token(token) for token in self._display_tokens ]

        # Some tokens can normalize to empty (pure punctuation). Precompute a list of
        # indices whose normalized form is non-empty — those are the only candidates
        # for anchor matching. Original ordering/spacing is still driven by _display_tokens.
        self._matchable_indices: List[int] = [ index for index, token in enumerate(self._match_tokens) if token ]

        self._token_cursor: int = 0       # Position in _display_tokens for the next search window start.
        self._matchable_cursor: int = 0   # Position in _matchable_indices >= _token_cursor.
        self._last_end_time: float = 0.0  # Wall-clock end of the most recently emitted segment (matched or estimated).

    def feed(self, segment: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        if not isinstance(segment, dict):
            return

        # Reference already exhausted: nothing more to correct.
        if self._matchable_cursor >= len(self._matchable_indices):
            return

        text = segment.get(self.text_key)
        if not isinstance(text, str) or not text.strip():
            return

        tokens = [ self._normalize_token(token) for token in self._tokenize(text) ]
        tokens = [ token for token in tokens if token ]

        if not tokens:
            return

        window_size = max(self.min_window_tokens, int(len(tokens) * self.window_multiplier))
        candidate_end = min(len(self._matchable_indices), self._matchable_cursor + window_size)
        candidates = self._matchable_indices[self._matchable_cursor:candidate_end]

        if not candidates:
            return

        match = self._find_best_span(
            haystack=[ self._match_tokens[index] for index in candidates ],
            needle=tokens,
        )

        if match is None:
            return

        local_start, local_end, _ = match
        # Map candidate-local indices back to _display_tokens indices.
        matched_start = candidates[local_start]
        matched_end   = candidates[local_end - 1] + 1  # exclusive

        anchor_start_time = segment.get(self.start_time_key)
        anchor_end_time   = segment.get(self.end_time_key)

        # Any reference tokens between the previous anchor and this one form a
        # gap: fill them in with estimated segments so the output covers the
        # full reference.
        if matched_start > self._token_cursor and isinstance(anchor_start_time, (int, float)):
            for gap_segment in self._estimate_gap(
                self._token_cursor,
                matched_start,
                self._last_end_time,
                float(anchor_start_time),
            ):
                yield gap_segment

        corrected_text = self._detokenize(self._display_tokens[matched_start:matched_end])

        result = dict(segment)
        result[self.text_key] = corrected_text
        # start/end keys are preserved from the STT segment as-is (see design notes).

        # Advance cursors past the matched region.
        self._token_cursor = matched_end
        while self._matchable_cursor < len(self._matchable_indices) and self._matchable_indices[self._matchable_cursor] < matched_end:
            self._matchable_cursor += 1

        if isinstance(anchor_end_time, (int, float)):
            self._last_end_time = float(anchor_end_time)

        yield result

    def flush(self) -> Iterator[Dict[str, Any]]:
        # Emit any reference tokens left after the final anchor as estimated
        # segments. The true audio end is unknown here, so each sentence's
        # duration is estimated from its token count and a fallback speaking
        # rate rather than fitting into a known window.
        if self._token_cursor >= len(self._display_tokens):
            return

        for gap_segment in self._estimate_gap(
            self._token_cursor,
            len(self._display_tokens),
            self._last_end_time,
            end_time=None,
        ):
            yield gap_segment

        self._token_cursor = len(self._display_tokens)
        self._matchable_cursor = len(self._matchable_indices)

    def _estimate_gap(
        self,
        token_start: int,
        token_end: int,
        start_time: float,
        end_time: Optional[float],
    ) -> Iterator[Dict[str, Any]]:
        """Emit one estimated segment per sentence in ``[token_start, token_end)``.
        Sentence boundaries come from ``_sentence_break_after``; each detected
        sentence is emitted as its own segment.

        When ``end_time`` is known (a gap between two anchors), the gap window
        is distributed across sentences in proportion to their token count.
        When ``end_time`` is None (flush after the last anchor), each sentence
        gets a duration estimated from its token count and a fallback speaking
        rate.
        """
        if token_end <= token_start:
            return

        # Cut the gap into sentence groups. A sentence ends at the first
        # terminator seen; the final group has no trailing terminator and just
        # runs to token_end.
        sentence_groups: List[Tuple[int, int]] = []  # inclusive-exclusive token ranges
        sentence_start = token_start
        for index in range(token_start, token_end):
            if index in self._sentence_break_after or index == token_end - 1:
                sentence_groups.append((sentence_start, index + 1))
                sentence_start = index + 1

        if not sentence_groups:
            return

        total_tokens = token_end - token_start

        if end_time is not None:
            total_duration = max(0.0, end_time - start_time)
            if total_duration <= 0:
                return
        else:
            total_duration = None

        rate = _ESTIMATED_TOKENS_PER_SECOND_CHAR \
            if self._granularity == TranscriptGranularity.CHARACTER \
            else _ESTIMATED_TOKENS_PER_SECOND_WORD

        cursor_time = start_time
        for group_index, (group_start, group_end) in enumerate(sentence_groups):
            group_tokens = self._display_tokens[group_start:group_end]

            if total_duration is not None:
                sentence_duration = total_duration * len(group_tokens) / total_tokens
            else:
                sentence_duration = len(group_tokens) / rate

            sentence_start_time = cursor_time
            # Clamp the last sentence's end to the exact gap boundary so
            # floating-point drift doesn't leak past `end_time`.
            if end_time is not None and group_index == len(sentence_groups) - 1:
                sentence_end_time = end_time
            else:
                sentence_end_time = cursor_time + sentence_duration

            yield {
                self.text_key:       self._detokenize(group_tokens),
                self.start_time_key: round(sentence_start_time, 2),
                self.end_time_key:   round(sentence_end_time, 2),
                "estimated":         True,
            }

            cursor_time = sentence_end_time

        self._last_end_time = cursor_time

    def _tokenize_with_sentence_breaks(self, text: str) -> Tuple[List[str], Set[int]]:
        """Tokenize like ``_tokenize`` while also collecting the token indices
        that end a sentence in the source. A sentence ends at any character in
        ``_SENTENCE_TERMINATORS`` (Latin/CJK punctuation, ellipsis, newline).
        The break set is later used as hard boundaries when estimating gaps
        so each emitted gap segment is one sentence."""
        tokens: List[str] = []
        sentence_break_after: Set[int] = set()

        if self._granularity == TranscriptGranularity.CHARACTER:
            for char in text:
                if char in _SENTENCE_TERMINATORS:
                    if tokens:
                        sentence_break_after.add(len(tokens) - 1)
                elif not char.isspace():
                    tokens.append(char)
            return tokens, sentence_break_after

        cursor = 0
        for match in _WORD_PATTERN.finditer(text):
            start, end = match.span()
            if tokens and any(ch in _SENTENCE_TERMINATORS for ch in text[cursor:start]):
                sentence_break_after.add(len(tokens) - 1)
            tokens.append(match.group(0))
            cursor = end

        # Any terminator between the last matched token and end of text also
        # closes the final sentence.
        if tokens and any(ch in _SENTENCE_TERMINATORS for ch in text[cursor:]):
            sentence_break_after.add(len(tokens) - 1)

        return tokens, sentence_break_after

    def _tokenize(self, text: str) -> List[str]:
        if self._granularity == TranscriptGranularity.CHARACTER:
            # Every non-whitespace code point becomes its own token.
            return [ ch for ch in text if not ch.isspace() ]

        return _WORD_PATTERN.findall(text)

    def _detokenize(self, tokens: List[str]) -> str:
        if self._granularity == TranscriptGranularity.CHARACTER:
            return "".join(tokens)

        return " ".join(tokens)

    def _normalize_token(self, token: str) -> str:
        token = unicodedata.normalize("NFKC", token)

        if not self.case_sensitive:
            token = token.casefold()

        if self.ignore_punctuation:
            token = "".join(ch for ch in token if not unicodedata.category(ch).startswith("P"))

        return token

    def _find_best_span(self, haystack: List[str], needle: List[str]) -> Optional[Tuple[int, int, float]]:
        """Find the contiguous span of ``haystack`` that best matches ``needle``.

        Scores each candidate span with **character-level** Levenshtein similarity
        (the tokens are joined into strings first). Token-level Levenshtein treats
        each token as an atomic symbol, so ``["helo"]`` vs ``["hello"]`` scores zero
        despite being a single-character typo; character-level absorbs typical STT
        misspellings.

        Span lengths sweep n-2..n+2 (clamped to >=1) to also absorb one or two token
        insertions/deletions per segment. Returns ``(start, end, score)`` (end
        exclusive) for the best span whose score >= ``match_threshold``, or ``None``.
        """
        from rapidfuzz.distance import Levenshtein

        if not haystack or not needle:
            return None

        n = len(needle)
        needle = "".join(needle)

        if not needle:
            return None

        length_options = sorted({ max(1, n - 2), max(1, n - 1), n, n + 1, n + 2 })
        best: Optional[Tuple[int, int, float]] = None

        for span_length in length_options:
            if span_length > len(haystack):
                continue

            for start in range(0, len(haystack) - span_length + 1):
                end = start + span_length
                span = "".join(haystack[start:end])

                if not span:
                    continue

                distance = Levenshtein.distance(needle, span)
                denom = max(len(needle), len(span))
                score = 1.0 - (distance / denom) if denom > 0 else 0.0

                if score < self.match_threshold:
                    continue

                if best is None or score > best[2]:
                    best = (start, end, score)

                    if score == 1.0:
                        return best

        return best

@register_transcript_corrector_service(TranscriptCorrectorDriver.NATIVE)
class NativeTranscriptCorrectorService(TranscriptCorrectorService):
    def __init__(self, id: str, config: TranscriptCorrectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "rapidfuzz", "regex" ]

    async def _run(self, action: TranscriptCorrectorActionConfig, context: ComponentActionContext) -> Any:
        return await NativeTranscriptCorrectorAction(action).run(context)

class NativeTranscriptCorrectorAction(TranscriptCorrectorAction):
    async def _create_corrector(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> StreamingTranscriptCorrector:
        def _create() -> StreamingTranscriptCorrector:
            return NativeStreamingTranscriptCorrector(**params)

        return await self._run_in_executor(_create)
