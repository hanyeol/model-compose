# Redis Key-Value Store Example

This example demonstrates how to use model-compose with Redis as a key-value store for storing, retrieving, and managing data in workflows.

## Overview

This workflow provides basic key-value store operations:

1. **Set**: Store a value with an optional TTL (time-to-live)
2. **Get**: Retrieve a stored value by key
3. **Delete**: Remove a key from the store
4. **Exists**: Check if a key exists

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Redis server running (local or remote)

### Redis Installation

**Using Docker:**
```bash
docker run -d --name redis -p 6379:6379 redis
```

**Using Homebrew (macOS):**
```bash
brew install redis
brew services start redis
```

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/key-value-store/redis
   ```

2. Ensure Redis is running on `localhost:6379` (default configuration).

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

### Redis Key-Value Store Component (kv)
- **Type**: Key-value store component
- **Purpose**: Store and retrieve key-value pairs
- **Driver**: Redis
- **Features**:
  - Basic CRUD operations (get, set, delete, exists)
  - TTL support for automatic key expiration
  - JSON serialization/deserialization for complex values
  - Connection via host/port or URL

## Workflow Details

### "Set Value" Workflow

**Description**: Store a key-value pair in Redis with optional TTL.

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

**Description**: Retrieve a value by key from Redis.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | Yes | - | Key to retrieve |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `value` | any \| null | Stored value. null if key does not exist |

### "Delete Value" Workflow

**Description**: Delete a key from Redis.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | Yes | - | Key to delete |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `count` | integer | Number of keys deleted (0 or 1) |

### "Check Exists" Workflow

**Description**: Check if a key exists in Redis.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | Yes | - | Key to check |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `exists` | boolean | Whether the key exists |

## Customization

### Redis Connection

#### Using URL
```yaml
components:
  - id: kv
    type: key-value-store
    driver: redis
    url: redis://localhost:6379/0
```

#### Remote Redis with Authentication
```yaml
components:
  - id: kv
    type: key-value-store
    driver: redis
    host: redis.example.com
    port: 6379
    password: ${env.REDIS_PASSWORD}
    database: 1
    secure: true
```

### Value Types

The component automatically handles serialization:
- **Strings**: Stored as-is
- **Objects/Arrays**: Serialized as JSON, automatically deserialized on retrieval
- **Numbers/Booleans**: Converted to string for storage
