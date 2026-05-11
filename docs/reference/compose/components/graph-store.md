# Graph Store Component

The graph store component enables storing, querying, and traversing graph data using various backend databases. It supports operations like inserting nodes and relationships, updating properties, querying with native graph query languages, deleting elements, and traversing graph paths, making it ideal for knowledge graphs, social networks, recommendation engines, and relationship-driven data models.

## Basic Configuration

```yaml
component:
  type: graph-store
  driver: neo4j
  url: bolt://localhost:7687
  username: neo4j
  password: password
  action:
    method: query
    query: "MATCH (n:Person) RETURN n LIMIT 10"
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `graph-store` |
| `driver` | string | **required** | Backend driver: `neo4j`, `arangodb` |
| `actions` | array | `[]` | List of graph store actions |

### Common Action Configuration

All graph store actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Operation method: `query`, `insert`, `update`, `delete`, `traverse` |
| `output` | any | `null` | Output mapping to transform action results |

## Supported Drivers

### Neo4j

Neo4j for native property graph storage with Cypher query language:

```yaml
component:
  type: graph-store
  driver: neo4j
  url: bolt://localhost:7687
  username: neo4j
  password: password
  database: mydb
```

**Neo4j Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | `bolt://localhost:7687` | Neo4j connection URL (`bolt://`, `neo4j://`, `neo4j+s://`) |
| `username` | string | `null` | Username for authentication |
| `password` | string | `null` | Password for authentication |
| `database` | string | `null` | Target database name. Uses default database if not specified |
| `timeout` | string | `30s` | Client operation timeout |

### ArangoDB

ArangoDB for multi-model graph, document, and key-value storage with AQL query language:

```yaml
component:
  type: graph-store
  driver: arangodb
  host: localhost
  port: 8529
  username: root
  password: password
  database: social
```

**ArangoDB Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | string | `localhost` | Server hostname or IP address |
| `port` | integer | `8529` | Server port number (1-65535) |
| `protocol` | string | `http` | Connection protocol: `http`, `https` |
| `username` | string | `null` | Username for authentication |
| `password` | string | `null` | Password for authentication |
| `database` | string | `_system` | Target database name |
| `timeout` | string | `30s` | Client operation timeout |

## Graph Store Operations

### Query

Execute native graph queries using the driver's query language (Cypher for Neo4j, AQL for ArangoDB):

```yaml
# Neo4j - Cypher
component:
  type: graph-store
  driver: neo4j
  url: bolt://localhost:7687
  action:
    method: query
    query: "MATCH (p:Person)-[:KNOWS]->(friend) WHERE p.name = $name RETURN friend"
    params:
      name: ${input.name}
    output:
      friends: ${result}
```

```yaml
# ArangoDB - AQL
component:
  type: graph-store
  driver: arangodb
  action:
    method: query
    query: "FOR p IN persons FILTER p.name == @name FOR f IN OUTBOUND p friendships RETURN f"
    params:
      name: ${input.name}
    output:
      friends: ${result}
```

**Query Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `query` |
| `query` | string | **required** | Native graph query string |
| `params` | object | `null` | Query parameters to bind |
| `database` | string | `null` | Target database (Neo4j only, overrides component setting) |
| `collection` | string | `null` | Target collection context (ArangoDB only) |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | array | List of result records as dictionaries |

### Insert

Add nodes and/or relationships to the graph:

```yaml
component:
  type: graph-store
  driver: neo4j
  action:
    method: insert
    nodes:
      label: Person
      properties:
        name: ${input.name}
        age: ${input.age}
    output:
      result: ${result}
```

```yaml
# Insert a relationship
component:
  type: graph-store
  driver: neo4j
  action:
    method: insert
    relationships:
      type: KNOWS
      from: ${input.from_id}
      to: ${input.to_id}
      properties:
        since: ${input.year}
```

```yaml
# Insert multiple nodes at once
component:
  type: graph-store
  driver: neo4j
  action:
    method: insert
    nodes:
      - label: Person
        properties:
          name: Alice
      - label: Person
        properties:
          name: Bob
```

**Insert Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `insert` |
| `nodes` | object/array | `null` | Node(s) to insert with `label` and `properties` |
| `relationships` | object/array | `null` | Relationship(s) to insert with `type`, `from`, `to`, and `properties` |
| `collection` | string | `null` | Target collection (ArangoDB only) |
| `edge_collection` | string | `null` | Edge collection for relationships (ArangoDB only) |
| `graph` | string | `null` | Named graph to operate on (ArangoDB only) |

**Node Format:**

| Field | Type | Description |
|-------|------|-------------|
| `label` | string | Node label (Neo4j) or collection name (ArangoDB) |
| `properties` | object | Key-value properties for the node |
| `id` | string | Optional node key (ArangoDB `_key`) |

**Relationship Format:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Relationship type (Neo4j) or edge collection name (ArangoDB) |
| `from` | string | Source node ID |
| `to` | string | Target node ID |
| `properties` | object | Optional key-value properties for the relationship |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.created_nodes` | integer | Number of nodes created |
| `result.created_relationships` | integer | Number of relationships created |

### Update

Modify properties or labels of existing nodes and relationships:

```yaml
component:
  type: graph-store
  driver: neo4j
  action:
    method: update
    node_id: ${input.node_id}
    properties:
      age: ${input.new_age}
      email: ${input.email}
    labels: Senior
```

```yaml
# Update a relationship
component:
  type: graph-store
  driver: neo4j
  action:
    method: update
    relationship_id: ${input.rel_id}
    properties:
      weight: ${input.new_weight}
```

**Update Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `update` |
| `node_id` | string/array | `null` | ID(s) of node(s) to update |
| `relationship_id` | string/array | `null` | ID(s) of relationship(s) to update |
| `properties` | object | `null` | Properties to set on the target element(s) |
| `labels` | string/array | `null` | Label(s) to add to target node(s) (Neo4j only) |
| `collection` | string | `null` | Target collection (ArangoDB only) |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.affected_rows` | integer | Number of elements updated |

### Delete

Remove nodes and/or relationships from the graph:

```yaml
component:
  type: graph-store
  driver: neo4j
  action:
    method: delete
    node_id: ${input.node_id}
    detach: true
```

```yaml
# Delete a relationship only
component:
  type: graph-store
  driver: neo4j
  action:
    method: delete
    relationship_id: ${input.rel_id}
```

**Delete Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `delete` |
| `node_id` | string/array | `null` | ID(s) of node(s) to delete |
| `relationship_id` | string/array | `null` | ID(s) of relationship(s) to delete |
| `detach` | boolean | `true` | Also delete connected relationships when deleting nodes |
| `collection` | string | `null` | Target collection (ArangoDB only) |

> **Note**: In Neo4j, deleting a node with existing relationships requires `detach: true` (default). Setting `detach: false` will fail if the node has connections.

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.affected_rows` | integer | Number of elements deleted |

### Traverse

Perform graph traversal to discover connected nodes along paths:

```yaml
component:
  type: graph-store
  driver: neo4j
  action:
    method: traverse
    start_node: ${input.person_id}
    direction: both
    max_depth: 3
    relationship_types: [KNOWS, WORKS_WITH]
    node_labels: [Person]
    output:
      connections: ${result}
```

```yaml
# ArangoDB traversal using named graph
component:
  type: graph-store
  driver: arangodb
  action:
    method: traverse
    start_node: persons/${input.person_key}
    graph: social_graph
    direction: out
    max_depth: 2
```

**Traverse Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `traverse` |
| `start_node` | string | **required** | Starting node ID for traversal |
| `direction` | string | `out` | Traversal direction: `in`, `out`, `both` |
| `max_depth` | integer | `3` | Maximum traversal depth (minimum: 1) |
| `relationship_types` | array | `null` | Filter to specific relationship types |
| `node_labels` | array | `null` | Filter to nodes with specific labels |
| `graph` | string | `null` | Named graph to traverse (ArangoDB only) |
| `edge_collection` | string | `null` | Edge collection to traverse (ArangoDB only) |

**Return Value (Neo4j):**

| Field | Type | Description |
|-------|------|-------------|
| `result[].node` | object | Discovered node properties |
| `result[].depth` | integer | Distance from start node |
| `result[].relationship_types` | array | Relationship types along the path |

**Return Value (ArangoDB with named graph):**

| Field | Type | Description |
|-------|------|-------------|
| `result[].node` | object | Discovered vertex document |
| `result[].depth` | integer | Distance from start vertex |

## Multiple Actions Configuration

Define multiple graph store operations on one component:

```yaml
component:
  type: graph-store
  driver: neo4j
  url: bolt://localhost:7687
  username: neo4j
  password: password
  actions:
    - id: add-person
      method: insert
      nodes:
        label: Person
        properties:
          name: ${input.name}
          age: ${input.age}

    - id: add-friendship
      method: insert
      relationships:
        type: KNOWS
        from: ${input.from_id}
        to: ${input.to_id}
        properties:
          since: ${input.since}

    - id: find-person
      method: query
      query: "MATCH (p:Person {name: $name}) RETURN p"
      params:
        name: ${input.name}

    - id: find-connections
      method: traverse
      start_node: ${input.node_id}
      direction: both
      max_depth: 2
      relationship_types: [KNOWS]

    - id: update-person
      method: update
      node_id: ${input.node_id}
      properties:
        age: ${input.new_age}

    - id: remove-person
      method: delete
      node_id: ${input.node_id}
      detach: true
```

## Node ID Formats

### Neo4j

Neo4j uses `elementId()` format (e.g., `4:abc123:0`). These are returned by insert operations and used in update/delete/traverse actions.

### ArangoDB

ArangoDB uses `collection/key` format (e.g., `persons/12345`). When `node_id` or `relationship_id` contains a `/`, the collection name is extracted automatically. Otherwise, the `collection` field is used.

```yaml
# Full ID format - collection is extracted automatically
action:
  method: update
  node_id: persons/12345
  properties:
    age: 31

# Key-only format - requires collection field
action:
  method: update
  collection: persons
  node_id: "12345"
  properties:
    age: 31
```

## Integration with Workflows

Build knowledge graph pipelines using workflows:

```yaml
workflows:
  - id: build-knowledge-graph
    title: Build Knowledge Graph
    description: Extract entities and relationships, then store in graph
    jobs:
      - id: extract-entities
        component: llm
        input:
          prompt: "Extract person entities from: ${input.text}"
        output: ${output as json}

      - id: store-entities
        component: knowledge-graph
        action: add-person
        input:
          name: ${jobs.extract-entities.output.name}
          age: ${jobs.extract-entities.output.age}
        depends_on: [extract-entities]

  - id: find-related-people
    title: Find Related People
    jobs:
      - id: traverse
        component: knowledge-graph
        action: find-connections
        input:
          node_id: ${input.person_id}
        output: ${output as json}

components:
  - id: knowledge-graph
    type: graph-store
    driver: neo4j
    url: bolt://localhost:7687
    username: neo4j
    password: password
    actions:
      - id: add-person
        method: insert
        nodes:
          label: Person
          properties:
            name: ${input.name}
            age: ${input.age}

      - id: find-connections
        method: traverse
        start_node: ${input.node_id}
        direction: both
        max_depth: 2
        relationship_types: [KNOWS]

  - id: llm
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
      output: ${response.choices[0].message.content}
```

## Advanced Usage Examples

### Knowledge Graph with RAG

Combine graph store with vector store for graph-enhanced RAG:

```yaml
workflows:
  - id: graph-rag-query
    jobs:
      - id: find-entity
        component: knowledge-graph
        action: search-entity
        input:
          name: ${input.entity}

      - id: get-neighbors
        component: knowledge-graph
        action: find-connections
        input:
          node_id: ${jobs.find-entity.output.result[0].id}
        depends_on: [find-entity]

      - id: generate-answer
        component: llm
        input:
          prompt: |
            Based on the following knowledge graph context, answer the question.

            Entity: ${input.entity}
            Connected entities: ${jobs.get-neighbors.output.result}

            Question: ${input.question}
        depends_on: [get-neighbors]

components:
  - id: knowledge-graph
    type: graph-store
    driver: neo4j
    url: bolt://localhost:7687
    actions:
      - id: search-entity
        method: query
        query: "MATCH (n) WHERE n.name = $name RETURN n, elementId(n) AS id"
        params:
          name: ${input.name}

      - id: find-connections
        method: traverse
        start_node: ${input.node_id}
        direction: both
        max_depth: 2
```

### Social Network Analysis

```yaml
components:
  - id: social-graph
    type: graph-store
    driver: arangodb
    host: localhost
    database: social
    username: root
    password: password
    actions:
      - id: mutual-friends
        method: query
        query: |
          FOR friend1 IN OUTBOUND @person1 friendships
            FOR friend2 IN OUTBOUND @person2 friendships
              FILTER friend1._id == friend2._id
              RETURN friend1
        params:
          person1: ${input.person1_id}
          person2: ${input.person2_id}

      - id: shortest-path
        method: query
        query: |
          FOR v, e IN OUTBOUND
            SHORTEST_PATH @from TO @to friendships
            RETURN { vertex: v, edge: e }
        params:
          from: ${input.from_id}
          to: ${input.to_id}
```

### Fraud Detection Graph

```yaml
components:
  - id: fraud-graph
    type: graph-store
    driver: neo4j
    url: bolt://localhost:7687
    actions:
      - id: find-suspicious-patterns
        method: query
        query: |
          MATCH (a:Account)-[:TRANSFERRED_TO]->(b:Account)-[:TRANSFERRED_TO]->(c:Account)
          WHERE a = c AND a <> b
          RETURN a, b, c,
                 [(a)-[t:TRANSFERRED_TO]->(b) | t.amount] AS amounts
        output:
          circular_transfers: ${result}

      - id: trace-money-flow
        method: traverse
        start_node: ${input.account_id}
        direction: out
        max_depth: 5
        relationship_types: [TRANSFERRED_TO]
```

## Error Handling

Graph store operations can fail for various reasons:

- **Connection Issues**: Database server unreachable
- **Authentication Errors**: Invalid credentials
- **Query Errors**: Syntax errors in Cypher/AQL queries
- **Constraint Violations**: Unique constraint conflicts on insert
- **Not Found**: Node or relationship ID does not exist

Use workflow error handling to manage failures:

```yaml
workflow:
  jobs:
    - id: store-data
      component: knowledge-graph
      action: add-person
      input:
        name: ${input.name}
      on_error:
        - id: log-failure
          component: logger
          input:
            message: "Failed to store: ${input.name}"
```

## Variable Interpolation

Graph store supports dynamic configuration:

```yaml
component:
  type: graph-store
  driver: ${env.GRAPH_DB_DRIVER | neo4j}
  url: ${env.NEO4J_URL | bolt://localhost:7687}
  username: ${env.NEO4J_USER}
  password: ${env.NEO4J_PASSWORD}
  action:
    method: query
    query: "MATCH (n:${input.label}) WHERE n.name = $name RETURN n"
    params:
      name: ${input.name}
```

## Best Practices

1. **Use Native Queries for Complex Operations**: For complex graph patterns, prefer the `query` method with Cypher/AQL over multiple insert/update calls
2. **Detach Delete by Default**: Always use `detach: true` when deleting nodes to avoid orphaned relationship errors
3. **Limit Traversal Depth**: Set appropriate `max_depth` to prevent runaway traversals on large graphs
4. **Parameterize Queries**: Use `params` instead of string interpolation in query strings to prevent injection and improve caching
5. **Use Named Graphs (ArangoDB)**: Prefer named graphs over ad-hoc edge collections for consistent traversal behavior
6. **Index Key Properties**: Create indexes on frequently queried properties in your graph database for better performance
7. **Batch Inserts**: For bulk loading, use the `query` method with batch Cypher/AQL rather than individual insert operations
8. **Connection Reuse**: Define one graph store component and reference it from multiple workflows

## Common Use Cases

- **Knowledge Graphs**: Store and query structured knowledge with entities and relationships
- **Social Networks**: Model user connections, find mutual friends, shortest paths
- **Recommendation Engines**: Traverse user-item-category graphs for personalized suggestions
- **Fraud Detection**: Identify suspicious patterns like circular transfers or unusual connections
- **Dependency Analysis**: Map software dependencies, infrastructure relationships
- **Genealogy / Org Charts**: Model hierarchical relationships with traversal queries
- **Supply Chain**: Track product flows through manufacturing and distribution networks
- **Network Topology**: Model and analyze IT infrastructure, routing, and connectivity
