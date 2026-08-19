from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VectorStoreService, VectorStoreDriver, register_vector_store_service
from ..base import ComponentActionContext
from .common import VectorStoreAction
import ulid, os

if TYPE_CHECKING:
    from chromadb.api import ClientAPI as ChromaClient
    from chromadb.api import Collection

class ChromaWhereSpecBuilder:
    def build(self, filter: Any) -> Optional[Dict[str, Any]]:
        spec: Dict[str, Any] = self._build_where_spec(filter)

        if not spec:
            return None

        return spec

    def _build_where_spec(self, filter: Any) -> Dict[str, Any]:
        spec: Dict[str, Any] = {}

        if isinstance(filter, (list, tuple, set)):
            for item in filter:
                spec.update(self._build_where_spec(item))
            return spec

        if isinstance(filter, dict):
            for field, value in filter.items():
                spec.update({field: { "$eq": value }})
            return spec

        if isinstance(filter, VectorStoreFilterCondition):
            spec.update(self._build_condition_spec(filter))
            return spec

        return {}

    def _build_condition_spec(self, condition: VectorStoreFilterCondition) -> Optional[Dict[str, Dict[str, Any]]]:
        operator_map = {
            VectorStoreFilterOperator.EQ:     "$eq",
            VectorStoreFilterOperator.NEQ:    "$ne",
            VectorStoreFilterOperator.GT:     "$gt",
            VectorStoreFilterOperator.GTE:    "$gte",
            VectorStoreFilterOperator.LT:     "$lt",
            VectorStoreFilterOperator.LTE:    "$lte",
            VectorStoreFilterOperator.IN:     "$in",
            VectorStoreFilterOperator.NOT_IN: "$nin",
        }

        operator = operator_map.get(condition.operator)

        if not operator:
            return None

        return { condition.field: { operator: condition.value } }

class ChromaVectorStoreAction(VectorStoreAction):
    async def _prepare_input(
        self,
        method: VectorStoreActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        # Chroma extends the base per-item tuple with a `documents` slot. Base's
        # `_process` collects each slot and spreads them into the driver call,
        # so the tuple order here must match `_insert`/`_update` signatures.
        input, is_single_input, is_streaming_input = await super()._prepare_input(method, context)

        if method in (VectorStoreActionMethod.INSERT, VectorStoreActionMethod.UPDATE):
            documents = await context.render_array(self.config.document, single_as_array=True)

            if not is_streaming_input:
                is_streaming_input = isinstance(documents, (StreamIterator, AsyncIterator))

            return (*input, documents), is_single_input, is_streaming_input

        return input, is_single_input, is_streaming_input

    async def _insert(
        self,
        collection: Any,
        vector_ids: Optional[List[Any]],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]],
        documents: Optional[List[str]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        def _insert() -> Dict[str, Any]:
            # Chroma requires ids; auto-generate ulids when omitted.
            ids = vector_ids if vector_ids is not None else [ ulid.ulid() for _ in vectors ]

            database: Collection = self.client.get_or_create_collection(name=collection)
            database.add(
                ids=ids,
                embeddings=vectors,
                metadatas=metadatas,
                documents=documents
            )

            return { "ids": ids, "affected_rows": len(ids) }

        return await self._run_in_executor(_insert)

    async def _update(
        self,
        collection: Any,
        vector_ids: List[Any],
        vectors: Optional[List[List[float]]],
        metadatas: Optional[List[Dict[str, Any]]],
        documents: Optional[List[str]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        def _update() -> Dict[str, Any]:
            database: Collection = self.client.get_or_create_collection(name=collection)
            database.update(
                ids=vector_ids,
                embeddings=vectors,
                metadatas=metadatas,
                documents=documents
            )

            return { "affected_rows": len(vector_ids) }

        return await self._run_in_executor(_update)

    async def _search(
        self,
        collection: Any,
        queries: List[List[float]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[List[Dict[str, Any]]]:
        def _search() -> List[List[Dict[str, Any]]]:
            top_k         = params["top_k"]
            filter        = params["filter"]
            output_fields = params["output_fields"]

            database: Collection = self.client.get_or_create_collection(name=collection)
            where_spec = ChromaWhereSpecBuilder().build(filter)

            result = database.query(
                query_embeddings=queries,
                n_results=int(top_k),
                where=where_spec,
                include=[ "embeddings", "distances", "metadatas", "documents" ]
            )

            results = []

            for query in range(len(result["ids"])):
                hits = []
                for index, id in enumerate(result["ids"][query]):
                    metadata = result["metadatas"][query][index]

                    if output_fields:
                        metadata = { key: metadata[key] for key in output_fields if key in metadata }

                    hits.append({
                        "id": id,
                        "embedding": result["embeddings"][query][index],
                        "score": 1 / (1 + result["distances"][query][index]),
                        "distance": result["distances"][query][index],
                        "metadata": metadata,
                        "document": result["documents"][query][index]
                    })
                results.append(hits)

            return results

        return await self._run_in_executor(_search)

    async def _delete(
        self,
        collection: Any,
        vector_ids: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        def _delete() -> Dict[str, Any]:
            database: Collection = self.client.get_or_create_collection(name=collection)
            where_spec = ChromaWhereSpecBuilder().build(params["filter"])

            database.delete(
                ids=vector_ids,
                where=where_spec
            )

            return { "affected_rows": len(vector_ids) }

        return await self._run_in_executor(_delete)

@register_vector_store_service(VectorStoreDriver.CHROMA)
class ChromaVectorStoreService(VectorStoreService):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[ChromaClient] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "chromadb" ]

    async def _start(self) -> None:
        self.client = self._create_client()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.client:
            self.client = None

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await ChromaVectorStoreAction(action, self.client).run(context)

    def _create_client(self) -> ChromaClient:
        if self.config.mode == "server":
            from chromadb import HttpClient

            return HttpClient(
                **self._resolve_connection_params(),
                **self._resolve_database_params(),
                timeout=parse_time(self.config.timeout)
            )

        if self.config.mode == "local":
            from chromadb import PersistentClient

            return PersistentClient(
                path=os.path.expanduser(self.config.storage_dir),
                **self._resolve_database_params()
            )

        raise ValueError(f"Unsupported connection mode: {self.config.mode}")

    def _resolve_database_params(self) -> Dict[str, Any]:
        return {
            **({ "tenant":   self.config.tenant   } if self.config.tenant   else {}),
            **({ "database": self.config.database } if self.config.database else {})
        }

    def _resolve_connection_params(self) -> Dict[str, Any]:
        if self.config.endpoint:
            return { "api_base": self.config.endpoint }

        return { "host": self.config.host, "port": self.config.port, "ssl": bool(self.config.protocol == "https") }
