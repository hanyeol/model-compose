"""Tests for :class:`ToolCallParser` against real-world model output formats.

Each ``TestX`` class targets one model family and uses raw sample strings shaped
to match what the tokenizer's chat template + generation actually produces at
inference time. Sources cross-checked against the model's HuggingFace tokenizer
config, official cookbook, and vLLM's built-in tool parsers.
"""

import pytest

from mindor.core.component.services.model.tasks.chat_completion.common import (
    ToolCallParser,
    ToolCallStreamSplitter,
)
from mindor.dsl.schema.component.impl.model.tasks.chat_completion.impl.common import (
    ToolCallParserConfig,
)


def _strip_ids(blocks):
    """ToolCallParser assigns a fresh ulid to each call; drop it so tests can
    compare block dicts by structural equality without carrying random values."""
    normalized = []
    for block in blocks:
        block = dict(block)
        block.pop("id", None)
        normalized.append(block)
    return normalized


class TestHermesQwen:
    """Hermes-2-Pro, Qwen2.5-Instruct, Qwen3: <tool_call>{json}</tool_call>."""

    @pytest.fixture
    def parser(self):
        return ToolCallParser(ToolCallParserConfig(
            start_tag="<tool_call>",
            end_tag="</tool_call>",
        ))

    def test_single_call_surrounded_by_text(self, parser):
        raw = 'Let me check.\n<tool_call>\n{"name": "get_weather", "arguments": {"city": "Seoul"}}\n</tool_call>'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "text", "text": "Let me check.\n" },
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
        ]

    def test_parallel_calls_via_repeated_tags(self, parser):
        raw = (
            '<tool_call>{"name": "get_weather", "arguments": {"city": "Seoul"}}</tool_call>'
            '<tool_call>{"name": "get_weather", "arguments": {"city": "Tokyo"}}</tool_call>'
        )
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Tokyo" } },
        ]

    def test_arguments_with_nested_objects_and_arrays(self, parser):
        raw = '<tool_call>{"name": "search", "arguments": {"filters": {"tags": ["a","b"], "range": {"min": 1, "max": 10}}}}</tool_call>'
        blocks = _strip_ids(parser.parse(raw))
        assert blocks == [ {
            "type": "tool_call",
            "name": "search",
            "arguments": { "filters": { "tags": ["a", "b"], "range": { "min": 1, "max": 10 } } },
        } ]

    def test_arguments_with_escaped_quotes_in_strings(self, parser):
        raw = '<tool_call>{"name": "reply", "arguments": {"text": "say \\"hi\\" now"}}</tool_call>'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "reply", "arguments": { "text": 'say "hi" now' } },
        ]

    def test_empty_arguments_object(self, parser):
        raw = '<tool_call>{"name": "ping", "arguments": {}}</tool_call>'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "ping", "arguments": {} },
        ]

    def test_missing_arguments_key_defaults_to_empty(self, parser):
        raw = '<tool_call>{"name": "ping"}</tool_call>'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "ping", "arguments": {} },
        ]

    def test_ids_are_unique_across_calls(self, parser):
        raw = (
            '<tool_call>{"name": "a", "arguments": {}}</tool_call>'
            '<tool_call>{"name": "b", "arguments": {}}</tool_call>'
        )
        blocks = parser.parse(raw)
        ids = [ b["id"] for b in blocks if b["type"] == "tool_call" ]
        assert len(ids) == 2
        assert ids[0] != ids[1]
        assert all(i.startswith("call_") for i in ids)


class TestLlama3Json:
    """Llama 3.1 JSON tool format: <|python_tag|>{...} with no closing marker,
    and the ``parameters`` field instead of ``arguments``.
    """

    @pytest.fixture
    def parser(self):
        return ToolCallParser(ToolCallParserConfig(
            start_tag="<|python_tag|>",
            arguments_key="parameters",
        ))

    def test_single_call_terminated_by_json_length(self, parser):
        raw = '<|python_tag|>{"name": "get_weather", "parameters": {"city": "Seoul"}}'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
        ]

    def test_text_before_start_tag_is_preserved(self, parser):
        # Llama models occasionally emit reasoning text before the tag.
        raw = 'I will call the weather tool.\n<|python_tag|>{"name": "get_weather", "parameters": {"city": "Paris"}}'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "text", "text": "I will call the weather tool.\n" },
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Paris" } },
        ]

    def test_trailing_text_after_json_becomes_text_block(self, parser):
        raw = '<|python_tag|>{"name": "f", "parameters": {}}<|eom_id|>'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "f", "arguments": {} },
            { "type": "text", "text": "<|eom_id|>" },
        ]


class TestLlama3Pythonic:
    """Llama 3.2 pythonic format: <|python_tag|>[foo(x="v"), bar(y=1)]

    The Llama 3.2 tool prompt introduces the call list with the ``<|python_tag|>``
    marker, so we use it as ``start_tag``. ``end_tag`` is omitted because the
    body is itself a bracketed list; we let the pythonic-value probe consume
    one complete AST expression (its bracket balancing picks the outer ``]``
    correctly, even when arguments contain nested lists).
    """

    @pytest.fixture
    def parser(self):
        return ToolCallParser(ToolCallParserConfig(
            start_tag="<|python_tag|>",
            format="pythonic",
        ))

    def test_single_call(self, parser):
        raw = '<|python_tag|>[get_weather(city="Seoul")]'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
        ]

    def test_parallel_calls_in_one_list(self, parser):
        raw = '<|python_tag|>[get_weather(city="Seoul"), get_time(tz="UTC")]'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
            { "type": "tool_call", "name": "get_time", "arguments": { "tz": "UTC" } },
        ]

    def test_argument_literals_int_float_bool_none_list(self, parser):
        raw = '<|python_tag|>[configure(count=3, ratio=0.5, enabled=True, tag=None, tags=["a","b"])]'
        assert _strip_ids(parser.parse(raw)) == [ {
            "type": "tool_call",
            "name": "configure",
            "arguments": { "count": 3, "ratio": 0.5, "enabled": True, "tag": None, "tags": ["a", "b"] },
        } ]

    def test_no_positional_args_allowed(self, parser):
        # Pythonic tool calls should always use keyword args; positional means malformed.
        raw = '<|python_tag|>[get_weather("Seoul")]'
        # Malformed body → the start tag is kept as literal text and the parser resumes.
        # No successful tool_call blocks are emitted.
        blocks = parser.parse(raw)
        assert not any(b["type"] == "tool_call" for b in blocks)

    def test_leading_reasoning_text_is_preserved(self, parser):
        raw = 'Sure, I\'ll look that up.\n<|python_tag|>[get_weather(city="Paris")]'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "text", "text": "Sure, I'll look that up.\n" },
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Paris" } },
        ]


class TestMistral:
    """Mistral v0.3+: [TOOL_CALLS][{...}, {...}] — single tag, body is a JSON
    array that may contain multiple calls."""

    @pytest.fixture
    def parser(self):
        return ToolCallParser(ToolCallParserConfig(start_tag="[TOOL_CALLS]"))

    def test_single_call_in_array(self, parser):
        raw = '[TOOL_CALLS][{"name": "get_weather", "arguments": {"city": "Seoul"}}]'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
        ]

    def test_parallel_calls_in_single_array(self, parser):
        raw = '[TOOL_CALLS][{"name":"a","arguments":{}},{"name":"b","arguments":{"y":2}}]'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "a", "arguments": {} },
            { "type": "tool_call", "name": "b", "arguments": { "y": 2 } },
        ]

    def test_preceding_answer_text_is_preserved(self, parser):
        raw = 'Sure, calling now.\n[TOOL_CALLS][{"name": "ping", "arguments": {}}]'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "text", "text": "Sure, calling now.\n" },
            { "type": "tool_call", "name": "ping", "arguments": {} },
        ]


class TestGranite:
    """IBM Granite 3.x: <|tool_call|>[{"name":"...", "arguments":{...}}]
    — end_tag omitted, body is a JSON array."""

    @pytest.fixture
    def parser(self):
        return ToolCallParser(ToolCallParserConfig(start_tag="<|tool_call|>"))

    def test_single_call_in_array(self, parser):
        raw = '<|tool_call|>[{"name":"lookup","arguments":{"q":"cats"}}]'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "lookup", "arguments": { "q": "cats" } },
        ]

    def test_parallel_calls(self, parser):
        raw = '<|tool_call|>[{"name":"a","arguments":{}},{"name":"b","arguments":{}}]'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "a", "arguments": {} },
            { "type": "tool_call", "name": "b", "arguments": {} },
        ]


class TestMalformedBodies:
    """A malformed body must be reported as literal text; the parser must not
    swallow the rest of the response or crash."""

    @pytest.fixture
    def parser(self):
        return ToolCallParser(ToolCallParserConfig(
            start_tag="<tool_call>",
            end_tag="</tool_call>",
        ))

    def test_body_not_json(self, parser):
        raw = 'pre <tool_call>this is not json</tool_call> post'
        # start_tag is retained as literal text and parsing resumes past it.
        blocks = parser.parse(raw)
        assert all(b["type"] == "text" for b in blocks)
        assert "".join(b["text"] for b in blocks) == raw

    def test_body_missing_name_key(self, parser):
        raw = '<tool_call>{"arguments": {"x": 1}}</tool_call>'
        blocks = parser.parse(raw)
        assert all(b["type"] == "text" for b in blocks)

    def test_body_with_non_dict_arguments(self, parser):
        # arguments must be an object; a bare string is rejected.
        raw = '<tool_call>{"name": "f", "arguments": "oops"}</tool_call>'
        blocks = parser.parse(raw)
        assert all(b["type"] == "text" for b in blocks)

    def test_open_tag_without_close(self, parser):
        raw = 'partial <tool_call>{"name": "f", "arguments": {}} but no close'
        blocks = parser.parse(raw)
        assert all(b["type"] == "text" for b in blocks)

    def test_valid_call_after_a_malformed_one_still_parses(self, parser):
        # Malformed span must not consume the second, valid tool_call.
        raw = (
            'x <tool_call>nope</tool_call> y '
            '<tool_call>{"name": "ok", "arguments": {}}</tool_call>'
        )
        blocks = _strip_ids(parser.parse(raw))
        assert blocks[-1] == { "type": "tool_call", "name": "ok", "arguments": {} }
        assert any(b["type"] == "text" for b in blocks[:-1])


class TestStreamingSplitter:
    """`ToolCallStreamSplitter` sees output one chunk at a time. Regardless of
    how the raw string is sliced, the final concatenated emission must equal
    what the non-streaming parser produces on the joined string, minus any
    trailing text held back for boundary safety."""

    @pytest.fixture
    def parser(self):
        return ToolCallParser(ToolCallParserConfig(
            start_tag="<tool_call>",
            end_tag="</tool_call>",
        ))

    def _drive(self, parser, chunks):
        splitter = ToolCallStreamSplitter(parser)
        emitted = []
        for chunk in chunks:
            emitted.extend(splitter.feed(chunk))
        emitted.extend(splitter.flush())
        return _strip_ids(emitted)

    def _merge_text_blocks(self, blocks):
        # Streamed text may arrive as several adjacent text blocks; merge for
        # comparison against non-streaming output which coalesces them.
        merged = []
        for block in blocks:
            if block["type"] == "text" and merged and merged[-1]["type"] == "text":
                merged[-1]["text"] += block["text"]
            else:
                merged.append(dict(block))
        return merged

    def test_start_tag_split_across_chunk_boundary(self, parser):
        chunks = ['hi <tool_c', 'all>{"name":"get","arguments":{"x":1}}</tool_call> done']
        blocks = self._merge_text_blocks(self._drive(parser, chunks))
        assert blocks == [
            { "type": "text", "text": "hi " },
            { "type": "tool_call", "name": "get", "arguments": { "x": 1 } },
            { "type": "text", "text": " done" },
        ]

    def test_end_tag_split_across_chunk_boundary(self, parser):
        chunks = ['<tool_call>{"name":"f","arguments":{}}</tool', '_call>tail']
        blocks = self._merge_text_blocks(self._drive(parser, chunks))
        assert blocks == [
            { "type": "tool_call", "name": "f", "arguments": {} },
            { "type": "text", "text": "tail" },
        ]

    def test_body_split_across_many_tiny_chunks(self, parser):
        raw = '<tool_call>{"name":"search","arguments":{"q":"hello world","n":3}}</tool_call>'
        chunks = [ raw[i:i+3] for i in range(0, len(raw), 3) ]
        blocks = self._merge_text_blocks(self._drive(parser, chunks))
        assert blocks == [
            { "type": "tool_call", "name": "search", "arguments": { "q": "hello world", "n": 3 } },
        ]

    def test_parallel_calls_streamed(self, parser):
        chunks = [
            '<tool_call>{"name":"a","arguments":{}}</tool_call>',
            '<tool_call>{"name":"b","arguments":{}}</tool_call>',
        ]
        blocks = self._merge_text_blocks(self._drive(parser, chunks))
        assert blocks == [
            { "type": "tool_call", "name": "a", "arguments": {} },
            { "type": "tool_call", "name": "b", "arguments": {} },
        ]

    def test_flush_drops_unterminated_call(self, parser):
        # Stream ends mid-call (no </tool_call>). The buffered call is dropped
        # silently by the "malformed → discard" policy; preceding text stays.
        chunks = ['hello <tool_call>{"name":"f", "arg']
        blocks = self._merge_text_blocks(self._drive(parser, chunks))
        # We should see the leading text but no tool_call.
        assert not any(b["type"] == "tool_call" for b in blocks)
        assert any(b["type"] == "text" and "hello" in b["text"] for b in blocks)

    def test_no_parser_matches_are_not_split_from_text(self, parser):
        # Plain text with no tags should stream out losslessly (order + content).
        chunks = ['just ', 'plain ', 'text.']
        blocks = self._merge_text_blocks(self._drive(parser, chunks))
        assert blocks == [ { "type": "text", "text": "just plain text." } ]


class TestLlama3JsonStreaming:
    """Streaming behaviour when end_tag is absent (Llama 3.1 style):
    a JSON value's length defines the boundary."""

    @pytest.fixture
    def parser(self):
        return ToolCallParser(ToolCallParserConfig(
            start_tag="<|python_tag|>",
            arguments_key="parameters",
        ))

    def test_call_emitted_once_json_closes(self, parser):
        splitter = ToolCallStreamSplitter(parser)
        # Feed the tag first; nothing to emit yet.
        assert splitter.feed('<|python_tag|>') == []
        # Feed an incomplete JSON; splitter waits.
        assert splitter.feed('{"name":"f","parameters":{"x":') == []
        # Close the JSON — this triggers the call.
        emitted = splitter.feed('1}}')
        assert _strip_ids(emitted) == [
            { "type": "tool_call", "name": "f", "arguments": { "x": 1 } },
        ]


# --- Marker-based extraction (name_marker / arguments_marker) --------------------------


class TestNameMarker:
    """When a call body carries the tool name as a literal between two strings (not as a
    JSON field), ``name_marker`` should locate it. ``arguments_marker`` may still be absent
    in which case the whole body parses as JSON and ``arguments_key`` picks the args."""

    @pytest.fixture
    def parser(self):
        # Simulated body: "call:get_weather\n{\"city\":\"Seoul\"}"
        return ToolCallParser(ToolCallParserConfig(
            start_tag="<c>",
            end_tag="</c>",
            name_marker={ "prefix": "call:", "suffix": "\n" },
        ))

    def test_name_from_literal_arguments_from_json(self, parser):
        raw = '<c>call:get_weather\n{"city":"Seoul"}</c>'
        # Falls back to JSON body for arguments; but the body is not a valid JSON object
        # (leading "call:...") — the arguments fallback should fail, so no call is emitted.
        # This test documents that name_marker alone is not enough when the surrounding body
        # is not JSON. Use arguments_marker or arguments_key with a JSON body.
        assert not any(b["type"] == "tool_call" for b in parser.parse(raw))


class TestArgumentsMarker:
    """``arguments_marker`` locates a fenced/wrapped arguments payload inside the body."""

    @pytest.fixture
    def parser(self):
        return ToolCallParser(ToolCallParserConfig(
            start_tag="<c>",
            end_tag="</c>",
            name_marker={ "prefix": "name=", "suffix": ";" },
            arguments_marker={ "open": "args=", "close": ";" },
        ))

    def test_both_markers(self, parser):
        raw = '<c>name=get_weather;args={"city":"Seoul"};</c>'
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
        ]

    def test_missing_marker_drops_call(self, parser):
        # The name marker isn't present; the call span becomes literal text.
        raw = '<c>args={"x":1};</c>'
        assert not any(b["type"] == "tool_call" for b in parser.parse(raw))


class TestDeepSeekV3:
    """DeepSeek V3/R1 tool_calls block. Full nested structure:

        <｜tool_calls_begin｜>
          <｜tool_call_begin｜>function<｜tool_sep｜>NAME
          ```json
          {ARGUMENTS}
          ```
          <｜tool_call_end｜>
          ... (repeat) ...
        <｜tool_calls_end｜>

    Uses batch_start_tag/batch_end_tag for the outer wrapper, start_tag/end_tag for each
    call, name_marker for the ``function<｜tool_sep｜>NAME\\n`` literal, and arguments_marker
    for the fenced JSON block.
    """

    @pytest.fixture
    def config(self):
        return ToolCallParserConfig(
            batch_start_tag="<｜tool_calls_begin｜>",
            batch_end_tag="<｜tool_calls_end｜>",
            start_tag="<｜tool_call_begin｜>",
            end_tag="<｜tool_call_end｜>",
            name_marker={ "prefix": "function<｜tool_sep｜>", "suffix": "\n" },
            arguments_marker={ "open": "```json\n", "close": "\n```" },
        )

    def test_single_call(self, config):
        parser = ToolCallParser(config)
        raw = (
            "<｜tool_calls_begin｜>"
            "<｜tool_call_begin｜>function<｜tool_sep｜>get_weather\n"
            "```json\n"
            '{"city":"Seoul"}\n'
            "```\n"
            "<｜tool_call_end｜>"
            "<｜tool_calls_end｜>"
        )
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
        ]

    def test_parallel_calls(self, config):
        parser = ToolCallParser(config)
        raw = (
            "<｜tool_calls_begin｜>"
            "<｜tool_call_begin｜>function<｜tool_sep｜>get_weather\n"
            "```json\n"
            '{"city":"Seoul"}\n'
            "```\n"
            "<｜tool_call_end｜>"
            "<｜tool_call_begin｜>function<｜tool_sep｜>get_time\n"
            "```json\n"
            '{"tz":"UTC"}\n'
            "```\n"
            "<｜tool_call_end｜>"
            "<｜tool_calls_end｜>"
        )
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Seoul" } },
            { "type": "tool_call", "name": "get_time", "arguments": { "tz": "UTC" } },
        ]

    def test_reasoning_text_before_batch_is_preserved(self, config):
        parser = ToolCallParser(config)
        raw = (
            "Let me look those up.\n"
            "<｜tool_calls_begin｜>"
            "<｜tool_call_begin｜>function<｜tool_sep｜>get_weather\n"
            "```json\n"
            '{"city":"Paris"}\n'
            "```\n"
            "<｜tool_call_end｜>"
            "<｜tool_calls_end｜>"
        )
        blocks = _strip_ids(parser.parse(raw))
        assert blocks[0] == { "type": "text", "text": "Let me look those up.\n" }
        assert blocks[1] == { "type": "tool_call", "name": "get_weather", "arguments": { "city": "Paris" } }

    def test_framing_between_calls_is_dropped(self, config):
        # Framing whitespace/newlines between inner calls must not surface as text blocks;
        # only tool_call blocks propagate from within a batch.
        parser = ToolCallParser(config)
        raw = (
            "<｜tool_calls_begin｜>"
            "<｜tool_call_begin｜>function<｜tool_sep｜>a\n```json\n{}\n```\n<｜tool_call_end｜>"
            "\n\n"  # noise between calls
            "<｜tool_call_begin｜>function<｜tool_sep｜>b\n```json\n{}\n```\n<｜tool_call_end｜>"
            "<｜tool_calls_end｜>"
        )
        blocks = _strip_ids(parser.parse(raw))
        assert all(b["type"] == "tool_call" for b in blocks)
        assert [ b["name"] for b in blocks ] == [ "a", "b" ]

    def test_unclosed_batch_returns_remainder_as_text(self, config):
        parser = ToolCallParser(config)
        raw = (
            "prefix "
            "<｜tool_calls_begin｜>"
            "<｜tool_call_begin｜>function<｜tool_sep｜>a\n```json\n{}\n```\n<｜tool_call_end｜>"
            # missing <｜tool_calls_end｜>
        )
        blocks = parser.parse(raw)
        # Nothing is silently swallowed: everything from the opening batch tag is preserved.
        assert any(b["type"] == "text" and b["text"].startswith("<｜tool_calls_begin｜>") for b in blocks)
        assert not any(b["type"] == "tool_call" for b in blocks)


class TestBatchOnlyWithoutMarkers:
    """A batch envelope can also wrap plain hermes-style call tags — markers are optional.
    This isn't a real model today but documents that batch is orthogonal to marker mode."""

    def test_hermes_wrapped_in_batch(self):
        parser = ToolCallParser(ToolCallParserConfig(
            batch_start_tag="[BATCH]",
            batch_end_tag="[/BATCH]",
            start_tag="<tool_call>",
            end_tag="</tool_call>",
        ))
        raw = (
            "[BATCH]"
            '<tool_call>{"name":"a","arguments":{}}</tool_call>'
            '<tool_call>{"name":"b","arguments":{}}</tool_call>'
            "[/BATCH]"
        )
        assert _strip_ids(parser.parse(raw)) == [
            { "type": "tool_call", "name": "a", "arguments": {} },
            { "type": "tool_call", "name": "b", "arguments": {} },
        ]
