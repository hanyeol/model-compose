from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import (
    VectorProcessorActionConfig,
    VectorProcessorActionMethod,
    VectorSimilarityMetric,
)
from ..base import ComponentActionContext
import asyncio

class VectorProcessorAction:
    def __init__(self, config: VectorProcessorActionConfig):
        self.config: VectorProcessorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        method: VectorProcessorActionMethod = self.config.method
        params = await self._resolve_params(method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await asyncio.to_thread(self._process, method, params)

        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, method: VectorProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == VectorProcessorActionMethod.COSINE_SIMILARITY:
            vector = await context.render_variable(self.config.vector)
            other  = await context.render_variable(self.config.other)

            return { "vector": vector, "other": other }

        if method == VectorProcessorActionMethod.DOT_PRODUCT:
            vector = await context.render_variable(self.config.vector)
            other  = await context.render_variable(self.config.other)

            return { "vector": vector, "other": other }

        if method == VectorProcessorActionMethod.EUCLIDEAN_DISTANCE:
            vector = await context.render_variable(self.config.vector)
            other  = await context.render_variable(self.config.other)

            return { "vector": vector, "other": other }

        if method == VectorProcessorActionMethod.NORMALIZE:
            vector = await context.render_variable(self.config.vector)

            return { "vector": vector }

        if method == VectorProcessorActionMethod.MEAN:
            vectors = await context.render_variable(self.config.vectors)
            axis = await context.render_variable(self.config.axis)

            return { "vectors": vectors, "axis": int(axis) if axis is not None else 0 }

        if method == VectorProcessorActionMethod.SUM:
            vectors = await context.render_variable(self.config.vectors)
            axis = await context.render_variable(self.config.axis)

            return { "vectors": vectors, "axis": int(axis) if axis is not None else 0 }

        if method == VectorProcessorActionMethod.TOP_K:
            query      = await context.render_variable(self.config.query)
            candidates = await context.render_variable(self.config.candidates)
            k          = await context.render_variable(self.config.k)
            metric     = await context.render_variable(self.config.metric)
            flatten    = await context.render_variable(self.config.flatten)

            try:
                metric = VectorSimilarityMetric(metric)
            except ValueError:
                raise ValueError(f"Invalid similarity metric: {metric}")

            return {
                "query": query,
                "candidates": candidates,
                "k": int(k) if k is not None else 1,
                "metric": metric,
                "flatten": bool(flatten) if flatten is not None else True,
            }

        if method == VectorProcessorActionMethod.THRESHOLD_FILTER:
            query      = await context.render_variable(self.config.query)
            candidates = await context.render_variable(self.config.candidates)
            threshold  = await context.render_variable(self.config.threshold)
            metric     = await context.render_variable(self.config.metric)
            flatten    = await context.render_variable(self.config.flatten)

            if threshold is None:
                raise ValueError("'threshold' must be specified for 'threshold-filter' method")

            try:
                metric = VectorSimilarityMetric(metric)
            except ValueError:
                raise ValueError(f"Invalid similarity metric: {metric}")

            return {
                "query": query,
                "candidates": candidates,
                "threshold": float(threshold),
                "metric": metric,
                "flatten": bool(flatten) if flatten is not None else True,
            }

        raise ValueError(f"Unsupported vector processor action method: {method}")

    def _process(self, method: VectorProcessorActionMethod, params: Dict[str, Any]) -> Any:
        if method == VectorProcessorActionMethod.COSINE_SIMILARITY:
            return self._cosine_similarity(params)

        if method == VectorProcessorActionMethod.DOT_PRODUCT:
            return self._dot_product(params)

        if method == VectorProcessorActionMethod.EUCLIDEAN_DISTANCE:
            return self._euclidean_distance(params)

        if method == VectorProcessorActionMethod.NORMALIZE:
            return self._normalize(params)

        if method == VectorProcessorActionMethod.MEAN:
            return self._mean(params)

        if method == VectorProcessorActionMethod.SUM:
            return self._sum(params)

        if method == VectorProcessorActionMethod.TOP_K:
            return self._top_k(params)

        if method == VectorProcessorActionMethod.THRESHOLD_FILTER:
            return self._threshold_filter(params)

        raise ValueError(f"Unsupported vector processor action method: {method}")

    @abstractmethod
    def _cosine_similarity(self, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _dot_product(self, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _euclidean_distance(self, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _normalize(self, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _mean(self, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _sum(self, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _top_k(self, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def _threshold_filter(self, params: Dict[str, Any]) -> Any:
        pass
