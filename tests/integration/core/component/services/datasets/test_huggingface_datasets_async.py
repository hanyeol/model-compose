"""Async / non-blocking integration test for the HuggingFace datasets driver.

We build an in-memory `Dataset.from_dict(...)` — no network, no HF Hub — and
drive `HuggingfaceDatasetsAction._select` and `._map` through the shared
DatasetsAction wrapper. The `datasets` library's `.map` / `.select` calls
are sync and CPU-bound; the driver wraps them in `_run_in_executor`.

Focus: confirm contract (returned Dataset shape) and non-blocking behavior
under a moderately expensive map function.
"""

from __future__ import annotations

import inspect
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("datasets")

from datasets import Dataset

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.datasets.drivers.huggingface import (
    HuggingfaceDatasetsAction,
    HuggingfaceDatasetsService,
)
from mindor.dsl.schema.action import (
    HuggingfaceDatasetsSelectActionConfig,
    HuggingfaceDatasetsMapActionConfig,
)

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def sample_dataset() -> Dataset:
    """A small in-memory dataset — no network I/O."""
    return Dataset.from_dict({
        "question": [f"question {i}" for i in range(200)],
        "answer":   [f"answer {i}"   for i in range(200)],
    })


def _make_context(sources: dict) -> ComponentActionContext:
    """Minimal fake context that resolves ${input.dataset} and ${input.indices}
    (and any other keys) directly from the provided `sources` map."""
    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    registered: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        registered[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result}":
                return registered.get("result")
            for key, resolved in sources.items():
                if value == "${" + key + "}":
                    return resolved
        return value
    ctx.render_variable = AsyncMock(side_effect=render_variable)

    async def render_text(value, **kwargs):
        return await render_variable(value)
    ctx.render_text = AsyncMock(side_effect=render_text)

    return ctx


class TestHuggingfaceDatasetsContract:
    @pytest.mark.anyio
    async def test_select_rows_returns_subset(self, sample_dataset):
        config = HuggingfaceDatasetsSelectActionConfig(
            method="select",
            dataset="${input.dataset}",
            axis="rows",
            indices=[0, 5, 10],
        )
        ctx = _make_context({"input.dataset": sample_dataset})

        result = await HuggingfaceDatasetsAction(config).run(ctx)

        assert isinstance(result, Dataset)
        assert len(result) == 3
        assert result["question"] == ["question 0", "question 5", "question 10"]

    @pytest.mark.anyio
    async def test_select_columns_returns_column_subset(self, sample_dataset):
        config = HuggingfaceDatasetsSelectActionConfig(
            method="select",
            dataset="${input.dataset}",
            axis="columns",
            columns=["question"],
        )
        ctx = _make_context({"input.dataset": sample_dataset})

        result = await HuggingfaceDatasetsAction(config).run(ctx)

        assert isinstance(result, Dataset)
        assert list(result.column_names) == ["question"]

    @pytest.mark.anyio
    async def test_map_adds_output_column(self, sample_dataset):
        config = HuggingfaceDatasetsMapActionConfig(
            method="map",
            dataset="${input.dataset}",
            template="Q: {question}\nA: {answer}",
            output_column="text",
        )
        ctx = _make_context({"input.dataset": sample_dataset})

        result = await HuggingfaceDatasetsAction(config).run(ctx)

        assert isinstance(result, Dataset)
        assert "text" in result.column_names
        assert result["text"][0] == "Q: question 0\nA: answer 0"


class TestHuggingfaceDatasetsServiceSignature:
    def test_service_run_has_no_loop_kwarg(self):
        signature = inspect.signature(HuggingfaceDatasetsService._run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "action", "context"]

    def test_action_run_has_no_loop_kwarg(self):
        signature = inspect.signature(HuggingfaceDatasetsAction.run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "context"]
