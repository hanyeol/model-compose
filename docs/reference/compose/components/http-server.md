# HTTP Server Component

The HTTP server component enables creating HTTP endpoints and servers within your model-compose workflow. It supports managing server lifecycle, defining endpoints, handling requests/responses, and integrating with external processes.

## Basic Configuration

```yaml
component:
  type: http-server
  port: 8000
  start: [ uvicorn, main:app, --reload ]
  path: /api/endpoint
  method: POST
  headers:
    Content-Type: application/json
  body:
    message: ${input.message}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `http-server` |
| `port` | integer | `8000` | Port on which the HTTP server will listen (1-65535) |
| `base_path` | string | `null` | Base path to prefix all HTTP routes exposed by this component |
| `headers` | object | `{}` | Headers to be included in all outgoing HTTP requests |
| `manage` | object | `{}` | Configuration used to manage the HTTP server lifecycle |
| `actions` | array | `[]` | List of HTTP endpoint actions |

### Server Management

The `manage` configuration controls server lifecycle:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scripts` | object | `{}` | Shell scripts for server management |
| `working_dir` | string | `null` | Working directory for the scripts |
| `env` | object | `{}` | Environment variables to set when executing scripts |

#### Management Scripts

| Script | Type | Description |
|--------|------|-------------|
| `install` | array | One or more scripts to install dependencies |
| `build` | array | One or more scripts to build the server |
| `clean` | array | One or more scripts to clean the server environment |
| `start` | array | Script to start the server |

### Action Configuration

HTTP server actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | `null` | URL path for this HTTP server endpoint |
| `method` | string | `POST` | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH` |
| `headers` | object | `{}` | HTTP headers to include in responses |
| `body` | object | `{}` | Default response body template |
| `params` | object | `{}` | Expected URL query parameters |
| `stream_format` | string | `null` | Stream format: `server-sent-events`, `json-lines` |
| `completion` | object | `null` | Asynchronous completion configuration |

## Usage Examples

### Simple Echo Server

```yaml
component:
  type: http-server
  start: [ uvicorn, main:app, --reload ]
  port: 8000
  method: POST
  path: /echo
  headers:
    Content-Type: application/json
  body:
    text: ${input.text}
  output:
    text: ${response.echo.text}
```

### Server with Multiple Endpoints

```yaml
component:
  type: http-server
  port: 8080
  base_path: /api
  manage:
    scripts:
      start: [ python, server.py ]
      install: [ pip, install, -r, requirements.txt ]
    working_dir: ./server
    env:
      PORT: 8080
      DEBUG: true
  actions:
    - id: health-check
      path: /health
      method: GET
      headers:
        Content-Type: application/json
      body:
        status: healthy
        timestamp: ${now}
    
    - id: process-data
      path: /process
      method: POST
      headers:
        Content-Type: application/json
      body:
        result: ${input.data | process}
        processed_at: ${now}
      
    - id: get-status
      path: /status
      method: GET
      params:
        format: json
      body:
        server_status: running
        uptime: ${uptime}
```

### Server with Custom Management

```yaml
component:
  type: http-server
  port: 3000
  manage:
    scripts:
      install: 
        - [ npm, install ]
        - [ npm, run, build ]
      clean: [ rm, -rf, node_modules, dist ]
      start: [ npm, start ]
    working_dir: ./frontend
    env:
      NODE_ENV: production
      API_URL: http://localhost:8080
  path: /api/webhook
  method: POST
  headers:
    Content-Type: application/json
  body:
    received: ${input}
    processed: true
```

## Asynchronous Completion

HTTP server supports asynchronous request completion through polling or callbacks.

### Polling Completion

Monitor request status by polling a completion endpoint:

```yaml
component:
  type: http-server
  port: 8000
  path: /long-task
  method: POST
  body:
    task_id: ${generate_id}
    data: ${input.data}
  completion:
    type: polling
    path: /status/${response.task_id}
    method: GET
    status: status
    success_when: [ completed, finished ]
    fail_when: [ failed, error ]
    interval: 5s
    timeout: 300s
  output:
    result: ${response.result}
```

**Polling Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `polling` |
| `path` | string | `null` | URL path for polling endpoint |
| `method` | string | `GET` | HTTP method for polling requests |
| `headers` | object | `{}` | Headers for polling requests |
| `body` | object | `{}` | Body data for polling requests |
| `params` | object | `{}` | Query parameters for polling requests |
| `status` | string | `null` | Field path to check for completion status |
| `success_when` | array | `null` | Status values indicating success |
| `fail_when` | array | `null` | Status values indicating failure |
| `interval` | string | `null` | Time interval between polls |
| `timeout` | string | `null` | Maximum time to wait |

### Callback Completion

Wait for external callback notification:

```yaml
component:
  type: http-server
  port: 8000
  path: /async-task
  method: POST
  body:
    task_id: ${generate_id}
    callback_url: https://myapp.com/callback
    data: ${input.data}
  completion:
    type: callback
    wait_for: ${response.task_id}
  output:
    result: ${response.result}
```

**Callback Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `callback` |
| `wait_for` | string | `null` | Callback identifier to wait for |

## Stream Formats

### Server-Sent Events

Handle Server-Sent Events (SSE) streams:

```yaml
stream_format: server-sent-events
```

### JSON Lines

Handle newline-delimited JSON streams:

```yaml
stream_format: json-lines
```

## Server Lifecycle Management

### Installation Scripts

Run multiple installation commands:

```yaml
manage:
  scripts:
    install:
      - [ pip, install, -r, requirements.txt ]
      - [ npm, install ]
      - [ chmod, +x, start-server.sh ]
```

### Build Process

Build the server before starting:

```yaml
manage:
  scripts:
    build:
      - [ npm, run, build ]
      - [ docker, build, -t, myserver, . ]
    start: [ docker, run, -p, 8000:8000, myserver ]
```

### Environment Configuration

Set environment variables for server processes:

```yaml
manage:
  env:
    DATABASE_URL: ${env.DATABASE_URL}
    API_KEY: ${env.API_KEY}
    LOG_LEVEL: info
  working_dir: ./server
```

## Integration Patterns

### With External Servers

Launch and manage external server processes:

```yaml
component:
  type: http-server
  manage:
    scripts:
      start: [ python, -m, flask, run ]
    env:
      FLASK_APP: app.py
      FLASK_ENV: development
  port: 5000
  path: /api/data
  method: POST
```

### With Docker Containers

Manage containerized services:

```yaml
component:
  type: http-server
  manage:
    scripts:
      start: [ docker, run, -d, -p, 8080:80, nginx ]
      clean: [ docker, stop, nginx ]
  port: 8080
```

### API Gateway Pattern

Create multiple endpoints for different services:

```yaml
component:
  type: http-server
  port: 8080
  base_path: /api/v1
  actions:
    - id: auth
      path: /auth
      method: POST
      
    - id: users
      path: /users
      method: GET
      
    - id: data
      path: /data
      method: POST
```

## Error Handling

HTTP server automatically handles:

- **Server startup failures**: Component initialization fails if server cannot start
- **Port conflicts**: Automatic error if port is already in use
- **Script execution errors**: Management scripts that fail will stop component initialization

For custom error handling, use completion configuration with specific status checks.

## Variable Interpolation

HTTP server supports dynamic configuration:

```yaml
component:
  type: http-server
  port: ${env.SERVER_PORT as integer | 8000}
  path: /api/${input.version}
  headers:
    Authorization: Bearer ${env.API_TOKEN}
  body:
    user_id: ${input.user_id}
    data: ${input.data}
    timestamp: ${now}
```

## Best Practices

1. **Port Management**: Use environment variables for port configuration
2. **Process Management**: Use proper start scripts with process managers
3. **Health Checks**: Implement health check endpoints for monitoring
4. **Security**: Never expose sensitive data in response bodies
5. **Resource Cleanup**: Use clean scripts to properly shutdown services
6. **Logging**: Configure appropriate logging levels in environment variables
7. **Base Paths**: Use base_path for API versioning and organization

## Integration with Workflows

Reference HTTP server in workflow jobs:

```yaml
workflow:
  jobs:
    - id: start-server
      component: my-http-server
      action: health-check
      
    - id: process-request
      component: my-http-server
      action: process-data
      input:
        data: ${input.request_data}
        
    - id: handle-response
      component: processor
      input:
        server_response: ${process-request.output}
```

## Common Use Cases

- **API Servers**: Create REST API endpoints
- **Webhooks**: Handle incoming webhook requests
- **Microservices**: Launch and manage service processes
- **Development Servers**: Start development environments
- **Mock Services**: Create mock API endpoints for testing
- **Proxy Services**: Route requests to backend services
- **Static File Servers**: Serve static content and assets
