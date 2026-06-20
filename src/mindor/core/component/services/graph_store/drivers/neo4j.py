from __future__ import annotations
from typing import TYPE_CHECKING

import re
from typing import Union, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import GraphStoreComponentConfig
from mindor.dsl.schema.action import GraphStoreActionConfig
from mindor.core.utils.time import parse_duration
from ..base import GraphStoreService, GraphStoreDriver, register_graph_store_service
from ..base import ComponentActionContext
from .common import GraphStoreAction

if TYPE_CHECKING:
    from neo4j import AsyncDriver, AsyncSession

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

class Neo4jQueryBuilder:
    @staticmethod
    def verify_identifier(value: str, field: str) -> str:
        if not _IDENTIFIER_PATTERN.match(value):
            raise ValueError(f"Invalid {field} identifier: '{value}'")
        return value

    @staticmethod
    def build_create_node(label: str, properties: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        label = Neo4jQueryBuilder.verify_identifier(label, "label")
        prop_str = ", ".join(f"{k}: ${k}" for k in properties.keys())
        cypher = f"CREATE (n:{label} {{{prop_str}}}) RETURN elementId(n) AS id"
        return cypher, properties

    @staticmethod
    def build_create_relationship(rel_type: str, from_id: str, to_id: str, properties: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        rel_type = Neo4jQueryBuilder.verify_identifier(rel_type, "relationship type")
        prop_params = { f"prop_{k}": v for k, v in properties.items() }
        params: Dict[str, Any] = { "from_id": from_id, "to_id": to_id, **prop_params }

        if properties:
            prop_str = ", ".join(f"{k}: $prop_{k}" for k in properties.keys())
            cypher = f"MATCH (a), (b) WHERE elementId(a) = $from_id AND elementId(b) = $to_id CREATE (a)-[r:{rel_type} {{{prop_str}}}]->(b) RETURN elementId(r) AS id"
        else:
            cypher = f"MATCH (a), (b) WHERE elementId(a) = $from_id AND elementId(b) = $to_id CREATE (a)-[r:{rel_type}]->(b) RETURN elementId(r) AS id"

        return cypher, params

    @staticmethod
    def build_update_node(node_id: str, properties: Optional[Dict[str, Any]], labels: Optional[Union[str, List[str]]]) -> Optional[Tuple[str, Dict[str, Any]]]:
        clauses = []
        params: Dict[str, Any] = { "id": node_id }

        if properties:
            set_parts = []
            for k, v in properties.items():
                params[f"prop_{k}"] = v
                set_parts.append(f"n.{k} = $prop_{k}")
            clauses.append("SET " + ", ".join(set_parts))

        if labels:
            label_list = labels if isinstance(labels, list) else [labels]
            for label in label_list:
                Neo4jQueryBuilder.verify_identifier(label, "label")
                clauses.append(f"SET n:{label}")

        if not clauses:
            return None

        cypher = f"MATCH (n) WHERE elementId(n) = $id {' '.join(clauses)} RETURN n"
        return cypher, params

    @staticmethod
    def build_update_relationship(relationship_id: str, properties: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        params: Dict[str, Any] = { "id": relationship_id }
        set_parts = []
        for k, v in properties.items():
            params[f"prop_{k}"] = v
            set_parts.append(f"r.{k} = $prop_{k}")
        cypher = f"MATCH ()-[r]->() WHERE elementId(r) = $id SET {', '.join(set_parts)} RETURN r"
        return cypher, params

    @staticmethod
    def build_delete_node(node_id: str, detach: bool) -> Tuple[str, Dict[str, Any]]:
        delete_clause = "DETACH DELETE n" if detach else "DELETE n"
        cypher = f"MATCH (n) WHERE elementId(n) = $id {delete_clause}"
        return cypher, { "id": node_id }

    @staticmethod
    def build_delete_relationship(relationship_id: str) -> Tuple[str, Dict[str, Any]]:
        cypher = "MATCH ()-[r]->() WHERE elementId(r) = $id DELETE r"
        return cypher, { "id": relationship_id }

    @staticmethod
    def build_traverse(
        start_node: str,
        direction: str,
        max_depth: int,
        relationship_types: Optional[List[str]],
        node_labels: Optional[List[str]],
    ) -> Tuple[str, Dict[str, Any]]:
        rel_filter = ""
        if relationship_types:
            for rt in relationship_types:
                Neo4jQueryBuilder.verify_identifier(rt, "relationship type")
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
                Neo4jQueryBuilder.verify_identifier(nl, "node label")
            label_filter = " AND (" + " OR ".join(f"ANY(l IN labels(end) WHERE l = '{label}')" for label in node_labels) + ")"

        cypher = f"MATCH p = {path_pattern} WHERE elementId(start) = $start_id{label_filter} RETURN end AS node, length(p) AS depth, [rel IN relationships(p) | type(rel)] AS relationship_types"

        return cypher, { "start_id": start_node }

class Neo4jGraphStoreAction(GraphStoreAction):
    async def _query(self, context: ComponentActionContext) -> List[Dict[str, Any]]:
        query  = await context.render_variable(self.config.query)
        params = await context.render_variable(self.config.params)

        result = await self.database.run(query, parameters=params or {})
        records = await result.data()

        return records

    async def _insert(self, context: ComponentActionContext) -> Dict[str, Any]:
        nodes         = await context.render_variable(self.config.nodes)
        relationships = await context.render_variable(self.config.relationships)

        node_ids: List[str] = []
        relationship_ids: List[str] = []
        created_nodes = 0
        created_relationships = 0

        if nodes:
            for node in nodes if isinstance(nodes, list) else [ nodes ]:
                cypher, params = Neo4jQueryBuilder.build_create_node(
                    node.get("label", "Node"),
                    node.get("properties", {}),
                )
                result = await self.database.run(cypher, parameters=params)
                record = await result.single()
                if record:
                    node_ids.append(record["id"])
                created_nodes += 1

        if relationships:
            for relation in relationships if isinstance(relationships, list) else [ relationships ]:
                cypher, params = Neo4jQueryBuilder.build_create_relationship(
                    relation.get("type", "RELATED_TO"),
                    relation.get("from"),
                    relation.get("to"),
                    relation.get("properties", {}) or {},
                )
                result = await self.database.run(cypher, parameters=params)
                record = await result.single()
                if record:
                    relationship_ids.append(record["id"])
                created_relationships += 1

        return {
            "ids": node_ids + relationship_ids,
            "created_nodes": created_nodes,
            "created_relationships": created_relationships,
        }

    async def _update(self, context: ComponentActionContext) -> Dict[str, Any]:
        node_id         = await context.render_variable(self.config.node_id)
        relationship_id = await context.render_variable(self.config.relationship_id)
        properties      = await context.render_variable(self.config.properties)
        labels          = await context.render_variable(self.config.labels)

        affected_rows = 0

        if node_id is not None:
            for id in node_id if isinstance(node_id, list) else [ node_id ]:
                built = Neo4jQueryBuilder.build_update_node(id, properties, labels)
                if built:
                    cypher, params = built
                    await self.database.run(cypher, parameters=params)
                    affected_rows += 1

        if relationship_id is not None:
            for id in relationship_id if isinstance(relationship_id, list) else [ relationship_id ]:
                if properties:
                    cypher, params = Neo4jQueryBuilder.build_update_relationship(id, properties)
                    await self.database.run(cypher, parameters=params)
                    affected_rows += 1

        return { "affected_rows": affected_rows }

    async def _delete(self, context: ComponentActionContext) -> Dict[str, Any]:
        node_id         = await context.render_variable(self.config.node_id)
        relationship_id = await context.render_variable(self.config.relationship_id)
        detach          = await context.render_variable(self.config.detach)

        affected_rows = 0

        if node_id is not None:
            for id in node_id if isinstance(node_id, list) else [ node_id ]:
                cypher, params = Neo4jQueryBuilder.build_delete_node(id, detach)
                await self.database.run(cypher, parameters=params)
                affected_rows += 1

        if relationship_id is not None:
            for id in relationship_id if isinstance(relationship_id, list) else [ relationship_id ]:
                cypher, params = Neo4jQueryBuilder.build_delete_relationship(id)
                await self.database.run(cypher, parameters=params)
                affected_rows += 1

        return { "affected_rows": affected_rows }

    async def _traverse(self, context: ComponentActionContext) -> List[Dict[str, Any]]:
        start_node         = await context.render_variable(self.config.start_node)
        relationship_types = await context.render_variable(self.config.relationship_types)
        node_labels        = await context.render_variable(self.config.node_labels)

        cypher, params = Neo4jQueryBuilder.build_traverse(
            start_node,
            self.config.direction,
            self.config.max_depth,
            relationship_types,
            node_labels,
        )

        result = await self.database.run(cypher, parameters=params)
        records = await result.data()

        return records

@register_graph_store_service(GraphStoreDriver.NEO4J)
class Neo4jGraphStoreService(GraphStoreService):
    def __init__(self, id: str, config: GraphStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.driver: Optional[AsyncDriver] = None
        self.session: Optional[AsyncSession] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "neo4j" ]

    async def _start(self) -> None:
        self.driver = self._create_driver()
        self.session = self.driver.session(database=self.config.database)
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        if self.session:
            await self.session.close()
            self.session = None
        if self.driver:
            await self.driver.close()
            self.driver = None

    async def _run(self, action: GraphStoreActionConfig, context: ComponentActionContext) -> Any:
        return await Neo4jGraphStoreAction(action, self.session).run(context)

    def _create_driver(self) -> AsyncDriver:
        from neo4j import AsyncGraphDatabase

        auth = (self.config.username, self.config.password) if self.config.username else None
        url = self.config.url if self.config.url else f"{self.config.protocol}://{self.config.host}:{self.config.port}"

        return AsyncGraphDatabase.driver(
            url,
            auth=auth,
            connection_timeout=parse_duration(self.config.timeout)
        )
