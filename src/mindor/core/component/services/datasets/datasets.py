from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from mindor.dsl.schema.action import DatasetsActionConfig, DatasetsActionMethod, DatasetsProvider
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .providers import HuggingfaceDatasetsProvider, LocalDatasetsProvider
from .utils import format_template_example

if TYPE_CHECKING:
    from datasets import Dataset

class DatasetsAction:
    def __init__(self, config: DatasetsActionConfig):
        self.config: DatasetsActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        result = await self._dispatch(context)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext) -> Dataset:
        if self.config.method == DatasetsActionMethod.LOAD:
            return await self._load(context)

        if self.config.method == DatasetsActionMethod.CONCAT:
            return await self._concat(context)

        if self.config.method == DatasetsActionMethod.SELECT:
            return await self._select(context)

        if self.config.method == DatasetsActionMethod.MAP:
            return await self._map(context)

        raise ValueError(f"Unsupported datasets action method: {self.config.method}")

    async def _load(self, context: ComponentActionContext) -> Dataset:
        fraction = await context.render_variable(self.config.fraction)
        shuffle  = await context.render_variable(self.config.shuffle)

        dataset = await self._load_dataset(context)

        if shuffle:
            dataset = dataset.shuffle()

        if isinstance(fraction, float) and fraction < 1.0:
            sample_size = max(int(len(dataset) * fraction), 1)
            dataset = dataset.select(range(sample_size))

        return dataset

    async def _load_dataset(self, context: ComponentActionContext) -> Dataset:
        if self.config.provider == DatasetsProvider.HUGGINGFACE:
            return await HuggingfaceDatasetsProvider(self.config).load(context)

        if self.config.provider == DatasetsProvider.LOCAL:
            return await LocalDatasetsProvider(self.config).load(context)

        raise ValueError(f"Unsupported dataset provider: {self.config.provider}")

    async def _concat(self, context: ComponentActionContext) -> Dataset:
        from datasets import concatenate_datasets

        datasets  = await context.render_variable(self.config.datasets)
        direction = await context.render_variable(self.config.direction)
        info      = await context.render_variable(self.config.info)
        split     = await context.render_variable(self.config.split)

        for dataset in datasets:
            if not isinstance(dataset, Dataset):
                raise ValueError(f"Expected Dataset instance, but got {type(dataset).__name__}")

        return concatenate_datasets(
            datasets,
            info=info,
            split=split,
            axis=0 if direction == "vertical" else 1
        )

    async def _select(self, context: ComponentActionContext) -> Dataset:
        dataset = await context.render_variable(self.config.dataset)
        axis    = await context.render_variable(self.config.axis)
        indices = await context.render_variable(self.config.indices)
        columns = await context.render_variable(self.config.columns)

        if not isinstance(dataset, Dataset):
            raise ValueError(f"Expected Dataset instance, but got {type(dataset).__name__}")

        if axis == "rows":
            if indices is None:
                raise ValueError("indices must be provided when axis='rows'")
            return dataset.select([ int(index) for index in indices ])

        if axis == "columns":
            if columns is None:
                raise ValueError("columns must be provided when axis='columns'")
            return dataset.select_columns(columns)

        raise ValueError(f"Unsupported axis: {axis}")

    async def _map(self, context: ComponentActionContext) -> Dataset:
        dataset        = await context.render_variable(self.config.dataset)
        template       = await context.render_variable(self.config.template)
        output_column  = await context.render_variable(self.config.output_column)
        remove_columns = await context.render_variable(self.config.remove_columns)

        if not isinstance(dataset, Dataset):
            raise ValueError(f"Expected Dataset instance, but got {type(dataset).__name__}")

        def format_example(example):
            return { output_column: format_template_example(template, example) }

        return dataset.map(format_example, remove_columns=remove_columns)

@register_component(ComponentType.DATASETS)
class DatasetsComponent(ComponentService):
    def __init__(self, id: str, config: DatasetsActionConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "datasets" ]

    async def _run(self, action: DatasetsActionConfig, context: ComponentActionContext) -> Any:
        async def _run():
            return await DatasetsAction(action).run(context)

        return await self.run_in_thread(_run)
