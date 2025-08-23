from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from typing import TYPE_CHECKING
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, ChromaVectorStoreActionConfig, VectorStoreActionMethod, VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.utils.streamer import AsyncStreamer
from mindor.core.logger import logging
from ..base import VectorStoreService, VectorStoreDriver, register_vector_store_service
from ..base import ComponentActionContext
import ulid

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

class ChromaVectorStoreAction:
    def __init__(self, config: ChromaVectorStoreActionConfig):
        self.config: ChromaVectorStoreActionConfig = config

    async def run(self, context: ComponentActionContext, client: ChromaClient) -> Any:
        result = await self._dispatch(context, client)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext, client: ChromaClient) -> Dict[str, Any]:
        if self.config.method == VectorStoreActionMethod.INSERT:
            return await self._insert(context, client)

        if self.config.method == VectorStoreActionMethod.UPDATE:
            return await self._update(context, client)

        if self.config.method == VectorStoreActionMethod.SEARCH:
            return await self._search(context, client)

        if self.config.method == VectorStoreActionMethod.DELETE:
            return await self._delete(context, client)

        raise ValueError(f"Unsupported vector action method: {self.config.method}")

    async def _insert(self, context: ComponentActionContext, client: ChromaClient) -> Dict[str, Any]:
        collection_name = await context.render_variable(self.config.collection)
        vector          = await context.render_variable(self.config.vector)
        vector_id       = await context.render_variable(self.config.vector_id)
        document        = await context.render_variable(self.config.document)
        metadata        = await context.render_variable(self.config.metadata)
        batch_size      = await context.render_variable(self.config.batch_size)

        is_single_input: bool = bool(not (isinstance(vector, list) and vector and isinstance(vector[0], (list, tuple))))
        vectors: List[List[float]] = [ vector ] if is_single_input else vector
        vector_ids: Optional[List[Union[int, str]]] = [ vector_id ] if is_single_input and vector_id else vector_id
        metadatas: Optional[List[Dict[str, Any]]] = [ metadata ] if is_single_input and metadata else metadata
        documents: Optional[List[str]] = [ document ] if is_single_input and document else document
        batch_size = batch_size if batch_size and batch_size > 0 else len(vectors)
        inserted_ids, affected_rows = [], 0

        if vector_ids is None:
            vector_ids = [ ulid.ulid() for _ in vectors ]

        collection: Collection = client.get_or_create_collection(name=collection_name)
        for index in range(0, len(vectors), batch_size):
            batch_vectors = vectors[index:index + batch_size]
            batch_vector_ids = vector_ids[index:index + batch_size] if vector_ids else None
            batch_metadatas = metadatas[index:index + batch_size] if metadatas else None
            batch_documents = documents[index:index + batch_size] if documents else None

            collection.add(
                ids=batch_vector_ids,
                embeddings=batch_vectors,
                metadatas=batch_metadatas,
                documents=batch_documents
            )
            inserted_ids.extend(batch_vector_ids)
            affected_rows += len(batch_vector_ids)

        return { "ids": inserted_ids, "affected_rows": affected_rows }

    async def _update(self, context: ComponentActionContext, client: ChromaClient) -> Dict[str, Any]:
        collection_name = await context.render_variable(self.config.collection)
        vector_id       = await context.render_variable(self.config.vector_id)
        vector          = await context.render_variable(self.config.vector)
        metadata        = await context.render_variable(self.config.metadata)
        document        = await context.render_variable(self.config.document)
        batch_size      = await context.render_variable(self.config.batch_size)

        is_single_input: bool = bool(not isinstance(vector_id, list))
        vector_ids: List[Union[int, str]] = [ vector_id ] if is_single_input else vector_id
        vectors: List[List[float]] = [ vector ] if is_single_input and vector else vector
        metadatas: List[Dict[str, Any]] = [ metadata ] if is_single_input and metadata else metadata
        documents: Optional[List[str]] = [ document ] if is_single_input and document else document
        batch_size = batch_size if batch_size and batch_size > 0 else len(vector_ids)
        affected_rows = 0

        collection: Collection = client.get_or_create_collection(name=collection_name)
        for index in range(0, len(vector_ids), batch_size):
            batch_vector_ids = vector_ids[index:index + batch_size]
            batch_vectors = vectors[index:index + batch_size] if vectors else None
            batch_metadatas = metadatas[index:index + batch_size] if metadatas else None
            batch_documents = documents[index:index + batch_size] if documents else None

            collection.update(
                ids=batch_vector_ids,
                embeddings=batch_vectors,
                metadatas=batch_metadatas,
                documents=batch_documents
            )
            affected_rows += len(batch_vector_ids)

        return { "affected_rows": affected_rows }

    async def _search(self, context: ComponentActionContext, client: ChromaClient) -> List[List[Dict[str, Any]]] | List[Dict[str, Any]]:
        collection_name = await context.render_variable(self.config.collection)
        query           = await context.render_variable(self.config.query)
        top_k           = await context.render_variable(self.config.top_k)
        filter          = await context.render_variable(self.config.filter)
        output_fields   = await context.render_variable(self.config.output_fields)
        batch_size      = await context.render_variable(self.config.batch_size)

        is_single_input: bool = bool(not (isinstance(query, list) and query and isinstance(query[0], (list, tuple))))
        queries: List[List[float]] = [ query ] if is_single_input else query
        batch_size = batch_size if batch_size and batch_size > 0 else len(queries)
        results = []

        collection: Collection = client.get_or_create_collection(name=collection_name)
        where_spec = ChromaWhereSpecBuilder().build(filter)

        for index in range(0, len(queries), batch_size):
            batch_queries = queries[index:index + batch_size]

            result = collection.query(
                query_embeddings=batch_queries,
                n_results=int(top_k),
                where=where_spec,
                include=[ "embeddings", "distances", "metadatas", "documents" ]
            )

            for n in range(len(result["ids"])):
                hits = []
                for index, id in enumerate(result["ids"][n]):
                    metadata = result["metadatas"][n][index]
                    if output_fields:
                        metadata = { key: metadata[key] for key in output_fields if key in metadata }

                    hits.append({
                        "id": id,
                        "embedding": result["embeddings"][n][index],
                        "score": 1 / (1 + result["distances"][n][index]),
                        "distance": result["distances"][n][index],
                        "metadata": metadata,
                        "document": result["documents"][n][index]
                    })
                results.append(hits)

        return results[0] if is_single_input else results

    async def _delete(self, context: ComponentActionContext, client: ChromaClient) -> Dict[str, Any]:
        collection_name = await context.render_variable(self.config.collection)
        vector_id       = await context.render_variable(self.config.vector_id)
        filter          = await context.render_variable(self.config.filter)
        batch_size      = await context.render_variable(self.config.batch_size)

        is_single_input: bool = bool(not isinstance(vector_id, list))
        vector_ids: List[Union[int, str]] = [ vector_id ] if is_single_input else vector_id
        batch_size = batch_size if batch_size and batch_size > 0 else len(vector_ids)
        affected_rows = 0

        collection: Collection = client.get_or_create_collection(name=collection_name)
        where_spec = ChromaWhereSpecBuilder().build(filter)

        for index in range(0, len(vector_ids), batch_size):
            batch_vector_ids = vector_ids[index:index + batch_size]
        
            collection.delete(
                ids=batch_vector_ids,
                where=where_spec
            )
            affected_rows += len(batch_vector_ids)

        return { "affected_rows": affected_rows }

@register_vector_store_service(VectorStoreDriver.CHROMA)
class ChromaVectorStoreService(VectorStoreService):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[ChromaClient] = None

    async def _serve(self) -> None:
        self.client = self._create_client()

    async def _shutdown(self) -> None:
        if self.client:
            self.client = None

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        async def _run():
            return await ChromaVectorStoreAction(action).run(context, self.client)

        return await self.run_in_thread(_run)

    def _create_client(self) -> ChromaClient:
        if self.config.mode == "server":
            from chromadb import HttpClient

            return HttpClient(
                **self._resolve_connection_params(),
                **self._resolve_database_params()
            )

        if self.config.mode == "local":
            from chromadb import PersistentClient

            return PersistentClient(
                path=self.config.storage_dir,
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
