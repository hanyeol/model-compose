from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, MilvusVectorStoreActionConfig
from mindor.core.utils.streamer import AsyncStreamer
from mindor.core.logger import logging
from ..base import VectorStoreService, VectorStoreDriver, register_vector_store_service
from ..base import ComponentActionContext

class MilvusVectorStoreAction:
    def __init__(self, config: MilvusVectorStoreActionConfig):
        self.config: MilvusVectorStoreActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        pass

@register_vector_store_service(VectorStoreDriver.MILVUS)
class MilvusVectorStoreService(VectorStoreService):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await MilvusVectorStoreAction(action).run(context)
