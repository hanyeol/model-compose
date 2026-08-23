# SQLite Key-Value Store Example

This example demonstrates how to use model-compose with SQLite as a key-value store for storing, retrieving, and managing data in workflows.

## Overview

This workflow provides basic key-value store operations:

1. **Set**: Store a value with an optional TTL (time-to-live)
2. **Get**: Retrieve a stored value by key
3. **Delete**: Remove a key from the store
4. **Exists**: Check if a key exists

The SQLite driver persists entries to a local database file, so data survives controller restarts. It requires no external server, making it a lightweight alternative to Redis when you need durability but not a full network-accessible store.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH

No external services are required. SQLite is embedded and the database file is created on first use.

### Environment Configuration

Navigate to this example directory:
```bash
cd examples/integrations/key-value-store/sqlite
```

The example writes to `storage/kv-store.sqlite` (relative to this directory) by default. The `storage/` directory and the database file are created automatically when the controller starts.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflows:**

   **Set a value:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "set-value", "input": {"key": "greeting", "value": "Hello, World!", "ttl": 3600}}'
   ```

   **Get a value:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "get-value", "input": {"key": "greeting"}}'
   ```

   **Check if a key exists:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "check-value", "input": {"key": "greeting"}}'
   ```

   **Delete a key:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "delete-value", "input": {"key": "greeting"}}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select the desired workflow (set, get, delete, exists)
   - Enter your input parameters
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   # Set a value with TTL
   model-compose run set-value --input '{"key": "user:1", "value": {"name": "Alice", "role": "admin"}, "ttl": 86400}'

   # Get a value
   model-compose run get-value --input '{"key": "user:1"}'

   # Check existence
   model-compose run check-value --input '{"key": "user:1"}'

   # Delete a key
   model-compose run delete-value --input '{"key": "user:1"}'
   ```

## Component Details

### SQLite Key-Value Store Component (kv)
- **Type**: Key-value store component
- **Purpose**: Store and retrieve key-value pairs
- **Driver**: SQLite (embedded)
- **Features**:
  - Basic CRUD operations (get, set, delete, exists)
  - TTL support for automatic key expiration
  - JSON serialization/deserialization for complex values
  - Persistent storage in a single database file
  - No external server required

## Workflow Details

### "Set Value" Workflow

**Description**: Store a key-value pair in SQLite with optional TTL.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | Yes | - | Key to store |
| `value` | any | Yes | - | Value to store (string, number, object, array) |
| `ttl` | integer | No | null | Time-to-live in seconds. null = no expiry |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the operation succeeded |

### "Get Value" Workflow

**Description**: Retrieve a value by key from SQLite.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | Yes | - | Key to retrieve |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `value` | any \| null | Stored value. null if key does not exist |

### "Delete Value" Workflow

**Description**: Delete a key from SQLite.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | Yes | - | Key to delete |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `count` | integer | Number of keys deleted (0 or 1) |

### "Check Exists" Workflow

**Description**: Check if a key exists in SQLite.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | Yes | - | Key to check |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `exists` | boolean | Whether the key exists |

## Customization

### Database Location

Set `path` to control where the SQLite file lives. Relative paths are resolved against the example directory. Use an absolute path to keep the database elsewhere, or `:memory:` for a non-persistent in-memory database.

```yaml
components:
  - id: kv
    type: key-value-store
    driver: sqlite
    path: /var/lib/model-compose/kv-store.sqlite
```

```yaml
components:
  - id: kv
    type: key-value-store
    driver: sqlite
    path: ":memory:"
```

### Table Name

By default entries are stored in a table named `kv_store`. Override it with `table` if you want to co-locate multiple stores in one database file:

```yaml
components:
  - id: sessions
    type: key-value-store
    driver: sqlite
    path: app.sqlite
    table: sessions

  - id: cache
    type: key-value-store
    driver: sqlite
    path: app.sqlite
    table: cache
```

### Value Types

The component automatically handles serialization:
- **Strings**: Stored as-is
- **Objects/Arrays**: Serialized as JSON, automatically deserialized on retrieval
- **Numbers/Booleans**: Converted to string for storage
