# Neo4j Graph Store Example

This example demonstrates how to use model-compose with Neo4j as a graph store for building and querying knowledge graphs.

## Overview

This workflow provides graph database operations using Neo4j:

1. **Add Person**: Insert a person node into the knowledge graph
2. **Add Friendship**: Create a KNOWS relationship between two people
3. **Find Person**: Query a person by name using Cypher
4. **Find Connections**: Traverse the graph to discover connected people

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Neo4j server running (local or remote)

### Neo4j Installation

**Using Docker:**
```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j
```

**Using Homebrew (macOS):**
```bash
brew install neo4j
neo4j start
```

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/graph-store/neo4j
   ```

2. Ensure Neo4j is running on `localhost:7687` (default Bolt port).

3. Access Neo4j Browser at http://localhost:7474 to verify the connection.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflows:**

   **Add a person:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "add-person", "input": {"name": "Alice", "age": 30}}'
   ```

   **Add a friendship:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "add-friendship", "input": {"from_id": "<node_id_1>", "to_id": "<node_id_2>", "since": "2024-01-01"}}'
   ```

   **Find a person:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-person", "input": {"name": "Alice"}}'
   ```

   **Find connections:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-connections", "input": {"node_id": "<node_id>"}}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select the desired workflow
   - Enter your input parameters
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   # Add a person
   model-compose run add-person --input '{"name": "Alice", "age": 30}'

   # Find a person
   model-compose run find-person --input '{"name": "Alice"}'

   # Find connections (traverse)
   model-compose run find-connections --input '{"node_id": "<node_id>"}'
   ```

## Component Details

### Neo4j Graph Store Component (knowledge-graph)
- **Type**: Graph store component
- **Purpose**: Store and query graph-structured data
- **Driver**: Neo4j
- **Features**:
  - Node and relationship CRUD operations
  - Cypher query execution
  - Graph traversal with configurable depth and direction
  - Connection via URL or host/port

## Workflow Details

### "Add Person" Workflow

**Description**: Insert a person node into the knowledge graph.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | - | Person's name |
| `age` | integer | Yes | - | Person's age |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `ids` | array | List of created node element IDs |
| `created_nodes` | integer | Number of nodes created |
| `created_relationships` | integer | Number of relationships created |

### "Add Friendship" Workflow

**Description**: Create a KNOWS relationship between two people.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `from_id` | string | Yes | - | Source node element ID |
| `to_id` | string | Yes | - | Target node element ID |
| `since` | string | Yes | - | Date the friendship started |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `ids` | array | List of created relationship element IDs |
| `created_nodes` | integer | Number of nodes created |
| `created_relationships` | integer | Number of relationships created |

### "Find Person" Workflow

**Description**: Find a person by name using Cypher query.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | - | Person's name to search |

#### Output Format

Returns a list of matching records with node properties.

### "Find Connections" Workflow

**Description**: Traverse the graph to find connected people within 2 hops.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `node_id` | string | Yes | - | Starting node element ID |

#### Output Format

Returns a list of connected nodes with depth and relationship type information.

## Customization

### Neo4j Connection

#### Using URL
```yaml
components:
  - id: knowledge-graph
    type: graph-store
    driver: neo4j
    url: bolt://localhost:7687
```

#### Using Host/Port
```yaml
components:
  - id: knowledge-graph
    type: graph-store
    driver: neo4j
    host: neo4j.example.com
    port: 7687
    protocol: neo4j+s
    username: neo4j
    password: ${env.NEO4J_PASSWORD}
```

### Supported Protocols

| Protocol | Description |
|----------|-------------|
| `bolt` | Unencrypted Bolt connection |
| `bolt+s` | Bolt with TLS (verified certificate) |
| `bolt+ssc` | Bolt with TLS (self-signed certificate) |
| `neo4j` | Neo4j protocol (supports routing) |
| `neo4j+s` | Neo4j protocol with TLS (verified certificate) |
| `neo4j+ssc` | Neo4j protocol with TLS (self-signed certificate) |
