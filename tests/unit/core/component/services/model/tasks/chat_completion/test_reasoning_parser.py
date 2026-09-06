"""Tests for :class:`ReasoningParser` against real reasoning model output shapes.

Two DSL modes:
  * tagged (``<think>...</think>``) — DeepSeek-R1, GLM-Z1, Kimi-K1.5
  * tagless (``</think>`` only) — Qwen3 thinking mode, which begins its response
    already inside the reasoning span and closes it before regular content.

We also cover the combined pipeline through :class:`ChatChoicesBuilder` (reasoning
runs first, tool_call parser sees the surviving text runs) since that is the
production entry point.
"""

import pytest
import asyncio

from mindor.core.component.services.model.tasks.chat_completion.common import (
    ChatChoicesBuilder,
    ReasoningParser,
    ReasoningStreamSplitter,
    ToolCallParser,
)
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.common import (
    ReasoningParserConfig,
    ToolCallParserConfig,
)


def _strip_ids(blocks):
    normalized = []
    for block in blocks:
        block = dict(block)
        block.pop("id", None)
        normalized.append(block)
    return normalized


# --- Non-streaming (ReasoningParser.parse) -----------------------------------------------


class TestTaggedReasoning:
    """DeepSeek-R1 style: <think>...</think> may appear anywhere in the output."""

    @pytest.fixture
    def parser(self):
        return ReasoningParser(ReasoningParserConfig(
            start_tag="<think>",
            end_tag="</think>",
        ))

    def test_reasoning_at_start(self, parser):
        raw = "<think>I should look it up.</think>The answer is 42."
        assert parser.parse(raw) == [
            { "type": "reasoning", "text": "I should look it up." },
            { "type": "text", "text": "The answer is 42." },
        ]

    def test_text_before_reasoning_is_preserved(self, parser):
        raw = "Sure. <think>let me think</think> Done."
        assert parser.parse(raw) == [
            { "type": "text", "text": "Sure. " },
            { "type": "reasoning", "text": "let me think" },
            { "type": "text", "text": " Done." },
        ]

    def test_no_reasoning_spans_yields_single_text_block(self, parser):
        raw = "Just a plain answer."
        assert parser.parse(raw) == [ { "type": "text", "text": "Just a plain answer." } ]

    def test_multiple_reasoning_spans(self, parser):
        raw = "<think>first</think>step one<think>second</think>step two"
        assert parser.parse(raw) == [
            { "type": "reasoning", "text": "first" },
            { "type": "text", "text": "step one" },
            { "type": "reasoning", "text": "second" },
            { "type": "text", "text": "step two" },
        ]

    def test_unclosed_reasoning_is_dropped(self, parser):
        raw = "prefix <think>never closes"
        assert parser.parse(raw) == [
            { "type": "text", "text": "prefix " },
        ]

    def test_empty_reasoning_body_yields_no_block(self, parser):
        raw = "before<think></think>after"
        assert parser.parse(raw) == [
            { "type": "text", "text": "before" },
            { "type": "text", "text": "after" },
        ]


class TestTaglessReasoning:
    """Qwen3 thinking mode: the response begins inside the reasoning span; only the
    closing marker separates reasoning from the rest of the answer."""

    @pytest.fixture
    def parser(self):
        return ReasoningParser(ReasoningParserConfig(end_tag="</think>"))

    def test_prefix_reasoning_then_text(self, parser):
        raw = "Let me consider the options.</think>Here is my answer."
        assert parser.parse(raw) == [
            { "type": "reasoning", "text": "Let me consider the options." },
            { "type": "text", "text": "Here is my answer." },
        ]

    def test_missing_end_tag_treats_entire_output_as_reasoning(self, parser):
        raw = "still thinking..."
        assert parser.parse(raw) == [
            { "type": "reasoning", "text": "still thinking..." },
        ]

    def test_empty_reasoning_then_text(self, parser):
        raw = "</think>Direct answer."
        assert parser.parse(raw) == [
            { "type": "text", "text": "Direct answer." },
        ]


# --- Pipeline (reasoning + tool_call) ----------------------------------------------------


class TestReasoningPlusToolCall:
    """End-to-end through ChatChoicesBuilder: reasoning first, then tool_call parser
    sees only the surviving text runs."""

    def test_deepseek_r1_style(self):
        reasoning = ReasoningParser(ReasoningParserConfig(start_tag="<think>", end_tag="</think>"))
        tool_call = ToolCallParser(ToolCallParserConfig(start_tag="<tool_call>", end_tag="</tool_call>"))
        builder = ChatChoicesBuilder(tool_call, reasoning)
        raw = '<think>Need weather.</think>Sure. <tool_call>{"name":"get_weather","arguments":{"city":"Seoul"}}</tool_call>'
        blocks = _strip_ids(builder.build([raw])["choices"][0]["content"])
        assert blocks == [
            { "type": "reasoning", "text": "Need weather." },
            { "type": "text", "text": "Sure. " },
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
        ]

    def test_qwen3_tagless_reasoning_with_tool(self):
        reasoning = ReasoningParser(ReasoningParserConfig(end_tag="</think>"))
        tool_call = ToolCallParser(ToolCallParserConfig(start_tag="<tool_call>", end_tag="</tool_call>"))
        builder = ChatChoicesBuilder(tool_call, reasoning)
        raw = 'thinking through it</think>Here you go.<tool_call>{"name":"f","arguments":{"x":1}}</tool_call>'
        blocks = _strip_ids(builder.build([raw])["choices"][0]["content"])
        assert blocks == [
            { "type": "reasoning", "text": "thinking through it" },
            { "type": "text", "text": "Here you go." },
            { "type": "tool_call", "name": "f", "arguments": { "x": 1 } },
        ]

    def test_reasoning_only_no_tool_call_parser(self):
        # tool_call parser is optional; if only a reasoning parser is set the pipeline
        # returns text blocks alongside reasoning blocks unchanged.
        reasoning = ReasoningParser(ReasoningParserConfig(start_tag="<think>", end_tag="</think>"))
        builder = ChatChoicesBuilder(None, reasoning)
        raw = "before<think>ponder</think>after"
        blocks = builder.build([raw])["choices"][0]["content"]
        assert blocks == [
            { "type": "text", "text": "before" },
            { "type": "reasoning", "text": "ponder" },
            { "type": "text", "text": "after" },
        ]

    def test_tool_call_inside_reasoning_span_is_ignored(self):
        # Whatever appears inside a reasoning span is opaque reasoning text; the tool_call
        # parser must not descend into it.
        reasoning = ReasoningParser(ReasoningParserConfig(start_tag="<think>", end_tag="</think>"))
        tool_call = ToolCallParser(ToolCallParserConfig(start_tag="<tool_call>", end_tag="</tool_call>"))
        builder = ChatChoicesBuilder(tool_call, reasoning)
        raw = '<think>maybe <tool_call>{"name":"x","arguments":{}}</tool_call></think>real answer'
        blocks = _strip_ids(builder.build([raw])["choices"][0]["content"])
        assert blocks == [
            { "type": "reasoning", "text": 'maybe <tool_call>{"name":"x","arguments":{}}</tool_call>' },
            { "type": "text", "text": "real answer" },
        ]


# --- Streaming ---------------------------------------------------------------------------


class TestReasoningStreaming:
    """Streaming should surface reasoning as incremental text-like deltas; the closing
    tag is never emitted; unclosed reasoning at end-of-stream is dropped."""

    def _drive(self, config, chunks):
        splitter = ReasoningStreamSplitter(ReasoningParser(config))
        emitted = []
        for chunk in chunks:
            emitted.extend(splitter.feed(chunk))
        emitted.extend(splitter.flush())
        return emitted

    def _merge_adjacent(self, blocks):
        merged = []
        for block in blocks:
            if merged and merged[-1]["type"] == block["type"]:
                merged[-1]["text"] += block["text"]
            else:
                merged.append(dict(block))
        return merged

    def test_tagged_reasoning_deltas_across_chunks(self):
        config = ReasoningParserConfig(start_tag="<think>", end_tag="</think>")
        chunks = ["<thi", "nk>partial", " thought", "</thi", "nk>done"]
        blocks = self._merge_adjacent(self._drive(config, chunks))
        assert blocks == [
            { "type": "reasoning", "text": "partial thought" },
            { "type": "text", "text": "done" },
        ]

    def test_tagless_prefix_reasoning_streams(self):
        config = ReasoningParserConfig(end_tag="</think>")
        chunks = ["thinking...", " more", "</thi", "nk>final"]
        blocks = self._merge_adjacent(self._drive(config, chunks))
        assert blocks == [
            { "type": "reasoning", "text": "thinking... more" },
            { "type": "text", "text": "final" },
        ]

    def test_unclosed_reasoning_flush_drops_only_unemitted_tail(self):
        # Streaming policy: reasoning flows out incrementally like text (users see it live),
        # so bytes already emitted stay emitted. On flush any bytes still buffered inside an
        # open reasoning span are silently discarded — we never emit them as text.
        config = ReasoningParserConfig(start_tag="<think>", end_tag="</think>")
        chunks = ["hello <think>partial reasoning"]
        blocks = self._merge_adjacent(self._drive(config, chunks))
        # Preceding text is preserved; whatever reasoning bytes crossed the safety zone were
        # emitted live, but flush contributes no new text block for the unclosed span.
        assert blocks[0] == { "type": "text", "text": "hello " }
        assert all(b["type"] != "text" or b["text"] == "hello " for b in blocks)

    def test_no_start_tag_appears_streams_as_text(self):
        config = ReasoningParserConfig(start_tag="<think>", end_tag="</think>")
        chunks = ["just ", "plain ", "text."]
        blocks = self._merge_adjacent(self._drive(config, chunks))
        assert blocks == [ { "type": "text", "text": "just plain text." } ]


class TestBuilderStreamingPipeline:
    """The full stream pipeline (ChatChoicesBuilder.stream) fuses reasoning + tool_call
    splitters correctly."""

    async def _collect(self, agen):
        events = []
        async for event in agen:
            events.append(event)
        return events

    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    def _all_blocks(self, events):
        blocks = []
        for event in events:
            blocks.extend(event["choices"][0]["content"])
        return blocks

    def _drop_ids_and_merge_text(self, blocks):
        merged = []
        for block in blocks:
            block = dict(block)
            block.pop("id", None)
            if merged and merged[-1]["type"] == block["type"] == "text":
                merged[-1]["text"] += block["text"]
            elif merged and merged[-1]["type"] == block["type"] == "reasoning":
                merged[-1]["text"] += block["text"]
            else:
                merged.append(block)
        return merged

    def test_deepseek_r1_pipeline_streaming(self):
        reasoning = ReasoningParser(ReasoningParserConfig(start_tag="<think>", end_tag="</think>"))
        tool_call = ToolCallParser(ToolCallParserConfig(start_tag="<tool_call>", end_tag="</tool_call>"))
        builder = ChatChoicesBuilder(tool_call, reasoning)

        async def source():
            for c in ['<think>reason', 'ing.</think>OK <tool_c', 'all>{"name":"f","arguments":{}}</tool_call>']:
                yield c

        events = asyncio.run(self._collect(builder.stream([source()])))
        assert events[-1]["choices"][0]["finish_reason"] == "stop"
        blocks = self._drop_ids_and_merge_text(self._all_blocks(events[:-1]))
        assert blocks == [
            { "type": "reasoning", "text": "reasoning." },
            { "type": "text", "text": "OK " },
            { "type": "tool_call", "name": "f", "arguments": {} },
        ]
