from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.foundation.variable.time import parse_duration
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
    async def _resolve_params(self, method: VectorStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(method, context)

        if method in (VectorStoreActionMethod.INSERT, VectorStoreActionMethod.UPDATE):
            document = await context.render_variable(self.config.document)

            params.update({
                "document": document,
            })

            return params

        return params

    async def _insert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        def _insert() -> Dict[str, Any]:
            collection_name = params["collection"]
            vector          = params["vector"]
            vector_id       = params["vector_id"]
            document        = params["document"]
            metadata        = params["metadata"]
            batch_size      = params["batch_size"]

            is_single_input: bool = bool(not (isinstance(vector, list) and vector and isinstance(vector[0], (list, tuple))))
            vectors: List[List[float]] = [ vector ] if is_single_input else vector
            vector_ids: Optional[List[Union[int, str]]] = [ vector_id ] if is_single_input and vector_id else vector_id
            metadatas: Optional[List[Dict[str, Any]]] = [ metadata ] if is_single_input and metadata else metadata
            documents: Optional[List[str]] = [ document ] if is_single_input and document else document
            batch_size = batch_size if batch_size and batch_size > 0 else len(vectors)
            inserted_ids, affected_rows = [], 0

            if vector_ids is None:
                vector_ids = [ ulid.ulid() for _ in vectors ]

            collection: Collection = self.client.get_or_create_collection(name=collection_name)
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

        return await self._run_in_executor(_insert)

    async def _update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        def _update() -> Dict[str, Any]:
            collection_name = params["collection"]
            vector_id       = params["vector_id"]
            vector          = params["vector"]
            metadata        = params["metadata"]
            document        = params["document"]
            batch_size      = params["batch_size"]

            is_single_input: bool = bool(not isinstance(vector_id, list))
            vector_ids: List[Union[int, str]] = [ vector_id ] if is_single_input else vector_id
            vectors: List[List[float]] = [ vector ] if is_single_input and vector else vector
            metadatas: List[Dict[str, Any]] = [ metadata ] if is_single_input and metadata else metadata
            documents: Optional[List[str]] = [ document ] if is_single_input and document else document
            batch_size = batch_size if batch_size and batch_size > 0 else len(vector_ids)
            affected_rows = 0

            collection: Collection = self.client.get_or_create_collection(name=collection_name)
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

        return await self._run_in_executor(_update)

    async def _search(self, params: Dict[str, Any]) -> Union[List[List[Dict[str, Any]]], List[Dict[str, Any]]]:
        def _search() -> Union[List[List[Dict[str, Any]]], List[Dict[str, Any]]]:
            collection_name = params["collection"]
            query           = params["query"]
            top_k           = params["top_k"]
            filter          = params["filter"]
            output_fields   = params["output_fields"]
            batch_size      = params["batch_size"]

            is_single_input: bool = bool(not (isinstance(query, list) and query and isinstance(query[0], (list, tuple))))
            queries: List[List[float]] = [ query ] if is_single_input else query
            batch_size = batch_size if batch_size and batch_size > 0 else len(queries)
            results = []

            collection: Collection = self.client.get_or_create_collection(name=collection_name)
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

        return await self._run_in_executor(_search)

    async def _delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        def _delete() -> Dict[str, Any]:
            collection_name = params["collection"]
            vector_id       = params["vector_id"]
            filter          = params["filter"]
            batch_size      = params["batch_size"]

            is_single_input: bool = bool(not isinstance(vector_id, list))
            vector_ids: List[Union[int, str]] = [ vector_id ] if is_single_input else vector_id
            batch_size = batch_size if batch_size and batch_size > 0 else len(vector_ids)
            affected_rows = 0

            collection: Collection = self.client.get_or_create_collection(name=collection_name)
            where_spec = ChromaWhereSpecBuilder().build(filter)

            for index in range(0, len(vector_ids), batch_size):
                batch_vector_ids = vector_ids[index:index + batch_size]

                collection.delete(
                    ids=batch_vector_ids,
                    where=where_spec
                )
                affected_rows += len(batch_vector_ids)

            return { "affected_rows": affected_rows }

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
                timeout=parse_duration(self.config.timeout)
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
