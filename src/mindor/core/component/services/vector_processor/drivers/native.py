from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Tuple, Any
from mindor.dsl.schema.component import VectorProcessorComponentConfig
from mindor.dsl.schema.action import (
    VectorProcessorActionConfig,
    VectorProcessorActionMethod,
    SimilarityMetric,
    DistanceMetric,
)
from ..base import VectorProcessorService, VectorProcessorDriver, register_vector_processor_service
from ..base import ComponentActionContext
from .common import VectorProcessorAction
import asyncio

if TYPE_CHECKING:
    import numpy as np

class NativeVectorProcessorAction(VectorProcessorAction):
    def _similarity(self, params: Dict[str, Any]) -> Any:
        vector = self._as_array(params["vector"])
        other  = self._as_array(params["other"])

        return self._pairwise(vector, other, self._similarity_fn(params["metric"]))

    def _distance(self, params: Dict[str, Any]) -> Any:
        vector = self._as_array(params["vector"])
        other  = self._as_array(params["other"])

        return self._pairwise(vector, other, self._distance_fn(params["metric"]))

    def _dot_product(self, params: Dict[str, Any]) -> Any:
        vector = self._as_array(params["vector"])
        other  = self._as_array(params["other"])

        return self._pairwise(vector, other, self._dot)

    def _normalize(self, params: Dict[str, Any]) -> Any:
        import numpy as np

        v = self._as_array(params["vector"])
        if v.ndim == 1:
            n = float(np.linalg.norm(v))
            return (v / n if n > 0 else v).tolist()
        norms = np.linalg.norm(v, axis=1, keepdims=True)
        norms[norms == 0] = 1.0

        return (v / norms).tolist()

    def _mean(self, params: Dict[str, Any]) -> Any:
        import numpy as np

        vectors = self._as_array(params["vectors"])
        axis = params["axis"]
        result = np.mean(vectors, axis=axis)

        return self._as_native(result)

    def _sum(self, params: Dict[str, Any]) -> Any:
        import numpy as np

        vectors = self._as_array(params["vectors"])
        axis = params["axis"]
        result = np.sum(vectors, axis=axis)

        return self._as_native(result)

    def _top_k(self, params: Dict[str, Any]) -> Any:
        import numpy as np

        query = self._as_array(params["query"])
        k: int = params["k"]
        metric = params["metric"]

        vectors, provenance = self._normalize_candidates(params["candidates"])

        if not vectors:
            return []

        scores = self._score_all(query, vectors, metric)

        # Similarity: higher-is-better; distance: lower-is-better.
        order = np.argsort(scores)

        if isinstance(metric, SimilarityMetric):
            order = order[::-1]

        results: List[Dict[str, Any]] = []

        for index in order[:k]:
            result = { "score": float(scores[index]) }
            result.update(provenance[index])
            results.append(result)

        return results

    def _threshold_filter(self, params: Dict[str, Any]) -> Any:
        query = self._as_array(params["query"])
        threshold: float = params["threshold"]
        metric = params["metric"]

        vectors, provenance = self._normalize_candidates(params["candidates"])
        if not vectors:
            return []

        scores = self._score_all(query, vectors, metric)
        keep_higher = isinstance(metric, SimilarityMetric)

        results: List[Dict[str, Any]] = []

        for index, score in enumerate(scores):
            keep = score >= threshold if keep_higher else score <= threshold
            if keep:
                result = { "score": float(score) }
                result.update(provenance[index])
                results.append(result)

        return results

    @staticmethod
    def _as_array(value: Any) -> np.ndarray:
        import numpy as np

        if value is None:
            raise ValueError("Vector input is None.")
        return np.asarray(value, dtype=np.float64)

    @staticmethod
    def _as_native(value: Any) -> Any:
        import numpy as np

        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (np.floating, np.integer)):
            return value.item()
        return value

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        import numpy as np

        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    @staticmethod
    def _euclidean(a: np.ndarray, b: np.ndarray) -> float:
        import numpy as np

        return float(np.linalg.norm(a - b))

    @staticmethod
    def _dot(a: np.ndarray, b: np.ndarray) -> float:
        import numpy as np

        return float(np.dot(a, b))

    @staticmethod
    def _similarity_fn(metric: SimilarityMetric):
        if metric == SimilarityMetric.COSINE:
            return NativeVectorProcessorAction._cosine
        raise ValueError(f"Unsupported similarity metric: {metric}")

    @staticmethod
    def _distance_fn(metric: DistanceMetric):
        if metric == DistanceMetric.EUCLIDEAN:
            return NativeVectorProcessorAction._euclidean
        raise ValueError(f"Unsupported distance metric: {metric}")

    @staticmethod
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

    @staticmethod
    def _normalize_candidates(raw: Any) -> Tuple[List[np.ndarray], List[Dict[str, int]]]:
        """Normalize a flat list of vectors and pair each with its original index.

        Input must be `List[Vector]`. `None` entries or empty vectors are dropped
        but original indices are preserved for surviving vectors.
        """
        import numpy as np

        if raw is None:
            return [], []

        if not isinstance(raw, list):
            raise ValueError("`candidates` must be a list.")

        vectors: List[np.ndarray] = []
        provenance: List[Dict[str, int]] = []

        for index, vector in enumerate(raw):
            if vector is None or (isinstance(vector, list) and not vector):
                continue
            vectors.append(np.asarray(vector, dtype=np.float64))
            provenance.append({ "index": index })

        return vectors, provenance

    @staticmethod
    def _score_all(query: np.ndarray, candidates: List[np.ndarray], metric: Union[SimilarityMetric, DistanceMetric]) -> np.ndarray:
        import numpy as np

        if query.ndim != 1:
            raise ValueError("`query` must be a 1D vector.")

        stacked = np.stack(candidates, axis=0)  # shape: (N, D)

        if metric == SimilarityMetric.COSINE:
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

        if metric == DistanceMetric.EUCLIDEAN:
            return np.linalg.norm(stacked - query, axis=1)

        raise ValueError(f"Unsupported ranking metric: {metric}")

@register_vector_processor_service(VectorProcessorDriver.NATIVE)
class NativeVectorProcessorService(VectorProcessorService):
    def __init__(self, id: str, config: VectorProcessorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "numpy" ]

    async def _run(self, action: VectorProcessorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await NativeVectorProcessorAction(action).run(context, loop)
