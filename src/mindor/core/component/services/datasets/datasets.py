from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from mindor.dsl.schema.action import DatasetsActionConfig, DatasetsActionMethod, DatasetsProvider
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .providers import HuggingfaceDatasetsProvider, LocalDatasetsProvider

class DatasetsAction:
    def __init__(self, config: DatasetsActionConfig):
        self.config: DatasetsActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        result = await self._dispatch(context)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext) -> Dict[str, Any]:
        if self.config.method == DatasetsActionMethod.LOAD:
            return await self._load(context)

        raise ValueError(f"Unsupported datasets action method: {self.config.method}")

    async def _load(self, context: ComponentActionContext) -> Dict[str, Any]:
        if self.config.provider == DatasetsProvider.HUGGINGFACE:
            return await HuggingfaceDatasetsProvider(self.config).load(context)

        if self.config.provider == DatasetsProvider.LOCAL:
            return await LocalDatasetsProvider(self.config).load(context)

        raise ValueError(f"Unsupported dataset provider: {self.config.provider}")

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
