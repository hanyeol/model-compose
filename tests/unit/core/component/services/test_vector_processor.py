"""End-to-end tests for VectorProcessorAction.

Covers:
  - DSL schema round-trip via TypeAdapter (discriminator on `method` field, default values)
  - Full action execution through ComponentActionContext
  - Output containers (single value, list of dicts, list of floats, matrix)
  - Metric-dependent semantics (top-k / threshold-filter: higher-better for
    similarity metrics, lower-better for distance metrics)
  - Provenance in ranking results (`index` for each surviving candidate)
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

import numpy as np
import pytest
from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.vector_processor.drivers.native import (
    NativeVectorProcessorAction as VectorProcessorAction,
)
from mindor.dsl.schema.action import VectorProcessorActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _cfg(raw: dict) -> VectorProcessorActionConfig:
    return TypeAdapter(VectorProcessorActionConfig).validate_python(raw)


def _metric_value(m) -> str:
    return m.value if hasattr(m, "value") else m


async def _run(config: VectorProcessorActionConfig, inputs: dict) -> Any:
    action = VectorProcessorAction(config)
    context = ComponentActionContext("test", inputs)
    return await action.run(context, asyncio.get_running_loop())


def _approx(x: float, y: float, tol: float = 1e-9) -> bool:
    return math.isclose(x, y, abs_tol=tol)


def _approx_nested(actual: Any, expected: Any, tol: float = 1e-9) -> None:
    """Assert that a nested list-of-lists matches within tolerance.
    pytest.approx does not support nested structures.
    """
    np.testing.assert_allclose(np.asarray(actual), np.asarray(expected), atol=tol)


# ------------------------------------------------------------------ #
# Schema validation                                                  #
# ------------------------------------------------------------------ #

class TestSchemaValidation:
    """Round-trip every method through the discriminated union."""

    def test_similarity_schema_default_metric(self):
        c = _cfg({"method": "similarity", "vector": [1, 0], "other": [0, 1]})
        assert c.method.value == "similarity"
        assert c.vector == [1, 0]
        assert c.other == [0, 1]
        assert _metric_value(c.metric) == "cosine"

    def test_similarity_schema_explicit_metric(self):
        c = _cfg({"method": "similarity", "vector": [1, 0], "other": [0, 1], "metric": "cosine"})
        assert _metric_value(c.metric) == "cosine"

    def test_dot_product_schema(self):
        c = _cfg({"method": "dot-product", "vector": [1, 2], "other": [3, 4]})
        assert c.method.value == "dot-product"

    def test_distance_schema_default_metric(self):
        c = _cfg({"method": "distance", "vector": [0, 0], "other": [3, 4]})
        assert c.method.value == "distance"
        assert _metric_value(c.metric) == "euclidean"

    def test_normalize_schema(self):
        c = _cfg({"method": "normalize", "vector": [3, 4]})
        assert c.method.value == "normalize"

    def test_mean_default_axis(self):
        c = _cfg({"method": "mean", "vectors": [[1, 2], [3, 4]]})
        assert c.axis == 0

    def test_mean_explicit_axis(self):
        c = _cfg({"method": "mean", "vectors": [[1, 2], [3, 4]], "axis": 1})
        assert c.axis == 1

    def test_sum_schema(self):
        c = _cfg({"method": "sum", "vectors": [[1, 2], [3, 4]]})
        assert c.method.value == "sum"

    def test_top_k_defaults(self):
        c = _cfg({"method": "top-k", "query": [1, 0], "candidates": [[1, 0]]})
        assert c.k == 1
        # `metric` may be resolved as either the enum or its string value depending
        # on which arm of the Union pydantic picks; both are accepted downstream.
        assert _metric_value(c.metric) == "cosine"

    def test_top_k_custom_metric(self):
        c = _cfg({
            "method": "top-k",
            "query": [1, 0],
            "candidates": [[1, 0]],
            "k": 3,
            "metric": "euclidean",
        })
        assert c.k == 3
        assert _metric_value(c.metric) == "euclidean"

    def test_threshold_filter_requires_threshold(self):
        with pytest.raises(Exception):
            _cfg({"method": "threshold-filter", "query": [1, 0], "candidates": [[1, 0]]})

    def test_threshold_filter_schema(self):
        c = _cfg({
            "method": "threshold-filter",
            "query": [1, 0],
            "candidates": [[1, 0]],
            "threshold": 0.5,
        })
        assert c.threshold == 0.5
        assert _metric_value(c.metric) == "cosine"

    def test_unknown_method_rejected(self):
        with pytest.raises(Exception):
            _cfg({"method": "cross-product", "vector": [1, 0], "other": [0, 1]})


# ------------------------------------------------------------------ #
# Similarity (default metric: cosine)                                #
# ------------------------------------------------------------------ #

class TestSimilarity:

    @pytest.mark.anyio
    async def test_1d_vs_1d_returns_scalar(self):
        cfg = _cfg({"method": "similarity", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [1, 0, 0], "b": [1, 0, 0]})
        assert isinstance(result, float)
        assert _approx(result, 1.0)

    @pytest.mark.anyio
    async def test_orthogonal_is_zero(self):
        cfg = _cfg({"method": "similarity", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [1, 0], "b": [0, 1]})
        assert _approx(result, 0.0)

    @pytest.mark.anyio
    async def test_opposite_is_minus_one(self):
        cfg = _cfg({"method": "similarity", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [1, 0], "b": [-1, 0]})
        assert _approx(result, -1.0)

    @pytest.mark.anyio
    async def test_1d_vs_2d_returns_list(self):
        cfg = _cfg({"method": "similarity", "vector": "${input.q}", "other": "${input.candidates}"})
        result = await _run(cfg, {"q": [1, 0], "candidates": [[1, 0], [0, 1], [-1, 0]]})
        assert result == pytest.approx([1.0, 0.0, -1.0])

    @pytest.mark.anyio
    async def test_2d_vs_1d_returns_list(self):
        cfg = _cfg({"method": "similarity", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [[1, 0], [0, 1]], "b": [1, 0]})
        assert result == pytest.approx([1.0, 0.0])

    @pytest.mark.anyio
    async def test_2d_vs_2d_pairs_element_wise(self):
        """Both sides as batches -> each row of `vector` paired with the same-index row of `other`.
        This is zip semantics, not an outer product (matrix)."""
        cfg = _cfg({"method": "similarity", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [[1, 0], [0, 1]], "b": [[1, 0], [0, 1]]})
        assert result == pytest.approx([1.0, 1.0])

    @pytest.mark.anyio
    async def test_2d_vs_2d_length_mismatch_raises(self):
        cfg = _cfg({"method": "similarity", "vector": "${input.a}", "other": "${input.b}"})
        with pytest.raises(ValueError, match="different lengths"):
            await _run(cfg, {"a": [[1, 0]], "b": [[1, 0], [0, 1]]})

    @pytest.mark.anyio
    async def test_zero_vector_returns_zero_similarity(self):
        cfg = _cfg({"method": "similarity", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [0, 0], "b": [1, 0]})
        assert _approx(result, 0.0)

    @pytest.mark.anyio
    async def test_distance_metric_rejected_at_runtime(self):
        """method=similarity + metric=euclidean is caught at param resolution."""
        cfg = _cfg({"method": "similarity", "vector": "${input.a}", "other": "${input.b}", "metric": "euclidean"})
        with pytest.raises(ValueError, match="similarity metric"):
            await _run(cfg, {"a": [1, 0], "b": [0, 1]})


# ------------------------------------------------------------------ #
# Dot product                                                        #
# ------------------------------------------------------------------ #

class TestDotProduct:

    @pytest.mark.anyio
    async def test_1d_vs_1d(self):
        cfg = _cfg({"method": "dot-product", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [1, 2, 3], "b": [4, 5, 6]})
        # 1*4 + 2*5 + 3*6 = 32
        assert _approx(result, 32.0)

    @pytest.mark.anyio
    async def test_1d_vs_2d(self):
        cfg = _cfg({"method": "dot-product", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [1, 2], "b": [[1, 0], [0, 1], [1, 1]]})
        assert result == pytest.approx([1.0, 2.0, 3.0])


# ------------------------------------------------------------------ #
# Distance (default metric: euclidean)                               #
# ------------------------------------------------------------------ #

class TestDistance:

    @pytest.mark.anyio
    async def test_3_4_5(self):
        cfg = _cfg({"method": "distance", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [0, 0], "b": [3, 4]})
        assert _approx(result, 5.0)

    @pytest.mark.anyio
    async def test_identical_vectors_zero(self):
        cfg = _cfg({"method": "distance", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [1, 2, 3], "b": [1, 2, 3]})
        assert _approx(result, 0.0)

    @pytest.mark.anyio
    async def test_1d_vs_2d(self):
        cfg = _cfg({"method": "distance", "vector": "${input.a}", "other": "${input.b}"})
        result = await _run(cfg, {"a": [0, 0], "b": [[3, 4], [0, 0], [1, 0]]})
        assert result == pytest.approx([5.0, 0.0, 1.0])


# ------------------------------------------------------------------ #
# Normalize                                                          #
# ------------------------------------------------------------------ #

class TestNormalize:

    @pytest.mark.anyio
    async def test_1d(self):
        cfg = _cfg({"method": "normalize", "vector": "${input.v}"})
        result = await _run(cfg, {"v": [3, 4]})
        assert result == pytest.approx([0.6, 0.8])

    @pytest.mark.anyio
    async def test_1d_already_unit(self):
        cfg = _cfg({"method": "normalize", "vector": "${input.v}"})
        result = await _run(cfg, {"v": [1, 0, 0]})
        assert result == pytest.approx([1.0, 0.0, 0.0])

    @pytest.mark.anyio
    async def test_2d_normalizes_each_row(self):
        cfg = _cfg({"method": "normalize", "vector": "${input.v}"})
        result = await _run(cfg, {"v": [[3, 4], [0, 5], [1, 0]]})
        _approx_nested(result, [[0.6, 0.8], [0.0, 1.0], [1.0, 0.0]])

    @pytest.mark.anyio
    async def test_zero_vector_passes_through(self):
        """A zero-norm vector cannot be normalized; return it unchanged rather than raise."""
        cfg = _cfg({"method": "normalize", "vector": "${input.v}"})
        result = await _run(cfg, {"v": [0, 0, 0]})
        assert result == pytest.approx([0.0, 0.0, 0.0])

    @pytest.mark.anyio
    async def test_zero_row_in_batch(self):
        cfg = _cfg({"method": "normalize", "vector": "${input.v}"})
        result = await _run(cfg, {"v": [[3, 4], [0, 0]]})
        _approx_nested(result, [[0.6, 0.8], [0.0, 0.0]])


# ------------------------------------------------------------------ #
# Mean / Sum                                                         #
# ------------------------------------------------------------------ #

class TestMean:

    @pytest.mark.anyio
    async def test_axis_0(self):
        cfg = _cfg({"method": "mean", "vectors": "${input.v}", "axis": 0})
        result = await _run(cfg, {"v": [[1, 2], [3, 4], [5, 6]]})
        assert result == pytest.approx([3.0, 4.0])

    @pytest.mark.anyio
    async def test_axis_1(self):
        cfg = _cfg({"method": "mean", "vectors": "${input.v}", "axis": 1})
        result = await _run(cfg, {"v": [[1, 2, 3], [4, 5, 6]]})
        assert result == pytest.approx([2.0, 5.0])

    @pytest.mark.anyio
    async def test_default_axis_is_0(self):
        cfg = _cfg({"method": "mean", "vectors": "${input.v}"})
        result = await _run(cfg, {"v": [[2, 4], [4, 8]]})
        assert result == pytest.approx([3.0, 6.0])


class TestSum:

    @pytest.mark.anyio
    async def test_axis_0(self):
        cfg = _cfg({"method": "sum", "vectors": "${input.v}", "axis": 0})
        result = await _run(cfg, {"v": [[1, 2], [3, 4]]})
        assert result == pytest.approx([4.0, 6.0])

    @pytest.mark.anyio
    async def test_single_vector_input_treated_as_one_row_matrix(self):
        """A 1D input is a single vector, so summing axis=0 across a
        one-row matrix yields that same vector back."""
        cfg = _cfg({"method": "sum", "vectors": "${input.v}", "axis": 0})
        result = await _run(cfg, {"v": [1, 2, 3, 4]})
        assert result == pytest.approx([1.0, 2.0, 3.0, 4.0])


# ------------------------------------------------------------------ #
# Top-K                                                              #
# ------------------------------------------------------------------ #

class TestTopK:

    @pytest.mark.anyio
    async def test_flat_candidates_cosine(self):
        cfg = _cfg({
            "method": "top-k",
            "query": "${input.q}",
            "candidates": "${input.c}",
            "k": 2,
        })
        result = await _run(cfg, {"q": [1, 0], "c": [[1, 0], [0, 1], [0.9, 0.1]]})
        assert len(result) == 2
        assert result[0]["index"] == 0
        assert _approx(result[0]["score"], 1.0)
        assert result[1]["index"] == 2  # closer to [1,0] than [0,1]

    @pytest.mark.anyio
    async def test_k_larger_than_candidates(self):
        cfg = _cfg({
            "method": "top-k",
            "query": "${input.q}",
            "candidates": "${input.c}",
            "k": 10,
        })
        result = await _run(cfg, {"q": [1, 0], "c": [[1, 0], [0, 1]]})
        # Only 2 candidates exist; result should return what's available.
        assert len(result) == 2

    @pytest.mark.anyio
    async def test_euclidean_ranks_lower_first(self):
        cfg = _cfg({
            "method": "top-k",
            "query": "${input.q}",
            "candidates": "${input.c}",
            "k": 3,
            "metric": "euclidean",
        })
        result = await _run(cfg, {"q": [0, 0], "c": [[3, 4], [1, 1], [10, 10]]})
        # Distances: 5, sqrt(2), 10*sqrt(2). Sorted ascending -> index 1, 0, 2.
        assert [r["index"] for r in result] == [1, 0, 2]


# ------------------------------------------------------------------ #
# Threshold filter                                                   #
# ------------------------------------------------------------------ #

class TestThresholdFilter:

    @pytest.mark.anyio
    async def test_cosine_keeps_above_threshold(self):
        cfg = _cfg({
            "method": "threshold-filter",
            "query": "${input.q}",
            "candidates": "${input.c}",
            "threshold": 0.5,
        })
        result = await _run(cfg, {"q": [1, 0], "c": [[1, 0], [0, 1], [0.9, 0.1]]})
        indices = sorted(r["index"] for r in result)
        # cosines: 1.0, 0.0, ~0.994 — keep indices 0 and 2.
        assert indices == [0, 2]

    @pytest.mark.anyio
    async def test_euclidean_keeps_below_threshold(self):
        cfg = _cfg({
            "method": "threshold-filter",
            "query": "${input.q}",
            "candidates": "${input.c}",
            "threshold": 5.0,
            "metric": "euclidean",
        })
        result = await _run(cfg, {"q": [0, 0], "c": [[3, 4], [10, 10], [1, 1]]})
        # Distances: 5.0, ~14.14, ~1.41. Keep <= 5.0 -> indices 0, 2.
        indices = sorted(r["index"] for r in result)
        assert indices == [0, 2]

    @pytest.mark.anyio
    async def test_all_below_threshold_returns_empty(self):
        cfg = _cfg({
            "method": "threshold-filter",
            "query": "${input.q}",
            "candidates": "${input.c}",
            "threshold": 0.99,
        })
        result = await _run(cfg, {"q": [1, 0], "c": [[0, 1], [0.5, 0.5]]})
        assert result == []

