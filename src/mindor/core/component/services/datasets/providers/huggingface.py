from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from .common import CommonDatasetsProvider, ComponentActionContext

if TYPE_CHECKING:
    from datasets import Dataset

class HuggingfaceDatasetsProvider(CommonDatasetsProvider):
    async def load(self, context: ComponentActionContext) -> Dataset:
        from datasets import load_dataset

        path              = await context.render_variable(self.config.path)
        name              = await context.render_variable(self.config.name)
        revision          = await context.render_variable(self.config.revision)
        token             = await context.render_variable(self.config.token)
        split             = await context.render_variable(self.config.split)
        streaming         = await context.render_variable(self.config.streaming)
        keep_in_memory    = await context.render_variable(self.config.keep_in_memory)
        cache_dir         = await context.render_variable(self.config.cache_dir)
        save_infos        = await context.render_variable(self.config.save_infos)
        trust_remote_code = await context.render_variable(self.config.trust_remote_code)

        return load_dataset(
            path=path,
            name=name,
            revision=revision,
            token=token,
            split=split,
            streaming=streaming,
            keep_in_memory=keep_in_memory,
            cache_dir=cache_dir,
            save_infos=save_infos,
            trust_remote_code=trust_remote_code
        )
