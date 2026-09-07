"""Property tests asserting that streaming and non-streaming code paths agree.

For every documented parser shape the two entry points — ``parse(full_text)`` and
``feed(chunk)+flush()`` — must produce the same block sequence once normalised
(strip ``id``, merge adjacent same-type text/reasoning blocks, drop empty text).

These tests exist because prior defects were all divergences between the two paths
that the per-path tests could not catch: the pythonic terminator bug, the batch
envelope skipped by the stream splitter, and the prefix-reasoning tail lost on
flush. Any future edit that shifts one path without the other will fail here.
"""

import pytest

from mindor.core.component.services.model.tasks.chat_completion.common import (
    ReasoningParser,
    ReasoningStreamSplitter,
    ToolCallParser,
    ToolCallStreamSplitter,
)
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.common import (
    ReasoningParserConfig,
    ToolCallParserConfig,
)


# Chunk sizes covering: byte-at-a-time (worst case for boundary safety), small
# splits that straddle tags, mid-body splits, and whole-string (equivalent to
# non-streaming). If parse == stream holds across all four, it holds for any
# realistic tokenizer emission cadence.
CHUNK_SIZES = [1, 3, 7, None]


def _chunks(text, size):
    if size is None or size >= len(text):
        return [text]
    return [text[i:i + size] for i in range(0, len(text), size)]


def _normalise(blocks):
    """Drop ids, merge adjacent same-type text/reasoning blocks, drop empty text."""
    out = []

    for block in blocks:
        block = dict(block)
        block.pop("id", None)

        if block.get("type") == "text" and not block.get("text"):
            continue

        block_type = block.get("type")

        if out and out[-1].get("type") == block_type and block_type in ("text", "reasoning"):
            out[-1]["text"] += block["text"]
        else:
            out.append(block)

    return out


def _run_tool_call_stream(parser, chunks):
    splitter = ToolCallStreamSplitter(parser)
    emitted = []

    for chunk in chunks:
        emitted.extend(splitter.feed(chunk))

    emitted.extend(splitter.flush())

    return emitted


def _run_reasoning_stream(parser, chunks):
    splitter = ReasoningStreamSplitter(parser)
    emitted = []

    for chunk in chunks:
        emitted.extend(splitter.feed(chunk))

    emitted.extend(splitter.flush())

    return emitted


# --- tool_call corpus ---------------------------------------------------------------------


TOOL_CALL_CASES = [
    # (config, raw_text, id)
    (
        ToolCallParserConfig(start_tag="<tool_call>", end_tag="</tool_call>"),
        'Let me check.\n<tool_call>{"name":"get_weather","arguments":{"city":"Seoul"}}</tool_call>',
        "hermes_single",
    ),
    (
        ToolCallParserConfig(start_tag="<tool_call>", end_tag="</tool_call>"),
        '<tool_call>{"name":"a","arguments":{}}</tool_call><tool_call>{"name":"b","arguments":{}}</tool_call>',
        "hermes_parallel",
    ),
    (
        ToolCallParserConfig(start_tag="<|python_tag|>", arguments_key="parameters"),
        '<|python_tag|>{"name":"get_weather","parameters":{"city":"Paris"}}',
        "llama_json",
    ),
    (
        ToolCallParserConfig(start_tag="<|python_tag|>", format="pythonic"),
        '<|python_tag|>[get_weather(city="Seoul"), get_time(tz="UTC")]',
        "llama_pythonic_list",
    ),
    (
        ToolCallParserConfig(start_tag="<|python_tag|>", format="pythonic"),
        '<|python_tag|>get_weather(city="Seoul")',
        "llama_pythonic_single_nonbracketed",
    ),
    (
        ToolCallParserConfig(start_tag="<|python_tag|>", format="pythonic"),
        '<|python_tag|>get_weather(city="Seoul") and then extra prose',
        "llama_pythonic_single_with_trailing",
    ),
    (
        ToolCallParserConfig(start_tag="[TOOL_CALLS]"),
        '[TOOL_CALLS][{"name":"a","arguments":{}},{"name":"b","arguments":{"y":2}}]',
        "mistral_batch_array",
    ),
    (
        ToolCallParserConfig(start_tag="<|tool_call|>"),
        '<|tool_call|>[{"name":"lookup","arguments":{"q":"cats"}}]',
        "granite_array",
    ),
    (
        ToolCallParserConfig(
            batch_start_tag="<｜tool_calls_begin｜>",
            batch_end_tag="<｜tool_calls_end｜>",
            start_tag="<｜tool_call_begin｜>",
            end_tag="<｜tool_call_end｜>",
            name_marker={"prefix": "function<｜tool_sep｜>", "suffix": "\n"},
            arguments_marker={"open": "```json\n", "close": "\n```"},
        ),
        (
            "Sure.\n"
            "<｜tool_calls_begin｜>"
            "<｜tool_call_begin｜>function<｜tool_sep｜>a\n```json\n{}\n```\n<｜tool_call_end｜>"
            "\n\n"
            "<｜tool_call_begin｜>function<｜tool_sep｜>b\n```json\n{\"y\":2}\n```\n<｜tool_call_end｜>"
            "<｜tool_calls_end｜>"
            "bye"
        ),
        "deepseek_batch_with_framing",
    ),
    (
        ToolCallParserConfig(
            batch_start_tag="[BATCH]",
            batch_end_tag="[/BATCH]",
            start_tag="<tool_call>",
            end_tag="</tool_call>",
        ),
        'hi[BATCH]<tool_call>{"name":"f","arguments":{}}</tool_call>\n<tool_call>{"name":"g","arguments":{}}</tool_call>[/BATCH]bye',
        "hermes_wrapped_in_batch",
    ),
    (
        # Two envelopes, text between them, text before/after.
        ToolCallParserConfig(
            batch_start_tag="[BATCH]",
            batch_end_tag="[/BATCH]",
            start_tag="<tool_call>",
            end_tag="</tool_call>",
        ),
        'a[BATCH]<tool_call>{"name":"f","arguments":{}}</tool_call>[/BATCH]b[BATCH]<tool_call>{"name":"g","arguments":{}}</tool_call>[/BATCH]c',
        "multi_envelope",
    ),
    (
        # Envelope opened, immediately closed with no calls inside — pure framing.
        ToolCallParserConfig(
            batch_start_tag="[BATCH]",
            batch_end_tag="[/BATCH]",
            start_tag="<tool_call>",
            end_tag="</tool_call>",
        ),
        'a[BATCH]no calls here[/BATCH]b',
        "empty_envelope",
    ),
    (
        ToolCallParserConfig(start_tag="<tool_call>", end_tag="</tool_call>"),
        'plain text with no tool calls at all',
        "no_tags",
    ),
    (
        ToolCallParserConfig(start_tag="<tool_call>", end_tag="</tool_call>"),
        'pre <tool_call>this is not json</tool_call> post',
        "malformed_body",
    ),
]


@pytest.mark.parametrize("chunk_size", CHUNK_SIZES)
@pytest.mark.parametrize("config,raw,case_id", TOOL_CALL_CASES, ids=[c[2] for c in TOOL_CALL_CASES])
def test_tool_call_stream_matches_parse(config, raw, case_id, chunk_size):
    parser = ToolCallParser(config)
    expected = _normalise(parser.parse(raw))
    actual = _normalise(_run_tool_call_stream(parser, _chunks(raw, chunk_size)))
    assert actual == expected, f"{case_id} @ chunk_size={chunk_size}"


# --- reasoning corpus ---------------------------------------------------------------------


REASONING_CASES = [
    (
        ReasoningParserConfig(start_tag="<think>", end_tag="</think>"),
        "<think>ponder</think>the answer",
        "tagged_at_start",
    ),
    (
        ReasoningParserConfig(start_tag="<think>", end_tag="</think>"),
        "prefix text <think>ponder</think> suffix text",
        "tagged_mid",
    ),
    (
        ReasoningParserConfig(start_tag="<think>", end_tag="</think>"),
        "<think>first</think>step one<think>second</think>step two",
        "tagged_multi",
    ),
    (
        ReasoningParserConfig(start_tag="<think>", end_tag="</think>"),
        "plain answer without reasoning",
        "tagged_none",
    ),
    (
        ReasoningParserConfig(end_tag="</think>"),
        "thinking through it</think>the actual answer",
        "prefix_normal",
    ),
    (
        ReasoningParserConfig(end_tag="</think>"),
        "Hello, this is a normal answer.",
        "prefix_missing_end_tag_all_reasoning",
    ),
    (
        ReasoningParserConfig(end_tag="</think>"),
        "</think>direct answer",
        "prefix_empty_reasoning",
    ),
]


@pytest.mark.parametrize("chunk_size", CHUNK_SIZES)
@pytest.mark.parametrize("config,raw,case_id", REASONING_CASES, ids=[c[2] for c in REASONING_CASES])
def test_reasoning_stream_matches_parse(config, raw, case_id, chunk_size):
    parser = ReasoningParser(config)
    expected = _normalise(parser.parse(raw))
    actual = _normalise(_run_reasoning_stream(parser, _chunks(raw, chunk_size)))
    assert actual == expected, f"{case_id} @ chunk_size={chunk_size}"
