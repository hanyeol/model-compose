# Key-Value Store Component

The key-value store component enables storing, retrieving, and managing key-value pairs using various backend databases. It supports operations like get, set, delete, and exists, making it ideal for caching, session management, and data sharing between workflows.

## Basic Configuration

```yaml
component:
  type: key-value-store
  driver: redis
  host: localhost
  port: 6379
  action:
    method: set
    key: "session:${input.session_id}"
    value: ${input.data}
    ttl: 3600
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `key-value-store` |
| `driver` | string | **required** | Backend driver: `redis` |
| `actions` | array | `[]` | List of key-value store actions |

### Common Action Configuration

All key-value store actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Operation method: `get`, `set`, `delete`, `exists` |

## Supported Drivers

### Redis

Redis for high-performance in-memory key-value storage:

```yaml
component:
  type: key-value-store
  driver: redis
  host: localhost
  port: 6379
  database: 0
```

**Redis Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | `null` | Redis connection URL (e.g., `redis://localhost:6379`, `rediss://localhost:6379` for TLS) |
| `host` | string | `localhost` | Server hostname or IP address |
| `port` | integer | `6379` | Server port number (1-65535) |
| `secure` | boolean | `false` | Use TLS/SSL for connections (equivalent to `rediss://` protocol) |
| `database` | integer | `0` | Database number (0-15) |
| `password` | string | `null` | Redis password |

> **Note**: `url` and `host` are mutually exclusive. If `url` is provided, `host`/`port`/`secure`/`database` are ignored.

**Using URL:**

```yaml
component:
  type: key-value-store
  driver: redis
  url: redis://localhost:6379/0
```

**Using host/port with authentication:**

```yaml
component:
  type: key-value-store
  driver: redis
  host: redis.example.com
  port: 6379
  password: ${env.REDIS_PASSWORD}
  database: 1
  secure: true
```

## Key-Value Store Operations

### Get Value

Retrieve a value by key:

```yaml
component:
  type: key-value-store
  driver: redis
  action:
    method: get
    key: "session:${input.session_id}"
    output:
      data: ${result.value}
```

**Get Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `get` |
| `key` | string | **required** | Key to retrieve |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.value` | any \| null | Stored value. `null` if key does not exist |

### Set Value

Store a value with optional TTL:

```yaml
component:
  type: key-value-store
  driver: redis
  action:
    method: set
    key: "cache:${input.prompt_hash}"
    value: ${input.response}
    ttl: 3600
    output:
      ok: ${result.success}
```

**Set Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `set` |
| `key` | string | **required** | Key to store |
| `value` | any | **required** | Value to store |
| `ttl` | integer | `null` | Time-to-live in seconds. `null` = no expiry |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.success` | boolean | Whether the operation succeeded |

### Delete Key

Remove a key from the store:

```yaml
component:
  type: key-value-store
  driver: redis
  action:
    method: delete
    key: "session:${input.session_id}"
    output:
      deleted: ${result.count}
```

**Delete Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `delete` |
| `key` | string | **required** | Key to delete |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.count` | integer | Number of keys deleted (0 or 1) |

### Check Existence

Check if a key exists:

```yaml
component:
  type: key-value-store
  driver: redis
  action:
    method: exists
    key: "session:${input.session_id}"
    output:
      exists: ${result.exists}
```

**Exists Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `exists` |
| `key` | string | **required** | Key to check |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.exists` | boolean | Whether the key exists |

## Multiple Actions Configuration

Define multiple key-value store operations:

```yaml
component:
  type: key-value-store
  driver: redis
  host: localhost
  port: 6379
  actions:
    - id: save-session
      method: set
      key: "session:${input.user_id}"
      value: ${input.session_data}
      ttl: 86400
      output:
        success: ${result.success}

    - id: load-session
      method: get
      key: "session:${input.user_id}"
      output:
        session: ${result.value}

    - id: delete-session
      method: delete
      key: "session:${input.user_id}"
      output:
        deleted: ${result.count}

    - id: check-session
      method: exists
      key: "session:${input.user_id}"
      output:
        exists: ${result.exists}
```

## Value Serialization

The key-value store handles value serialization automatically:

### Storing Values (`set`)

| Input Type | Storage |
|------------|---------|
| `string` | Stored as-is |
| `dict`, `list` | Serialized via `json.dumps()` |
| `int`, `float`, `bool` | Converted to string |

### Retrieving Values (`get`)

On retrieval, the component attempts JSON parsing:
1. If JSON parsing succeeds, returns the parsed object (dict, list, etc.)
2. If JSON parsing fails, returns the raw string

This means objects and arrays stored via `set` are automatically deserialized on `get`.

## Advanced Usage Examples

### API Response Caching

```yaml
workflows:
  - id: cached-chat
    jobs:
      - id: check-cache
        component: cache
        action: get-response
        input:
          prompt_hash: ${input.prompt}

      - id: generate
        component: openai
        condition: ${jobs.check-cache.output.cached == null}
        input:
          prompt: ${input.prompt}

      - id: save-cache
        component: cache
        action: set-response
        condition: ${jobs.check-cache.output.cached == null}
        input:
          prompt_hash: ${input.prompt}
          response: ${jobs.generate.output.message}
    output:
      message: ${jobs.check-cache.output.cached ?? jobs.generate.output.message}

components:
  - id: cache
    type: key-value-store
    driver: redis
    host: localhost
    actions:
      - id: get-response
        method: get
        key: "chat:${input.prompt_hash}"
        output:
          cached: ${result.value}
      - id: set-response
        method: set
        key: "chat:${input.prompt_hash}"
        value: ${input.response}
        ttl: 3600
```

### Session Management

```yaml
components:
  - id: session-store
    type: key-value-store
    driver: redis
    url: redis://localhost:6379/1
    actions:
      - id: save
        method: set
        key: "session:${input.user_id}"
        value:
          history: ${input.history}
          preferences: ${input.preferences}
        ttl: 86400

      - id: load
        method: get
        key: "session:${input.user_id}"
        output:
          session: ${result.value}

      - id: logout
        method: delete
        key: "session:${input.user_id}"
```

### Workflow Data Sharing

Share intermediate results between different workflow executions:

```yaml
components:
  - id: shared-store
    type: key-value-store
    driver: redis
    host: localhost
    actions:
      - id: store-result
        method: set
        key: "pipeline:${input.run_id}:${input.step}"
        value: ${input.result}
        ttl: 7200

      - id: fetch-result
        method: get
        key: "pipeline:${input.run_id}:${input.step}"
        output:
          data: ${result.value}
```

## Error Handling

Key-value store operations can fail for various reasons:

- **Connection Issues**: Redis server unreachable
- **Authentication Errors**: Invalid password or access denied
- **Key Not Found**: `get` returns `null` for non-existent keys (not an error)
- **Memory Limits**: Redis server out of memory

Use workflow error handling to manage failures:

```yaml
workflow:
  jobs:
    - id: load-data
      component: cache
      action: load
      input:
        key: ${input.key}
      on_error:
        - id: fallback
          component: database
          input:
            key: ${input.key}
```

## Variable Interpolation

Key-value store supports dynamic configuration:

```yaml
component:
  type: key-value-store
  driver: redis
  host: ${env.REDIS_HOST | localhost}
  port: ${env.REDIS_PORT | 6379}
  password: ${env.REDIS_PASSWORD}
  action:
    method: set
    key: "${input.namespace}:${input.key}"
    value: ${input.data}
    ttl: ${input.ttl}
```

## Best Practices

1. **Key Naming**: Use consistent key naming conventions with namespaces (e.g., `session:user123`, `cache:api:response`)
2. **TTL Management**: Always set TTL for cache entries to prevent unbounded memory growth
3. **Value Size**: Keep values reasonably sized; use references for large objects
4. **Connection Reuse**: Define one key-value store component and reference it from multiple workflows
5. **Error Handling**: Handle `null` return values from `get` gracefully in workflow conditions
6. **Security**: Store Redis passwords in environment variables, use TLS for remote connections

## Integration with Workflows

Reference key-value store in workflow jobs:

```yaml
workflow:
  jobs:
    - id: check-cache
      component: cache
      action: get-data
      input:
        key: ${input.cache_key}

    - id: process
      component: processor
      condition: ${jobs.check-cache.output.data == null}
      input:
        raw_data: ${input.data}
      depends_on: [ check-cache ]

    - id: update-cache
      component: cache
      action: set-data
      condition: ${jobs.check-cache.output.data == null}
      input:
        key: ${input.cache_key}
        value: ${jobs.process.output.result}
      depends_on: [ process ]
```

## Common Use Cases

- **Session Storage**: Store user session data across requests
- **API Response Caching**: Cache expensive API call results with TTL
- **Workflow Data Sharing**: Share intermediate results between workflow executions
- **Feature Flags**: Store and retrieve feature toggles
- **Rate Limiting**: Track request counts per user/IP
- **Temporary Data**: Store short-lived data with automatic expiration
- **External Integration**: Read/write data from existing Redis instances
