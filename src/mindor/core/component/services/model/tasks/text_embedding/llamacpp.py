from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import LlamaCppModelTaskService, ComponentActionContext
from .common import TextEmbeddingTaskAction
import asyncio

if TYPE_CHECKING:
    from llama_cpp import Llama

class LlamaCppTextEmbeddingTaskAction(TextEmbeddingTaskAction):
    def __init__(
        self,
        config: TextEmbeddingModelActionConfig,
        model: Llama,
    ):
        super().__init__(config)

        self.model: Llama = model

    async def _embed(self, texts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[List[float]]:
        import math

        embeddings = self.model.embed(texts)

        if params["normalize"]:
            normalized_embeddings = []
            for embedding in embeddings:
                norm = math.sqrt(sum(x * x for x in embedding))
                if norm > 1e-12:
                    normalized_embeddings.append([x / norm for x in embedding])
                else:
                    normalized_embeddings.append(embedding)
            return normalized_embeddings

        return embeddings

@register_model_task_service(ModelTaskType.TEXT_EMBEDDING, ModelDriver.LLAMACPP)
class LlamaCppTextEmbeddingTaskService(LlamaCppModelTaskService):
    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await LlamaCppTextEmbeddingTaskAction(action, self.model).run(context, loop)

    async def _load_model(self) -> None:
        from llama_cpp import Llama

        model_path = self._get_model_path()
        params = self._get_model_params()
        params["embedding"] = True

        logging.info(f"Component '{self.id}': loading llama.cpp embedding model from '{model_path}'")
        self.model = Llama(model_path=model_path, **params)
