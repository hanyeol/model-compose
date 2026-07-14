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
from mindor.core.foundation.variable.vector import VectorValue
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import ComponentActionContext
import asyncio

class VectorProcessorAction:
    def __init__(self, config: VectorProcessorActionConfig):
        self.config: VectorProcessorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        batch_size = await context.render_variable(self.config.batch_size)

        input, is_single_input, streaming, params = await self._prepare_input(self.config.method, context)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if streaming:
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
    ) -> Tuple[Any, bool, bool, Dict[str, Any]]:
        if method == VectorProcessorActionMethod.SIMILARITY:
            vector = await context.render_vector(self.config.vector)
            other  = await context.render_vector(self.config.other)
            metric = self._as_similarity_metric(await context.render_variable(self.config.metric))

            if vector is None:
                raise ValueError("'vector' must be specified for 'similarity' method")

            if other is None:
                raise ValueError("'other' must be specified for 'similarity' method")

            is_single_input = isinstance(vector, VectorValue) and isinstance(other, VectorValue)
            streaming = isinstance(vector, (StreamIterator, AsyncIterator)) or isinstance(other, (StreamIterator, AsyncIterator))

            return (vector, other), is_single_input, streaming, { "metric": metric }

        if method == VectorProcessorActionMethod.DISTANCE:
            vector = await context.render_vector(self.config.vector)
            other  = await context.render_vector(self.config.other)
            metric = self._as_distance_metric(await context.render_variable(self.config.metric))

            if vector is None:
                raise ValueError("'vector' must be specified for 'distance' method")

            if other is None:
                raise ValueError("'other' must be specified for 'distance' method")

            is_single_input = isinstance(vector, VectorValue) and isinstance(other, VectorValue)
            streaming = isinstance(vector, (StreamIterator, AsyncIterator)) or isinstance(other, (StreamIterator, AsyncIterator))

            return (vector, other), is_single_input, streaming, { "metric": metric }

        if method == VectorProcessorActionMethod.DOT_PRODUCT:
            vector = await context.render_vector(self.config.vector)
            other  = await context.render_vector(self.config.other)

            if vector is None:
                raise ValueError("'vector' must be specified for 'dot-product' method")

            if other is None:
                raise ValueError("'other' must be specified for 'dot-product' method")

            is_single_input = isinstance(vector, VectorValue) and isinstance(other, VectorValue)
            streaming = isinstance(vector, (StreamIterator, AsyncIterator)) or isinstance(other, (StreamIterator, AsyncIterator))

            return (vector, other), is_single_input, streaming, {}

        if method == VectorProcessorActionMethod.NORMALIZE:
            vector = await context.render_vector(self.config.vector)

            if vector is None:
                raise ValueError("'vector' must be specified for 'normalize' method")

            is_single_input = isinstance(vector, VectorValue)
            streaming = isinstance(vector, (StreamIterator, AsyncIterator))

            return (vector,), is_single_input, streaming, {}

        if method == VectorProcessorActionMethod.MEAN:
            vectors = await context.render_vector_list(self.config.vectors)
            axis    = await context.render_variable(self.config.axis)

            if vectors is None:
                raise ValueError("'vectors' must be specified for 'mean' method")

            is_single_input = not isinstance(vectors, (StreamIterator, AsyncIterator))
            streaming       = isinstance(vectors, (StreamIterator, AsyncIterator))
            batches         = vectors if streaming else [ vectors ]

            return (batches,), is_single_input, streaming, { "axis": int(axis) if axis is not None else 0 }

        if method == VectorProcessorActionMethod.SUM:
            vectors = await context.render_vector_list(self.config.vectors)
            axis    = await context.render_variable(self.config.axis)

            if vectors is None:
                raise ValueError("'vectors' must be specified for 'sum' method")

            is_single_input = not isinstance(vectors, (StreamIterator, AsyncIterator))
            streaming       = isinstance(vectors, (StreamIterator, AsyncIterator))
            batches         = vectors if streaming else [ vectors ]

            return (batches,), is_single_input, streaming, { "axis": int(axis) if axis is not None else 0 }

        if method == VectorProcessorActionMethod.TOP_K:
            query      = await context.render_vector(self.config.query)
            candidates = await context.render_vector_list(self.config.candidates)
            k          = await context.render_variable(self.config.k)
            metric     = self._as_ranking_metric(await context.render_variable(self.config.metric))

            if query is None:
                raise ValueError("'query' must be specified for 'top-k' method")

            if candidates is None:
                raise ValueError("'candidates' must be specified for 'top-k' method")

            is_single_input = isinstance(query, VectorValue)
            streaming = isinstance(query, (StreamIterator, AsyncIterator))

            return (query,), is_single_input, streaming, {
                "candidates": candidates,
                "k":          int(k) if k is not None else 1,
                "metric":     metric,
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

            is_single_input = isinstance(query, VectorValue)
            streaming = isinstance(query, (StreamIterator, AsyncIterator))

            return (query,), is_single_input, streaming, {
                "candidates": candidates,
                "threshold":  float(threshold),
                "metric":     metric,
            }

        raise ValueError(f"Unsupported vector processor action method: {method}")

    def _process(self, method: VectorProcessorActionMethod, batch: Tuple[Any, ...], params: Dict[str, Any]) -> List[Any]:
        if method == VectorProcessorActionMethod.SIMILARITY:
            return self._similarity(batch[0], batch[1], params)

        if method == VectorProcessorActionMethod.DISTANCE:
            return self._distance(batch[0], batch[1], params)

        if method == VectorProcessorActionMethod.DOT_PRODUCT:
            return self._dot_product(batch[0], batch[1], params)

        if method == VectorProcessorActionMethod.NORMALIZE:
            return self._normalize(batch[0], params)

        if method == VectorProcessorActionMethod.MEAN:
            return self._mean(batch[0], params)

        if method == VectorProcessorActionMethod.SUM:
            return self._sum(batch[0], params)

        if method == VectorProcessorActionMethod.TOP_K:
            return self._top_k(batch[0], params["candidates"], params)

        if method == VectorProcessorActionMethod.THRESHOLD_FILTER:
            return self._threshold_filter(batch[0], params["candidates"], params)

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
    def _normalize(self, vectors: List[VectorValue], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _mean(self, batches: List[List[VectorValue]], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _sum(self, batches: List[List[VectorValue]], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _top_k(self, queries: List[VectorValue], candidates: List[VectorValue], params: Dict[str, Any]) -> List[Any]:
        pass

    @abstractmethod
    def _threshold_filter(self, queries: List[VectorValue], candidates: List[VectorValue], params: Dict[str, Any]) -> List[Any]:
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
