from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import (
    VectorProcessorActionConfig,
    VectorProcessorActionMethod,
    SimilarityMetric,
    DistanceMetric,
    RankingMetric,
)
from mindor.core.foundation.variable.vector import VectorValue, VectorArrayValue
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import ComponentActionContext
import asyncio

class VectorProcessorAction:
    def __init__(self, config: VectorProcessorActionConfig):
        self.config: VectorProcessorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator(source=input):
                async for batch in BatchSourceIterator(source, batch_size=batch_size or 1):
                    for result in self._process(self.config.method, batch, params):
                        yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch in BatchSourceIterator(input, batch_size=batch_size or 1):
                results.extend(self._process(self.config.method, batch, params))

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: VectorProcessorActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        if method in (
            VectorProcessorActionMethod.SIMILARITY,
            VectorProcessorActionMethod.DISTANCE,
            VectorProcessorActionMethod.DOT_PRODUCT,
        ):
            vector = await context.render_vector(self.config.vector)
            other  = await context.render_vector(self.config.other)

            if vector is None:
                raise ValueError(f"'vector' must be specified for '{method.value}' method")

            if other is None:
                raise ValueError(f"'other' must be specified for '{method.value}' method")

            is_single_input = isinstance(vector, VectorValue) and isinstance(other, VectorValue)
            is_streaming_input = isinstance(vector, (StreamIterator, AsyncIterator)) or isinstance(other, (StreamIterator, AsyncIterator))

            return (vector, other), is_single_input, is_streaming_input

        if method in (VectorProcessorActionMethod.TOP_K, VectorProcessorActionMethod.THRESHOLD_FILTER):
            query      = await context.render_vector(self.config.query)
            candidates = await context.render_vector_array(self.config.candidates)

            if query is None:
                raise ValueError(f"'query' must be specified for '{method.value}' method")

            if candidates is None:
                raise ValueError(f"'candidates' must be specified for '{method.value}' method")

            is_single_input = isinstance(query, VectorValue) and isinstance(candidates, VectorArrayValue)
            is_streaming_input = isinstance(query, (StreamIterator, AsyncIterator)) or isinstance(candidates, (StreamIterator, AsyncIterator))

            return (query, candidates), is_single_input, is_streaming_input

        if method == VectorProcessorActionMethod.NORMALIZE:
            vector = await context.render_vector(self.config.vector)

            if vector is None:
                raise ValueError("'vector' must be specified for 'normalize' method")

            is_single_input = isinstance(vector, VectorValue)
            is_streaming_input = isinstance(vector, (StreamIterator, AsyncIterator))

            return (vector,), is_single_input, is_streaming_input

        if method in (VectorProcessorActionMethod.MEAN, VectorProcessorActionMethod.SUM):
            vectors = await context.render_vector_array(self.config.vectors)

            if vectors is None:
                raise ValueError(f"'vectors' must be specified for '{method.value}' method")

            is_single_input = isinstance(vectors, VectorArrayValue)
            is_streaming_input = isinstance(vectors, (StreamIterator, AsyncIterator))

            return (vectors,), is_single_input, is_streaming_input

        raise ValueError(f"Unsupported vector processor action method: {method}")

    async def _resolve_params(
        self,
        method: VectorProcessorActionMethod,
        context: ComponentActionContext,
    ) -> Dict[str, Any]:
        if method == VectorProcessorActionMethod.SIMILARITY:
            metric = self._as_similarity_metric(await context.render_variable(self.config.metric))

            return { "metric": metric }

        if method == VectorProcessorActionMethod.DISTANCE:
            metric = self._as_distance_metric(await context.render_variable(self.config.metric))

            return { "metric": metric }

        if method == VectorProcessorActionMethod.DOT_PRODUCT:
            return {}

        if method == VectorProcessorActionMethod.TOP_K:
            k      = await context.render_variable(self.config.k)
            metric = self._as_ranking_metric(await context.render_variable(self.config.metric))

            return {
                "k":      int(k) if k is not None else 1,
                "metric": metric,
            }

        if method == VectorProcessorActionMethod.THRESHOLD_FILTER:
            threshold = await context.render_variable(self.config.threshold)
            metric    = self._as_ranking_metric(await context.render_variable(self.config.metric))

            if threshold is None:
                raise ValueError("'threshold' must be specified for 'threshold-filter' method")

            return {
                "threshold": float(threshold),
                "metric":    metric,
            }

        if method == VectorProcessorActionMethod.NORMALIZE:
            return {}

        if method in (VectorProcessorActionMethod.MEAN, VectorProcessorActionMethod.SUM):
            axis = await context.render_variable(self.config.axis)

            return { "axis": int(axis) if axis is not None else 0 }

        raise ValueError(f"Unsupported vector processor action method: {method}")

    def _process(self, method: VectorProcessorActionMethod, batch: Tuple[Any, ...], params: Dict[str, Any]) -> List[Any]:
        if method == VectorProcessorActionMethod.SIMILARITY:
            return self._similarity(batch[0], batch[1], params)

        if method == VectorProcessorActionMethod.DISTANCE:
            return self._distance(batch[0], batch[1], params)

        if method == VectorProcessorActionMethod.DOT_PRODUCT:
            return self._dot_product(batch[0], batch[1], params)

        if method == VectorProcessorActionMethod.TOP_K:
            return self._top_k(batch[0], batch[1], params)

        if method == VectorProcessorActionMethod.THRESHOLD_FILTER:
            return self._threshold_filter(batch[0], batch[1], params)

        if method == VectorProcessorActionMethod.NORMALIZE:
            return self._normalize(batch[0], params)

        if method == VectorProcessorActionMethod.MEAN:
            return self._mean(batch[0], params)

        if method == VectorProcessorActionMethod.SUM:
            return self._sum(batch[0], params)

        raise ValueError(f"Unsupported vector processor action method: {method}")


    @abstractmethod
    def _similarity(self, vectors: List[VectorValue], others: List[VectorValue], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _distance(self, vectors: List[VectorValue], others: List[VectorValue], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _dot_product(self, vectors: List[VectorValue], others: List[VectorValue], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _top_k(self, queries: List[VectorValue], candidates: List[VectorArrayValue], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _threshold_filter(self, queries: List[VectorValue], candidates: List[VectorArrayValue], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _normalize(self, vectors: List[VectorValue], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _mean(self, batches: List[VectorArrayValue], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _sum(self, batches: List[VectorArrayValue], params: Dict[str, Any]) -> List[Any]:
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
    def _as_ranking_metric(value: Any) -> RankingMetric:
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
