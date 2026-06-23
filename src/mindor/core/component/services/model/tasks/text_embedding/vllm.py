from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import VllmModelTaskService, ComponentActionContext
from .common import TextEmbeddingTaskAction
import asyncio, math, uuid

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine

class VllmTextEmbeddingTaskAction(TextEmbeddingTaskAction):
    def __init__(
        self,
        config: TextEmbeddingModelActionConfig,
        engine: AsyncLLMEngine,
    ):
        super().__init__(config)

        self.engine: AsyncLLMEngine = engine

    async def _embed(self, texts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[List[float]]:
        from vllm import PoolingParams

        pooling_params = PoolingParams()
        embeddings: List[List[float]] = []

        for text in texts:
            request_id = f"emb-{uuid.uuid4().hex}"
            final_output = None
            async for output in self.engine.encode(text, pooling_params, request_id=request_id):
                final_output = output

            if final_output is None:
                embeddings.append([])
                continue

            vec = final_output.outputs.embedding
            embeddings.append(list(vec))

        if params["normalize"]:
            normalized: List[List[float]] = []
            for emb in embeddings:
                norm = math.sqrt(sum(x * x for x in emb))
                if norm > 1e-12:
                    normalized.append([ x / norm for x in emb ])
                else:
                    normalized.append(emb)
            return normalized

        return embeddings


@register_model_task_service(ModelTaskType.TEXT_EMBEDDING, ModelDriver.VLLM)
class VllmTextEmbeddingTaskService(VllmModelTaskService):
    async def _load_model(self) -> None:
        from vllm import AsyncEngineArgs, AsyncLLMEngine

        model_path = self._get_model_path()
        params = self._get_model_params()
        params.setdefault("task", "embed")

        logging.info(f"Component '{self.id}': loading vLLM embedding model from '{model_path}'")

        engine_args = AsyncEngineArgs(model=model_path, **params)
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)

        self._load_tokenizer(model_path, params)

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await VllmTextEmbeddingTaskAction(action, self.engine).run(context, loop)
