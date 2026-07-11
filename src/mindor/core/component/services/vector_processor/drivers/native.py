from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any, Union
from mindor.dsl.schema.component import VectorProcessorComponentConfig
from mindor.dsl.schema.action import (
    VectorProcessorActionConfig,
    VectorProcessorActionMethod,
    VectorSimilarityMetric,
)
from ..base import VectorProcessorService, VectorProcessorDriver, register_vector_processor_service
from ..base import ComponentActionContext
from .common import VectorProcessorAction
import asyncio
import numpy as np

class NativeVectorProcessorAction(VectorProcessorAction):
    # ---- pairwise metrics ----

    def _cosine_similarity(self, params: Dict[str, Any]) -> Any:
        vector = _as_array(params["vector"])
        other  = _as_array(params["other"])
        return _pairwise(vector, other, _cosine)

    def _dot_product(self, params: Dict[str, Any]) -> Any:
        vector = _as_array(params["vector"])
        other  = _as_array(params["other"])
        return _pairwise(vector, other, _dot)

    def _euclidean_distance(self, params: Dict[str, Any]) -> Any:
        vector = _as_array(params["vector"])
        other  = _as_array(params["other"])
        return _pairwise(vector, other, _euclidean)

    # ---- reductions / transforms ----

    def _normalize(self, params: Dict[str, Any]) -> Any:
        v = _as_array(params["vector"])
        if v.ndim == 1:
            n = float(np.linalg.norm(v))
            return (v / n if n > 0 else v).tolist()
        norms = np.linalg.norm(v, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (v / norms).tolist()

    def _mean(self, params: Dict[str, Any]) -> Any:
        vectors = _as_array(params["vectors"])
        axis = params["axis"]
        result = np.mean(vectors, axis=axis)
        return _to_python(result)

    def _sum(self, params: Dict[str, Any]) -> Any:
        vectors = _as_array(params["vectors"])
        axis = params["axis"]
        result = np.sum(vectors, axis=axis)
        return _to_python(result)

    # ---- ranking / filtering ----

    def _top_k(self, params: Dict[str, Any]) -> Any:
        query = _as_array(params["query"])
        candidates_raw = params["candidates"]
        k: int = params["k"]
        metric: VectorSimilarityMetric = params["metric"]
        flatten: bool = params["flatten"]

        flat_vecs, provenance = _flatten_candidates(candidates_raw, flatten)
        if not flat_vecs:
            return []

        scores = _score_all(query, flat_vecs, metric)
        # Higher-is-better for cosine/dot; lower-is-better for euclidean.
        better_first = metric != VectorSimilarityMetric.EUCLIDEAN
        order = np.argsort(scores)
        if better_first:
            order = order[::-1]

        results: List[Dict[str, Any]] = []
        for idx in order[:k]:
            entry = { "score": float(scores[idx]) }
            entry.update(provenance[idx])
            results.append(entry)
        return results

    def _threshold_filter(self, params: Dict[str, Any]) -> Any:
        query = _as_array(params["query"])
        candidates_raw = params["candidates"]
        threshold: float = params["threshold"]
        metric: VectorSimilarityMetric = params["metric"]
        flatten: bool = params["flatten"]

        flat_vecs, provenance = _flatten_candidates(candidates_raw, flatten)
        if not flat_vecs:
            return []

        scores = _score_all(query, flat_vecs, metric)
        keep_higher = metric != VectorSimilarityMetric.EUCLIDEAN

        results: List[Dict[str, Any]] = []
        for i, score in enumerate(scores):
            keep = score >= threshold if keep_higher else score <= threshold
            if keep:
                entry = { "score": float(score) }
                entry.update(provenance[i])
                results.append(entry)
        return results

# ---------------- helpers ----------------

def _as_array(value: Any) -> np.ndarray:
    if value is None:
        raise ValueError("Vector input is None.")
    arr = np.asarray(value, dtype=np.float64)
    return arr

def _to_python(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

def _dot(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))

def _euclidean(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))

def _pairwise(a: np.ndarray, b: np.ndarray, metric_fn) -> Union[float, List[float], List[List[float]]]:
    """Broadcast metric_fn over `a` and `b`.

    Rules:
      1D vs 1D -> float
      1D vs 2D -> [float, ...]   (each row of b vs a)
      2D vs 1D -> [float, ...]   (each row of a vs b)
      2D vs 2D -> [[float, ...], ...]  (pairwise all rows of a x all rows of b)
    """
    if a.ndim == 1 and b.ndim == 1:
        return metric_fn(a, b)
    if a.ndim == 1 and b.ndim == 2:
        return [metric_fn(a, row) for row in b]
    if a.ndim == 2 and b.ndim == 1:
        return [metric_fn(row, b) for row in a]
    if a.ndim == 2 and b.ndim == 2:
        return [[metric_fn(ra, rb) for rb in b] for ra in a]
    raise ValueError(f"Unsupported input shapes: a.ndim={a.ndim}, b.ndim={b.ndim}")

def _looks_nested(raw: List[Any]) -> bool:
    """Return True if `raw` is a list-of-list-of-scalar shape (per-group vectors).

    Robust against leading empty groups by scanning until it finds a probe item.
    """
    for item in raw:
        if not isinstance(item, list):
            return False
        if not item:  # empty group; keep scanning
            continue
        return isinstance(item[0], list)
    return False

def _flatten_candidates(raw: Any, flatten: bool) -> Tuple[List[np.ndarray], List[Dict[str, int]]]:
    """Normalize candidates to a flat list of vectors, keeping original indices.

    Supports two shapes when `flatten=True`:
      - List[Vector]              -> provenance: {"index": i}
      - List[List[Vector]]        -> provenance: {"outer_index": i, "inner_index": j}
        (e.g. per-frame list of per-face embeddings)

    When `flatten=False`, expects List[Vector] directly.
    """
    if raw is None:
        return [], []

    if not isinstance(raw, list):
        raise ValueError("`candidates` must be a list.")

    if not raw:
        return [], []

    vectors: List[np.ndarray] = []
    provenance: List[Dict[str, int]] = []

    is_nested = flatten and _looks_nested(raw)

    if is_nested:
        for i, group in enumerate(raw):
            if not isinstance(group, list):
                continue
            for j, vec in enumerate(group):
                if vec is None or (isinstance(vec, list) and not vec):
                    continue
                vectors.append(np.asarray(vec, dtype=np.float64))
                provenance.append({ "outer_index": i, "inner_index": j })
    else:
        for i, vec in enumerate(raw):
            if vec is None or (isinstance(vec, list) and not vec):
                continue
            vectors.append(np.asarray(vec, dtype=np.float64))
            provenance.append({ "index": i })

    return vectors, provenance

def _score_all(query: np.ndarray, candidates: List[np.ndarray], metric: VectorSimilarityMetric) -> np.ndarray:
    if query.ndim != 1:
        raise ValueError("`query` must be a 1D vector.")

    stacked = np.stack(candidates, axis=0)  # shape: (N, D)

    if metric == VectorSimilarityMetric.COSINE:
        qn = np.linalg.norm(query)
        cn = np.linalg.norm(stacked, axis=1)
        denom = cn * qn
        denom[denom == 0] = 1.0  # avoid divide-by-zero; those rows score 0 anyway
        scores = (stacked @ query) / denom
        # Force to 0 where a norm was actually 0
        scores[cn == 0] = 0.0
        if qn == 0:
            scores[:] = 0.0
        return scores

    if metric == VectorSimilarityMetric.DOT:
        return stacked @ query

    if metric == VectorSimilarityMetric.EUCLIDEAN:
        return np.linalg.norm(stacked - query, axis=1)

    raise ValueError(f"Unsupported similarity metric: {metric}")


@register_vector_processor_service(VectorProcessorDriver.NATIVE)
class NativeVectorProcessorService(VectorProcessorService):
    def __init__(self, id: str, config: VectorProcessorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def _run(self, action: VectorProcessorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await NativeVectorProcessorAction(action).run(context, loop)
