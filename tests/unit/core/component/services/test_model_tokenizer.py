"""Tests for HuggingfaceTextModelTokenizerTaskAction covering the unified I/O matrix.

A fake tokenizer mocks the HF interface so tests run without loading a real model.
"""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model_tokenizer.tasks.text.huggingface import (
    HuggingfaceTextModelTokenizerTaskAction,
)
from mindor.dsl.schema.action import ModelTokenizerActionConfig
from pydantic import TypeAdapter


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeTokenizer:
    """Minimal stand-in for an HF tokenizer: splits on whitespace, maps to char codes.

    Always batches: accepts ``List[str]`` and returns parallel-list outputs to match the
    real HF interface used by HuggingfaceTextModelTokenizerTaskAction._encode.
    """

    def _encode_one(self, text: str, **kwargs):
        tokens = text.split()
        ids = [hash(t) % 1000 for t in tokens]
        mask = [1] * len(ids)
        if kwargs.get("padding") == "max_length" and kwargs.get("max_length"):
            pad = kwargs["max_length"] - len(ids)
            if pad > 0:
                ids += [0] * pad
                mask += [0] * pad
        if kwargs.get("truncation") and kwargs.get("max_length"):
            ids = ids[: kwargs["max_length"]]
            mask = mask[: kwargs["max_length"]]
        return ids, mask

    def __call__(self, text, **kwargs):
        if isinstance(text, list):
            encoded = [self._encode_one(t, **kwargs) for t in text]
            return {
                "input_ids": [ids for ids, _ in encoded],
                "attention_mask": [mask for _, mask in encoded],
            }
        ids, mask = self._encode_one(text, **kwargs)
        return {"input_ids": ids, "attention_mask": mask}

    def decode(self, token_ids, skip_special_tokens=True):
        return "decoded-" + ",".join(str(i) for i in token_ids)

    def batch_decode(self, token_ids_list, skip_special_tokens=True):
        return [self.decode(ids, skip_special_tokens=skip_special_tokens) for ids in token_ids_list]

    def encode(self, text):
        return [hash(t) % 1000 for t in text.split()]


def _make_context() -> ComponentActionContext:
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
        return value

    ctx.render_variable = AsyncMock(side_effect=render_variable)

    async def render_text(value, **kwargs):
        return value
    ctx.render_text = AsyncMock(side_effect=render_text)

    from mindor.core.foundation.variable.array import ArrayValue

    async def render_array(value, **kwargs):
        # Mirror real ArrayValueRenderer:
        # - list of lists → List[ArrayValue]
        # - flat list     → ArrayValue
        # - other         → None
        if isinstance(value, list) and value and isinstance(value[0], list):
            return [ArrayValue(list(item)) for item in value]
        if isinstance(value, (list, tuple)):
            return ArrayValue(list(value))
        return None
    ctx.render_array = AsyncMock(side_effect=render_array)

    return ctx


def _make_action(method: str, **kwargs) -> HuggingfaceTextModelTokenizerTaskAction:
    config = TypeAdapter(ModelTokenizerActionConfig).validate_python({"method": method, **kwargs})
    return HuggingfaceTextModelTokenizerTaskAction(config, _FakeTokenizer())


class TestEncodeSingleInput:
    @pytest.mark.anyio
    async def test_single_string_returns_single_dict(self):
        action = _make_action("encode", text="hello world")
        ctx = _make_context()

        result = await action.run(ctx)

        assert isinstance(result, dict)
        assert "input_ids" in result and "attention_mask" in result
        assert len(result["input_ids"]) == 2


class TestEncodeListInput:
    @pytest.mark.anyio
    async def test_list_returns_list_of_dicts(self):
        action = _make_action("encode", text=["one two", "three four five"])
        ctx = _make_context()

        result = await action.run(ctx)

        assert isinstance(result, list)
        assert len(result) == 2
        assert len(result[0]["input_ids"]) == 2
        assert len(result[1]["input_ids"]) == 3


class TestDecodeSingleInput:
    @pytest.mark.anyio
    async def test_flat_token_ids_treated_as_single(self):
        action = _make_action("decode", token_ids=[1, 2, 3])
        ctx = _make_context()

        result = await action.run(ctx)

        assert isinstance(result, dict)
        assert result["text"] == "decoded-1,2,3"


class TestDecodeListInput:
    @pytest.mark.anyio
    async def test_nested_token_ids_treated_as_list(self):
        action = _make_action("decode", token_ids=[[1, 2], [3, 4, 5]])
        ctx = _make_context()

        result = await action.run(ctx)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["text"] == "decoded-1,2"
        assert result[1]["text"] == "decoded-3,4,5"


class TestCount:
    @pytest.mark.anyio
    async def test_single_text(self):
        action = _make_action("count", text="alpha beta gamma")
        ctx = _make_context()

        result = await action.run(ctx)

        assert result == {"count": 3}

    @pytest.mark.anyio
    async def test_list_of_texts(self):
        action = _make_action("count", text=["a b", "c d e"])
        ctx = _make_context()

        result = await action.run(ctx)

        assert result == [{"count": 2}, {"count": 3}]


class TestStreamOutput:
    @pytest.mark.anyio
    async def test_async_iterator_input_returns_async_iterator(self):
        """AsyncIterator input triggers the streaming branch which yields per-batch results.

        The DSL schema only accepts strings/lists, so this case is reachable only via
        runtime rendering (a ``${input.texts}`` template resolving to an AsyncIterator).
        We simulate that by overriding ``render_text`` in the fake context.
        """
        async def _texts():
            yield "one"
            yield "two three"

        action = _make_action("encode", text="placeholder")
        ctx = _make_context()
        # Override render_text to return the async iterator regardless of input value.
        async def render_text_stream(value, **kwargs):
            return _texts()
        ctx.render_text = AsyncMock(side_effect=render_text_stream)

        result = await action.run(ctx)

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 2
        assert len(items[0]["input_ids"]) == 1
        assert len(items[1]["input_ids"]) == 2


class TestBatchSize:
    @pytest.mark.anyio
    @pytest.mark.parametrize("batch_size", [1, 2, 5])
    async def test_list_with_batch_size(self, batch_size: int):
        action = _make_action(
            "count",
            text=["a", "b c", "d e f"],
            batch_size=batch_size,
        )
        ctx = _make_context()

        result = await action.run(ctx)

        assert result == [{"count": 1}, {"count": 2}, {"count": 3}]


