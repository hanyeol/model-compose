from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonActionConfig

class GraphStoreActionMethod(str, Enum):
    QUERY    = "query"
    INSERT   = "insert"
    UPDATE   = "update"
    DELETE   = "delete"
    TRAVERSE = "traverse"

class GraphNodeConfig(BaseModel):
    label: str = Field(..., description="Node label (Neo4j) or collection name (ArangoDB).")
    properties: Union[Dict[str, Any], str] = Field(default_factory=dict, description="Key-value properties for the node.")
    id: Optional[Union[str, int]] = Field(default=None, description="Optional node key.")

class GraphRelationshipConfig(BaseModel):
    type: str = Field(..., description="Relationship type (Neo4j) or edge collection name (ArangoDB).")
    from_: Union[str, int] = Field(..., alias="from", description="Source node ID.")
    to: Union[str, int] = Field(..., description="Target node ID.")
    properties: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Key-value properties for the relationship.")

    model_config = { "populate_by_name": True }  # `from` is a reserved keyword, so allow `from_` too.

class CommonGraphStoreActionConfig(CommonActionConfig):
    method: GraphStoreActionMethod = Field(..., description="Graph store operation method.")

class CommonGraphQueryActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.QUERY]
    query: str = Field(..., description="Native graph query string (Cypher for Neo4j, AQL for ArangoDB).")
    params: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Query parameters to bind.")

class CommonGraphInsertActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.INSERT]
    nodes: Optional[Union[GraphNodeConfig, List[GraphNodeConfig], str]] = Field(default=None, description="Node(s) to insert.")
    relationships: Optional[Union[GraphRelationshipConfig, List[GraphRelationshipConfig], str]] = Field(default=None, description="Relationship(s) to insert.")

class CommonGraphUpdateActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.UPDATE]
    node_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID(s) of node(s) to update.")
    relationship_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID(s) of relationship(s) to update.")
    properties: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Properties to set on the target element(s).")
    labels: Optional[Union[str, List[str]]] = Field(default=None, description="Label(s) to add to the target node(s).")

class CommonGraphDeleteActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.DELETE]
    node_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID(s) of node(s) to delete.")
    relationship_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID(s) of relationship(s) to delete.")
    detach: Union[bool, str] = Field(default=True, description="Also delete connected relationships when deleting nodes.")

class CommonGraphTraverseActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.TRAVERSE]
    start_node: Union[str, int] = Field(..., description="Starting node ID for traversal.")
    direction: Literal[ "in", "out", "both" ] = Field(default="out", description="Traversal direction relative to start node.")
    max_depth: int = Field(default=3, ge=1, description="Maximum traversal depth.")
    relationship_types: Optional[List[str]] = Field(default=None, description="Filter traversal to specific relationship types.")
    node_labels: Optional[List[str]] = Field(default=None, description="Filter traversal to nodes with specific labels.")
