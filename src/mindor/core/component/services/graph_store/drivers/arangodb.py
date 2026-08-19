from __future__ import annotations
from typing import TYPE_CHECKING

import re
from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import GraphStoreComponentConfig
from mindor.dsl.schema.action import GraphStoreActionConfig, GraphStoreActionMethod
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from ..base import GraphStoreService, GraphStoreDriver, register_graph_store_service
from ..base import ComponentActionContext
from .common import GraphStoreAction

if TYPE_CHECKING:
    from arango import ArangoClient
    from arango.database import StandardDatabase

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

class ArangoDBQueryBuilder:
    @staticmethod
    def verify_identifier(value: str, field: str) -> str:
        if not _IDENTIFIER_PATTERN.match(value):
            raise ValueError(f"Invalid {field} identifier: '{value}'")
        return value

    @staticmethod
    def resolve_doc_id(doc_id: str, default_collection: str) -> Tuple[str, str]:
        if "/" in doc_id:
            collection, key = doc_id.split("/", 1)
            ArangoDBQueryBuilder.verify_identifier(collection, "collection")
            return collection, key
        return default_collection, doc_id

    @staticmethod
    def build_insert_node_doc(node: Dict[str, Any], default_collection: Optional[str]) -> Tuple[str, Dict[str, Any]]:
        collection = ArangoDBQueryBuilder.verify_identifier(node.get("label", default_collection or "nodes"), "collection")
        doc = { **node.get("properties", {}) }
        node_id = node.get("id")
        if node_id:
            doc["_key"] = str(node_id)
        return collection, doc

    @staticmethod
    def build_insert_edge_doc(rel: Dict[str, Any], default_edge_collection: Optional[str]) -> Tuple[str, Dict[str, Any]]:
        collection = ArangoDBQueryBuilder.verify_identifier(default_edge_collection or rel.get("type", "edges"), "edge collection")
        doc = {
            "_from": rel.get("from"),
            "_to": rel.get("to"),
            **(rel.get("properties", {}) or {}),
        }
        return collection, doc

    @staticmethod
    def build_update_doc(doc_id: str, properties: Dict[str, Any], default_collection: str) -> Tuple[str, Dict[str, Any]]:
        collection, key = ArangoDBQueryBuilder.resolve_doc_id(doc_id, default_collection)
        doc = { "_key": key, **properties }
        return collection, doc

    @staticmethod
    def build_traverse(
        start_node: str,
        direction: str,
        max_depth: int,
        edge_collection: Optional[str],
        relationship_types: Optional[List[str]],
    ) -> Tuple[str, Dict[str, Any]]:
        direction_map = { "out": "outbound", "in": "inbound", "both": "any" }
        arango_direction = direction_map.get(direction, "outbound")

        edge_collections = []
        if edge_collection:
            edge_collections = [ edge_collection ]
        elif relationship_types:
            edge_collections = relationship_types

        if edge_collections:
            for collection in edge_collections:
                ArangoDBQueryBuilder.verify_identifier(collection, "edge collection")
            edge_str = ", ".join(edge_collections)
        else:
            edge_str = "edges"

        aql = f"FOR v, e, p IN 1..@max_depth {arango_direction.upper()} @start_node {edge_str} RETURN {{node: v, edge: e, depth: LENGTH(p.edges)}}"
        return aql, { "start_node": str(start_node), "max_depth": max_depth }

class ArangoDBGraphStoreAction(GraphStoreAction):
    async def _resolve_params(self, method: GraphStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(method, context)

        if method in (GraphStoreActionMethod.INSERT, GraphStoreActionMethod.UPDATE, GraphStoreActionMethod.DELETE):
            collection = await context.render_variable(getattr(self.config, "collection", None))

            params.update({
                "collection": collection,
            })

            if method == GraphStoreActionMethod.INSERT:
                edge_collection = await context.render_variable(getattr(self.config, "edge_collection", None))

                params.update({
                    "edge_collection": edge_collection,
                })

            return params

        if method == GraphStoreActionMethod.TRAVERSE:
            graph           = await context.render_variable(getattr(self.config, "graph", None))
            edge_collection = await context.render_variable(getattr(self.config, "edge_collection", None))

            params.update({
                "graph":           graph,
                "edge_collection": edge_collection,
            })

            return params

        return params

    async def _query(
        self,
        queries: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        def _query() -> List[Dict[str, Any]]:
            bind_vars = params["bind_vars"]

            records: List[Dict[str, Any]] = []

            for query in queries:
                cursor = self.database.aql.execute(query, bind_vars=bind_vars or {})
                records.extend(doc for doc in cursor)

            return records

        return await self._run_in_executor(_query)

    async def _insert(
        self,
        nodes: Optional[List[Dict[str, Any]]],
        relationships: Optional[List[Dict[str, Any]]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        def _insert() -> Dict[str, Any]:
            collection      = params["collection"]
            edge_collection = params["edge_collection"]

            created_nodes = 0
            created_relationships = 0
            inserted_ids: List[str] = []

            for node in nodes or []:
                collection_name, doc = ArangoDBQueryBuilder.build_insert_node_doc(node, collection)

                if not self.database.has_collection(collection_name):
                    self.database.create_collection(collection_name)

                result = self.database.collection(collection_name).insert(doc)
                inserted_ids.append(result.get("_id", result.get("_key", "")))
                created_nodes += 1

            for relationship in relationships or []:
                collection_name, doc = ArangoDBQueryBuilder.build_insert_edge_doc(relationship, edge_collection)

                if not self.database.has_collection(collection_name):
                    self.database.create_collection(collection_name, edge=True)

                result = self.database.collection(collection_name).insert(doc)
                inserted_ids.append(result.get("_id", result.get("_key", "")))
                created_relationships += 1

            return {
                "ids": inserted_ids,
                "created_nodes": created_nodes,
                "created_relationships": created_relationships,
            }

        return await self._run_in_executor(_insert)

    async def _update(
        self,
        node_ids: Optional[List[Any]],
        relationship_ids: Optional[List[Any]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        def _update() -> Dict[str, Any]:
            properties = params["properties"]
            collection = params["collection"]

            affected_rows = 0

            if properties:
                for id in node_ids or []:
                    collection_name, doc = ArangoDBQueryBuilder.build_update_doc(str(id), properties, collection or "nodes")
                    self.database.collection(collection_name).update(doc)
                    affected_rows += 1

                for id in relationship_ids or []:
                    collection_name, doc = ArangoDBQueryBuilder.build_update_doc(str(id), properties, collection or "edges")
                    self.database.collection(collection_name).update(doc)
                    affected_rows += 1

            return { "affected_rows": affected_rows }

        return await self._run_in_executor(_update)

    async def _delete(
        self,
        node_ids: Optional[List[Any]],
        relationship_ids: Optional[List[Any]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        def _delete() -> Dict[str, Any]:
            collection = params["collection"]

            affected_rows = 0

            for id in node_ids or []:
                collection_name, key = ArangoDBQueryBuilder.resolve_doc_id(str(id), collection or "nodes")
                self.database.collection(collection_name).delete(key)
                affected_rows += 1

            for id in relationship_ids or []:
                collection_name, key = ArangoDBQueryBuilder.resolve_doc_id(str(id), collection or "edges")
                self.database.collection(collection_name).delete(key)
                affected_rows += 1

            return { "affected_rows": affected_rows }

        return await self._run_in_executor(_delete)

    async def _traverse(
        self,
        start_nodes: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        def _traverse() -> List[Dict[str, Any]]:
            direction          = params["direction"]
            max_depth          = params["max_depth"]
            relationship_types = params["relationship_types"]
            graph_name         = params["graph"]
            edge_collection    = params["edge_collection"]

            direction_map = { "out": "outbound", "in": "inbound", "both": "any" }
            arango_direction = direction_map.get(direction, "outbound")

            records: List[Dict[str, Any]] = []

            for start_node in start_nodes:
                if graph_name:
                    ArangoDBQueryBuilder.verify_identifier(graph_name, "graph")
                    graph = self.database.graph(graph_name)
                    result = graph.traverse(
                        start_vertex=str(start_node),
                        direction=arango_direction,
                        max_depth=max_depth
                    )

                    vertices = result.get("vertices", [])
                    records.extend({ "node": vertex, "depth": None } for vertex in vertices[1:])
                    continue

                aql, bind_vars = ArangoDBQueryBuilder.build_traverse(
                    start_node,
                    direction,
                    max_depth,
                    edge_collection,
                    relationship_types,
                )
                cursor = self.database.aql.execute(aql, bind_vars=bind_vars)
                records.extend(doc for doc in cursor)

            return records

        return await self._run_in_executor(_traverse)

@register_graph_store_service(GraphStoreDriver.ARANGODB)
class ArangoDBGraphStoreService(GraphStoreService):
    def __init__(self, id: str, config: GraphStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[ArangoClient] = None
        self.database: Optional[StandardDatabase] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "python-arango" ]

    async def _start(self) -> None:
        self.client, self.database = self._create_client()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.client:
            self.client.close()
            self.client = None
            self.database = None

    async def _run(self, action: GraphStoreActionConfig, context: ComponentActionContext) -> Any:
        return await ArangoDBGraphStoreAction(action, self.database).run(context)

    def _create_client(self) -> Tuple[ArangoClient, StandardDatabase]:
        from arango import ArangoClient

        url = self.config.url if self.config.url else f"{self.config.protocol}://{self.config.host}:{self.config.port}"
        client = ArangoClient(
            hosts=url,
            request_timeout=parse_time(self.config.timeout)
        )

        database = client.db(
            self.config.database,
            username=self.config.username,
            password=self.config.password
        ) if self.config.username else client.db(self.config.database)

        return client, database
