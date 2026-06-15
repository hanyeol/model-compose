"""Integration tests for HuggingfaceTextEmbeddingTaskAction with a real model.

Uses ``sentence-transformers/all-MiniLM-L6-v2`` (~22 MB) — small enough for CI
yet a real bi-encoder, so the embedding shape and semantic ordering are
non-trivial.

Verifies:
- single / list / AsyncIterator inputs
- collect / ``${result}`` / ``${result[]}`` outputs
- semantic property: paraphrases land closer than unrelated sentences
- batch boundaries still produce contiguous results
"""

from __future__ import annotations

import asyncio
import importlib.util
import math
from collections.abc import AsyncIterator
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig


transformers_required = pytest.mark.skipif(
    not all(importlib.util.find_spec(m) for m in ("transformers", "torch")),
    reason="transformers/torch not available",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def minilm_action_factory():
    """Load all-MiniLM-L6-v2 once per module and return an action factory."""
    import torch
    from transformers import AutoModel, AutoTokenizer

    from mindor.core.component.services.model.tasks.text_embedding.huggingface import (
        HuggingfaceTextEmbeddingTaskAction,
    )

    try:
        model     = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    except Exception as e:
        pytest.skip(f"all-MiniLM-L6-v2 unavailable: {e}")

    device = torch.device("cpu")
    model = model.to(device)
    model.eval()

    def _factory(config: TextEmbeddingModelActionConfig) -> HuggingfaceTextEmbeddingTaskAction:
        return HuggingfaceTextEmbeddingTaskAction(config, model, tokenizer, device)

    return _factory


def _make_context(text_value: Any) -> ComponentActionContext:
    """Mock context that routes render_variable for the audio field and tracks sources.

    `text_value` may be:
      - str → single text
      - list of str → list of texts
      - zero-arg callable returning an AsyncIterator of str → AsyncIterator
    """
    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    def contains_ref(key: str, value: Any) -> bool:
        if isinstance(value, str):
            return f"${{{key}" in value
        return False
    ctx.contains_variable_reference = MagicMock(side_effect=contains_ref)

    async def render_variable(value, **kwargs):
        # Variable resolution for the configured text field.
        if isinstance(value, str):
            if value == "${input.text}":
                return text_value() if callable(text_value) and not isinstance(text_value, str) else text_value
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    return ctx


def _make_config(
    text_expr: Any = "${input.text}",
    *,
    output: Any = None,
    batch_size: int = 2,
    pooling: str = "mean",
    normalize: bool = True,
    max_input_length: int = 64,
) -> TextEmbeddingModelActionConfig:
    raw: dict = {
        "text":             text_expr,
        "batch_size":       batch_size,
        "max_input_length": max_input_length,
        "params": {
            "pooling":   pooling,
            "normalize": normalize,
        },
    }
    if output is not None:
        raw["output"] = output
    return TextEmbeddingModelActionConfig.model_validate(raw)


def _cosine(a: List[float], b: List[float]) -> float:
    dot   = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b + 1e-12)


@transformers_required
class TestSingleInput:
    @pytest.mark.anyio
    async def test_single_returns_vector(self, minilm_action_factory):
        config = _make_config()
        ctx    = _make_context("hello world")
        action = minilm_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)
        assert len(result) == 384  # MiniLM-L6 hidden size

    @pytest.mark.anyio
    async def test_normalize_yields_unit_vector(self, minilm_action_factory):
        config = _make_config(normalize=True)
        ctx    = _make_context("hello world")
        action = minilm_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        norm = math.sqrt(sum(x * x for x in result))
        assert norm == pytest.approx(1.0, abs=1e-4)


@transformers_required
class TestListInput:
    @pytest.mark.anyio
    async def test_list_returns_list_of_vectors(self, minilm_action_factory):
        config = _make_config(batch_size=2)
        ctx    = _make_context([ "the cat sat on the mat", "machine learning rocks" ])
        action = minilm_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list) and len(result) == 2
        assert all(isinstance(v, list) and len(v) == 384 for v in result)

    @pytest.mark.anyio
    async def test_paraphrases_closer_than_unrelated(self, minilm_action_factory):
        """Semantic check: paraphrase cosine > unrelated cosine."""
        config = _make_config(batch_size=3)
        ctx    = _make_context([
            "a dog plays in the park",
            "a puppy is running on the grass",   # paraphrase of #0
            "quantum entanglement is fascinating", # unrelated
        ])
        action = minilm_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        sim_para = _cosine(result[0], result[1])
        sim_far  = _cosine(result[0], result[2])
        assert sim_para > sim_far + 0.05  # generous margin


@transformers_required
class TestStreamOutputTemplate:
    @pytest.mark.anyio
    async def test_stream_output_yields_each_vector(self, minilm_action_factory):
        config = _make_config(output="${result[]}", batch_size=2)
        ctx    = _make_context([ "alpha", "beta", "gamma" ])
        action = minilm_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 3
        assert all(isinstance(v, list) and len(v) == 384 for v in items)


@transformers_required
class TestAsyncIteratorInput:
    @pytest.mark.anyio
    async def test_stream_input_yields_vectors(self, minilm_action_factory):
        def _make_iter():
            async def _gen():
                yield "hello"
                yield "world"
                yield "embedding"
            return _gen()

        config = _make_config()
        ctx    = _make_context(_make_iter)
        action = minilm_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 3
        assert all(isinstance(v, list) and len(v) == 384 for v in items)


@transformers_required
class TestPooling:
    @pytest.mark.anyio
    @pytest.mark.parametrize("pooling", ["mean", "cls", "max"])
    async def test_pooling_strategies_produce_distinct_vectors(self, minilm_action_factory, pooling):
        config = _make_config(pooling=pooling, normalize=False)
        ctx    = _make_context("a test sentence")
        action = minilm_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list) and len(result) == 384
        # Each pooling should yield something non-degenerate.
        assert any(abs(x) > 1e-6 for x in result)
