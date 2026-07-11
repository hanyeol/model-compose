"""Pure-numpy helper tests for the native vector-processor driver.

These bypass ComponentActionContext and pydantic to exercise the internal
math primitives directly. Anything the end-to-end tests would find hard to
diagnose (matrix construction, numeric edge cases, metric functions) belongs here.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from mindor.core.component.services.vector_processor.drivers.native import NativeVectorProcessorAction as _NA
from mindor.core.foundation.variable.vector import VectorValue
from mindor.dsl.schema.action import SimilarityMetric, DistanceMetric

_as_array      = _NA._as_array
_as_array_list = _NA._as_array_list
_as_matrix     = _NA._as_matrix
_as_native     = _NA._as_native
_cosine        = _NA._cosine
_euclidean     = _NA._euclidean
_score         = _NA._score


def _v(values) -> VectorValue:
    return VectorValue(list(values))


# ------------------------------------------------------------------ #
# _as_array (VectorValue -> np.ndarray)                              #
# ------------------------------------------------------------------ #

class TestAsArray:

    def test_basic_1d(self):
        arr = _as_array(_v([1, 2, 3]))
        assert arr.shape == (3,)
        assert arr.dtype == np.float64

    def test_int_and_float_promoted_to_float64(self):
        arr = _as_array(_v([1, 2.5, 3]))
        assert arr.dtype == np.float64


# ------------------------------------------------------------------ #
# _as_array_list (List[VectorValue] -> List[np.ndarray])             #
# ------------------------------------------------------------------ #

class TestAsArrayList:

    def test_multiple(self):
        arrays = _as_array_list([_v([1, 0]), _v([0, 1])])
        assert len(arrays) == 2
        assert all(a.shape == (2,) for a in arrays)

    def test_empty(self):
        assert _as_array_list([]) == []


# ------------------------------------------------------------------ #
# _as_matrix (List[VectorValue] -> 2D ndarray)                       #
# ------------------------------------------------------------------ #

class TestAsMatrix:

    def test_shape(self):
        matrix = _as_matrix([_v([1, 2]), _v([3, 4]), _v([5, 6])])
        assert matrix.shape == (3, 2)

    def test_dtype(self):
        matrix = _as_matrix([_v([1, 2]), _v([3, 4])])
        assert matrix.dtype == np.float64


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


class TestEuclidean:

    def test_3_4_5(self):
        assert _euclidean(np.array([0.0, 0.0]), np.array([3.0, 4.0])) == pytest.approx(5.0)

    def test_identical_zero(self):
        assert _euclidean(np.array([1.0, 2.0]), np.array([1.0, 2.0])) == 0.0


# ------------------------------------------------------------------ #
# _score                                                             #
# ------------------------------------------------------------------ #

class TestScore:

    def test_cosine(self):
        query = np.array([1.0, 0.0])
        candidates = [np.array([1.0, 0.0]), np.array([0.0, 1.0]), np.array([-1.0, 0.0])]
        scores = _score(query, candidates, SimilarityMetric.COSINE)
        assert scores == pytest.approx([1.0, 0.0, -1.0])

    def test_euclidean(self):
        query = np.array([0.0, 0.0])
        candidates = [np.array([3.0, 4.0]), np.array([0.0, 0.0]), np.array([1.0, 1.0])]
        scores = _score(query, candidates, DistanceMetric.EUCLIDEAN)
        assert scores == pytest.approx([5.0, 0.0, math.sqrt(2.0)])

    def test_cosine_zero_candidate_gives_zero_score(self):
        query = np.array([1.0, 0.0])
        candidates = [np.array([0.0, 0.0]), np.array([1.0, 0.0])]
        scores = _score(query, candidates, SimilarityMetric.COSINE)
        assert scores[0] == 0.0
        assert scores[1] == pytest.approx(1.0)

    def test_cosine_zero_query_gives_all_zero(self):
        query = np.array([0.0, 0.0])
        candidates = [np.array([1.0, 0.0]), np.array([0.0, 1.0])]
        scores = _score(query, candidates, SimilarityMetric.COSINE)
        assert list(scores) == [0.0, 0.0]
