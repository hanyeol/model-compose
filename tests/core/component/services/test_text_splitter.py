"""
Tests for text_splitter component.

This file contains both unit tests and comparison tests with langchain's TextSplitter behavior.
The comparison tests use pre-generated expected results from langchain to avoid runtime dependency.

To regenerate expected results, run:
    python tests/core/component/services/generate_langchain_results.py
"""

import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock
from mindor.core.component.services.text_splitter import TextSplitterAction
from mindor.dsl.schema.action import TextSplitterActionConfig
from mindor.core.component.context import ComponentActionContext


# Configure anyio to use only asyncio backend
@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_context():
    """Create a mock ComponentActionContext for testing."""
    context = MagicMock(spec=ComponentActionContext)
    # Make render_variable return the value as-is by default
    async def render_variable(value):
        return value
    context.render_variable = AsyncMock(side_effect=render_variable)
    return context


@pytest.fixture
def test_cases():
    """Load pre-generated test cases."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    results_file = os.path.join(current_dir, "test_text_splitter_cases.json")

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
        result = await action.run(mock_context)

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
            result = await action.run(mock_context)

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
