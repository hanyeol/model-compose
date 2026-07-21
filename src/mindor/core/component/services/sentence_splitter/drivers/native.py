from __future__ import annotations

from typing import Optional, Iterator, Tuple, Any
from mindor.dsl.schema.component import SentenceSplitterComponentConfig, SentenceSplitterDriver
from mindor.dsl.schema.action import SentenceSplitterActionConfig
from ..base import SentenceSplitterService, register_sentence_splitter_service
from ..base import ComponentActionContext
from .common import SentenceSplitterAction, StreamingSentenceSplitter
import asyncio

# Sentence terminators covering common Latin, CJK, and ellipsis punctuation.
# All are single characters, safe to detect without lookahead beyond themselves.
_TERMINATORS: frozenset = frozenset(".!?。！？…\n")

# Whitespace to prefer as a hard-split boundary for oversize sentences.
_WHITESPACE: frozenset = frozenset(" \t\n")

class NativeStreamingSentenceSplitter(StreamingSentenceSplitter):
    """Rule-based streaming sentence splitter.

    Emits sentences as terminators are seen in the pending buffer. A run of
    consecutive terminators (e.g. ``!!``, ``?!``, ``...``) is treated as one
    boundary so they stay attached to the sentence they end.

    ``min_chunk_length`` accumulates short sentences into a single emitted
    chunk until the length threshold is met. ``max_chunk_length``, if set,
    force-splits any pending buffer that grows past the limit without a
    terminator, preferring the last whitespace within the limit.
    """
    def __init__(self, min_chunk_length: int, max_chunk_length: Optional[int]):
        self.min_chunk_length: int = min_chunk_length
        self.max_chunk_length: Optional[int] = max_chunk_length

        self._pending_text: str = ""       # Text received but not yet cut into a sentence.
        self._chunk_buffer: str = ""  # Sentences accumulated waiting for min_chunk_length.

    def feed(self, text: str) -> Iterator[str]:
        if text:
            self._pending_text += text
            yield from self._process_pending_text(final=False)

    def flush(self) -> Iterator[str]:
        yield from self._process_pending_text(final=True)

        # Emit any remainder in the chunk buffer, even if under min_chunk_length —
        # the input stream is over, there's nothing more coming.
        tail = self._chunk_buffer.strip()
        self._chunk_buffer = ""
        if tail:
            yield tail

    def _process_pending_text(self, final: bool) -> Iterator[str]:
        while True:
            sentence, end = self._extract_sentence(final=final)

            if sentence is None:
                break

            self._pending_text = self._pending_text[end:]
            self._append_sentence(sentence)
            chunk = self._build_chunk()

            if chunk is not None:
                yield chunk

        if final and self._pending_text:
            # Anything left is a terminator-less trailing fragment. Treat it as
            # one final sentence so it can go through the merge buffer.
            remainder = self._pending_text.strip()
            self._pending_text = ""

            if remainder:
                self._append_sentence(remainder)
                chunk = self._build_chunk()

                if chunk is not None:
                    yield chunk

    def _extract_sentence(self, final: bool) -> Tuple[Optional[str], int]:
        """Find the next sentence boundary in ``self._pending_text``.

        Returns ``(sentence, end)`` where ``sentence`` is the extracted text
        (stripped) and ``end`` is the index in ``self._pending_text`` where the
        next sentence begins. Returns ``(None, 0)`` when no boundary is ready
        yet.
        """
        text = self._pending_text

        for index, char in enumerate(text):
            if char not in _TERMINATORS:
                continue

            # Extend past any run of consecutive terminators so "!!" or "..."
            # stays attached to the sentence.
            end = index + 1
            while end < len(text) and text[end] in _TERMINATORS:
                end += 1

            # Not final and terminator run reaches the buffer end: it might
            # still grow (e.g. "..." arriving as ".", ".", "."). Hold back.
            if not final and end == len(text):
                break

            sentence = text[:end].strip()

            # Skip fragments that carry no substantive content — either pure
            # whitespace ("   .") or a run of terminators alone ("...").
            if sentence and any(char not in _TERMINATORS for char in sentence):
                return sentence, end

            return "", end

        # No terminator found. Force-split if oversize.
        if self.max_chunk_length is not None and len(text) >= self.max_chunk_length:
            end = self._find_overflow_break(text, self.max_chunk_length)
            sentence = text[:end].strip()

            if sentence:
                return sentence, end

            return "", end

        return None, 0

    @staticmethod
    def _find_overflow_break(text: str, limit: int) -> int:
        """Pick a break index at or before ``limit`` for a sentence that has
        overflowed ``max_chunk_length`` without a terminator. Prefers the last
        whitespace within the limit; falls back to the limit itself."""
        for index in range(min(limit, len(text)) - 1, 0, -1):
            if text[index] in _WHITESPACE:
                return index
        return limit

    def _append_sentence(self, sentence: str) -> None:
        """Append ``sentence`` to the chunk buffer, joining with a space."""
        if sentence:
            if self._chunk_buffer:
                self._chunk_buffer = f"{self._chunk_buffer} {sentence}"
            else:
                self._chunk_buffer = sentence

    def _build_chunk(self) -> Optional[str]:
        """Return the buffered chunk if it has reached ``min_chunk_length``,
        otherwise ``None``. Clears the buffer on emit."""
        if not self._chunk_buffer or len(self._chunk_buffer) < self.min_chunk_length:
            return None

        chunk = self._chunk_buffer
        self._chunk_buffer = ""

        return chunk

class NativeSentenceSplitterAction(SentenceSplitterAction):
    def _create_splitter(self, min_chunk_length: int, max_chunk_length: Optional[int]) -> StreamingSentenceSplitter:
        return NativeStreamingSentenceSplitter(min_chunk_length, max_chunk_length)

@register_sentence_splitter_service(SentenceSplitterDriver.NATIVE)
class NativeSentenceSplitterService(SentenceSplitterService):
    def __init__(self, id: str, config: SentenceSplitterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: SentenceSplitterActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await NativeSentenceSplitterAction(action).run(context, loop)
