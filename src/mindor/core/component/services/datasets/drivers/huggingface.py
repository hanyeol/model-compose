from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, Any
from mindor.dsl.schema.component import HuggingfaceDatasetsComponentConfig
from mindor.dsl.schema.action import DatasetsActionConfig, DatasetsActionMethod
from mindor.core.foundation.cancellation import CancellationToken
from ..base import DatasetsDriver, DatasetsDriverType, register_datasets_driver
from ..base import ComponentActionContext
from .common import DatasetsAction
import os

if TYPE_CHECKING:
    from datasets import Dataset

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
        load_params = self._build_load_params(params)

        def _fn() -> Dataset:
            from datasets import load_dataset

            dataset = load_dataset(**load_params)

            if params["shuffle"]:
                dataset = dataset.shuffle()

            fraction = params["fraction"]

            if isinstance(fraction, float) and fraction < 1.0:
                sample_size = max(int(len(dataset) * fraction), 1)
                dataset = dataset.select(range(sample_size))

            return dataset

        return await self._run_in_executor(_fn)

    def _build_load_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Only include kwargs whose value is non-default so `load_dataset()` uses
        # its own defaults for anything the user did not set. Passing `None` /
        # `False` explicitly would override defaults and can break behavior
        # (e.g. `cache_dir=None` bypasses the standard cache lookup).
        load_params: Dict[str, Any] = { "path": params["path"] }

        if params["name"]:
            load_params["name"] = params["name"]

        if params["revision"]:
            load_params["revision"] = params["revision"]

        if params["token"]:
            load_params["token"] = params["token"]

        if params["trust_remote_code"]:
            load_params["trust_remote_code"] = params["trust_remote_code"]

        if params["data_files"]:
            load_params["data_files"] = params["data_files"]

        if params["data_dir"]:
            load_params["data_dir"] = params["data_dir"]

        if params["split"]:
            load_params["split"] = params["split"]

        if params["streaming"]:
            load_params["streaming"] = params["streaming"]

        if params["keep_in_memory"]:
            load_params["keep_in_memory"] = params["keep_in_memory"]

        if params["cache_dir"]:
            load_params["cache_dir"] = params["cache_dir"]

        if params["save_infos"]:
            load_params["save_infos"] = params["save_infos"]

        return load_params

@register_datasets_driver(DatasetsDriverType.HUGGINGFACE)
class HuggingfaceDatasetsService(DatasetsDriver):
    def __init__(self, id: str, config: HuggingfaceDatasetsComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self):
        return [ "datasets" ]

    async def _run(self, action: DatasetsActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceDatasetsAction(action).run(context)
