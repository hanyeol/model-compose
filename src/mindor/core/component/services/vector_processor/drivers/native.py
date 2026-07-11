from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import VectorProcessorComponentConfig
from mindor.dsl.schema.action import VectorProcessorActionConfig, SimilarityMetric, DistanceMetric, RankingMetric
from mindor.core.foundation.variable.vector import VectorValue
from ..base import VectorProcessorService, VectorProcessorDriver, register_vector_processor_service
from ..base import ComponentActionContext
from .common import VectorProcessorAction
import asyncio

if TYPE_CHECKING:
    import numpy as np

class NativeVectorProcessorAction(VectorProcessorAction):
    def _similarity(self, vector: VectorValue, other: VectorValue, params: Dict[str, Any]) -> Any:
        a = self._as_array(vector)
        b = self._as_array(other)

        return self._similarity_fn(params["metric"])(a, b)

    def _distance(self, vector: VectorValue, other: VectorValue, params: Dict[str, Any]) -> Any:
        a = self._as_array(vector)
        b = self._as_array(other)

        return self._distance_fn(params["metric"])(a, b)

    def _dot_product(self, vector: VectorValue, other: VectorValue, params: Dict[str, Any]) -> Any:
        import numpy as np

        a = self._as_array(vector)
        b = self._as_array(other)

        return float(np.dot(a, b))

    def _normalize(self, vector: VectorValue, params: Dict[str, Any]) -> Any:
        import numpy as np

        v = self._as_array(vector)
        n = float(np.linalg.norm(v))

        return (v / n if n > 0 else v).tolist()

    def _mean(self, vectors: List[VectorValue], params: Dict[str, Any]) -> Any:
        import numpy as np

        matrix = self._as_matrix(vectors)
        axis = params["axis"]
        result = np.mean(matrix, axis=axis)

        return self._as_native(result)

    def _sum(self, vectors: List[VectorValue], params: Dict[str, Any]) -> Any:
        import numpy as np

        matrix = self._as_matrix(vectors)
        axis = params["axis"]
        result = np.sum(matrix, axis=axis)

        return self._as_native(result)

    def _top_k(self, query: VectorValue, candidates: List[VectorValue], params: Dict[str, Any]) -> Any:
        import numpy as np

        q = self._as_array(query)
        k: int = params["k"]
        metric = params["metric"]

        vectors = self._as_array_list(candidates)
        scores = self._score(q, vectors, metric)

        order = np.argsort(scores)

        if isinstance(metric, SimilarityMetric):
            order = order[::-1]

        return [ { "index": int(index), "score": float(scores[index]) } for index in order[:k] ]

    def _threshold_filter(self, query: VectorValue, candidates: List[VectorValue], params: Dict[str, Any]) -> Any:
        q = self._as_array(query)
        threshold: float = params["threshold"]
        metric = params["metric"]

        vectors = self._as_array_list(candidates)
        scores = self._score(q, vectors, metric)
        keep_higher = isinstance(metric, SimilarityMetric)

        matches: List[Dict[str, Any]] = []

        for index, score in enumerate(scores):
            if (score >= threshold if keep_higher else score <= threshold):
                matches.append({ "index": index, "score": float(score) })

        return matches

    @staticmethod
    def _as_array(value: VectorValue) -> np.ndarray:
        import numpy as np

        return np.asarray(value.values, dtype=np.float64)

    @staticmethod
    def _as_array_list(value: List[VectorValue]) -> List[np.ndarray]:
        import numpy as np

        return [ np.asarray(v.values, dtype=np.float64) for v in value ]

    @staticmethod
    def _as_matrix(value: List[VectorValue]) -> np.ndarray:
        import numpy as np

        return np.asarray([ v.values for v in value ], dtype=np.float64)

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
    def _score(query: np.ndarray, candidates: List[np.ndarray], metric: RankingMetric) -> np.ndarray:
        import numpy as np

        stacked = np.stack(candidates, axis=0)  # shape: (N, D)

        if metric == SimilarityMetric.COSINE:
            qn = np.linalg.norm(query)
            cn = np.linalg.norm(stacked, axis=1)
            denom = cn * qn
            denom[denom == 0] = 1.0
            scores = (stacked @ query) / denom
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
