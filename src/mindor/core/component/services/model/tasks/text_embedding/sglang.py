from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import SglangModelTaskDriver, ComponentActionContext
from .common import TextEmbedding, TextEmbeddingTaskAction
import math, ulid

if TYPE_CHECKING:
    from sglang import Engine

class SglangTextEmbeddingTaskAction(TextEmbeddingTaskAction):
    def __init__(
        self,
        config: TextEmbeddingModelActionConfig,
        engine: Engine,
    ):
        super().__init__(config)

        self.engine: Engine = engine

    async def _embed_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[TextEmbedding]:
        embeddings: List[List[float]] = []

        for text in texts:
            request_id = f"request-{ulid.ulid()}"

            if cancellation_token is not None and cancellation_token.is_cancelled():
                self.engine.abort_request(request_id)
                return [ TextEmbedding(vector) for vector in embeddings ]

            output = await self.engine.async_encode(text, rid=request_id)

            if output is None:
                embeddings.append([])
                continue

            embeddings.append(list(output["embedding"]))

        if params["normalize"]:
            normalized: List[List[float]] = []
            for embedding in embeddings:
                norm = math.sqrt(sum(x * x for x in embedding))
                if norm > 1e-12:
                    normalized.append([ x / norm for x in embedding ])
                else:
                    normalized.append(embedding)
            embeddings = normalized

        return [ TextEmbedding(vector) for vector in embeddings ]

@register_model_task_driver(ModelTaskType.TEXT_EMBEDDING, ModelDriverType.SGLANG)
class SglangTextEmbeddingTaskDriver(SglangModelTaskDriver):
    async def _load_model(self) -> None:
        from sglang import Engine
        from transformers import AutoTokenizer

        model_path = await self._provision_model(self.config.model)

        logging.info(f"Component '{self.id}': loading SGLang embedding model from '{model_path}'")

        def _load():
            params: Dict[str, Any] = {
                "is_embedding": True,
                **self._get_model_params(self.config.model),
                **self._get_model_options(self.config),
            }

            engine = Engine(model_path=model_path, **params)

            self._load_tokenizer(AutoTokenizer, model_path, params)

            return engine

        self.engine = await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await SglangTextEmbeddingTaskAction(action, self.engine).run(context)
