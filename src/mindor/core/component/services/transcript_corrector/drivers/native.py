from __future__ import annotations

from typing import Optional, Dict, List, Iterator, Tuple, Any
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

class NativeStreamingTranscriptCorrector(StreamingTranscriptCorrector):
    """Segment-level streaming corrector.

    Each STT segment is confirmed on arrival: we search a sliding window of the
    reference for the best-matching contiguous span (Ratcliff-Obershelp / partial
    ratio), and if similarity >= ``match_threshold``, emit one corrected segment
    whose text is the reference span verbatim and whose timestamps are the STT
    segment's own. The reference cursor advances past the matched span.

    Design choices per user requirements:
    - Whole-segment replacement (matched STT text is replaced by the reference span).
    - Segments below threshold are skipped (not emitted, not fallback-passed-through).
    - Segments arriving after the reference is exhausted are skipped.
    - Leftover reference at flush time is discarded.
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
        # - ``_ref_display[i]``: the original token verbatim (for the corrected output)
        # - ``_ref_normalized[i]``: normalized form used only for similarity scoring
        self._ref_display: List[str] = self._tokenize(reference)
        self._ref_normalized: List[str] = [ self._normalize(token) for token in self._ref_display ]

        # Some tokens can normalize to empty (pure punctuation). Precompute a list of
        # indices whose normalized form is non-empty — those are the only candidates
        # for anchor matching. Original ordering/spacing is still driven by _ref_display.
        self._matchable_indices: List[int] = [ index for index, token in enumerate(self._ref_normalized) if token ]

        self._ref_cursor: int = 0                # Position in _ref_display for the next search window start.
        self._matchable_cursor: int = 0          # Position in _matchable_indices >= _ref_cursor.

    def feed(self, segment: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        if not isinstance(segment, dict):
            return

        # Reference already exhausted: user chose to skip further STT.
        if self._matchable_cursor >= len(self._matchable_indices):
            return

        text = segment.get(self.text_key)
        if not isinstance(text, str) or not text.strip():
            return

        stt_tokens = [ self._normalize(token) for token in self._tokenize(text) ]
        stt_tokens = [ token for token in stt_tokens if token ]

        if not stt_tokens:
            return

        window_size = max(self.min_window_tokens, int(len(stt_tokens) * self.window_multiplier))
        candidate_end = min(len(self._matchable_indices), self._matchable_cursor + window_size)
        candidates = self._matchable_indices[self._matchable_cursor:candidate_end]

        if not candidates:
            return

        match = self._find_best_span(
            haystack=[ self._ref_normalized[index] for index in candidates ],
            needle=stt_tokens,
        )

        if match is None:
            return

        local_start, local_end, _ = match
        # Map candidate-local indices back to _ref_display indices.
        matched_start = candidates[local_start]
        matched_end   = candidates[local_end - 1] + 1  # exclusive

        corrected_text = self._detokenize(self._ref_display[matched_start:matched_end])

        result = dict(segment)
        result[self.text_key] = corrected_text
        # start/end keys are preserved from the STT segment as-is (see design notes).

        # Advance cursors past the matched region.
        self._ref_cursor = matched_end
        while self._matchable_cursor < len(self._matchable_indices) and self._matchable_indices[self._matchable_cursor] < matched_end:
            self._matchable_cursor += 1

        yield result

    def flush(self) -> Iterator[Dict[str, Any]]:
        # Leftover reference is discarded by design.
        return iter(())

    def _tokenize(self, text: str) -> List[str]:
        if self._granularity == TranscriptGranularity.CHARACTER:
            # Every non-whitespace code point becomes its own token.
            return [ ch for ch in text if not ch.isspace() ]

        return _WORD_PATTERN.findall(text)

    def _detokenize(self, tokens: List[str]) -> str:
        if self._granularity == TranscriptGranularity.CHARACTER:
            return "".join(tokens)

        return " ".join(tokens)

    def _normalize(self, token: str) -> str:
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
        needle_str = "".join(needle)
        if not needle_str:
            return None

        length_options = sorted({ max(1, n - 2), max(1, n - 1), n, n + 1, n + 2 })

        best: Optional[Tuple[int, int, float]] = None

        for span_len in length_options:
            if span_len > len(haystack):
                continue

            for start in range(0, len(haystack) - span_len + 1):
                end = start + span_len
                span_str = "".join(haystack[start:end])
                if not span_str:
                    continue

                distance = Levenshtein.distance(needle_str, span_str)
                denom = max(len(needle_str), len(span_str))
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
        return ["rapidfuzz", "regex"]

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
