"""Async / non-blocking integration test for the HuggingFace text tokenizer task.

Requires `transformers` and a locally-cached small tokenizer. Skips otherwise.
We deliberately avoid downloading over the network at test time; if the model
isn't already cached, the tokenizer construction will attempt to fetch it and
the test will skip on any resulting connection failure.

Focus: driving `HuggingfaceTextModelTokenizerTaskAction._encode` with a long
(~30KB) input takes ≥50ms wall time on real HF tokenizers, so we can assert
the event loop keeps ticking through the whole call — proving the sync work
is off-loaded via `_run_in_executor`.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("transformers")

from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model_tokenizer.tasks.text.huggingface import (
    HuggingfaceTextModelTokenizerTaskAction,
    HuggingfaceTextModelTokenizerTaskService,
)
from mindor.dsl.schema.action import ModelTokenizerActionConfig

from tests.async_helpers import assert_does_not_block


_TOKENIZER_REPO = "sentence-transformers/all-MiniLM-L6-v2"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def real_tokenizer():
    """Load a small local HF tokenizer once for the module.

    Skips the whole module if the tokenizer isn't available (offline env,
    no cached model, missing dependency). We keep the try/except broad on
    purpose — the test isn't about network health, only about async
    behavior with a real tokenizer.
    """
    try:
        from transformers import AutoTokenizer  # noqa: WPS433

        return AutoTokenizer.from_pretrained(_TOKENIZER_REPO)
    except Exception as exc:  # network, offline cache miss, unresolved import
        pytest.skip(f"HF tokenizer {_TOKENIZER_REPO!r} not available: {exc}")


def _make_context(text: Any) -> ComponentActionContext:
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_text(value, **kwargs):
        return text
    ctx.render_text = AsyncMock(side_effect=render_text)

    async def render_variable(value, **kwargs):
        if isinstance(value, str) and value == "${result}":
            return sources.get("result")
        return value
    ctx.render_variable = AsyncMock(side_effect=render_variable)

    return ctx


def _make_action(tokenizer: Any, method: str, **kwargs) -> HuggingfaceTextModelTokenizerTaskAction:
    config = TypeAdapter(ModelTokenizerActionConfig).validate_python({"method": method, **kwargs})
    return HuggingfaceTextModelTokenizerTaskAction(config, tokenizer)


class TestHuggingfaceTokenizerContract:
    @pytest.mark.anyio
    async def test_encode_single_text_returns_dict(self, real_tokenizer):
        action = _make_action(real_tokenizer, "encode", text="hello world")
        ctx = _make_context("hello world")

        result = await action.run(ctx)

        assert isinstance(result, dict)
        assert "input_ids" in result
        assert len(result["input_ids"]) >= 2

    @pytest.mark.anyio
    async def test_count_matches_encode_length(self, real_tokenizer):
        sample = "The quick brown fox jumps over the lazy dog."

        enc = _make_action(real_tokenizer, "encode", text=sample)
        cnt = _make_action(real_tokenizer, "count", text=sample)

        enc_result = await enc.run(_make_context(sample))
        cnt_result = await cnt.run(_make_context(sample))

        assert cnt_result["count"] == len(enc_result["input_ids"])


class TestHuggingfaceTokenizerNonBlocking:
    @pytest.mark.anyio
    async def test_encode_long_text_does_not_block(self, real_tokenizer):
        """A ~30KB input takes real HF tokenizers well over 50ms; if the sync
        `tokenizer(...)` call is on the loop thread, ticker will barely fire."""
        long_text = ("The quick brown fox jumps over the lazy dog. " * 700)  # ~30KB

        action = _make_action(real_tokenizer, "encode", text=long_text)
        ctx = _make_context(long_text)

        result = await assert_does_not_block(
            action.run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, dict)
        assert "input_ids" in result

    @pytest.mark.anyio
    async def test_batch_encode_does_not_block(self, real_tokenizer):
        # Multiple long texts in one batch.
        texts = [("Lorem ipsum dolor sit amet. " * 500) for _ in range(4)]

        action = _make_action(real_tokenizer, "encode", text=texts, batch_size=2)
        ctx = _make_context(texts)

        result = await assert_does_not_block(
            action.run(ctx),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, list)
        assert len(result) == 4
        for item in result:
            assert "input_ids" in item


class TestHuggingfaceTokenizerServiceSignature:
    def test_service_run_has_no_loop_kwarg(self):
        signature = inspect.signature(HuggingfaceTextModelTokenizerTaskService.run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "action", "context"]

    def test_action_run_has_no_loop_kwarg(self):
        signature = inspect.signature(HuggingfaceTextModelTokenizerTaskAction.run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "context"]
