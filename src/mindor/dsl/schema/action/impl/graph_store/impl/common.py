from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
import re
from pydantic import BaseModel, Field, field_validator
from pydantic import model_validator
from ...common import CommonActionConfig

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _validate_identifier(value: str) -> str:
    if "${" in value:
        return value
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(
            f"Invalid identifier '{value}': must match [A-Za-z_][A-Za-z0-9_]* "
            f"(use the 'query' method for complex expressions)"
        )
    return value

class GraphStoreActionMethod(str, Enum):
    QUERY    = "query"
    INSERT   = "insert"
    UPDATE   = "update"
    DELETE   = "delete"
    TRAVERSE = "traverse"

class GraphNodeConfig(BaseModel):
    label: str = Field(..., description="Node label (Neo4j) or collection name (ArangoDB).")
    properties: Union[Dict[str, Any], str] = Field(default_factory=dict, description="Key-value properties for the node.")
    id: Optional[Union[str, int]] = Field(default=None, description="Optional node key (ArangoDB _key).")

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        return _validate_identifier(v)

class GraphRelationshipConfig(BaseModel):
    type: str = Field(..., description="Relationship type (Neo4j) or edge collection name (ArangoDB).")
    from_node: Union[str, int] = Field(..., alias="from", description="Source node ID.")
    to_node: Union[str, int] = Field(..., alias="to", description="Target node ID.")
    properties: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Key-value properties for the relationship.")

    model_config = {"populate_by_name": True}

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        return _validate_identifier(v)

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

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v):
        if v is None:
            return v
        items = v if isinstance(v, list) else [v]
        for item in items:
            _validate_identifier(item)
        return v

class CommonGraphDeleteActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.DELETE]
    node_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID(s) of node(s) to delete.")
    relationship_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID(s) of relationship(s) to delete.")
    detach: bool = Field(default=True, description="Also delete connected relationships when deleting nodes.")

class CommonGraphTraverseActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.TRAVERSE]
    start_node: Union[str, int] = Field(..., description="Starting node ID for traversal.")
    direction: Literal["in", "out", "both"] = Field(default="out", description="Traversal direction relative to start node.")
    max_depth: int = Field(default=3, ge=1, description="Maximum traversal depth.")
    relationship_types: Optional[List[str]] = Field(default=None, description="Filter traversal to specific relationship types.")
    node_labels: Optional[List[str]] = Field(default=None, description="Filter traversal to nodes with specific labels.")

    @field_validator("relationship_types")
    @classmethod
    def validate_relationship_types(cls, v):
        if v is None:
            return v
        for item in v:
            _validate_identifier(item)
        return v

    @field_validator("node_labels")
    @classmethod
    def validate_node_labels(cls, v):
        if v is None:
            return v
        for item in v:
            _validate_identifier(item)
        return v
