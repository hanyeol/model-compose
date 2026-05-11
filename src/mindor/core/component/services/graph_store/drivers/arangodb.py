from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import GraphStoreComponentConfig
from mindor.dsl.schema.action import GraphStoreActionConfig, ArangoDBGraphStoreActionConfig
from mindor.dsl.schema.action import GraphStoreActionMethod
from mindor.core.utils.time import parse_duration
from mindor.core.logger import logging
from ..base import GraphStoreService, GraphStoreDriver, register_graph_store_service
from ..base import ComponentActionContext
import re

if TYPE_CHECKING:
    from arango import ArangoClient
    from arango.database import StandardDatabase

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _verify_identifier(value: str, field: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {field} identifier: '{value}'")
    return value

def _resolve_doc_id(doc_id: str, default_collection: str) -> Tuple[str, str]:
    if "/" in doc_id:
        collection, key = doc_id.split("/", 1)
        return collection, key
    return default_collection, doc_id

def _build_insert_node_doc(node: Dict[str, Any], default_collection: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    collection = _verify_identifier(node.get("label", default_collection or "nodes"), "collection")
    doc = { **node.get("properties", {}) }
    node_id = node.get("id")
    if node_id:
        doc["_key"] = str(node_id)
    return collection, doc

def _build_insert_edge_doc(rel: Dict[str, Any], default_edge_collection: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    collection = _verify_identifier(default_edge_collection or rel.get("type", "edges"), "edge collection")
    doc = {
        "_from": rel.get("from"),
        "_to": rel.get("to"),
        **(rel.get("properties", {}) or {}),
    }
    return collection, doc

def _build_update_doc(doc_id: str, properties: Dict[str, Any], default_collection: str) -> Tuple[str, Dict[str, Any]]:
    collection, key = _resolve_doc_id(doc_id, default_collection)
    doc = { "_key": key, **properties }
    return collection, doc

def _build_traverse_query(
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
            _verify_identifier(collection, "edge collection")
        edge_str = ", ".join(edge_collections)
    else:
        edge_str = "edges"

    aql = f"FOR v, e, p IN 1..@max_depth {arango_direction.upper()} @start_node {edge_str} RETURN {{node: v, edge: e, depth: LENGTH(p.edges)}}"
    return aql, { "start_node": str(start_node), "max_depth": max_depth }

class ArangoDBGraphStoreAction:
    def __init__(self, config: ArangoDBGraphStoreActionConfig):
        self.config: ArangoDBGraphStoreActionConfig = config

    async def run(self, context: ComponentActionContext, db: StandardDatabase) -> Any:
        result = await self._dispatch(context, db)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext, db: StandardDatabase) -> Any:
        if self.config.method == GraphStoreActionMethod.QUERY:
            return await self._query(context, db)

        if self.config.method == GraphStoreActionMethod.INSERT:
            return await self._insert(context, db)

        if self.config.method == GraphStoreActionMethod.UPDATE:
            return await self._update(context, db)

        if self.config.method == GraphStoreActionMethod.DELETE:
            return await self._delete(context, db)

        if self.config.method == GraphStoreActionMethod.TRAVERSE:
            return await self._traverse(context, db)

        raise ValueError(f"Unsupported graph action method: {self.config.method}")

    async def _query(self, context: ComponentActionContext, db: StandardDatabase) -> List[Dict[str, Any]]:
        query  = await context.render_variable(self.config.query)
        params = await context.render_variable(self.config.params)

        cursor = db.aql.execute(query, bind_vars=params or {})
        return [ doc for doc in cursor ]

    async def _insert(self, context: ComponentActionContext, db: StandardDatabase) -> Dict[str, Any]:
        nodes           = await context.render_variable(self.config.nodes)
        relationships   = await context.render_variable(self.config.relationships)
        collection      = getattr(self.config, "collection", None)
        edge_collection = getattr(self.config, "edge_collection", None)

        created_nodes = 0
        created_relationships = 0
        inserted_ids: List[str] = []

        if nodes:
            node_list = nodes if isinstance(nodes, list) else [nodes]
            for node in node_list:
                collection_name, doc = _build_insert_node_doc(node, collection)

                if not db.has_collection(collection_name):
                    db.create_collection(collection_name)

                result = db.collection(collection_name).insert(doc)
                inserted_ids.append(result.get("_id", result.get("_key", "")))
                created_nodes += 1

        if relationships:
            for relationship in relationships if isinstance(relationships, list) else [ relationships ]:
                collection_name, doc = _build_insert_edge_doc(relationship, edge_collection)

                if not db.has_collection(collection_name):
                    db.create_collection(collection_name, edge=True)

                result = db.collection(collection_name).insert(doc)
                inserted_ids.append(result.get("_id", result.get("_key", "")))
                created_relationships += 1

        return {
            "ids": inserted_ids,
            "created_nodes": created_nodes,
            "created_relationships": created_relationships,
        }

    async def _update(self, context: ComponentActionContext, db: StandardDatabase) -> Dict[str, Any]:
        node_id         = await context.render_variable(self.config.node_id)
        relationship_id = await context.render_variable(self.config.relationship_id)
        properties      = await context.render_variable(self.config.properties)
        collection      = getattr(self.config, "collection", None)

        affected_rows = 0

        if node_id is not None and properties:
            node_ids = node_id if isinstance(node_id, list) else [node_id]
            for nid in node_ids:
                collection_name, doc = _build_update_doc(str(nid), properties, collection or "nodes")
                db.collection(collection_name).update(doc)
                affected_rows += 1

        if relationship_id is not None and properties:
            rel_ids = relationship_id if isinstance(relationship_id, list) else [relationship_id]
            for rid in rel_ids:
                collection_name, doc = _build_update_doc(str(rid), properties, collection or "edges")
                db.collection(collection_name).update(doc)
                affected_rows += 1

        return {"affected_rows": affected_rows}

    async def _delete(self, context: ComponentActionContext, db: StandardDatabase) -> Dict[str, Any]:
        node_id         = await context.render_variable(self.config.node_id)
        relationship_id = await context.render_variable(self.config.relationship_id)
        collection      = getattr(self.config, "collection", None)

        affected_rows = 0

        if node_id is not None:
            node_ids = node_id if isinstance(node_id, list) else [node_id]
            for nid in node_ids:
                collection_name, key = _resolve_doc_id(str(nid), collection or "nodes")
                db.collection(collection_name).delete(key)
                affected_rows += 1

        if relationship_id is not None:
            rel_ids = relationship_id if isinstance(relationship_id, list) else [relationship_id]
            for rid in rel_ids:
                collection_name, key = _resolve_doc_id(str(rid), collection or "edges")
                db.collection(collection_name).delete(key)
                affected_rows += 1

        return {"affected_rows": affected_rows}

    async def _traverse(self, context: ComponentActionContext, db: StandardDatabase) -> List[Dict[str, Any]]:
        start_node         = await context.render_variable(self.config.start_node)
        relationship_types = await context.render_variable(self.config.relationship_types)
        node_labels        = await context.render_variable(self.config.node_labels)
        graph_name         = getattr(self.config, "graph", None)
        edge_collection      = getattr(self.config, "edge_collection", None)

        direction_map = {"out": "outbound", "in": "inbound", "both": "any"}
        arango_direction = direction_map.get(self.config.direction, "outbound")

        if graph_name:
            graph = db.graph(graph_name)
            result = graph.traverse(
                start_vertex=str(start_node),
                direction=arango_direction,
                max_depth=self.config.max_depth
            )

            vertices = result.get("vertices", [])
            return [{"node": vertex, "depth": None} for vertex in vertices[1:]]

        aql, bind_vars = _build_traverse_query(
            start_node,
            self.config.direction,
            self.config.max_depth,
            edge_collection,
            relationship_types,
        )
        cursor = db.aql.execute(aql, bind_vars=bind_vars)
        return [doc for doc in cursor]

@register_graph_store_service(GraphStoreDriver.ARANGODB)
class ArangoDBGraphStoreService(GraphStoreService):
    def __init__(self, id: str, config: GraphStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[ArangoClient] = None
        self.db: Optional[StandardDatabase] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return ["python-arango"]

    async def _serve(self) -> None:
        self.client, self.db = self._create_client()

    async def _shutdown(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    async def _run(self, action: GraphStoreActionConfig, context: ComponentActionContext) -> Any:
        async def _run():
            return await ArangoDBGraphStoreAction(action).run(context, self.db)

        return await self.run_in_thread(_run)

    def _create_client(self) -> Tuple[ArangoClient, StandardDatabase]:
        from arango import ArangoClient

        url = self.config.url if self.config.url else f"{self.config.protocol}://{self.config.host}:{self.config.port}"
        client = ArangoClient(
            hosts=url,
            request_timeout=parse_duration(self.config.timeout).total_seconds()
        )

        database = client.db(
            self.config.database,
            username=self.config.username,
            password=self.config.password
        ) if self.config.username else client.db(self.config.database)

        return client, database
