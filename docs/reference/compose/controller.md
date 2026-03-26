# Controller Configuration Reference

The controller section defines the server configuration for handling requests and managing workflows in model-compose. Controllers serve as the entry point for executing workflows and can be configured as HTTP servers, MCP (Model Context Protocol) servers, or queue subscribers for distributed task processing.

## Basic Structure

```yaml
controller:
  type: http-server | mcp-server | queue-subscriber
  name: optional-controller-name
  host: 0.0.0.0
  port: 8080
  base_path: /api
  origins: "*"
  max_concurrent_count: 1
  threaded: false
  runtime:
    type: native | docker
  webui:
    driver: gradio | static | dynamic
    host: 0.0.0.0
    port: 8081
```

## Controller Types

### HTTP Server (`http-server`)

Creates an HTTP server that exposes workflows as REST API endpoints.

```yaml
controller:
  type: http-server
  host: 0.0.0.0        # Host address to bind the server to
  port: 8080             # Port number for the HTTP server
  base_path: /api      # Base path prefix for all API routes
  origins: "*"           # CORS allowed origins (comma-separated)
```

**Example:**
```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio
    port: 8081
```

### MCP Server (`mcp-server`)

Creates an MCP (Model Context Protocol) server for integration with MCP-compatible clients.

```yaml
controller:
  type: mcp-server
  host: 0.0.0.0        # Host address to bind the MCP server to
  port: 8080             # Port number for the MCP server
  base_path: /mcp      # Base path prefix for MCP endpoints
```

**Example:**
```yaml
controller:
  type: mcp-server
  base_path: /mcp
  port: 8080
  webui:
    driver: gradio
    port: 8081
```

### Queue Subscriber (`queue-subscriber`)

Creates a queue subscriber that consumes tasks from a message queue (e.g., Redis) and executes workflows. Used for distributed worker patterns where multiple model-compose instances process tasks from a shared queue.

```yaml
# Using URL
controller:
  type: queue-subscriber
  driver: redis
  url: redis://localhost:6379

# Using host/port
controller:
  type: queue-subscriber
  driver: redis
  host: localhost
  port: 6379
```

> **Note**: Unlike `http-server` and `mcp-server`, the `queue-subscriber` type does not expose HTTP endpoints. It operates as a background worker that pulls tasks from the queue.

#### Queue Subscriber Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | **required** | Queue backend driver. Currently supported: `redis` |
| `queue_name` | string | `model-compose:tasks` | Base name for task queues. Actual queue keys: `{queue_name}:{workflow_id}` |
| `result_prefix` | string | `model-compose:result:` | Prefix for result keys and pub/sub channels |
| `result_ttl` | integer | `3600` | TTL in seconds for result entries. `0` means no expiry |
| `max_concurrent` | integer | `1` | Maximum number of tasks processed concurrently |
| `worker_id` | string | `null` | Unique worker identifier. Auto-generated (ULID) if not set |
| `workflows` | list | `["__default__"]` | Workflow IDs to handle. Each gets its own queue: `{queue_name}:{workflow_id}` |
| `workflow` | string | - | Shorthand for single workflow. Inflated to `workflows: [value]` |

#### Redis Driver Settings

Connection can be configured using either `url` or `host`/`port`/`tls` fields. If both `url` and `host` are provided, validation will fail.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | `null` | Redis connection URL (e.g., `redis://localhost:6379`, `rediss://localhost:6379` for TLS). Mutually exclusive with `host` |
| `host` | string | `localhost` | Redis server hostname or IP address. Mutually exclusive with `url` |
| `port` | integer | `6379` | Redis server port number (1-65535) |
| `tls` | boolean | `false` | Use TLS/SSL for connections (equivalent to `rediss://` protocol) |
| `db` | integer | `0` | Redis database number (0-15) |
| `password` | string | `null` | Redis password. Can also be specified in the URL |
| `pop_timeout` | integer | `1` | BRPOP timeout in seconds before retrying |

#### Data Flow

```
Producer                  Redis                    Worker (queue-subscriber)
   │                        │                              │
   │── LPUSH queue ────────>│                              │
   │                        │<──────── BRPOP queue ────────│
   │                        │                              │── run_workflow()
   │                        │<──── SET result:<run_id> ────│
   │                        │<── PUBLISH result:<run_id> ──│
   │<── GET result:<run_id> │                              │
   │<── SUBSCRIBE result:*  │                              │
```

#### Task Message Format (Producer → Queue)

```json
{
  "task_id": "user-task-123",
  "run_id": "01JXYZ...",
  "input": { "text": "Hello" }
}
```

- `task_id`: Logical task identifier (remains the same across retries)
- `run_id`: Execution instance identifier (unique per publish)
- `input`: Workflow input data

#### Result Message Format (Worker → Redis)

```json
{
  "task_id": "user-task-123",
  "run_id": "01JXYZ...",
  "status": "completed",
  "output": { "message": "Hello!" },
  "worker_id": "01JXY..."
}
```

Result status values: `completed`, `failed`, `interrupted`

When `interrupted`, the result includes an `interrupt` field:
```json
{
  "status": "interrupted",
  "interrupt": {
    "job_id": "review-step",
    "phase": "before",
    "message": "Please review before proceeding.",
    "metadata": {}
  }
}
```

#### Redis Key/Channel Reference

| Key/Channel | Type | Description |
|---|---|---|
| `{queue_name}:{workflow_id}` | List | Task queue (LPUSH/BRPOP) |
| `{result_prefix}{run_id}` | String | Result storage (with TTL) |
| `{result_prefix}{run_id}` | Pub/Sub | Result notification channel |

#### Examples

**Single workflow worker:**
```yaml
controller:
  type: queue-subscriber
  driver: redis
  url: redis://localhost:6379
  workflow: my-workflow
  max_concurrent: 3
```

**Multi-workflow worker:**
```yaml
controller:
  type: queue-subscriber
  driver: redis
  url: redis://localhost:6379
  workflows:
    - text-summary
    - translation
  max_concurrent: 5
```

**Worker with custom queue and result settings:**
```yaml
controller:
  type: queue-subscriber
  driver: redis
  host: redis.internal
  port: 6379
  password: ${env.REDIS_PASSWORD}
  db: 2
  queue_name: myapp:tasks
  result_prefix: myapp:result:
  result_ttl: 7200
  worker_id: gpu-worker-01
  workflows:
    - image-generation
  max_concurrent: 2
```

**TLS connection using URL:**
```yaml
controller:
  type: queue-subscriber
  driver: redis
  url: rediss://:${env.REDIS_PASSWORD}@redis.internal:6380/2
  workflows:
    - image-generation
  max_concurrent: 2
```

**TLS connection using host/port:**
```yaml
controller:
  type: queue-subscriber
  driver: redis
  host: redis.internal
  port: 6380
  tls: true
  password: ${env.REDIS_PASSWORD}
  db: 2
  workflows:
    - image-generation
  max_concurrent: 2
```

## Common Configuration Options

### Core Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `null` | Optional name to identify the controller |
| `type` | string | **required** | Controller type: `http-server`, `mcp-server`, or `queue-subscriber` |
| `host` | string | `0.0.0.0` | Host address to bind the server to |
| `port` | integer | `8080` | Port number for the server |
| `base_path` | string | `null` | Base path prefix for all routes/endpoints |

### HTTP Server Specific

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `origins` | string | `"*"` | CORS allowed origins (comma-separated string) |

### Concurrency & Threading

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_concurrent_count` | integer | `1` | Maximum number of tasks that can execute concurrently |
| `threaded` | boolean | `false` | Whether to run tasks in separate threads |

### Runtime Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `runtime` | object/string | `native` | Runtime environment settings |

**Runtime Options:**
- `native` - Run directly on the host system
- `docker` - Run in Docker containers

**Examples:**
```yaml
# Simple string format
runtime: native

# Object format with additional configuration
runtime:
  type: docker
  # Additional docker-specific options can be added here
```

## Web UI Configuration

The `webui` section configures an optional web interface for interacting with workflows.

### Common Web UI Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | `gradio` | Web UI rendering mode |
| `host` | string | `0.0.0.0` | Host address for the Web UI server |
| `port` | integer | `8081` | Port number for the Web UI |

### Web UI Drivers

#### Gradio (`gradio`)
Creates an interactive web interface using Gradio.

```yaml
webui:
  driver: gradio
  host: 0.0.0.0
  port: 8081
```

#### Static (`static`)
Serves static HTML/CSS/JS files.

```yaml
webui:
  driver: static
  host: 0.0.0.0
  port: 8081
  static_dir: webui    # Directory containing static files
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `static_dir` | string | `webui` | Directory containing static HTML/CSS/JS files |

#### Dynamic (`dynamic`)
Runs a custom web server command.

```yaml
webui:
  driver: dynamic
  host: 0.0.0.0
  port: 8081
  command: npm start              # Command to start the web server
  server_dir: webui/server        # Directory with server source code
  static_dir: webui/static        # Directory with static files
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `command` | string | **required** | Command to start the web UI server |
| `server_dir` | string | `webui/server` | Directory containing server source code and entry point |
| `static_dir` | string | `webui/static` | Directory containing static HTML/CSS/JS files |

## Complete Examples

### HTTP Server with Gradio UI
```yaml
controller:
  type: http-server
  name: my-api-server
  port: 8080
  base_path: /api
  origins: http://localhost:3000,https://myapp.com
  max_concurrent_count: 5
  threaded: true
  webui:
    driver: gradio
    port: 8081
```

### MCP Server with Static UI
```yaml
controller:
  type: mcp-server
  port: 8080
  base_path: /mcp
  runtime: docker
  webui:
    driver: static
    port: 8081
    static_dir: custom-webui
```

### HTTP Server with Custom Dynamic UI
```yaml
controller:
  type: http-server
  port: 8080
  max_concurrent_count: 10
  webui:
    driver: dynamic
    port: 8081
    command: node server.js
    server_dir: frontend/server
    static_dir: frontend/dist
```

### Queue Subscriber with Redis
```yaml
controller:
  type: queue-subscriber
  driver: redis
  url: redis://localhost:6379
  queue_name: model-compose:tasks
  workflows:
    - image-generation
    - text-summary
  max_concurrent: 4
  result_ttl: 3600
```

## Usage Notes

1. **Port Conflicts**: Ensure the controller port and webui port are different to avoid conflicts.

2. **CORS Configuration**: For HTTP servers, configure `origins` appropriately for your client applications.

3. **Concurrency**: Higher `max_concurrent_count` values allow more simultaneous workflow executions but consume more resources.

4. **Base Paths**: Use `base_path` to namespace your API routes, especially useful when running behind a reverse proxy.

5. **Runtime Selection**: Choose `docker` runtime for better isolation, `native` for better performance and simpler deployment.
