from __future__ import annotations
from typing import TYPE_CHECKING

import re
from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import GraphStoreComponentConfig
from mindor.dsl.schema.action import GraphStoreActionConfig
from mindor.core.foundation.variable.time import parse_duration
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
    async def _query(self, context: ComponentActionContext) -> List[Dict[str, Any]]:
        query  = await context.render_variable(self.config.query)
        params = await context.render_variable(self.config.params)

        cursor = self.database.aql.execute(query, bind_vars=params or {})

        return [ doc for doc in cursor ]

    async def _insert(self, context: ComponentActionContext) -> Dict[str, Any]:
        nodes           = await context.render_variable(self.config.nodes)
        relationships   = await context.render_variable(self.config.relationships)
        collection      = await context.render_variable(getattr(self.config, "collection", None))
        edge_collection = await context.render_variable(getattr(self.config, "edge_collection", None))

        created_nodes = 0
        created_relationships = 0
        inserted_ids: List[str] = []

        if nodes:
            for node in nodes if isinstance(nodes, list) else [ nodes ]:
                collection_name, doc = ArangoDBQueryBuilder.build_insert_node_doc(node, collection)

                if not self.database.has_collection(collection_name):
                    self.database.create_collection(collection_name)

                result = self.database.collection(collection_name).insert(doc)
                inserted_ids.append(result.get("_id", result.get("_key", "")))
                created_nodes += 1

        if relationships:
            for relationship in relationships if isinstance(relationships, list) else [ relationships ]:
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

    async def _update(self, context: ComponentActionContext) -> Dict[str, Any]:
        node_id         = await context.render_variable(self.config.node_id)
        relationship_id = await context.render_variable(self.config.relationship_id)
        properties      = await context.render_variable(self.config.properties)
        collection      = await context.render_variable(getattr(self.config, "collection", None))

        affected_rows = 0

        if node_id is not None and properties:
            for id in node_id if isinstance(node_id, list) else [ node_id ]:
                collection_name, doc = ArangoDBQueryBuilder.build_update_doc(str(id), properties, collection or "nodes")
                self.database.collection(collection_name).update(doc)
                affected_rows += 1

        if relationship_id is not None and properties:
            for id in relationship_id if isinstance(relationship_id, list) else [ relationship_id ]:
                collection_name, doc = ArangoDBQueryBuilder.build_update_doc(str(id), properties, collection or "edges")
                self.database.collection(collection_name).update(doc)
                affected_rows += 1

        return { "affected_rows": affected_rows }

    async def _delete(self, context: ComponentActionContext) -> Dict[str, Any]:
        node_id         = await context.render_variable(self.config.node_id)
        relationship_id = await context.render_variable(self.config.relationship_id)
        collection      = await context.render_variable(getattr(self.config, "collection", None))

        affected_rows = 0

        if node_id is not None:
            for id in node_id if isinstance(node_id, list) else [ node_id ]:
                collection_name, key = ArangoDBQueryBuilder.resolve_doc_id(str(id), collection or "nodes")
                self.database.collection(collection_name).delete(key)
                affected_rows += 1

        if relationship_id is not None:
            for id in relationship_id if isinstance(relationship_id, list) else [ relationship_id ]:
                collection_name, key = ArangoDBQueryBuilder.resolve_doc_id(str(id), collection or "edges")
                self.database.collection(collection_name).delete(key)
                affected_rows += 1

        return { "affected_rows": affected_rows }

    async def _traverse(self, context: ComponentActionContext) -> List[Dict[str, Any]]:
        start_node         = await context.render_variable(self.config.start_node)
        relationship_types = await context.render_variable(self.config.relationship_types)
        graph_name         = await context.render_variable(getattr(self.config, "graph", None))
        edge_collection    = await context.render_variable(getattr(self.config, "edge_collection", None))

        direction_map = { "out": "outbound", "in": "inbound", "both": "any" }
        direction = direction_map.get(self.config.direction, "outbound")

        if graph_name:
            ArangoDBQueryBuilder.verify_identifier(graph_name, "graph")
            graph = self.database.graph(graph_name)
            result = graph.traverse(
                start_vertex=str(start_node),
                direction=direction,
                max_depth=self.config.max_depth
            )

            vertices = result.get("vertices", [])
            return [ { "node": vertex, "depth": None } for vertex in vertices[1:] ]

        aql, bind_vars = ArangoDBQueryBuilder.build_traverse(
            start_node,
            self.config.direction,
            self.config.max_depth,
            edge_collection,
            relationship_types,
        )
        cursor = self.database.aql.execute(aql, bind_vars=bind_vars)
        
        return [ doc for doc in cursor ]

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
        async def _run():
            return await ArangoDBGraphStoreAction(action, self.database).run(context)

        return await self.run_in_thread(_run)

    def _create_client(self) -> Tuple[ArangoClient, StandardDatabase]:
        from arango import ArangoClient

        url = self.config.url if self.config.url else f"{self.config.protocol}://{self.config.host}:{self.config.port}"
        client = ArangoClient(
            hosts=url,
            request_timeout=parse_duration(self.config.timeout)
        )

        database = client.db(
            self.config.database,
            username=self.config.username,
            password=self.config.password
        ) if self.config.username else client.db(self.config.database)

        return client, database
