"""Tests for the TextClassificationTaskAction's I/O matrix.

text_classification has no `streaming` config (the model API is batch-only). The
output-shape rule is the same as the other model tasks:

    is_stream_input  = isinstance(text, AsyncIterator)
    is_stream_output = output references "result[]"
    is_direct_output = output is empty or output == "${result}"
    is_stream_mode   = is_stream_input or is_stream_output

Stream mode  → AsyncIterator yielding per-prediction output.
Collect mode → single value or list, matching the input shape.

Tests cover all combinations of:
- Input shape: single str / List[str] / AsyncIterator[str]
- Output: unspecified / ${result} / ${result[]}
- Batch boundaries (batch_size=2 with 4 inputs produces 2 batches)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.text_classification.common import TextClassificationTaskAction
from mindor.core.foundation.cancellation import CancellationToken
from mindor.dsl.schema.action import TextClassificationModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeClassificationAction(TextClassificationTaskAction):
    """Deterministic ``_predict`` for testing.

    Each text produces ``{"label": ..., "score": len(text)}`` so we can verify
    both the batching and per-item dispatch.
    """

    def __init__(self, config: TextClassificationModelActionConfig, labels: Optional[List[str]] = None):
        super().__init__(config, labels)
        self.batches_seen: List[List[str]] = []
        self.params_seen: List[Dict[str, Any]] = []
        self.labels_seen: List[Optional[List[str]]] = []

    async def _predict(self, texts: List[str], params: Dict[str, Any], labels: Optional[List[str]], loop: asyncio.AbstractEventLoop, cancellation_token: Optional[CancellationToken] = None) -> List[Any]:
        self.batches_seen.append(list(texts))
        self.params_seen.append(params)
        self.labels_seen.append(labels)
        return [ { "label": "pos" if len(t) % 2 == 0 else "neg", "score": float(len(t)) } for t in texts ]


def _make_config(text_expr: Any, output: Any = None, batch_size: int = 2) -> TextClassificationModelActionConfig:
    raw: dict = { "text": text_expr, "batch_size": batch_size }
    if output is not None:
        raw["output"] = output
    return TextClassificationModelActionConfig.model_validate(raw)


async def _make_async_iter(items: List[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


class TestSingleInput:
    """Single str input → single prediction."""

    @pytest.mark.anyio
    async def test_no_output_returns_single_prediction(self):
        action = _FakeClassificationAction(_make_config("${input.text}"))
        ctx    = ComponentActionContext("r-1", { "text": "hello" })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, dict)
        assert result == { "label": "neg", "score": 5.0 }
        assert action.batches_seen == [ [ "hello" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_single_prediction(self):
        action = _FakeClassificationAction(_make_config("${input.text}", output="${result}"))
        ctx    = ComponentActionContext("r-2", { "text": "hi" })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, dict)
        assert result["score"] == 2.0

    # NOTE: ``output="${result[]}"`` on collect-mode (single/list) input is unsupported
    # by text_classification — the source only enters the stream-emitting branch when
    # the input is an AsyncIterator. See TestStreamInput tests below.


class TestListInput:
    """List[str] input, batch_size=2 with 4 items → 2 batches."""

    @pytest.mark.anyio
    async def test_no_output_returns_list(self):
        action = _FakeClassificationAction(_make_config("${input.texts}"))
        ctx    = ComponentActionContext("r-4", { "texts": [ "a", "bb", "ccc", "dddd" ] })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list)
        assert len(result) == 4
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc", "dddd" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_list(self):
        action = _FakeClassificationAction(_make_config("${input.texts}", output="${result}"))
        ctx    = ComponentActionContext("r-5", { "texts": [ "x", "y" ] })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, list)
        assert len(result) == 2

    # NOTE: see TestSingleInput — list input + ``output="${result[]}"`` doesn't enter
    # the stream-emitting branch in text_classification.


class TestStreamInput:
    """AsyncIterator[str] input always produces stream output (stream-in → stream-out)."""

    @pytest.mark.anyio
    async def test_no_output_returns_async_iterator(self):
        action = _FakeClassificationAction(_make_config("${input.texts}"))
        stream = _make_async_iter([ "a", "bb", "ccc" ])
        ctx    = ComponentActionContext("r-7", { "texts": stream })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 3
        # batch_size=2 → two batches: ["a", "bb"] and ["ccc"]
        assert action.batches_seen == [ [ "a", "bb" ], [ "ccc" ] ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_async_iterator(self):
        action = _FakeClassificationAction(_make_config("${input.texts}", output="${result}"))
        stream = _make_async_iter([ "a", "bb" ])
        ctx    = ComponentActionContext("r-8", { "texts": stream })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 2

    @pytest.mark.anyio
    async def test_stream_output_returns_async_iterator(self):
        action = _FakeClassificationAction(_make_config("${input.texts}", output="${result[]}"))
        stream = _make_async_iter([ "a", "bb", "ccc", "dddd" ])
        ctx    = ComponentActionContext("r-9", { "texts": stream })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 4


class TestParamsPropagation:
    """``_resolve_params`` builds the dict that the driver consumes via ``_predict``."""

    @pytest.mark.anyio
    async def test_default_params_dict_keys(self):
        action = _FakeClassificationAction(_make_config("${input.text}"))
        ctx    = ComponentActionContext("r-10", { "text": "hi" })
        loop   = asyncio.get_running_loop()
        await action.run(ctx, loop)

        assert len(action.params_seen) == 1
        params = action.params_seen[0]
        # Driver-agnostic params surfaced from the base resolver.
        assert set(params.keys()) >= { "max_input_length", "return_probabilities" }
        assert params["max_input_length"] == 512
        assert params["return_probabilities"] is False


class TestLabelsPropagation:
    """``labels`` are passed to ``_predict`` as a separate positional argument."""

    @pytest.mark.anyio
    async def test_labels_default_is_none(self):
        action = _FakeClassificationAction(_make_config("${input.text}"))
        ctx    = ComponentActionContext("r-11", { "text": "hi" })
        loop   = asyncio.get_running_loop()
        await action.run(ctx, loop)

        assert action.labels_seen == [ None ]

    @pytest.mark.anyio
    async def test_labels_passed_through(self):
        labels = [ "positive", "negative", "neutral" ]
        action = _FakeClassificationAction(_make_config("${input.texts}"), labels=labels)
        ctx    = ComponentActionContext("r-12", { "texts": [ "a", "bb", "ccc" ] })
        loop   = asyncio.get_running_loop()
        await action.run(ctx, loop)

        # batch_size=2 with 3 items → 2 batches; labels seen once per batch
        assert action.labels_seen == [ labels, labels ]
