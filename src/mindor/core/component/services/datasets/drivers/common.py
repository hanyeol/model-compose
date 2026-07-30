from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.action import DatasetsActionConfig, DatasetsActionMethod
from mindor.core.foundation.cancellation import CancellationToken
from ....action.base import ComponentAction
from ..base import ComponentActionContext
from ..utils import format_template_example
import os

if TYPE_CHECKING:
    from datasets import Dataset

class DatasetsAction(ComponentAction):
    def __init__(self, config: DatasetsActionConfig):
        self.config: DatasetsActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(self.config.method, params, context.cancellation_token)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, method: DatasetsActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == DatasetsActionMethod.LOAD:
            fraction       = await context.render_variable(self.config.fraction)
            shuffle        = await context.render_variable(self.config.shuffle)
            split          = await context.render_variable(self.config.split)
            streaming      = await context.render_variable(self.config.streaming)
            keep_in_memory = await context.render_variable(self.config.keep_in_memory)
            cache_dir      = await context.render_variable(self.config.cache_dir)
            save_infos     = await context.render_variable(self.config.save_infos)

            if cache_dir:
                cache_dir = os.path.expanduser(cache_dir)

            return {
                "fraction":       fraction,
                "shuffle":        shuffle,
                "split":          split,
                "streaming":      streaming,
                "keep_in_memory": keep_in_memory,
                "cache_dir":      cache_dir,
                "save_infos":     save_infos,
            }

        if method == DatasetsActionMethod.CONCAT:
            datasets  = await context.render_variable(self.config.datasets)
            direction = await context.render_variable(self.config.direction)
            info      = await context.render_variable(self.config.info)
            split     = await context.render_variable(self.config.split)

            return {
                "datasets":  datasets,
                "direction": direction,
                "info":      info,
                "split":     split,
            }

        if method == DatasetsActionMethod.SELECT:
            dataset = await context.render_variable(self.config.dataset)
            axis    = await context.render_variable(self.config.axis)
            indices = await context.render_variable(self.config.indices)
            columns = await context.render_variable(self.config.columns)

            return {
                "dataset": dataset,
                "axis":    axis,
                "indices": indices,
                "columns": columns,
            }

        if method == DatasetsActionMethod.MAP:
            dataset        = await context.render_variable(self.config.dataset)
            template       = await context.render_variable(self.config.template)
            output_column  = await context.render_variable(self.config.output_column)
            remove_columns = await context.render_variable(self.config.remove_columns)

            return {
                "dataset":        dataset,
                "template":       template,
                "output_column":  output_column,
                "remove_columns": remove_columns,
            }

        raise ValueError(f"Unsupported datasets action method: {method}")

    async def _dispatch(
        self,
        method: DatasetsActionMethod,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dataset:
        if method == DatasetsActionMethod.LOAD:
            return await self._load(params, cancellation_token)

        if method == DatasetsActionMethod.CONCAT:
            return await self._concat(params, cancellation_token)

        if method == DatasetsActionMethod.SELECT:
            return await self._select(params, cancellation_token)

        if method == DatasetsActionMethod.MAP:
            return await self._map(params, cancellation_token)

        raise ValueError(f"Unsupported datasets action method: {method}")

    @abstractmethod
    async def _load(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dataset:
        pass

    async def _concat(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dataset:
        from datasets import Dataset, concatenate_datasets

        datasets  = params["datasets"]
        direction = params["direction"]
        info      = params["info"]
        split     = params["split"]

        for dataset in datasets:
            if not isinstance(dataset, Dataset):
                raise TypeError(f"Expected Dataset instance, but got {type(dataset).__name__}")

        def _fn() -> Dataset:
            return concatenate_datasets(
                datasets,
                info=info,
                split=split,
                axis=0 if direction == "vertical" else 1
            )

        return await self._run_in_executor(_fn)

    async def _select(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dataset:
        from datasets import Dataset

        dataset = params["dataset"]
        axis    = params["axis"]
        indices = params["indices"]
        columns = params["columns"]

        if not isinstance(dataset, Dataset):
            raise TypeError(f"Expected Dataset instance, but got {type(dataset).__name__}")

        if axis == "rows":
            if indices is None:
                raise ValueError("indices must be provided when axis='rows'")

            def _fn() -> Dataset:
                return dataset.select([ int(index) for index in indices ])

            return await self._run_in_executor(_fn)

        if axis == "columns":
            if columns is None:
                raise ValueError("columns must be provided when axis='columns'")

            def _fn() -> Dataset:
                return dataset.select_columns(columns)

            return await self._run_in_executor(_fn)

        raise ValueError(f"Unsupported axis: {axis}")

    async def _map(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dataset:
        from datasets import Dataset

        dataset        = params["dataset"]
        template       = params["template"]
        output_column  = params["output_column"]
        remove_columns = params["remove_columns"]

        if not isinstance(dataset, Dataset):
            raise TypeError(f"Expected Dataset instance, but got {type(dataset).__name__}")

        def _format_example(example):
            return { output_column: format_template_example(template, example) }

        def _fn() -> Dataset:
            return dataset.map(_format_example, remove_columns=remove_columns)

        return await self._run_in_executor(_fn)
