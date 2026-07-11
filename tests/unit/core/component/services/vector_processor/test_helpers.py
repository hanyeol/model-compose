"""Pure-numpy helper tests for the native vector-processor driver.

These bypass ComponentActionContext and pydantic to exercise the internal
math primitives directly. Anything the end-to-end tests would find hard to
diagnose (shape/broadcasting mishaps, provenance construction, numeric edge
cases) belongs here.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from mindor.core.component.services.vector_processor.drivers.native import NativeVectorProcessorAction as _NA
from mindor.dsl.schema.action import SimilarityMetric, DistanceMetric

_as_array             = _NA._as_array
_cosine               = _NA._cosine
_dot                  = _NA._dot
_euclidean            = _NA._euclidean
_normalize_candidates = _NA._normalize_candidates
_pairwise             = _NA._pairwise
_score_all            = _NA._score_all
_as_native            = _NA._as_native


# ------------------------------------------------------------------ #
# _as_array                                                          #
# ------------------------------------------------------------------ #

class TestAsArray:

    def test_list_1d(self):
        arr = _as_array([1, 2, 3])
        assert arr.shape == (3,)
        assert arr.dtype == np.float64

    def test_list_2d(self):
        arr = _as_array([[1, 2], [3, 4]])
        assert arr.shape == (2, 2)

    def test_int_and_float_promoted_to_float64(self):
        arr = _as_array([1, 2.5, 3])
        assert arr.dtype == np.float64

    def test_none_raises(self):
        with pytest.raises(ValueError):
            _as_array(None)


# ------------------------------------------------------------------ #
# _as_native                                                         #
# ------------------------------------------------------------------ #

class TestAsNative:

    def test_array_to_list(self):
        assert _as_native(np.array([1.0, 2.0])) == [1.0, 2.0]

    def test_numpy_scalar_as_native_float(self):
        result = _as_native(np.float64(3.14))
        assert isinstance(result, float)
        assert result == pytest.approx(3.14)

    def test_numpy_int_as_native_int(self):
        result = _as_native(np.int64(42))
        assert isinstance(result, int)
        assert result == 42

    def test_python_scalar_passthrough(self):
        assert _as_native(3.14) == 3.14


# ------------------------------------------------------------------ #
# Pairwise metric primitives                                         #
# ------------------------------------------------------------------ #

class TestCosine:

    def test_identical(self):
        assert _cosine(np.array([1.0, 2.0]), np.array([1.0, 2.0])) == pytest.approx(1.0)

    def test_orthogonal(self):
        assert _cosine(np.array([1.0, 0.0]), np.array([0.0, 1.0])) == pytest.approx(0.0)

    def test_opposite(self):
        assert _cosine(np.array([1.0, 0.0]), np.array([-1.0, 0.0])) == pytest.approx(-1.0)

    def test_scaled_vectors_same_direction(self):
        assert _cosine(np.array([1.0, 0.0]), np.array([5.0, 0.0])) == pytest.approx(1.0)

    def test_zero_first(self):
        assert _cosine(np.array([0.0, 0.0]), np.array([1.0, 1.0])) == 0.0

    def test_zero_second(self):
        assert _cosine(np.array([1.0, 1.0]), np.array([0.0, 0.0])) == 0.0

    def test_both_zero(self):
        assert _cosine(np.array([0.0, 0.0]), np.array([0.0, 0.0])) == 0.0


class TestDot:

    def test_basic(self):
        assert _dot(np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])) == pytest.approx(32.0)

    def test_zero(self):
        assert _dot(np.array([0.0, 0.0]), np.array([1.0, 2.0])) == 0.0


class TestEuclidean:

    def test_3_4_5(self):
        assert _euclidean(np.array([0.0, 0.0]), np.array([3.0, 4.0])) == pytest.approx(5.0)

    def test_identical_zero(self):
        assert _euclidean(np.array([1.0, 2.0]), np.array([1.0, 2.0])) == 0.0


# ------------------------------------------------------------------ #
# _pairwise broadcasting                                             #
# ------------------------------------------------------------------ #

class TestPairwise:

    def test_1d_vs_1d_returns_scalar(self):
        result = _pairwise(np.array([1.0, 0.0]), np.array([0.0, 1.0]), _cosine)
        assert isinstance(result, float)
        assert result == pytest.approx(0.0)

    def test_1d_vs_2d_returns_list(self):
        result = _pairwise(
            np.array([1.0, 0.0]),
            np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]),
            _cosine,
        )
        assert isinstance(result, list)
        assert len(result) == 3
        assert result == pytest.approx([1.0, 0.0, -1.0])

    def test_2d_vs_1d_returns_list(self):
        result = _pairwise(
            np.array([[1.0, 0.0], [0.0, 1.0]]),
            np.array([1.0, 0.0]),
            _cosine,
        )
        assert result == pytest.approx([1.0, 0.0])

    def test_2d_vs_2d_returns_matrix(self):
        result = _pairwise(
            np.array([[1.0, 0.0], [0.0, 1.0]]),
            np.array([[1.0, 0.0], [0.0, 1.0]]),
            _cosine,
        )
        np.testing.assert_allclose(np.asarray(result), [[1.0, 0.0], [0.0, 1.0]], atol=1e-9)

    def test_3d_input_raises(self):
        with pytest.raises(ValueError):
            _pairwise(
                np.zeros((2, 2, 2)),
                np.zeros((2,)),
                _cosine,
            )


# ------------------------------------------------------------------ #
# _normalize_candidates                                              #
# ------------------------------------------------------------------ #

class TestNormalizeCandidates:

    def test_none_returns_empty(self):
        vecs, prov = _normalize_candidates(None)
        assert vecs == []
        assert prov == []

    def test_empty_list_returns_empty(self):
        vecs, prov = _normalize_candidates([])
        assert vecs == []
        assert prov == []

    def test_non_list_raises(self):
        with pytest.raises(ValueError):
            _normalize_candidates("not a list")

    def test_flat_list(self):
        vecs, prov = _normalize_candidates([[1, 0], [0, 1]])
        assert len(vecs) == 2
        assert prov == [{"index": 0}, {"index": 1}]

    def test_none_entries_skipped_but_indices_preserved(self):
        vecs, prov = _normalize_candidates([[1, 0], None, [0, 1]])
        assert len(vecs) == 2
        assert prov == [{"index": 0}, {"index": 2}]

    def test_empty_vector_entries_skipped(self):
        vecs, prov = _normalize_candidates([[1, 0], [], [0, 1]])
        assert len(vecs) == 2
        assert prov == [{"index": 0}, {"index": 2}]


# ------------------------------------------------------------------ #
# _score_all                                                         #
# ------------------------------------------------------------------ #

class TestScoreAll:

    def test_cosine(self):
        query = np.array([1.0, 0.0])
        candidates = [np.array([1.0, 0.0]), np.array([0.0, 1.0]), np.array([-1.0, 0.0])]
        scores = _score_all(query, candidates, SimilarityMetric.COSINE)
        assert scores == pytest.approx([1.0, 0.0, -1.0])

    def test_euclidean(self):
        query = np.array([0.0, 0.0])
        candidates = [np.array([3.0, 4.0]), np.array([0.0, 0.0]), np.array([1.0, 1.0])]
        scores = _score_all(query, candidates, DistanceMetric.EUCLIDEAN)
        assert scores == pytest.approx([5.0, 0.0, math.sqrt(2.0)])

    def test_2d_query_raises(self):
        query = np.zeros((2, 2))
        with pytest.raises(ValueError):
            _score_all(query, [np.array([1.0, 0.0])], SimilarityMetric.COSINE)

    def test_cosine_zero_candidate_gives_zero_score(self):
        query = np.array([1.0, 0.0])
        candidates = [np.array([0.0, 0.0]), np.array([1.0, 0.0])]
        scores = _score_all(query, candidates, SimilarityMetric.COSINE)
        assert scores[0] == 0.0
        assert scores[1] == pytest.approx(1.0)

    def test_cosine_zero_query_gives_all_zero(self):
        query = np.array([0.0, 0.0])
        candidates = [np.array([1.0, 0.0]), np.array([0.0, 1.0])]
        scores = _score_all(query, candidates, SimilarityMetric.COSINE)
        assert list(scores) == [0.0, 0.0]
