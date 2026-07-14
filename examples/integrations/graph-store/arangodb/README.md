# ArangoDB Graph Store Example

This example demonstrates how to use model-compose with ArangoDB as a graph store for building and querying social graphs.

## Overview

This workflow provides graph database operations using ArangoDB:

1. **Add Person**: Insert a person document into the graph
2. **Find Friends**: Query friends using AQL (ArangoDB Query Language)
3. **Find Connections**: Traverse the social graph to discover connections

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- ArangoDB server running (local or remote)

### ArangoDB Installation

**Using Docker:**
```bash
docker run -d --name arangodb \
  -p 8529:8529 \
  -e ARANGO_ROOT_PASSWORD=password \
  arangodb
```

**Using Homebrew (macOS):**
```bash
brew install arangodb
brew services start arangodb
```

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/graph-store/arangodb
   ```

2. Ensure ArangoDB is running on `localhost:8529` (default port).

3. Access ArangoDB Web UI at http://localhost:8529 to verify the connection.

4. Create the database and collections:
   - Create a database named `social`
   - Create a document collection named `persons`
   - Create an edge collection named `friendships`
   - Create a named graph `social_graph` with edge definition: `friendships` (from: `persons`, to: `persons`)

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

   **Find friends:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-friends", "input": {"name": "Alice"}}'
   ```

   **Find connections:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-connections", "input": {"node_id": "persons/12345"}}'
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

   # Find friends by name
   model-compose run find-friends --input '{"name": "Alice"}'

   # Find connections (traverse)
   model-compose run find-connections --input '{"node_id": "persons/12345"}'
   ```

## Component Details

### ArangoDB Graph Store Component (social-graph)
- **Type**: Graph store component
- **Purpose**: Store and query graph-structured data
- **Driver**: ArangoDB
- **Features**:
  - Document and edge CRUD operations
  - AQL query execution
  - Named graph traversal with configurable depth and direction
  - Connection via URL or host/port

## Workflow Details

### "Add Person" Workflow

**Description**: Insert a person document into the graph.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | - | Person's name |
| `age` | integer | Yes | - | Person's age |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `ids` | array | List of created document IDs |
| `created_nodes` | integer | Number of documents created |
| `created_relationships` | integer | Number of edges created |

### "Find Friends" Workflow

**Description**: Query friends by name using AQL.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | Yes | - | Person's name to search |

#### Output Format

Returns a list of matching documents with their properties.

### "Find Connections" Workflow

**Description**: Traverse the social graph to find connections within 2 hops.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `node_id` | string | Yes | - | Starting document ID (e.g., `persons/12345`) |

#### Output Format

Returns a list of connected documents with depth and path information.

## Customization

### ArangoDB Connection

#### Using URL
```yaml
components:
  - id: social-graph
    type: graph-store
    driver: arangodb
    url: http://localhost:8529
    username: root
    password: password
    database: social
```

#### Using Host/Port
```yaml
components:
  - id: social-graph
    type: graph-store
    driver: arangodb
    host: arangodb.example.com
    port: 8529
    protocol: https
    username: root
    password: ${env.ARANGO_PASSWORD}
    database: social
```

### ArangoDB-Specific Features

- **Named Graphs**: Use the `graph` field in actions to leverage ArangoDB's named graph feature for traversals
- **Collections**: Specify `collection` for document operations and `edge_collection` for edge operations
- **AQL Queries**: Write custom AQL queries with bind parameters for flexible data access
