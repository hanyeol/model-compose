from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, Any
from mindor.dsl.schema.component import HuggingfaceDatasetsComponentConfig
from mindor.dsl.schema.action import DatasetsActionConfig, DatasetsActionMethod
from mindor.core.foundation.cancellation import CancellationToken
from ..base import DatasetsService, DatasetsDriver, register_datasets_service
from ..base import ComponentActionContext
from .common import DatasetsAction
import os

if TYPE_CHECKING:
    from datasets import Dataset

_LOAD_DATASET_KEYS = (
    "path", "name", "revision", "token", "split",
    "streaming", "keep_in_memory", "cache_dir", "save_infos",
    "trust_remote_code", "data_files", "data_dir",
)

class HuggingfaceDatasetsAction(DatasetsAction):
    async def _resolve_params(self, method: DatasetsActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(method, context)

        if method == DatasetsActionMethod.LOAD:
            path              = await context.render_variable(self.config.path)
            name              = await context.render_variable(self.config.name)
            revision          = await context.render_variable(self.config.revision)
            token             = await context.render_variable(self.config.token)
            trust_remote_code = await context.render_variable(self.config.trust_remote_code)
            data_files        = await context.render_variable(self.config.data_files)
            data_dir          = await context.render_variable(self.config.data_dir)

            if path:
                path = os.path.expanduser(path)
            if data_dir:
                data_dir = os.path.expanduser(data_dir)

            params.update({
                "path":              path,
                "name":              name,
                "revision":          revision,
                "token":             token,
                "trust_remote_code": trust_remote_code,
                "data_files":        data_files,
                "data_dir":          data_dir,
            })

            return params

        return params

    async def _load(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dataset:
        def _fn() -> Dataset:
            from datasets import load_dataset

            dataset = load_dataset(**{ key: params[key] for key in _LOAD_DATASET_KEYS })

            if params["shuffle"]:
                dataset = dataset.shuffle()

            fraction = params["fraction"]

            if isinstance(fraction, float) and fraction < 1.0:
                sample_size = max(int(len(dataset) * fraction), 1)
                dataset = dataset.select(range(sample_size))

            return dataset

        return await self._run_in_executor(_fn)

@register_datasets_service(DatasetsDriver.HUGGINGFACE)
class HuggingfaceDatasetsService(DatasetsService):
    def __init__(self, id: str, config: HuggingfaceDatasetsComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self):
        return [ "datasets" ]

    async def _run(self, action: DatasetsActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceDatasetsAction(action).run(context)
