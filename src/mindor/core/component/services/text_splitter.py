from typing import Optional, Dict, List, Iterator, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import TextSplitterComponentConfig
from mindor.dsl.schema.action import ActionConfig, TextSplitterActionConfig
from mindor.core.utils.iterators import BatchSourceIterator, TextDecodeIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.logger import logging
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
import asyncio

class SegmentMergeBuffer:
    """Accumulates segments up to ``chunk_size``, then yields a chunk and trims so
    the next chunk overlaps the previous one by at most ``chunk_overlap`` characters.

    Segments are joined with ``separator`` when building a chunk. Merge & overlap
    behavior matches LangChain's ``_merge_splits``.
    """
    def __init__(self, chunk_size: int, chunk_overlap: int, separator: str = ""):
        self.chunk_size: int = chunk_size
        self.chunk_overlap: int = chunk_overlap
        self.separator: str = separator

        self._segments: List[str] = []
        self._length: int = 0

    def add(self, segment: str) -> Iterator[str]:
        """Add ``segment`` to the buffer. Before doing so, if it would push the buffer
        over ``chunk_size``, yield the current chunk and drop the oldest segments down
        to the overlap budget."""
        segment_len = len(segment)

        if self._length + segment_len + self._separator_overhead_for_append() > self.chunk_size:
            chunk = self._build_chunk()
            if chunk is not None:
                yield chunk

            while self._should_drop_oldest(segment_len):
                self._drop_oldest()

        self._append(segment)

    def flush(self) -> Optional[str]:
        """Build the final chunk from whatever is buffered and clear state."""
        chunk = self._build_chunk()
        self._segments = []
        self._length = 0
        return chunk

    def _build_chunk(self) -> Optional[str]:
        if not self._segments:
            return None
        text = self.separator.join(self._segments).strip()
        return text or None

    def _should_drop_oldest(self, segment_len: int) -> bool:
        if self._length > self.chunk_overlap:
            return True
        if self._length > 0:
            overhead = len(self.separator) if self._segments else 0
            return self._length + segment_len + overhead > self.chunk_size
        return False

    def _drop_oldest(self) -> None:
        oldest_len = len(self._segments[0])
        overhead = len(self.separator) if len(self._segments) > 1 else 0
        self._length -= oldest_len + overhead
        self._segments.pop(0)

    def _append(self, segment: str) -> None:
        overhead = len(self.separator) if len(self._segments) > 1 else 0
        self._segments.append(segment)
        self._length += len(segment) + overhead

    def _separator_overhead_for_append(self) -> int:
        return len(self.separator) if self._segments else 0


class StreamingTextSplitter:
    """Splits text incrementally as input is fed.

    Algorithm (streaming/batch equivalent):
    - Hold input in a pending buffer.
    - Decide a single separator (from `separators`, in priority order) the first time
      a candidate appears in the pending buffer. Once decided, the same separator is
      used for the rest of the input.
    - To keep streaming results identical to batch, decision is held back while the
      buffer end might still grow into a higher-priority separator (`max_separator_len`
      lookahead). On `flush()` the lookahead is lifted.
    - With a decided separator, segments are produced using the same keep_separator=True
      semantics as `_split_text_with_separator`: the first segment has no leading
      separator, subsequent segments carry the separator at their start.
    - Oversize segments (>= chunk_size) are recursively split with the lower-priority
      separators (`fallback_separators`), mirroring `_split_text`.
    - Merge & overlap behavior is delegated to ``SegmentMergeBuffer``.
    """
    def __init__(self, separators: List[str], chunk_size: int, chunk_overlap: int):
        self.separators: List[str] = separators
        self.chunk_size: int = chunk_size
        self.chunk_overlap: int = chunk_overlap
        self.max_separator_len: int = max((len(s) for s in separators if s), default=0)

        self._pending_text: str = ""
        self._separator: Optional[str] = None       # Decided on first match.
        self._fallback_separators: List[str] = []   # Lower-priority separators (for oversize segments).
        self._is_first_segment: bool = True         # Tracks keep_separator semantics for the FIRST segment.

        self._merge_buffer: SegmentMergeBuffer = SegmentMergeBuffer(chunk_size, chunk_overlap)

    def feed(self, text: str) -> Iterator[str]:
        if text:
            self._pending_text += text
            yield from self._extract_segments(final=False)

    def flush(self) -> Iterator[str]:
        yield from self._extract_segments(final=True)
        chunk = self._merge_buffer.flush()
        if chunk is not None:
            yield chunk

    def _extract_segments(self, final: bool) -> Iterator[str]:
        if self._separator is None:
            if not self._try_decide_separator(final=final):
                return
            # After decision, the part of pending BEFORE the first separator occurrence is
            # the first segment (no leading separator).
            first_pos = self._pending_text.find(self._separator) if self._separator else -1
            if self._separator and first_pos >= 0:
                first_segment = self._pending_text[:first_pos]
                self._pending_text = self._pending_text[first_pos:]
                if first_segment:
                    yield from self._consume_segment(first_segment)
                self._is_first_segment = False
            elif not self._separator:
                # Empty separator: character-level split. No "first segment" notion —
                # every character is its own segment, all with empty separator (no leading sep).
                self._is_first_segment = False

        while True:
            segment, remaining = self._extract_segment(self._pending_text, final=final)
            if segment is None:
                break
            self._pending_text = remaining
            yield from self._consume_segment(segment)

    def _try_decide_separator(self, final: bool) -> bool:
        """Try to pick a separator from `separators` in priority order.

        Decision is held back while the buffer is shorter than `chunk_size` AND not
        final: a higher-priority separator might still appear in the upcoming input.
        Once the buffer has grown to `chunk_size`, or input is finalized, we commit to
        the highest-priority separator that actually appears in what we have (falling
        through to the empty-string character fallback if none do).
        """
        if not final and len(self._pending_text) < self.chunk_size:
            return False

        for index, separator in enumerate(self.separators):
            if not separator:
                # Empty separator — character split fallback.
                self._separator = separator
                self._fallback_separators = []
                return True

            if self._pending_text.find(separator) < 0:
                continue

            self._separator = separator
            self._fallback_separators = self.separators[index + 1:]
            return True

        return False

    def _extract_segment(self, text: str, final: bool) -> Tuple[Optional[str], str]:
        """Extract one segment from the start of `text` using the decided separator.

        keep_separator=True: every segment after the first STARTS with the separator.
        So we look for the NEXT separator occurrence after position `len(separator)`
        (skipping the leading separator) and cut there. The segment is
        `text[:next_pos]` (which starts with the leading separator), the rest is
        `text[next_pos:]` (which also starts with that next separator, ready for
        the following extraction).
        """
        separator = self._separator
        if separator is None:
            return None, text

        if not separator:
            # Empty separator: yield one character at a time.
            if not text:
                return None, text
            if not final and len(text) <= self.max_separator_len:
                # Hold back the last character so a higher-priority separator (none here,
                # since we only decide empty when final) could still complete — but in
                # practice empty is only decided on final, so this branch is unreachable.
                return None, text
            return text[:1], text[1:]

        # The text here should start with `separator` (or be empty / shorter than
        # separator, which means nothing to cut yet).
        if len(text) < len(separator):
            return None, text

        next_pos = text.find(separator, len(separator))
        if next_pos < 0:
            # No further separator visible. Hold the text until more arrives or final.
            if not final:
                return None, text
            # Final: the whole remaining text is the last segment.
            return text, ""

        return text[:next_pos], text[next_pos:]

    def _consume_segment(self, segment: str) -> Iterator[str]:
        if len(segment) < self.chunk_size:
            yield from self._merge_buffer.add(segment)
            return

        # Oversize: flush merge buffer, then recursively split with lower-priority
        # separators. If none left, emit the segment as-is.
        chunk = self._merge_buffer.flush()
        if chunk is not None:
            yield chunk

        if not self._fallback_separators:
            text = segment.strip()
            if text:
                yield text
            return

        sub = StreamingTextSplitter(self._fallback_separators, self.chunk_size, self.chunk_overlap)
        for chunk in sub.feed(segment):
            yield chunk
        for chunk in sub.flush():
            yield chunk

class TextSplitterAction:
    def __init__(self, config: TextSplitterActionConfig):
        self.config: TextSplitterActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        text       = await context.render_text(self.config.text)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(text, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_texts, params, streaming, loop)
                    for result in batch_results:
                        if isinstance(result, (StreamIterator, AsyncIterator)):
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_texts, params, streaming, loop)
                for result in batch_results:
                    if isinstance(result, (StreamIterator, AsyncIterator)):
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        separators    = await context.render_variable(self.config.separators)
        chunk_size    = await context.render_variable(self.config.chunk_size)
        chunk_overlap = await context.render_variable(self.config.chunk_overlap)

        if chunk_size is None:
            raise ValueError("'chunk_size' must be specified for text splitter")

        if chunk_overlap is None:
            raise ValueError("'chunk_overlap' must be specified for text splitter")

        if chunk_overlap > chunk_size:
            raise ValueError(f"Got a larger chunk overlap ({chunk_overlap}) than chunk size ({chunk_size}), should be smaller.")

        if not separators:
            separators = [ "\n\n", "\n", " ", "" ]

        return { "separators": separators, "chunk_size": chunk_size, "chunk_overlap": chunk_overlap }

    async def _process_batch(
        self,
        texts: List[Any],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> List[Any]:
        return await asyncio.gather(*[
            self._process(text, params, streaming, loop) for text in texts
        ])

    async def _process(
        self,
        text: Any,
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        if text is None:
            logging.debug("Text splitter skipped because no text was provided.")
            return None

        if streaming:
            return self._split_text(text, params["separators"], params["chunk_size"], params["chunk_overlap"])

        results: List[str] = []
        async for chunk in self._split_text(text, params["separators"], params["chunk_size"], params["chunk_overlap"]):
            results.append(chunk)

        return results

    async def _split_text(self, text: Any, separators: List[str], chunk_size: int, chunk_overlap: int) -> AsyncIterator[str]:
        splitter = StreamingTextSplitter(separators, chunk_size, chunk_overlap)

        if isinstance(text, TextStreamResource):
            text = text.text

        if isinstance(text, (StreamResource, StreamChunkIterator)):
            async for piece in TextDecodeIterator(text):
                for chunk in splitter.feed(piece):
                    yield chunk
        else:
            for chunk in splitter.feed(text):
                yield chunk

        for chunk in splitter.flush():
            yield chunk

@register_component(ComponentType.TEXT_SPLITTER)
class TextSplitterComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: TextSplitterComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        return await TextSplitterAction(action).run(context, loop)
