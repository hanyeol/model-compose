from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import (
    VectorProcessorActionConfig,
    VectorProcessorActionMethod,
    SimilarityMetric,
    DistanceMetric,
)
from mindor.core.foundation.variable.vector import VectorValue
from ..base import ComponentActionContext
import asyncio

class VectorProcessorAction:
    def __init__(self, config: VectorProcessorActionConfig):
        self.config: VectorProcessorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await asyncio.to_thread(self._process, self.config.method, params)

        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, method: VectorProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == VectorProcessorActionMethod.SIMILARITY:
            vector = await context.render_vector(self.config.vector)
            other  = await context.render_vector(self.config.other)
            metric = self._as_similarity_metric(await context.render_variable(self.config.metric))

            if vector is None:
                raise ValueError("'vector' must be specified for 'similarity' method")

            if other is None:
                raise ValueError("'other' must be specified for 'similarity' method")

            return { "vector": vector, "other": other, "metric": metric }

        if method == VectorProcessorActionMethod.DISTANCE:
            vector = await context.render_vector(self.config.vector)
            other  = await context.render_vector(self.config.other)
            metric = self._as_distance_metric(await context.render_variable(self.config.metric))

            if vector is None:
                raise ValueError("'vector' must be specified for 'distance' method")

            if other is None:
                raise ValueError("'other' must be specified for 'distance' method")

            return { "vector": vector, "other": other, "metric": metric }

        if method == VectorProcessorActionMethod.DOT_PRODUCT:
            vector = await context.render_vector(self.config.vector)
            other  = await context.render_vector(self.config.other)

            if vector is None:
                raise ValueError("'vector' must be specified for 'dot-product' method")

            if other is None:
                raise ValueError("'other' must be specified for 'dot-product' method")

            return { "vector": vector, "other": other }

        if method == VectorProcessorActionMethod.NORMALIZE:
            vector = await context.render_vector(self.config.vector)

            if vector is None:
                raise ValueError("'vector' must be specified for 'normalize' method")

            return { "vector": vector }

        if method == VectorProcessorActionMethod.MEAN:
            vectors = await context.render_vector_list(self.config.vectors)
            axis    = await context.render_variable(self.config.axis)

            if vectors is None:
                raise ValueError("'vectors' must be specified for 'mean' method")

            return { "vectors": vectors, "axis": int(axis) if axis is not None else 0 }

        if method == VectorProcessorActionMethod.SUM:
            vectors = await context.render_vector_list(self.config.vectors)
            axis    = await context.render_variable(self.config.axis)

            if vectors is None:
                raise ValueError("'vectors' must be specified for 'sum' method")

            return { "vectors": vectors, "axis": int(axis) if axis is not None else 0 }

        if method == VectorProcessorActionMethod.TOP_K:
            query      = await context.render_vector(self.config.query)
            candidates = await context.render_vector_list(self.config.candidates)
            k          = await context.render_variable(self.config.k)
            metric     = self._as_ranking_metric(await context.render_variable(self.config.metric))

            if query is None:
                raise ValueError("'query' must be specified for 'top-k' method")

            if candidates is None:
                raise ValueError("'candidates' must be specified for 'top-k' method")

            return {
                "query": query,
                "candidates": candidates,
                "k": int(k) if k is not None else 1,
                "metric": metric,
            }

        if method == VectorProcessorActionMethod.THRESHOLD_FILTER:
            query      = await context.render_vector(self.config.query)
            candidates = await context.render_vector_list(self.config.candidates)
            threshold  = await context.render_variable(self.config.threshold)
            metric     = self._as_ranking_metric(await context.render_variable(self.config.metric))

            if query is None:
                raise ValueError("'query' must be specified for 'threshold-filter' method")

            if candidates is None:
                raise ValueError("'candidates' must be specified for 'threshold-filter' method")

            if threshold is None:
                raise ValueError("'threshold' must be specified for 'threshold-filter' method")

            return {
                "query": query,
                "candidates": candidates,
                "threshold": float(threshold),
                "metric": metric,
            }

        raise ValueError(f"Unsupported vector processor action method: {method}")

    def _process(self, method: VectorProcessorActionMethod, params: Dict[str, Any]) -> Any:
        if method == VectorProcessorActionMethod.SIMILARITY:
            vector = params.pop("vector")
            other  = params.pop("other")

            if isinstance(vector, list) and isinstance(other, list):
                if len(vector) != len(other):
                    raise ValueError(f"'vector' and 'other' length mismatch: {len(vector)} vs {len(other)}")
                return [ self._similarity(v, o, params) for v, o in zip(vector, other) ]

            if isinstance(vector, list):
                return [ self._similarity(v, other, params) for v in vector ]

            if isinstance(other, list):
                return [ self._similarity(vector, o, params) for o in other ]

            return self._similarity(vector, other, params)

        if method == VectorProcessorActionMethod.DISTANCE:
            vector = params.pop("vector")
            other  = params.pop("other")

            if isinstance(vector, list) and isinstance(other, list):
                if len(vector) != len(other):
                    raise ValueError(f"'vector' and 'other' length mismatch: {len(vector)} vs {len(other)}")
                return [ self._distance(v, o, params) for v, o in zip(vector, other) ]

            if isinstance(vector, list):
                return [ self._distance(v, other, params) for v in vector ]

            if isinstance(other, list):
                return [ self._distance(vector, o, params) for o in other ]

            return self._distance(vector, other, params)

        if method == VectorProcessorActionMethod.DOT_PRODUCT:
            vector = params.pop("vector")
            other  = params.pop("other")

            if isinstance(vector, list) and isinstance(other, list):
                if len(vector) != len(other):
                    raise ValueError(f"'vector' and 'other' length mismatch: {len(vector)} vs {len(other)}")
                return [ self._dot_product(v, o, params) for v, o in zip(vector, other) ]

            if isinstance(vector, list):
                return [ self._dot_product(v, other, params) for v in vector ]

            if isinstance(other, list):
                return [ self._dot_product(vector, o, params) for o in other ]

            return self._dot_product(vector, other, params)

        if method == VectorProcessorActionMethod.NORMALIZE:
            vector = params.pop("vector")

            if isinstance(vector, list):
                return [ self._normalize(v, params) for v in vector ]

            return self._normalize(vector, params)

        if method == VectorProcessorActionMethod.MEAN:
            vectors = params.pop("vectors")

            return self._mean(vectors, params)

        if method == VectorProcessorActionMethod.SUM:
            vectors = params.pop("vectors")

            return self._sum(vectors, params)

        if method == VectorProcessorActionMethod.TOP_K:
            query      = params.pop("query")
            candidates = params.pop("candidates")

            if isinstance(query, list):
                return [ self._top_k(q, candidates, params) for q in query ]

            return self._top_k(query, candidates, params)

        if method == VectorProcessorActionMethod.THRESHOLD_FILTER:
            query      = params.pop("query")
            candidates = params.pop("candidates")

            if isinstance(query, list):
                return [ self._threshold_filter(q, candidates, params) for q in query ]

            return self._threshold_filter(query, candidates, params)

        raise ValueError(f"Unsupported vector processor action method: {method}")

    @abstractmethod
    def _similarity(self, vector: VectorValue, other: VectorValue, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _distance(self, vector: VectorValue, other: VectorValue, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _dot_product(self, vector: VectorValue, other: VectorValue, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _normalize(self, vector: VectorValue, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _mean(self, vectors: List[VectorValue], params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _sum(self, vectors: List[VectorValue], params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _top_k(self, query: VectorValue, candidates: List[VectorValue], params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _threshold_filter(self, query: VectorValue, candidates: List[VectorValue], params: Dict[str, Any]) -> Any:
        pass

    @staticmethod
    def _as_similarity_metric(value: Any) -> SimilarityMetric:
        try:
            return SimilarityMetric(value)
        except ValueError:
            raise ValueError(f"Invalid similarity metric: {value}")

    @staticmethod
    def _as_distance_metric(value: Any) -> DistanceMetric:
        try:
            return DistanceMetric(value)
        except ValueError:
            raise ValueError(f"Invalid distance metric: {value}")

    @staticmethod
    def _as_ranking_metric(value: Any) -> Union[SimilarityMetric, DistanceMetric]:
        """Ranking metrics may be either a similarity or a distance measure.

        The sign convention (higher-is-better vs lower-is-better) is decided by
        which enum the value belongs to.
        """
        try:
            return SimilarityMetric(value)
        except ValueError:
            pass
        try:
            return DistanceMetric(value)
        except ValueError:
            raise ValueError(f"Invalid ranking metric: {value}")
