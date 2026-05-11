from __future__ import annotations
from typing import TYPE_CHECKING

import re
from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import GraphStoreComponentConfig
from mindor.dsl.schema.action import GraphStoreActionConfig, Neo4jGraphStoreActionConfig
from mindor.dsl.schema.action import GraphStoreActionMethod
from mindor.core.utils.time import parse_duration
from mindor.core.logger import logging
from ..base import GraphStoreService, GraphStoreDriver, register_graph_store_service
from ..base import ComponentActionContext

if TYPE_CHECKING:
    from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _verify_identifier(value: str, field: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {field} identifier: '{value}'")
    return value

def _build_create_node_query(label: str, properties: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    label = _verify_identifier(label, "label")
    prop_str = ", ".join(f"{k}: ${k}" for k in properties.keys())
    cypher = f"CREATE (n:{label} {{{prop_str}}}) RETURN elementId(n) AS id"
    return cypher, properties

def _build_create_relationship_query(
    rel_type: str, from_id: str, to_id: str, properties: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    rel_type = _verify_identifier(rel_type, "relationship type")
    prop_params = {f"prop_{k}": v for k, v in properties.items()}
    params: Dict[str, Any] = {"from_id": from_id, "to_id": to_id, **prop_params}

    if properties:
        prop_str = ", ".join(f"{k}: $prop_{k}" for k in properties.keys())
        cypher = f"MATCH (a), (b) WHERE elementId(a) = $from_id AND elementId(b) = $to_id CREATE (a)-[r:{rel_type} {{{prop_str}}}]->(b) RETURN elementId(r) AS id"
    else:
        cypher = f"MATCH (a), (b) WHERE elementId(a) = $from_id AND elementId(b) = $to_id CREATE (a)-[r:{rel_type}]->(b) RETURN elementId(r) AS id"

    return cypher, params

def _build_update_node_query(
    node_id: str, properties: Optional[Dict[str, Any]], labels: Optional[Union[str, List[str]]]
) -> Optional[Tuple[str, Dict[str, Any]]]:
    clauses = []
    params: Dict[str, Any] = {"id": node_id}

    if properties:
        set_parts = []
        for k, v in properties.items():
            params[f"prop_{k}"] = v
            set_parts.append(f"n.{k} = $prop_{k}")
        clauses.append("SET " + ", ".join(set_parts))

    if labels:
        label_list = labels if isinstance(labels, list) else [labels]
        for label in label_list:
            _verify_identifier(label, "label")
            clauses.append(f"SET n:{label}")

    if not clauses:
        return None

    cypher = f"MATCH (n) WHERE elementId(n) = $id {' '.join(clauses)} RETURN n"
    return cypher, params

def _build_update_relationship_query(
    relationship_id: str, properties: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    params: Dict[str, Any] = {"id": relationship_id}
    set_parts = []
    for k, v in properties.items():
        params[f"prop_{k}"] = v
        set_parts.append(f"r.{k} = $prop_{k}")
    cypher = f"MATCH ()-[r]->() WHERE elementId(r) = $id SET {', '.join(set_parts)} RETURN r"
    return cypher, params

def _build_delete_node_query(node_id: str, detach: bool) -> Tuple[str, Dict[str, Any]]:
    delete_clause = "DETACH DELETE n" if detach else "DELETE n"
    cypher = f"MATCH (n) WHERE elementId(n) = $id {delete_clause}"
    return cypher, {"id": node_id}

def _build_delete_relationship_query(relationship_id: str) -> Tuple[str, Dict[str, Any]]:
    cypher = "MATCH ()-[r]->() WHERE elementId(r) = $id DELETE r"
    return cypher, {"id": relationship_id}

def _build_traverse_query(
    start_node: str,
    direction: str,
    max_depth: int,
    relationship_types: Optional[List[str]],
    node_labels: Optional[List[str]],
) -> Tuple[str, Dict[str, Any]]:
    rel_filter = ""
    if relationship_types:
        for rt in relationship_types:
            _verify_identifier(rt, "relationship type")
        rel_filter = ":" + "|".join(relationship_types)

    if direction == "out":
        path_pattern = f"(start)-[r{rel_filter}*1..{max_depth}]->(end)"
    elif direction == "in":
        path_pattern = f"(start)<-[r{rel_filter}*1..{max_depth}]-(end)"
    else:
        path_pattern = f"(start)-[r{rel_filter}*1..{max_depth}]-(end)"

    label_filter = ""
    if node_labels:
        for nl in node_labels:
            _verify_identifier(nl, "node label")
        label_filter = " AND (" + " OR ".join(f"ANY(l IN labels(end) WHERE l = '{label}')" for label in node_labels) + ")"

    cypher = f"MATCH p = {path_pattern} WHERE elementId(start) = $start_id{label_filter} RETURN end AS node, length(p) AS depth, [rel IN relationships(p) | type(rel)] AS relationship_types"
    return cypher, {"start_id": start_node}

class Neo4jGraphStoreAction:
    def __init__(self, config: Neo4jGraphStoreActionConfig):
        self.config: Neo4jGraphStoreActionConfig = config

    async def run(self, context: ComponentActionContext, driver: AsyncDriver, default_database: Optional[str]) -> Any:
        result = await self._dispatch(context, driver, default_database)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext, driver: AsyncDriver, default_database: Optional[str]) -> Any:
        if self.config.method == GraphStoreActionMethod.QUERY:
            return await self._query(context, driver, default_database)

        if self.config.method == GraphStoreActionMethod.INSERT:
            return await self._insert(context, driver, default_database)

        if self.config.method == GraphStoreActionMethod.UPDATE:
            return await self._update(context, driver, default_database)

        if self.config.method == GraphStoreActionMethod.DELETE:
            return await self._delete(context, driver, default_database)

        if self.config.method == GraphStoreActionMethod.TRAVERSE:
            return await self._traverse(context, driver, default_database)

        raise ValueError(f"Unsupported graph action method: {self.config.method}")

    def _get_database(self, default_database: Optional[str]) -> Optional[str]:
        return getattr(self.config, "database", None) or default_database

    async def _query(self, context: ComponentActionContext, driver: AsyncDriver, default_database: Optional[str]) -> List[Dict[str, Any]]:
        query  = await context.render_variable(self.config.query)
        params = await context.render_variable(self.config.params)
        database = self._get_database(default_database)

        async with driver.session(database=database) as session:
            result = await session.run(query, parameters=params or {})
            records = await result.data()
            return records

    async def _insert(self, context: ComponentActionContext, driver: AsyncDriver, default_database: Optional[str]) -> Dict[str, Any]:
        nodes         = await context.render_variable(self.config.nodes)
        relationships = await context.render_variable(self.config.relationships)
        database      = self._get_database(default_database)

        created_nodes = 0
        created_relationships = 0

        node_ids: List[str] = []
        relationship_ids: List[str] = []

        async with driver.session(database=database) as session:
            if nodes:
                node_list = nodes if isinstance(nodes, list) else [nodes]
                for node in node_list:
                    cypher, params = _build_create_node_query(
                        node.get("label", "Node"),
                        node.get("properties", {}),
                    )
                    result = await session.run(cypher, parameters=params)
                    record = await result.single()
                    if record:
                        node_ids.append(record["id"])
                    created_nodes += 1

            if relationships:
                rel_list = relationships if isinstance(relationships, list) else [relationships]
                for rel in rel_list:
                    cypher, params = _build_create_relationship_query(
                        rel.get("type", "RELATED_TO"),
                        rel.get("from"),
                        rel.get("to"),
                        rel.get("properties", {}) or {},
                    )
                    result = await session.run(cypher, parameters=params)
                    record = await result.single()
                    if record:
                        relationship_ids.append(record["id"])
                    created_relationships += 1

        return {
            "ids": node_ids + relationship_ids,
            "created_nodes": created_nodes,
            "created_relationships": created_relationships,
        }

    async def _update(self, context: ComponentActionContext, driver: AsyncDriver, default_database: Optional[str]) -> Dict[str, Any]:
        node_id         = await context.render_variable(self.config.node_id)
        relationship_id = await context.render_variable(self.config.relationship_id)
        properties      = await context.render_variable(self.config.properties)
        labels          = await context.render_variable(self.config.labels)
        database        = self._get_database(default_database)

        affected_rows = 0

        async with driver.session(database=database) as session:
            if node_id is not None:
                node_ids = node_id if isinstance(node_id, list) else [node_id]
                for nid in node_ids:
                    built = _build_update_node_query(nid, properties, labels)
                    if built:
                        cypher, params = built
                        await session.run(cypher, parameters=params)
                        affected_rows += 1

            if relationship_id is not None:
                rel_ids = relationship_id if isinstance(relationship_id, list) else [relationship_id]
                for rid in rel_ids:
                    if properties:
                        cypher, params = _build_update_relationship_query(rid, properties)
                        await session.run(cypher, parameters=params)
                        affected_rows += 1

        return {"affected_rows": affected_rows}

    async def _delete(self, context: ComponentActionContext, driver: AsyncDriver, default_database: Optional[str]) -> Dict[str, Any]:
        node_id         = await context.render_variable(self.config.node_id)
        relationship_id = await context.render_variable(self.config.relationship_id)
        detach          = self.config.detach
        database        = self._get_database(default_database)

        affected_rows = 0

        async with driver.session(database=database) as session:
            if node_id is not None:
                node_ids = node_id if isinstance(node_id, list) else [node_id]
                for nid in node_ids:
                    cypher, params = _build_delete_node_query(nid, detach)
                    await session.run(cypher, parameters=params)
                    affected_rows += 1

            if relationship_id is not None:
                rel_ids = relationship_id if isinstance(relationship_id, list) else [relationship_id]
                for rid in rel_ids:
                    cypher, params = _build_delete_relationship_query(rid)
                    await session.run(cypher, parameters=params)
                    affected_rows += 1

        return {"affected_rows": affected_rows}

    async def _traverse(self, context: ComponentActionContext, driver: AsyncDriver, default_database: Optional[str]) -> List[Dict[str, Any]]:
        start_node         = await context.render_variable(self.config.start_node)
        relationship_types = await context.render_variable(self.config.relationship_types)
        node_labels        = await context.render_variable(self.config.node_labels)
        database           = self._get_database(default_database)

        cypher, params = _build_traverse_query(
            start_node,
            self.config.direction,
            self.config.max_depth,
            relationship_types,
            node_labels,
        )

        async with driver.session(database=database) as session:
            result = await session.run(cypher, parameters=params)
            records = await result.data()
            return records

@register_graph_store_service(GraphStoreDriver.NEO4J)
class Neo4jGraphStoreService(GraphStoreService):
    def __init__(self, id: str, config: GraphStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.driver: Optional[AsyncDriver] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return ["neo4j"]

    async def _serve(self) -> None:
        self.driver = self._create_driver()

    async def _shutdown(self) -> None:
        if self.driver:
            await self.driver.close()
            self.driver = None

    async def _run(self, action: GraphStoreActionConfig, context: ComponentActionContext) -> Any:
        return await Neo4jGraphStoreAction(action).run(context, self.driver, self.config.database)

    def _create_driver(self) -> AsyncDriver:
        from neo4j import AsyncGraphDatabase

        auth = (self.config.username, self.config.password) if self.config.username else None
        url = self.config.url if self.config.url else f"{self.config.protocol}://{self.config.host}:{self.config.port}"

        return AsyncGraphDatabase.driver(
            url,
            auth=auth,
            connection_timeout=parse_duration(self.config.timeout).total_seconds()
        )
