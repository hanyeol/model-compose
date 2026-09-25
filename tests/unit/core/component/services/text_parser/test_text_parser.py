"""Tests for TextParserAction — covers JSON/YAML/code/XML/list/table/regex formats,
strategies, fallback, JSON schema validation, batch/stream input, output expression,
cancellation, and error paths."""

import asyncio

import pytest

from unittest.mock import AsyncMock, MagicMock

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.text_parser import TextParserAction
from mindor.dsl.schema.action import TextParserActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_context():
    context = MagicMock(spec=ComponentActionContext)
    context.cancellation_token = None

    async def render_variable(value, scope=None, skip_decode=False):
        return value

    async def render_text(value, collect=True):
        return value

    context.render_variable = AsyncMock(side_effect=render_variable)
    context.render_text = AsyncMock(side_effect=render_text)
    context.register_source = MagicMock()
    return context


async def _run(config: TextParserActionConfig, context):
    return await TextParserAction(config).run(context)


class TestJsonFormat:
    @pytest.mark.anyio
    async def test_plain_json_object(self, mock_context):
        result = await _run(TextParserActionConfig(
            text='{"answer": 42, "confidence": 0.9}', format="json",
        ), mock_context)
        assert result == {"answer": 42, "confidence": 0.9}

    @pytest.mark.anyio
    async def test_json_with_surrounding_prose(self, mock_context):
        text = 'Here is the answer: {"answer": 42} — hope this helps!'
        result = await _run(TextParserActionConfig(text=text, format="json"), mock_context)
        assert result == {"answer": 42}

    @pytest.mark.anyio
    async def test_json_in_code_fence(self, mock_context):
        text = 'Response:\n```json\n{"answer": 42}\n```\nDone.'
        result = await _run(TextParserActionConfig(text=text, format="json"), mock_context)
        assert result == {"answer": 42}

    @pytest.mark.anyio
    async def test_nested_json(self, mock_context):
        text = '{"a": {"b": {"c": [1, 2, 3]}}, "d": null}'
        result = await _run(TextParserActionConfig(text=text, format="json"), mock_context)
        assert result == {"a": {"b": {"c": [1, 2, 3]}}, "d": None}

    @pytest.mark.anyio
    async def test_json_array_top_level(self, mock_context):
        text = "prefix [1, 2, 3] suffix"
        result = await _run(TextParserActionConfig(text=text, format="json"), mock_context)
        assert result == [1, 2, 3]

    @pytest.mark.anyio
    async def test_json_trailing_comma_cleanup(self, mock_context):
        text = '{"a": 1, "b": 2,}'
        result = await _run(TextParserActionConfig(text=text, format="json"), mock_context)
        assert result == {"a": 1, "b": 2}

    @pytest.mark.anyio
    async def test_json_line_comment_cleanup(self, mock_context):
        text = '{"a": 1, // trailing note\n "b": 2}'
        result = await _run(TextParserActionConfig(text=text, format="json"), mock_context)
        assert result == {"a": 1, "b": 2}

    @pytest.mark.anyio
    async def test_json_block_comment_cleanup(self, mock_context):
        text = '{"a": 1, /* inline */ "b": 2}'
        result = await _run(TextParserActionConfig(text=text, format="json"), mock_context)
        assert result == {"a": 1, "b": 2}

    @pytest.mark.anyio
    async def test_json_comment_preserved_inside_string(self, mock_context):
        text = '{"note": "url is https://x.com/foo // path"}'
        result = await _run(TextParserActionConfig(text=text, format="json"), mock_context)
        assert result == {"note": "url is https://x.com/foo // path"}

    @pytest.mark.anyio
    async def test_json_braces_inside_string_literal(self, mock_context):
        text = '{"template": "hello {name}!"}'
        result = await _run(TextParserActionConfig(text=text, format="json"), mock_context)
        assert result == {"template": "hello {name}!"}

    @pytest.mark.anyio
    async def test_json_fallback_on_no_match(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="no json here", format="json", fallback={"default": True},
        ), mock_context)
        assert result == {"default": True}

    @pytest.mark.anyio
    async def test_json_fallback_none_when_absent(self, mock_context):
        result = await _run(TextParserActionConfig(text="no json here", format="json"), mock_context)
        assert result is None

    @pytest.mark.anyio
    async def test_json_dedupe_across_passes(self, mock_context):
        text = '```json\n{"answer": 42}\n```\nAlso: {"answer": 42}'
        result = await _run(TextParserActionConfig(
            text=text, format="json", strategy="all",
        ), mock_context)
        assert result == [{"answer": 42}]

    @pytest.mark.anyio
    async def test_json_multiple_distinct_candidates(self, mock_context):
        text = 'first {"x": 1} then {"y": 2}'
        result = await _run(TextParserActionConfig(
            text=text, format="json", strategy="all",
        ), mock_context)
        assert {"x": 1} in result
        assert {"y": 2} in result

    @pytest.mark.anyio
    async def test_json_schema_pass(self, mock_context):
        text = '{"answer": 42, "confidence": 0.9}'
        result = await _run(TextParserActionConfig(
            text=text, format="json",
            json_schema={
                "type": "object",
                "required": ["answer", "confidence"],
                "properties": {
                    "answer": {"type": "integer"},
                    "confidence": {"type": "number"},
                },
            },
        ), mock_context)
        assert result == {"answer": 42, "confidence": 0.9}

    @pytest.mark.anyio
    async def test_json_schema_fail_returns_fallback(self, mock_context):
        text = '{"answer": "not-an-int"}'
        result = await _run(TextParserActionConfig(
            text=text, format="json",
            json_schema={
                "type": "object",
                "required": ["answer"],
                "properties": {"answer": {"type": "integer"}},
            },
            fallback={"answer": None},
        ), mock_context)
        assert result == {"answer": None}


class TestYamlFormat:
    @pytest.mark.anyio
    async def test_yaml_in_code_fence(self, mock_context):
        text = "```yaml\nname: Alice\nage: 30\n```"
        result = await _run(TextParserActionConfig(text=text, format="yaml"), mock_context)
        assert result == {"name": "Alice", "age": 30}

    @pytest.mark.anyio
    async def test_yaml_multi_document(self, mock_context):
        text = "---\nname: Alice\n---\nname: Bob\n"
        result = await _run(TextParserActionConfig(
            text=text, format="yaml", strategy="all",
        ), mock_context)
        assert {"name": "Alice"} in result
        assert {"name": "Bob"} in result

    @pytest.mark.anyio
    async def test_yaml_scalar_excluded(self, mock_context):
        text = "```yaml\njust a string\n```"
        result = await _run(TextParserActionConfig(
            text=text, format="yaml", fallback="none",
        ), mock_context)
        assert result == "none"

    @pytest.mark.anyio
    async def test_yaml_list(self, mock_context):
        text = "```yaml\n- one\n- two\n- three\n```"
        result = await _run(TextParserActionConfig(text=text, format="yaml"), mock_context)
        assert result == ["one", "two", "three"]


class TestCodeFormat:
    @pytest.mark.anyio
    async def test_code_single_block(self, mock_context):
        text = "before\n```python\nprint('hi')\n```\nafter"
        result = await _run(TextParserActionConfig(text=text, format="code"), mock_context)
        assert "```python" in result
        assert "print('hi')" in result
        assert result.endswith("```")

    @pytest.mark.anyio
    async def test_code_multiple_languages(self, mock_context):
        text = "```python\nx=1\n```\ntext\n```sql\nSELECT 1\n```"
        result = await _run(TextParserActionConfig(
            text=text, format="code", strategy="all",
        ), mock_context)
        assert len(result) == 2
        assert any("python" in b for b in result)
        assert any("sql" in b for b in result)

    @pytest.mark.anyio
    async def test_code_empty_fence_skipped(self, mock_context):
        text = "```\n\n```\nreal:\n```py\nx=1\n```"
        result = await _run(TextParserActionConfig(
            text=text, format="code", strategy="all",
        ), mock_context)
        assert len(result) == 1


class TestXmlFormat:
    @pytest.mark.anyio
    async def test_xml_text_output(self, mock_context):
        text = "prefix <answer>42</answer> suffix"
        result = await _run(TextParserActionConfig(
            text=text, format="xml", xml_root="answer",
        ), mock_context)
        assert result == "<answer>42</answer>"

    @pytest.mark.anyio
    async def test_xml_root_filter_rejects_other_tags(self, mock_context):
        text = "<thinking>hmm</thinking><answer>42</answer>"
        result = await _run(TextParserActionConfig(
            text=text, format="xml", xml_root="answer",
        ), mock_context)
        assert result == "<answer>42</answer>"

    @pytest.mark.anyio
    async def test_xml_malformed_dropped(self, mock_context):
        text = "<a>ok</a> <b>bad</c>"
        result = await _run(TextParserActionConfig(
            text=text, format="xml", strategy="all",
        ), mock_context)
        assert result == ["<a>ok</a>"]

    @pytest.mark.anyio
    async def test_xml_dict_output_simple(self, mock_context):
        text = "<person><name>Alice</name><age>30</age></person>"
        result = await _run(TextParserActionConfig(
            text=text, format="xml", xml_root="person", xml_output="dict",
        ), mock_context)
        assert result == {"name": "Alice", "age": "30"}

    @pytest.mark.anyio
    async def test_xml_dict_output_with_attribute(self, mock_context):
        text = '<item id="42"><label>ok</label></item>'
        result = await _run(TextParserActionConfig(
            text=text, format="xml", xml_root="item", xml_output="dict",
        ), mock_context)
        assert result == {"@id": "42", "label": "ok"}

    @pytest.mark.anyio
    async def test_xml_dict_output_leaf_collapse(self, mock_context):
        text = "<answer>42</answer>"
        result = await _run(TextParserActionConfig(
            text=text, format="xml", xml_root="answer", xml_output="dict",
        ), mock_context)
        assert result == "42"

    @pytest.mark.anyio
    async def test_xml_dict_output_repeated_children_becomes_list(self, mock_context):
        text = "<list><item>a</item><item>b</item><item>c</item></list>"
        result = await _run(TextParserActionConfig(
            text=text, format="xml", xml_root="list", xml_output="dict",
        ), mock_context)
        assert result == {"item": ["a", "b", "c"]}

    @pytest.mark.anyio
    async def test_xml_dict_mixed_content_text_key(self, mock_context):
        text = '<msg lang="en">hello</msg>'
        result = await _run(TextParserActionConfig(
            text=text, format="xml", xml_root="msg", xml_output="dict",
        ), mock_context)
        assert result == {"@lang": "en", "#text": "hello"}

    @pytest.mark.anyio
    async def test_xml_inside_code_fence(self, mock_context):
        text = "```xml\n<answer>42</answer>\n```"
        result = await _run(TextParserActionConfig(
            text=text, format="xml", xml_root="answer",
        ), mock_context)
        assert result == "<answer>42</answer>"

    @pytest.mark.anyio
    async def test_xml_no_root_filter_returns_largest(self, mock_context):
        text = "<a>x</a><outer><inner>y</inner></outer>"
        result = await _run(TextParserActionConfig(text=text, format="xml"), mock_context)
        assert result == "<outer><inner>y</inner></outer>"


class TestListFormat:
    @pytest.mark.anyio
    async def test_list_default_comma(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="apple, banana, cherry", format="list",
        ), mock_context)
        assert result == ["apple", "banana", "cherry"]

    @pytest.mark.anyio
    async def test_list_custom_separator(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="a | b | c", format="list", list_separator="|",
        ), mock_context)
        assert result == ["a", "b", "c"]

    @pytest.mark.anyio
    async def test_list_empty_items_removed(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="a, , b,,c , ", format="list",
        ), mock_context)
        assert result == ["a", "b", "c"]

    @pytest.mark.anyio
    async def test_list_single_item(self, mock_context):
        result = await _run(TextParserActionConfig(text="only", format="list"), mock_context)
        assert result == ["only"]

    @pytest.mark.anyio
    async def test_list_strategy_no_effect(self, mock_context):
        for strategy in ("first", "last", "all", "largest"):
            result = await _run(TextParserActionConfig(
                text="a, b, c", format="list", strategy=strategy,
            ), mock_context)
            assert result == ["a", "b", "c"], f"strategy={strategy}"


class TestTableFormat:
    @pytest.mark.anyio
    async def test_table_csv_with_header(self, mock_context):
        text = "name,age\nAlice,30\nBob,25"
        result = await _run(TextParserActionConfig(text=text, format="table"), mock_context)
        assert result == [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]

    @pytest.mark.anyio
    async def test_table_without_header(self, mock_context):
        text = "Alice,30\nBob,25"
        result = await _run(TextParserActionConfig(
            text=text, format="table", table_header=False,
        ), mock_context)
        assert result == [["Alice", "30"], ["Bob", "25"]]

    @pytest.mark.anyio
    async def test_table_tsv(self, mock_context):
        text = "a\tb\n1\t2"
        result = await _run(TextParserActionConfig(
            text=text, format="table", table_column_separator="\t",
        ), mock_context)
        assert result == [{"a": "1", "b": "2"}]

    @pytest.mark.anyio
    async def test_table_semicolon_columns(self, mock_context):
        text = "a;b\n1;2"
        result = await _run(TextParserActionConfig(
            text=text, format="table", table_column_separator=";",
        ), mock_context)
        assert result == [{"a": "1", "b": "2"}]

    @pytest.mark.anyio
    async def test_table_quoted_cell_with_comma(self, mock_context):
        text = 'greeting,who\n"hello, world",Alice'
        result = await _run(TextParserActionConfig(text=text, format="table"), mock_context)
        assert result == [{"greeting": "hello, world", "who": "Alice"}]

    @pytest.mark.anyio
    async def test_table_custom_row_separator(self, mock_context):
        text = "a,b|1,2|3,4"
        result = await _run(TextParserActionConfig(
            text=text, format="table", table_row_separator="|",
        ), mock_context)
        assert result == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]

    @pytest.mark.anyio
    async def test_table_empty_input(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="", format="table", fallback=[],
        ), mock_context)
        assert result == []


class TestRegexFormat:
    @pytest.mark.anyio
    async def test_regex_named_groups_dict(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="온도는 23.5도 습도 67%",
            format="regex",
            regex_pattern=r"온도는 (?P<t>[\d.]+)도 습도 (?P<h>\d+)%",
            strategy="first",
        ), mock_context)
        assert result == {"t": "23.5", "h": "67"}

    @pytest.mark.anyio
    async def test_regex_unnamed_groups_list(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="a=1 b=2",
            format="regex",
            regex_pattern=r"(\w+)=(\d+)",
            strategy="all",
        ), mock_context)
        assert result == [["a", "1"], ["b", "2"]]

    @pytest.mark.anyio
    async def test_regex_no_groups_full_match(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="foo bar foo baz",
            format="regex",
            regex_pattern=r"foo",
            strategy="all",
        ), mock_context)
        assert result == ["foo", "foo"]

    @pytest.mark.anyio
    async def test_regex_flags_ignorecase(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="Foo bar FOO",
            format="regex",
            regex_pattern=r"foo",
            regex_flags="i",
            strategy="all",
        ), mock_context)
        assert result == ["Foo", "FOO"]

    @pytest.mark.anyio
    async def test_regex_flags_dotall(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="line1\nline2",
            format="regex",
            regex_pattern=r"line1.line2",
            regex_flags="s",
            strategy="first",
        ), mock_context)
        assert result == "line1\nline2"

    @pytest.mark.anyio
    async def test_regex_flags_multiline(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="first\nsecond\nthird",
            format="regex",
            regex_pattern=r"^\w+$",
            regex_flags="m",
            strategy="all",
        ), mock_context)
        assert result == ["first", "second", "third"]

    @pytest.mark.anyio
    async def test_regex_combined_flags(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="Foo\nBAR",
            format="regex",
            regex_pattern=r"^foo.bar$",
            regex_flags="ism",
            strategy="first",
        ), mock_context)
        assert result == "Foo\nBAR"

    @pytest.mark.anyio
    async def test_regex_invalid_flag_raises(self, mock_context):
        with pytest.raises(ValueError, match="Unsupported regex flag"):
            await _run(TextParserActionConfig(
                text="x",
                format="regex",
                regex_pattern=r"x",
                regex_flags="z",
            ), mock_context)

    @pytest.mark.anyio
    async def test_regex_pattern_required(self, mock_context):
        with pytest.raises(ValueError, match="regex_pattern"):
            await _run(TextParserActionConfig(
                text="x", format="regex",
            ), mock_context)

    @pytest.mark.anyio
    async def test_regex_no_match_fallback(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="nothing here",
            format="regex",
            regex_pattern=r"\d+",
            fallback="MISS",
        ), mock_context)
        assert result == "MISS"


class TestStrategies:
    @pytest.fixture
    def multi_json_text(self):
        return 'small: {"a": 1} — big: {"answer": 42, "extra": "long data here"}'

    @pytest.mark.anyio
    async def test_strategy_first(self, mock_context, multi_json_text):
        result = await _run(TextParserActionConfig(
            text=multi_json_text, format="json", strategy="first",
        ), mock_context)
        assert result == {"a": 1}

    @pytest.mark.anyio
    async def test_strategy_last(self, mock_context, multi_json_text):
        result = await _run(TextParserActionConfig(
            text=multi_json_text, format="json", strategy="last",
        ), mock_context)
        assert result == {"answer": 42, "extra": "long data here"}

    @pytest.mark.anyio
    async def test_strategy_all(self, mock_context, multi_json_text):
        result = await _run(TextParserActionConfig(
            text=multi_json_text, format="json", strategy="all",
        ), mock_context)
        assert isinstance(result, list)
        assert {"a": 1} in result
        assert {"answer": 42, "extra": "long data here"} in result

    @pytest.mark.anyio
    async def test_strategy_largest_default(self, mock_context, multi_json_text):
        result = await _run(TextParserActionConfig(
            text=multi_json_text, format="json",
        ), mock_context)
        assert result == {"answer": 42, "extra": "long data here"}


class TestFallback:
    @pytest.mark.anyio
    async def test_fallback_none_default(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="no candidates", format="json",
        ), mock_context)
        assert result is None

    @pytest.mark.anyio
    async def test_fallback_dict_value(self, mock_context):
        result = await _run(TextParserActionConfig(
            text="no candidates", format="json", fallback={"ok": False},
        ), mock_context)
        assert result == {"ok": False}

    @pytest.mark.anyio
    async def test_fallback_returned_when_schema_fails(self, mock_context):
        result = await _run(TextParserActionConfig(
            text='{"answer": "wrong"}',
            format="json",
            json_schema={"type": "object", "properties": {"answer": {"type": "integer"}}, "required": ["answer"]},
            fallback={"answer": 0},
        ), mock_context)
        assert result == {"answer": 0}


class TestInputShapes:
    @pytest.mark.anyio
    async def test_list_input_produces_list_result(self, mock_context):
        texts = ['{"a": 1}', '{"b": 2}', "no json"]
        result = await _run(TextParserActionConfig(text=texts, format="json"), mock_context)
        assert result == [{"a": 1}, {"b": 2}, None]

    @pytest.mark.anyio
    async def test_list_input_with_fallback(self, mock_context):
        texts = ['{"a": 1}', "no json"]
        result = await _run(TextParserActionConfig(
            text=texts, format="json", fallback={"miss": True},
        ), mock_context)
        assert result == [{"a": 1}, {"miss": True}]

    @pytest.mark.anyio
    async def test_async_iterator_input(self, mock_context):
        async def gen():
            for chunk in ['{"a": 1}', '{"b": 2}']:
                yield chunk

        # `text` gets rendered via context.render_text — override so the async
        # generator flows through instead of being validated as List[str].
        async def render_text(value, collect=True):
            return gen()

        mock_context.render_text = AsyncMock(side_effect=render_text)

        collected = []
        stream_result = await _run(
            TextParserActionConfig(text="${input.stream}", format="json"),
            mock_context,
        )
        async for item in stream_result:
            collected.append(item)
        assert collected == [{"a": 1}, {"b": 2}]

    @pytest.mark.anyio
    async def test_batch_size_grouping(self, mock_context):
        texts = ['{"i": 0}', '{"i": 1}', '{"i": 2}', '{"i": 3}']
        result = await _run(TextParserActionConfig(
            text=texts, format="json", batch_size=2,
        ), mock_context)
        assert result == [{"i": 0}, {"i": 1}, {"i": 2}, {"i": 3}]


class TestOutputExpression:
    @pytest.mark.anyio
    async def test_output_field_projection(self, mock_context):
        # Simulate the ${result.answer} projection by making render_variable
        # actually resolve on the registered scope.
        registered = {}

        def register_source(key, value, scope=None):
            registered[(scope, key)] = value

        async def render_variable(value, scope=None, skip_decode=False):
            if value == "${result.answer}":
                # emulate variable renderer's dot access on the "result" source
                base = registered.get((scope, "result"))
                if isinstance(base, dict):
                    return base.get("answer")
            return value

        mock_context.register_source = MagicMock(side_effect=register_source)
        mock_context.render_variable = AsyncMock(side_effect=render_variable)

        result = await _run(TextParserActionConfig(
            text='{"answer": 42}', format="json", output="${result.answer}",
        ), mock_context)
        assert result == 42

    @pytest.mark.anyio
    async def test_output_direct_result_short_circuit(self, mock_context):
        # ${result} means "return as-is" and shouldn't trigger extra render_variable.
        result = await _run(TextParserActionConfig(
            text='{"a": 1}', format="json", output="${result}",
        ), mock_context)
        assert result == {"a": 1}


class TestSourceRegistration:
    @pytest.mark.anyio
    async def test_register_source_called_for_single_input(self, mock_context):
        await _run(TextParserActionConfig(text='{"x": 1}', format="json"), mock_context)
        keys = [c.args[0] for c in mock_context.register_source.call_args_list]
        assert "result" in keys

    @pytest.mark.anyio
    async def test_register_source_called_per_stream_item(self, mock_context):
        async def gen():
            for c in ['{"i": 0}', '{"i": 1}']:
                yield c

        async def render_text(value, collect=True):
            return gen()

        mock_context.render_text = AsyncMock(side_effect=render_text)

        stream_result = await _run(
            TextParserActionConfig(text="${input.stream}", format="json"),
            mock_context,
        )
        async for _ in stream_result:
            pass
        # One register_source per streamed result.
        assert mock_context.register_source.call_count == 2


class TestErrorPaths:
    @pytest.mark.anyio
    async def test_unsupported_format_raises(self, mock_context):
        with pytest.raises(ValueError, match="Unsupported format"):
            await _run(TextParserActionConfig(text="x", format="unknown"), mock_context)

    @pytest.mark.anyio
    async def test_unsupported_strategy_raises(self, mock_context):
        with pytest.raises(ValueError, match="Unsupported strategy"):
            await _run(TextParserActionConfig(
                text="x", format="json", strategy="random",
            ), mock_context)

    @pytest.mark.anyio
    async def test_unsupported_xml_output_raises(self, mock_context):
        with pytest.raises(ValueError, match="Unsupported xml_output"):
            await _run(TextParserActionConfig(
                text="x", format="xml", xml_output="tree",
            ), mock_context)

    @pytest.mark.anyio
    async def test_rendered_none_returns_none(self, mock_context):
        # If render_text yields None (e.g. ${input.missing}), the parser skips.
        async def render_text(value, collect=True):
            return None

        mock_context.render_text = AsyncMock(side_effect=render_text)

        result = await _run(
            TextParserActionConfig(text="${input.missing}", format="json"),
            mock_context,
        )
        assert result is None

    @pytest.mark.anyio
    async def test_rendered_non_string_is_stringified(self, mock_context):
        # If render_text returns a non-string per-item (dict), the action
        # coerces to str, which won't parse as JSON — fallback wins.
        async def render_text(value, collect=True):
            return [{"a": 1}]

        mock_context.render_text = AsyncMock(side_effect=render_text)

        result = await _run(
            TextParserActionConfig(text="${input.items}", format="json", fallback="COERCED"),
            mock_context,
        )
        assert result == ["COERCED"]


class TestCancellationPropagation:
    @pytest.mark.anyio
    async def test_cancellation_token_forwarded_to_process_batch(self, mock_context):
        from mindor.core.foundation.cancellation import CancellationToken

        token = CancellationToken()
        mock_context.cancellation_token = token

        captured = {}
        real_process_batch = TextParserAction._process_batch

        async def spy(self, texts, params, cancellation_token=None):
            captured["token"] = cancellation_token
            return await real_process_batch(self, texts, params, cancellation_token)

        original = TextParserAction._process_batch
        TextParserAction._process_batch = spy  # type: ignore
        try:
            await _run(TextParserActionConfig(text='{"a": 1}', format="json"), mock_context)
        finally:
            TextParserAction._process_batch = original  # type: ignore

        assert captured["token"] is token


class TestVariableInterpolationRendering:
    @pytest.mark.anyio
    async def test_render_variable_used_for_config_fields(self, mock_context):
        # Confirm that render_variable is invoked at least for `format`, `strategy`
        # and other resolved fields — proves the string-templating hook stays wired.
        await _run(TextParserActionConfig(text='{"a":1}', format="json"), mock_context)
        rendered = [c.args[0] for c in mock_context.render_variable.call_args_list]
        # `format` and `strategy` should have been passed through render_variable
        # (their default enum values), plus batch_size (None) etc.
        assert any(v == "json" for v in rendered)
        assert any(v == "largest" for v in rendered)
