# Controller Configuration Reference

The controller section defines the server configuration for handling requests and managing workflows in model-compose. Controllers serve as the entry point for executing workflows and can be configured as HTTP servers or MCP (Model Context Protocol) servers.

## Basic Structure

```yaml
controller:
  type: http-server | mcp-server
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

## Common Configuration Options

### Core Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `null` | Optional name to identify the controller |
| `type` | string | **required** | Controller type: `http-server` or `mcp-server` |
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

## Usage Notes

1. **Port Conflicts**: Ensure the controller port and webui port are different to avoid conflicts.

2. **CORS Configuration**: For HTTP servers, configure `origins` appropriately for your client applications.

3. **Concurrency**: Higher `max_concurrent_count` values allow more simultaneous workflow executions but consume more resources.

4. **Base Paths**: Use `base_path` to namespace your API routes, especially useful when running behind a reverse proxy.

5. **Runtime Selection**: Choose `docker` runtime for better isolation, `native` for better performance and simpler deployment.
