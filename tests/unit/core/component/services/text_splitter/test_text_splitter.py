"""Tests for the TextSplitterAction, covering basic splitting, separators, chunk sizes,
overlap, edge cases, real-world scenarios, and comprehensive pre-generated test cases."""

import json
import asyncio
import os

import pytest

from unittest.mock import AsyncMock, MagicMock

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.text_splitter import TextSplitterAction
from mindor.dsl.schema.action import TextSplitterActionConfig


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


@pytest.fixture
def mock_context():
    """Create a mock ComponentActionContext for testing."""
    context = MagicMock(spec=ComponentActionContext)
    context.cancellation_token = None
    # Make render_variable return the value as-is by default
    async def render_variable(value, scope=None, skip_decode=False):
        return value
    async def render_text(value):
        return value
    context.render_variable = AsyncMock(side_effect=render_variable)
    context.render_text = AsyncMock(side_effect=render_text)
    context.register_source = MagicMock()
    return context


@pytest.fixture
def test_cases():
    """Load pre-generated test cases."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    results_file = os.path.join(current_dir, "cases.json")

    if not os.path.exists(results_file):
        pytest.skip(f"Test cases file not found: {results_file}")

    with open(results_file, "r", encoding="utf-8") as f:
        return json.load(f)


class TestTextSplitterBasicFunctionality:
    """Test basic text splitting functionality."""

    @pytest.mark.anyio
    async def test_short_text_no_split(self, mock_context):
        """Test that text shorter than chunk_size is not split."""
        config = TextSplitterActionConfig(
            text="Short text",
            chunk_size=100,
            chunk_overlap=0
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) == 1
        assert result[0] == "Short text"

    @pytest.mark.anyio
    async def test_simple_paragraph_split(self, mock_context):
        """Test splitting a simple multi-paragraph text."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        config = TextSplitterActionConfig(
            text=text,
            chunk_size=20,
            chunk_overlap=0
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= 25  # Allow some flexibility

    @pytest.mark.anyio
    async def test_newline_separator(self, mock_context):
        """Test splitting with newline separator."""
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        config = TextSplitterActionConfig(
            text=text,
            separators=["\n"],
            chunk_size=15,
            chunk_overlap=0
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) > 0


class TestTextSplitterSeparators:
    """Test different separator configurations."""

    @pytest.mark.anyio
    async def test_custom_single_separator(self, mock_context):
        """Test with a custom single separator."""
        text = "chunk1|chunk2|chunk3|chunk4"
        config = TextSplitterActionConfig(
            text=text,
            separators=["|"],
            chunk_size=10,
            chunk_overlap=0,
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) > 0

    @pytest.mark.anyio
    async def test_empty_separator_character_split(self, mock_context):
        """Test character-level splitting with empty separator."""
        text = "abcdefghijklmnop"
        config = TextSplitterActionConfig(
            text=text,
            separators=[""],
            chunk_size=5,
            chunk_overlap=0
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) == 4
        assert result[0] == "abcde"
        assert result[1] == "fghij"
        assert result[2] == "klmno"
        assert result[3] == "p"

    @pytest.mark.anyio
    async def test_default_separators(self, mock_context):
        """Test with default separators."""
        text = "Paragraph 1\n\nParagraph 2\nLine break\nAnother line"
        config = TextSplitterActionConfig(
            text=text,
            chunk_size=20,
            chunk_overlap=0,
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) > 0


class TestTextSplitterChunkSize:
    """Test different chunk size configurations."""

    @pytest.mark.anyio
    async def test_very_small_chunk_size(self, mock_context):
        """Test with very small chunk size."""
        text = "This is a test"
        config = TextSplitterActionConfig(
            text=text,
            chunk_size=5,
            chunk_overlap=0,
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) > 1

    @pytest.mark.anyio
    async def test_large_chunk_size(self, mock_context):
        """Test with large chunk size."""
        text = "Short text"
        config = TextSplitterActionConfig(
            text=text,
            chunk_size=10000,
            chunk_overlap=0
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) == 1
        assert result[0] == text

    @pytest.mark.anyio
    async def test_chunk_size_equal_to_text_length(self, mock_context):
        """Test when chunk_size equals text length."""
        text = "Exact size"
        config = TextSplitterActionConfig(
            text=text,
            chunk_size=len(text),
            chunk_overlap=0
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) == 1
        assert result[0] == text


class TestTextSplitterOverlap:
    """Test chunk overlap functionality."""

    @pytest.mark.anyio
    async def test_basic_overlap(self, mock_context):
        """Test basic overlap between chunks."""
        text = "AAAAA\n\nBBBBB\n\nCCCCC"
        config = TextSplitterActionConfig(
            text=text,
            separators=["\n\n"],
            chunk_size=10,
            chunk_overlap=3,
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) >= 1

    @pytest.mark.anyio
    async def test_zero_overlap(self, mock_context):
        """Test with zero overlap."""
        text = "Part1\n\nPart2\n\nPart3"
        config = TextSplitterActionConfig(
            text=text,
            separators=["\n\n"],
            chunk_size=10,
            chunk_overlap=0,
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) > 0

    @pytest.mark.anyio
    async def test_overlap_with_single_chunk(self, mock_context):
        """Test overlap when only one chunk is created."""
        text = "Short"
        config = TextSplitterActionConfig(
            text=text,
            chunk_size=100,
            chunk_overlap=10
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) == 1
        assert result[0] == text


class TestTextSplitterEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.anyio
    async def test_empty_text(self, mock_context):
        """Test with empty text."""
        config = TextSplitterActionConfig(
            text="",
            chunk_size=100,
            chunk_overlap=0
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) == 0

    @pytest.mark.anyio
    async def test_whitespace_only_text(self, mock_context):
        """Test with whitespace-only text."""
        text = "   \n\n   \n   "
        config = TextSplitterActionConfig(
            text=text,
            chunk_size=10,
            chunk_overlap=0
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) == 0

    @pytest.mark.anyio
    async def test_unicode_text(self, mock_context):
        """Test with Unicode characters."""
        text = "Hello 世界\n\nこんにちは\n\n안녕하세요"
        config = TextSplitterActionConfig(
            text=text,
            separators=["\n\n"],
            chunk_size=15,
            chunk_overlap=0,
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) > 0


class TestTextSplitterRealWorldScenarios:
    """Test real-world text splitting scenarios."""

    @pytest.mark.anyio
    async def test_markdown_document(self, mock_context):
        """Test splitting a markdown document."""
        text = """# Title

## Section 1

This is paragraph 1 with some text.

This is paragraph 2 with more text.

## Section 2

Another section with content."""

        config = TextSplitterActionConfig(
            text=text,
            separators=["\n\n", "\n", " "],
            chunk_size=50,
            chunk_overlap=10,
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) > 0

    @pytest.mark.anyio
    async def test_long_continuous_text(self, mock_context):
        """Test splitting long text without natural breaks."""
        text = "a" * 1000
        config = TextSplitterActionConfig(
            text=text,
            chunk_size=100,
            chunk_overlap=10,
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert len(result) > 1


class TestComprehensiveCases:
    """Comprehensive test cases for TextSplitter."""

    @pytest.mark.anyio
    async def test_basic_paragraph_split(self, mock_context, test_cases):
        """Test basic paragraph splitting."""
        test_case = next(tc for tc in test_cases["test_cases"] if tc["name"] == "basic_paragraph_split")

        config = TextSplitterActionConfig(
            text=test_case["input"]["text"],
            separators=test_case["input"]["separators"],
            chunk_size=test_case["input"]["chunk_size"],
            chunk_overlap=test_case["input"]["chunk_overlap"],
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        expected = test_case["expected_output"]
        assert len(result) == len(expected)

    @pytest.mark.anyio
    async def test_short_text_no_split(self, mock_context, test_cases):
        """Test short text that doesn't need splitting."""
        test_case = next(tc for tc in test_cases["test_cases"] if tc["name"] == "short_text_no_split")

        config = TextSplitterActionConfig(
            text=test_case["input"]["text"],
            separators=test_case["input"]["separators"],
            chunk_size=test_case["input"]["chunk_size"],
            chunk_overlap=test_case["input"]["chunk_overlap"],
        )
        action = TextSplitterAction(config)
        result = await action.run(mock_context, asyncio.get_running_loop())

        expected = test_case["expected_output"]
        assert result == expected

    @pytest.mark.anyio
    async def test_all_comprehensive_cases(self, mock_context, test_cases):
        """Test all comprehensive test cases."""
        failures = []

        for test_case in test_cases["test_cases"]:
            config = TextSplitterActionConfig(
                text=test_case["input"]["text"],
                separators=test_case["input"]["separators"],
                chunk_size=test_case["input"]["chunk_size"],
                chunk_overlap=test_case["input"]["chunk_overlap"],
            )
            action = TextSplitterAction(config)
            result = await action.run(mock_context, asyncio.get_running_loop())

            expected = test_case["expected_output"]

            # Special case for empty text
            if test_case["name"] == "empty_text":
                if len(result) > 1 or (len(result) == 1 and result[0] != ""):
                    failures.append(f"{test_case['name']}: Empty text handling differs")
                continue

            # Check number of chunks
            if len(result) != len(expected):
                failures.append(
                    f"{test_case['name']}: Chunk count mismatch - "
                    f"expected {len(expected)}, got {len(result)}"
                )
                continue

            # Check each chunk matches
            for i, (actual_chunk, expected_chunk) in enumerate(zip(result, expected)):
                if actual_chunk != expected_chunk:
                    failures.append(
                        f"{test_case['name']}: Chunk {i} mismatch\n"
                        f"  Expected: {repr(expected_chunk)}\n"
                        f"  Actual: {repr(actual_chunk)}"
                    )

        if failures:
            failure_msg = "\n\n".join(failures)
            pytest.fail(f"The following test cases failed:\n\n{failure_msg}")


def _stream_texts(texts):
    """Async iterator that yields a sequence of separate input texts."""
    async def _iter():
        for text in texts:
            yield text
    return _iter()


async def _collect(stream):
    return [ item async for item in stream ]


class TestTextSplitterStreamingInput:
    """AsyncIterator[str] input is treated as a stream of SEPARATE texts.

    Under the new model the outer container preserves the input's stream shape, and
    the inner shape is decided by the explicit `streaming` option:
      - AsyncIterator[T] + streaming=true  → AsyncIterator[StreamChunkIterator]
      - AsyncIterator[T] + streaming=false → AsyncIterator[List[str]]
    """

    @pytest.mark.anyio
    async def test_streaming_input_yields_one_inner_stream_per_text(self, mock_context, test_cases):
        # Take a few cases and feed them as a streamed sequence.
        cases = test_cases["test_cases"][:4]
        texts = [ case["input"]["text"] for case in cases ]
        # Use shared config from the first case for simplicity.
        common_kwargs = dict(
            separators=cases[0]["input"]["separators"],
            chunk_size=cases[0]["input"]["chunk_size"],
            chunk_overlap=cases[0]["input"]["chunk_overlap"],
        )

        # Batch reference: same texts as a list. Returns List[List[str]] (chunks per text).
        batch_config = TextSplitterActionConfig(text=texts, **common_kwargs)
        batch_action = TextSplitterAction(batch_config)
        batch_result = await batch_action.run(mock_context, asyncio.get_running_loop())

        # Stream input + streaming=true: outer is an async iterator; each item is itself
        # an async iterator of chunks.
        stream_config = TextSplitterActionConfig(text="UNUSED", streaming=True, **common_kwargs)
        stream_action = TextSplitterAction(stream_config)

        stream_mock = MagicMock(spec=ComponentActionContext)
        stream_mock.cancellation_token = None
        async def render_variable(value, scope=None, skip_decode=False):
            if value == "UNUSED":
                return _stream_texts(texts)
            return value
        async def render_text(value):
            return await render_variable(value)
        stream_mock.render_variable = AsyncMock(side_effect=render_variable)
        stream_mock.render_text = AsyncMock(side_effect=render_text)
        stream_mock.register_source = MagicMock()

        stream_result = await stream_action.run(stream_mock, asyncio.get_running_loop())
        stream_collected = []
        async for inner in stream_result:
            stream_collected.append(await _collect(inner))

        assert stream_collected == batch_result


# ---------------------------------------------------------------------------
# Language presets — verify that `language` selects a preset separator list,
# `language` and `separators` are mutually exclusive at the schema layer, and
# every enum value is covered.
# ---------------------------------------------------------------------------

from mindor.dsl.schema.action import TextSplitterLanguage
from mindor.core.component.services.text_splitter.separators import (
    DEFAULT_SEPARATORS,
    LANGUAGE_SEPARATORS,
    from_language,
)


class TestLanguagePresets:
    """Language-preset resolution and end-to-end splitting behavior."""

    def test_every_enum_value_has_preset(self):
        # If a new enum value is added without a preset entry, this fails fast.
        missing = [ language.value for language in TextSplitterLanguage if language not in LANGUAGE_SEPARATORS ]
        assert missing == []

    def test_default_separators_constant(self):
        assert DEFAULT_SEPARATORS == [ "\n\n", "\n", " ", "" ]

    def test_language_selects_preset(self):
        result = from_language(TextSplitterLanguage.PYTHON)
        assert result[:3] == [ "\nclass ", "\ndef ", "\n\tdef " ]

    def test_preset_returns_fresh_copy(self):
        # Callers may mutate the returned list; the module-level table must stay clean.
        first = from_language(TextSplitterLanguage.PYTHON)
        first.append("MUTATED")
        second = from_language(TextSplitterLanguage.PYTHON)
        assert "MUTATED" not in second

    @pytest.mark.anyio
    async def test_python_preset_splits_on_class_boundary(self, mock_context):
        """Python preset should prefer `class`/`def` boundaries over paragraph breaks."""
        code = "\n".join([
            "class Foo:",
            "    def method_a(self):",
            "        return 1",
            "",
            "class Bar:",
            "    def method_b(self):",
            "        return 2",
        ])
        config = TextSplitterActionConfig(
            text=code,
            language=TextSplitterLanguage.PYTHON,
            chunk_size=60,
            chunk_overlap=0,
        )
        result = await TextSplitterAction(config).run(mock_context, asyncio.get_running_loop())

        # Both `class Foo:` and `class Bar:` should each start their own chunk.
        starts = [ chunk.lstrip("\n").splitlines()[0] for chunk in result ]
        assert any(line.startswith("class Foo") for line in starts)
        assert any(line.startswith("class Bar") for line in starts)

    @pytest.mark.anyio
    async def test_markdown_preset_splits_on_heading(self, mock_context):
        md = "\n".join([
            "# Title",
            "Intro paragraph.",
            "",
            "## Section A",
            "Content of section A goes here.",
            "",
            "## Section B",
            "Content of section B goes here.",
        ])
        config = TextSplitterActionConfig(
            text=md,
            language=TextSplitterLanguage.MARKDOWN,
            chunk_size=60,
            chunk_overlap=0,
        )
        result = await TextSplitterAction(config).run(mock_context, asyncio.get_running_loop())

        joined = " || ".join(result)
        # `## Section A` and `## Section B` should each begin a new chunk.
        assert "## Section A" in joined
        assert "## Section B" in joined

    def test_language_and_separators_are_mutually_exclusive(self):
        """DSL validation rejects configs that specify both."""
        with pytest.raises(ValueError, match="language.*separators|separators.*language"):
            TextSplitterActionConfig(
                text="hello world",
                language=TextSplitterLanguage.PYTHON,
                separators=[ " ", "" ],
                chunk_size=6,
                chunk_overlap=0,
            )


# ---------------------------------------------------------------------------
# Per-language preset splitting — for every language enum value, verify that
# splitting real code/markup keeps expected syntactic boundaries as chunk
# starts. Each case supplies:
#   - a representative source snippet with several top-level declarations,
#   - a list of substrings that MUST each begin one of the emitted chunks
#     (i.e. the preset's high-priority separators actually take effect).
# `chunk_size` is picked small enough to force a split but large enough that
# each declaration body stays intact within its own chunk.
# ---------------------------------------------------------------------------

def _chunk_starts(chunks):
    """Return the first non-empty line of each chunk (after stripping any
    leading separator characters the splitter kept around)."""
    starts = []
    for chunk in chunks:
        for line in chunk.splitlines():
            stripped = line.strip()
            if stripped:
                starts.append(stripped)
                break
        else:
            starts.append("")
    return starts


def _make_language_source(units):
    """Join a list of self-contained top-level units with blank lines."""
    return "\n\n".join(units)


LANGUAGE_SPLIT_CASES = [
    # (language, source, expected chunk-start substrings, chunk_size)
    #
    # chunk_size is tuned per case so each top-level declaration is small
    # enough to become its own chunk (the splitter merges consecutive
    # separator-delimited segments until they exceed chunk_size). Sources are
    # sized so at least two chunks fall out, which the sanity check enforces.
    (
        TextSplitterLanguage.PYTHON,
        _make_language_source([
            "class Foo:\n    def method_a(self):\n        return 1",
            "class Bar:\n    def method_b(self):\n        return 2",
            "def top_level():\n    return 3",
        ]),
        [ "class Foo:", "class Bar:", "def top_level():" ],
        60,
    ),
    (
        TextSplitterLanguage.JAVASCRIPT,
        _make_language_source([
            "function greet(name) { return `hi ${name}`; }",
            "const answer = 42;",
            "class Widget { constructor() { this.value = 0; } }",
        ]),
        [ "function greet(name) {", "const answer = 42;", "class Widget {" ],
        60,
    ),
    (
        TextSplitterLanguage.TYPESCRIPT,
        _make_language_source([
            "interface User { name: string; age: number; }",
            "type Callback = (u: User) => void;",
            "enum Status { Active, Inactive }",
            "class Session { constructor(public user: User) {} }",
        ]),
        [ "interface User {", "type Callback", "enum Status {", "class Session {" ],
        60,
    ),
    (
        TextSplitterLanguage.JAVA,
        _make_language_source([
            "class Foo { public int compute() { return 1; } }",
            "class Bar { private String name; public String name() { return name; } }",
            "public class Baz { }",
        ]),
        [ "class Foo {", "class Bar {", "public class Baz {" ],
        80,
    ),
    (
        TextSplitterLanguage.KOTLIN,
        _make_language_source([
            "class Point(val x: Int, val y: Int)",
            "object Origin { val point = Point(0, 0) }",
            "interface Drawable { fun draw() }",
            "fun main() { println(\"hi\") }",
        ]),
        [ "class Point(val x: Int, val y: Int)", "object Origin {", "interface Drawable {", "fun main() {" ],
        50,
    ),
    (
        TextSplitterLanguage.SCALA,
        _make_language_source([
            "class Foo(val n: Int)",
            "object Bar { def make(): Foo = new Foo(1) }",
            "trait Named { def name: String }",
            "def top(): Int = 42",
        ]),
        [ "class Foo(val n: Int)", "object Bar {", "trait Named {", "def top(): Int = 42" ],
        50,
    ),
    (
        TextSplitterLanguage.GO,
        _make_language_source([
            "func Hello() string { return \"hello\" }",
            "type Point struct { X, Y int }",
            "const Version = \"1.0\"",
        ]),
        [ "func Hello() string {", "type Point struct {", "const Version = \"1.0\"" ],
        50,
    ),
    (
        TextSplitterLanguage.RUST,
        _make_language_source([
            "struct Point { x: i32, y: i32 }",
            "enum Shape { Circle, Square }",
            "trait Draw { fn draw(&self); }",
            "impl Draw for Point { fn draw(&self) {} }",
            "fn main() { println!(\"hi\"); }",
        ]),
        [ "struct Point {", "enum Shape {", "trait Draw {", "impl Draw for Point {", "fn main() {" ],
        50,
    ),
    (
        TextSplitterLanguage.CPP,
        _make_language_source([
            "class Foo { public: int compute() { return 1; } };",
            "void greet() { std::cout << \"hello\"; }",
            "int main() { return compute() + 0; }",
        ]),
        [ "class Foo {", "void greet() {", "int main() {" ],
        45,
    ),
    (
        TextSplitterLanguage.C,
        _make_language_source([
            "struct Point { int x; int y; };",
            "void greet(void) { printf(\"hi\"); }",
            "int main(void) { return 0; }",
        ]),
        [ "struct Point {", "void greet(void) {", "int main(void) {" ],
        50,
    ),
    (
        TextSplitterLanguage.CSHARP,
        _make_language_source([
            "namespace App { class Foo { } }",
            "public class Bar { public int N { get; set; } }",
            "private class Baz { }",
        ]),
        [ "namespace App {", "public class Bar {", "private class Baz {" ],
        60,
    ),
    (
        TextSplitterLanguage.RUBY,
        _make_language_source([
            "class Foo\n  def bar\n    42\n  end\nend",
            "module Baz\n  def self.qux; end\nend",
            "def top\n  1\nend",
        ]),
        [ "class Foo", "module Baz", "def top" ],
        40,
    ),
    (
        TextSplitterLanguage.PHP,
        _make_language_source([
            "function greet($name) { return \"hi \" . $name; }",
            "class User { public $name; }",
            "function farewell($name) { return \"bye \" . $name; }",
        ]),
        [ "function greet($name) {", "class User {", "function farewell($name) {" ],
        60,
    ),
    (
        TextSplitterLanguage.SWIFT,
        _make_language_source([
            "struct Point { let x: Int; let y: Int }",
            "class Foo { func hi() { print(\"hi\") } }",
            "protocol Draw { func draw() }",
            "extension Point: Draw { func draw() {} }",
            "func top() { print(\"ok\") }",
        ]),
        [ "struct Point {", "class Foo {", "protocol Draw {", "extension Point: Draw {", "func top() {" ],
        50,
    ),
    (
        TextSplitterLanguage.HTML,
        (
            "<body>"
            "<div class=\"a\"><p>alpha paragraph text goes here</p></div>"
            "<div class=\"b\"><p>beta paragraph text goes here</p></div>"
            "<table><tr><td>cell text goes here</td></tr></table>"
            "</body>"
        ),
        [ "<body>", "<div class=\"a\">", "<div class=\"b\">", "<table>" ],
        60,
    ),
    (
        TextSplitterLanguage.MARKDOWN,
        _make_language_source([
            "## Section A\nContent of section A goes here.",
            "## Section B\nContent of section B goes here.",
            "### Section B.1\nNested detail lives inside B.",
        ]),
        [ "## Section A", "## Section B", "### Section B.1" ],
        50,
    ),
    (
        TextSplitterLanguage.LATEX,
        _make_language_source([
            "\\section{Intro}\nSome intro text goes here.",
            "\\subsection{Details}\nMore detailed text for the subsection.",
            "\\subsection{Wrap-up}\nClosing remarks for the section.",
        ]),
        [ "\\section{Intro}", "\\subsection{Details}", "\\subsection{Wrap-up}" ],
        60,
    ),
    (
        TextSplitterLanguage.SQL,
        _make_language_source([
            "SELECT id, name FROM users WHERE active = 1;",
            "INSERT INTO logs(event) VALUES ('login');",
            "UPDATE users SET last_login = NOW() WHERE id = 1;",
            "DELETE FROM sessions WHERE expired = 1;",
        ]),
        [ "SELECT id, name FROM users", "INSERT INTO logs(event)", "UPDATE users SET", "DELETE FROM sessions" ],
        50,
    ),
    (
        TextSplitterLanguage.SOLIDITY,
        _make_language_source([
            "pragma solidity ^0.8.0;",
            "contract Coin { address public minter; }",
            "interface IERC20 { function balanceOf(address) external view returns (uint256); }",
            "library Math { function add(uint a, uint b) internal pure returns (uint) { return a + b; } }",
        ]),
        [ "pragma solidity ^0.8.0;", "contract Coin {", "interface IERC20 {", "library Math {" ],
        90,
    ),
    (
        TextSplitterLanguage.PROTO,
        _make_language_source([
            "syntax = \"proto3\";",
            "message User { string name = 1; int32 age = 2; }",
            "service UserSvc { rpc Get (User) returns (User); }",
            "enum Status { ACTIVE = 0; INACTIVE = 1; }",
        ]),
        [ "syntax = \"proto3\";", "message User {", "service UserSvc {", "enum Status {" ],
        60,
    ),
]


class TestPerLanguagePresets:
    """Every language preset must actually cut on its language-specific boundaries."""

    def test_all_enum_values_covered(self):
        # Guard: adding a new enum value must also add a case here.
        covered = { case[0] for case in LANGUAGE_SPLIT_CASES }
        missing = [ language.value for language in TextSplitterLanguage if language not in covered ]
        assert missing == [], f"Missing per-language split cases for: {missing}"

    @pytest.mark.parametrize("language,source,expected_starts,chunk_size", LANGUAGE_SPLIT_CASES, ids=lambda p: p.value if isinstance(p, TextSplitterLanguage) else None)
    @pytest.mark.anyio
    async def test_language_preset_cuts_on_syntactic_boundary(self, mock_context, language, source, expected_starts, chunk_size):
        config = TextSplitterActionConfig(
            text=source,
            language=language,
            chunk_size=chunk_size,
            chunk_overlap=0,
        )
        chunks = await TextSplitterAction(config).run(mock_context, asyncio.get_running_loop())

        # Sanity: chunk_size is tuned so splitting produces at least one chunk
        # per expected boundary (i.e. more than one chunk overall).
        assert len(chunks) > 1, f"{language.value}: expected multiple chunks, got {len(chunks)}"

        starts = _chunk_starts(chunks)
        for expected in expected_starts:
            assert any(start.startswith(expected) for start in starts), (
                f"{language.value}: expected some chunk to START with {expected!r}; "
                f"got chunk starts {starts!r}"
            )
