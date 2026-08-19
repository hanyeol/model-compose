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
    properties: Union[Dict[str, Any], str] = Field(default_factory=dict, description="Key-value properties attached to the node.")
    id: Optional[Union[str, int]] = Field(default=None, description="Explicit key assigned to the node; auto-generated when omitted.")

class GraphRelationshipConfig(BaseModel):
    type: str = Field(..., description="Relationship type (Neo4j) or edge collection name (ArangoDB).")
    from_: Union[str, int] = Field(..., alias="from", description="ID of the source node.")
    to: Union[str, int] = Field(..., description="ID of the target node.")
    properties: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Key-value properties attached to the relationship.")

    model_config = { "populate_by_name": True }  # `from` is a reserved keyword, so allow `from_` too.

class CommonGraphStoreActionConfig(CommonActionConfig):
    method: GraphStoreActionMethod = Field(..., description="Graph store operation this action performs.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of items processed per batch.")

class CommonGraphQueryActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.QUERY]
    query: Union[str, List[str]] = Field(..., description="Native graph query or list of queries (Cypher for Neo4j, AQL for ArangoDB).")
    params: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Parameter values bound into the query.")

class CommonGraphInsertActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.INSERT]
    node: Optional[Union[GraphNodeConfig, List[GraphNodeConfig], str]] = Field(default=None, description="Node or nodes inserted into the graph.")
    relationship: Optional[Union[GraphRelationshipConfig, List[GraphRelationshipConfig], str]] = Field(default=None, description="Relationship or relationships inserted into the graph.")

class CommonGraphUpdateActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.UPDATE]
    node_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID or IDs of nodes to update.")
    relationship_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID or IDs of relationships to update.")
    properties: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Property values set on the target elements.")
    labels: Optional[Union[str, List[str]]] = Field(default=None, description="Labels added to the target nodes.")

class CommonGraphDeleteActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.DELETE]
    node_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID or IDs of nodes to delete.")
    relationship_id: Optional[Union[Union[str, int], List[Union[str, int]], str]] = Field(default=None, description="ID or IDs of relationships to delete.")
    detach: Union[bool, str] = Field(default=True, description="Whether connected relationships are deleted along with each node.")

class CommonGraphTraverseActionConfig(CommonGraphStoreActionConfig):
    method: Literal[GraphStoreActionMethod.TRAVERSE]
    start_node: Union[Union[str, int], List[Union[str, int]], str] = Field(..., description="ID or IDs of nodes the traversal starts from.")
    direction: Literal[ "in", "out", "both" ] = Field(default="out", description="Direction the traversal follows relative to the start node.")
    max_depth: int = Field(default=3, ge=1, description="Maximum traversal depth in edges.")
    relationship_types: Optional[List[str]] = Field(default=None, description="Relationship types the traversal is restricted to.")
    node_labels: Optional[List[str]] = Field(default=None, description="Node labels the traversal is restricted to.")
