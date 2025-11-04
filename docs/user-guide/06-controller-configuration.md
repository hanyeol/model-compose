# Chapter 6: Controller Configuration

This chapter covers how to configure model-compose controllers, including HTTP server and MCP server settings, concurrency control, and port management.

---

## 6.1 HTTP Server

The HTTP server controller exposes workflows as REST APIs.

### Basic Structure

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
```

### Example: Simple Chatbot API

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api

workflow:
  title: Chat with AI
  description: Generate text responses using AI
  input: ${input}
  output: ${output}

component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /chat/completions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
    Content-Type: application/json
  body:
    model: gpt-4o
    messages:
      - role: user
        content: ${input.prompt}
  output:
    message: ${response.choices[0].message.content}
```

### API Endpoints

The HTTP server controller automatically generates the following endpoints:

#### List Workflows
```
GET /api/workflows
GET /api/workflows?include_schema=true
```

Retrieves the list of workflows. Adding the `include_schema=true` parameter also returns input/output schemas for each workflow.

Request example:
```bash
curl http://localhost:8080/api/workflows
```

Response example:
```json
[
  {
    "workflow_id": "chat",
    "title": "Chat with AI",
    "default": true
  }
]
```

With schema request:
```bash
curl http://localhost:8080/api/workflows?include_schema=true
```

Response example:
```json
[
  {
    "workflow_id": "chat",
    "title": "Chat with AI",
    "description": "Generate text responses using AI",
    "input": [
      {
        "name": "prompt",
        "type": "string"
      }
    ],
    "output": [
      {
        "name": "message",
        "type": "string"
      }
    ],
    "default": true
  }
]
```

#### Get Workflow Schema
```
GET /api/workflows/{workflow_id}/schema
```

Retrieves the input/output schema for a specific workflow.

Request example:
```bash
curl http://localhost:8080/api/workflows/chat/schema
```

Response example:
```json
{
  "workflow_id": "chat",
  "title": "Chat with AI",
  "description": "Generate text responses using AI",
  "input": [
    {
      "name": "prompt",
      "type": "string"
    }
  ],
  "output": [
    {
      "name": "message",
      "type": "string"
    }
  ],
  "default": true
}
```

#### Execute Workflow
```
POST /api/workflows/runs
```

Executes a workflow. You can control sync/async execution with the `wait_for_completion` parameter.

Request body parameters:
- `workflow_id` (string, optional): Workflow ID to execute. If omitted, executes the default workflow
- `input` (object, optional): Workflow input data
- `wait_for_completion` (boolean, default: true): If true, waits until completion; if false, returns task_id immediately
- `output_only` (boolean, default: false): If true, returns only output data (requires wait_for_completion=true)

##### Synchronous Execution (Default)

Waits until completion and returns the result.

Request example:
```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "chat",
    "input": {
      "prompt": "Hello, AI!"
    },
    "wait_for_completion": true
  }'
```

Response example:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "completed",
  "output": {
    "message": "Hello! How can I help you today?"
  }
}
```

##### output_only Mode

Setting `output_only: true` returns only the output data without task metadata.

Request example:
```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "chat",
    "input": {
      "prompt": "Hello, AI!"
    },
    "wait_for_completion": true,
    "output_only": true
  }'
```

Response example:
```json
{
  "message": "Hello! How can I help you today?"
}
```

##### Asynchronous Execution

Setting `wait_for_completion: false` immediately returns task_id and executes in the background.

Request example:
```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "chat",
    "input": {
      "prompt": "Hello, AI!"
    },
    "wait_for_completion": false
  }'
```

Response example:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "pending"
}
```

#### Get Task Status
```
GET /api/tasks/{task_id}
GET /api/tasks/{task_id}?output_only=true
```

Retrieves the status and result of an asynchronously executed workflow.

Task states:
- `pending`: Waiting (not yet started)
- `processing`: Currently executing
- `completed`: Successfully completed
- `failed`: Failed during execution

Request example:
```bash
curl http://localhost:8080/api/tasks/01JBQR5KSXM8HNXF7N9VYW3K2T
```

Response when processing:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "processing"
}
```

Response when completed:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "completed",
  "output": {
    "message": "Hello! How can I help you today?"
  }
}
```

Response when failed:
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "failed",
  "error": "Connection timeout"
}
```

output_only mode:
```bash
curl http://localhost:8080/api/tasks/01JBQR5KSXM8HNXF7N9VYW3K2T?output_only=true
```

Returns HTTP 202 if not completed:
```
HTTP/1.1 202 Accepted
{"detail": "Task is still in progress."}
```

Returns output only when completed:
```json
{
  "message": "Hello! How can I help you today?"
}
```

Returns HTTP 500 if failed:
```
HTTP/1.1 500 Internal Server Error
{"detail": "Connection timeout"}
```

#### Health Check
```
GET /api/health
```

Checks server status.

Response example:
```json
{
  "status": "ok"
}
```

### Asynchronous Execution and Task Queue

#### Task Creation and Tracking

When a workflow is executed, a Task is created internally:

1. **Task Creation**: A unique `task_id` based on ULID is generated when executing a workflow
2. **Task State Tracking**: Tasks have 4 states (`pending`, `processing`, `completed`, `failed`)
3. **Task Caching**: Completed tasks are cached in memory for 1 hour and can be queried via the `/api/tasks/{task_id}` endpoint

#### Synchronous vs Asynchronous Execution

**Synchronous Execution** (`wait_for_completion: true`, default):
- The HTTP request waits until the workflow completes
- Returns the result immediately upon completion
- Use for simple workflows or when immediate results are needed

**Asynchronous Execution** (`wait_for_completion: false`):
- Immediately returns `task_id` and closes the connection
- The workflow executes in the background
- Query status and results via the `/api/tasks/{task_id}` endpoint
- Suitable for workflows with long execution times

### CORS Configuration

Control HTTP server CORS with the `origins` field.

```yaml
controller:
  type: http-server
  origins: "https://example.com,https://app.example.com"  # Allow specific domains only
  # origins: "*"  # Allow all domains (default, for development)
```

---

## 6.2 MCP Server

The MCP (Model Context Protocol) server controller integrates with Claude Desktop and other MCP clients using the Streamable HTTP protocol.

### Basic Structure

```yaml
controller:
  type: mcp-server
  port: 8080
  base_path: /mcp  # Streamable HTTP endpoint path
```

### Example: Content Moderation Tool

```yaml
controller:
  type: mcp-server
  base_path: /mcp
  port: 8080

workflows:
  - id: moderate-text
    title: Moderate Text Content
    description: Check if text content violates content policies
    action: text-moderation
    input:
      text: ${input.text}
    output: ${output}

  - id: moderate-image
    title: Moderate Image Content
    description: Check if image content is safe and appropriate
    action: image-moderation
    input:
      image_url: ${input.image_url}
    output: ${output}

components:
  - id: openai-moderation
    type: http-client
    base_url: https://api.openai.com/v1
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    actions:
      - id: text-moderation
        path: /moderations
        method: POST
        body:
          input: ${input.text}
        output:
          flagged: ${response.results[0].flagged}
          categories: ${response.results[0].categories}
          scores: ${response.results[0].category_scores}

      - id: image-moderation
        path: /moderations
        method: POST
        body:
          input: ${input.image_url}
          model: omni-moderation-latest
        output:
          flagged: ${response.results[0].flagged}
          categories: ${response.results[0].categories}
```

### MCP Workflow Features

MCP server workflows have the following characteristics:

- **title**: Tool name displayed in MCP client
- **description**: Tool description (shown in MCP client)
- **action**: Component action ID to connect to
- **input**: Tool input parameter definition

### MCP Client Integration

model-compose's MCP server uses the **Streamable HTTP** protocol (MCP spec 2025-03-26).

**Streamable HTTP Features**:
- **Single Endpoint**: Handles all MCP communication through one HTTP endpoint
- **Bidirectional Communication**: Server can send notifications and requests to client
- **SSE Support**: Optionally uses Server-Sent Events for streaming responses
- **Session Management**: Session tracking via `Mcp-Session-Id` header

> **Note**: Streamable HTTP replaces the previous HTTP+SSE approach (2024-11-05 spec). It provides a single endpoint and enhanced bidirectional communication.

#### Starting the Server

```bash
model-compose up -f model-compose.yml
```

Once the server starts, you can access the MCP server at:
```
http://localhost:8080/mcp
```

#### Client Connection

MCP clients supporting Streamable HTTP can connect to the above URL.

**Connection Information**:
- URL: `http://localhost:8080/mcp` (or your configured host:port and base_path)
- Transport: Streamable HTTP
- Protocol Version: 2025-03-26

**Production Environment**:

For production, it's recommended to use HTTPS when exposing the MCP server externally. You can apply SSL/TLS through a reverse proxy like Nginx or Caddy.

```yaml
# model-compose runs locally with HTTP
controller:
  type: mcp-server
  host: 127.0.0.1
  port: 8080
  base_path: /mcp
```

Nginx reverse proxy configuration example:
```nginx
server {
    listen 443 ssl;
    server_name mcp.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /mcp {
        proxy_pass http://127.0.0.1:8080/mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE streaming support
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

MCP clients connect to:
```
https://mcp.example.com/mcp
```

---

## 6.3 Concurrency Control

The `max_concurrent_count` setting is available for both HTTP and MCP servers, limiting the number of workflows that can execute concurrently at the controller level.

### Basic Configuration

```yaml
controller:
  type: http-server  # or mcp-server
  max_concurrent_count: 5  # Limit to maximum 5 concurrent executions
```

### How It Works

- `max_concurrent_count: 0` (default): Unlimited concurrent execution, task queue disabled
- `max_concurrent_count: 1`: Execute one workflow at a time (sequential execution)
- `max_concurrent_count: N` (N > 1): Execute up to N workflows concurrently, queue when exceeded

When task queue is activated (`max_concurrent_count > 0`):
1. New workflow execution requests are added to the queue
2. Up to `max_concurrent_count` workers fetch tasks from the queue and execute them
3. Even with `wait_for_completion: true`, tasks wait in the queue before execution

### Use Cases

```yaml
# Default: Unlimited
controller:
  type: http-server
  max_concurrent_count: 0

# When GPU resources need to be limited
controller:
  type: http-server
  max_concurrent_count: 3  # Limit total workflow execution to 3
```

### Controller vs Component Level Control

Concurrency control is possible at two levels:

**Controller Level** (`controller.max_concurrent_count`):
- Limits total workflow execution count
- Applied commonly to all workflows
- Use when protecting overall system resources (CPU, memory)

**Component Level** (`component.max_concurrent_count`):
- Limits concurrent calls to a specific component
- Can be set independently for each component
- Use when protecting specific resources like GPU, external API rate limits

Example:
```yaml
controller:
  type: http-server
  max_concurrent_count: 0  # Unlimited workflow execution

components:
  - id: image-model
    type: model
    max_concurrent_count: 2  # Limit to 2 concurrent executions due to GPU memory
    model: stabilityai/stable-diffusion-2-1
    task: text-to-image

  - id: openai-api
    type: http-client
    max_concurrent_count: 10  # Limit to 10 considering API rate limit
    base_url: https://api.openai.com/v1
```

**Recommendations**:
- Generally, component-level control provides finer resource management
- Use controller-level control only when preventing overall system overload
- If both levels are set, both limits apply

---

## 6.4 Port and Host Configuration

### Host

Specifies the network interface the controller binds to.

#### Allow Access from Localhost Only (Default)

```yaml
controller:
  type: http-server
  host: 127.0.0.1  # Default
  port: 8080       # Default
```

- Accessible only from the same machine
- Use when running behind a reverse proxy or when security is critical

#### Allow Access from All Interfaces

```yaml
controller:
  type: http-server
  host: 0.0.0.0
  port: 8080
```

- Accessible from external sources
- Use for development environment or when exposing to network

### Port

Specifies the port the controller API server uses.

```yaml
controller:
  type: http-server
  port: 8080  # Default
```

### Base Path

Sets a prefix for all API endpoints.

#### No Base Path (Default)

```yaml
controller:
  type: http-server
  port: 8080
  # No base_path
```

Endpoints:
- `POST /workflows/runs`
- `GET /workflows`
- `GET /tasks/{task_id}`

#### With Base Path

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
```

Endpoints:
- `POST /api/workflows/runs`
- `GET /api/workflows`
- `GET /api/tasks/{task_id}`

### Reverse Proxy Configuration

When running behind a reverse proxy like Nginx or Caddy.

#### model-compose Configuration

```yaml
controller:
  type: http-server
  host: 127.0.0.1  # Accessible from proxy only
  port: 8080
  base_path: /ai   # Match proxy path
```

#### Nginx Configuration Example

```nginx
server {
    listen 80;
    server_name example.com;

    location /ai/ {
        proxy_pass http://127.0.0.1:8080/ai/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Now external access to `http://example.com/ai/workflows/runs` is forwarded by Nginx to internal `http://127.0.0.1:8080/ai/workflows/runs`.

---

## 6.5 Controller Best Practices

### 1. Port Configuration by Environment

Use different ports for development, staging, and production:

```yaml
controller:
  type: http-server
  port: ${env.PORT | 8080}  # Environment variable or default 8080
  base_path: /api
```

### 2. Proper CORS Configuration

In production, allow only specific domains:

```yaml
# Development environment
controller:
  type: http-server
  origins: "*"

# Production environment
controller:
  type: http-server
  origins: "https://app.example.com,https://admin.example.com"
```

### 3. Concurrency Limit Configuration

Set appropriate `max_concurrent_count` based on resource usage:

```yaml
# GPU-using workflows - Limited concurrency
controller:
  type: http-server
  port: 8080
  max_concurrent_count: 2  # Consider GPU memory limits

# Lightweight API call workflows - High concurrency
controller:
  type: http-server
  port: 8080
  max_concurrent_count: 20
```

### 4. Utilize Asynchronous Execution

Execute workflows with long execution times asynchronously:

```javascript
// Client code example
async function runLongWorkflow(input) {
  // 1. Start workflow asynchronously
  const response = await fetch('/api/workflows/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflow_id: 'long-task',
      input: input,
      wait_for_completion: false
    })
  });

  const { task_id } = await response.json();

  // 2. Poll for status
  while (true) {
    const taskResponse = await fetch(`/api/tasks/${task_id}`);
    const task = await taskResponse.json();

    if (task.status === 'completed') {
      return task.output;
    } else if (task.status === 'failed') {
      throw new Error(task.error);
    }

    await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds
  }
}
```

### 5. Proper base_path Usage

Set base_path consistently when running behind a reverse proxy:

```yaml
controller:
  type: http-server
  host: 127.0.0.1
  port: 8080
  base_path: /ai-service  # Exactly match proxy path
```

### 6. Utilize output_only

Use `output_only` when you want to reduce API response size:

```yaml
# When task_id is not needed on the client
POST /api/workflows/runs
{
  "workflow_id": "simple-chat",
  "input": { "prompt": "Hello" },
  "wait_for_completion": true,
  "output_only": true
}

# Response: Returns only output without task_id and status
{ "message": "Hello! How can I help?" }
```

---

## Next Steps

Try these:
- Build REST APIs with HTTP server
- Build Streamable HTTP server with MCP server
- Utilize asynchronous execution and task status querying
- Run behind a reverse proxy

---

**Next Chapter**: [7. Web UI Configuration](./07-webui-configuration.md)
