# 第 6 章：控制器配置

本章介绍如何配置 model-compose 控制器，包括 HTTP 服务器和 MCP 服务器设置、并发控制和端口管理。

---

## 6.1 HTTP 服务器

HTTP 服务器控制器将工作流公开为 REST API。

### 基本结构

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
```

### 示例：简单聊天机器人 API

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

### API 端点

HTTP 服务器控制器自动生成以下端点：

#### 列出工作流
```
GET /api/workflows
GET /api/workflows?include_schema=true
```

检索工作流列表。添加 `include_schema=true` 参数还会返回每个工作流的输入/输出模式。

请求示例：
```bash
curl http://localhost:8080/api/workflows
```

响应示例：
```json
[
  {
    "workflow_id": "chat",
    "title": "Chat with AI",
    "default": true
  }
]
```

带模式请求：
```bash
curl http://localhost:8080/api/workflows?include_schema=true
```

响应示例：
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

#### 获取工作流模式
```
GET /api/workflows/{workflow_id}/schema
```

检索特定工作流的输入/输出模式。

请求示例：
```bash
curl http://localhost:8080/api/workflows/chat/schema
```

响应示例：
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

#### 执行工作流
```
POST /api/workflows/runs
```

执行工作流。您可以使用 `wait_for_completion` 参数控制同步/异步执行。

请求体参数：
- `workflow_id` (string, 可选): 要执行的工作流 ID。如果省略，执行默认工作流
- `input` (object, 可选): 工作流输入数据
- `wait_for_completion` (boolean, 默认: true): 如果为 true，等待完成；如果为 false，立即返回 task_id
- `output_only` (boolean, 默认: false): 如果为 true，仅返回输出数据（需要 wait_for_completion=true）

##### 同步执行（默认）

等待完成并返回结果。

请求示例：
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

响应示例：
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "completed",
  "output": {
    "message": "Hello! How can I help you today?"
  }
}
```

##### output_only 模式

设置 `output_only: true` 仅返回输出数据，不包含任务元数据。

请求示例：
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

响应示例：
```json
{
  "message": "Hello! How can I help you today?"
}
```

##### 异步执行

设置 `wait_for_completion: false` 立即返回 task_id 并在后台执行。

请求示例：
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

响应示例：
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "pending"
}
```

#### 获取任务状态
```
GET /api/tasks/{task_id}
GET /api/tasks/{task_id}?output_only=true
```

检索异步执行工作流的状态和结果。

任务状态：
- `pending`: 等待中（尚未开始）
- `processing`: 当前正在执行
- `completed`: 成功完成
- `failed`: 执行期间失败

请求示例：
```bash
curl http://localhost:8080/api/tasks/01JBQR5KSXM8HNXF7N9VYW3K2T
```

处理中时的响应：
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "processing"
}
```

完成时的响应：
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "completed",
  "output": {
    "message": "Hello! How can I help you today?"
  }
}
```

失败时的响应：
```json
{
  "task_id": "01JBQR5KSXM8HNXF7N9VYW3K2T",
  "status": "failed",
  "error": "Connection timeout"
}
```

output_only 模式：
```bash
curl http://localhost:8080/api/tasks/01JBQR5KSXM8HNXF7N9VYW3K2T?output_only=true
```

如果未完成，返回 HTTP 202：
```
HTTP/1.1 202 Accepted
{"detail": "Task is still in progress."}
```

完成时仅返回输出：
```json
{
  "message": "Hello! How can I help you today?"
}
```

失败时返回 HTTP 500：
```
HTTP/1.1 500 Internal Server Error
{"detail": "Connection timeout"}
```

#### 健康检查
```
GET /api/health
```

检查服务器状态。

响应示例：
```json
{
  "status": "ok"
}
```

### 异步执行和任务队列

#### 任务创建和跟踪

当执行工作流时，会在内部创建一个任务：

1. **任务创建**: 执行工作流时会生成一个基于 ULID 的唯一 `task_id`
2. **任务状态跟踪**: 任务有 4 种状态（`pending`、`processing`、`completed`、`failed`）
3. **任务缓存**: 已完成的任务在内存中缓存 1 小时，可以通过 `/api/tasks/{task_id}` 端点查询

#### 同步 vs 异步执行

**同步执行**（`wait_for_completion: true`，默认）：
- HTTP 请求等待工作流完成
- 完成后立即返回结果
- 用于简单工作流或需要立即结果时

**异步执行**（`wait_for_completion: false`）：
- 立即返回 `task_id` 并关闭连接
- 工作流在后台执行
- 通过 `/api/tasks/{task_id}` 端点查询状态和结果
- 适合执行时间较长的工作流

### CORS 配置

使用 `origins` 字段控制 HTTP 服务器 CORS。

```yaml
controller:
  type: http-server
  origins: "https://example.com,https://app.example.com"  # 仅允许特定域
  # origins: "*"  # 允许所有域（默认，用于开发）
```

---

## 6.2 MCP 服务器

MCP（模型上下文协议）服务器控制器使用 Streamable HTTP 协议与 Claude Desktop 和其他 MCP 客户端集成。

### 基本结构

```yaml
controller:
  type: mcp-server
  port: 8080
  base_path: /mcp  # Streamable HTTP 端点路径
```

### 示例：内容审核工具

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

### MCP 工作流特性

MCP 服务器工作流具有以下特征：

- **title**: MCP 客户端中显示的工具名称
- **description**: 工具描述（在 MCP 客户端中显示）
- **action**: 要连接的组件动作 ID
- **input**: 工具输入参数定义

### MCP 客户端集成

model-compose 的 MCP 服务器使用 **Streamable HTTP** 协议（MCP 规范 2025-03-26）。

**Streamable HTTP 特性**：
- **单一端点**: 通过一个 HTTP 端点处理所有 MCP 通信
- **双向通信**: 服务器可以向客户端发送通知和请求
- **SSE 支持**: 可选使用服务器发送事件进行流式响应
- **会话管理**: 通过 `Mcp-Session-Id` 标头进行会话跟踪

> **注意**: Streamable HTTP 替代了以前的 HTTP+SSE 方法（2024-11-05 规范）。它提供单一端点和增强的双向通信。

#### 启动服务器

```bash
model-compose up -f model-compose.yml
```

服务器启动后，您可以在以下位置访问 MCP 服务器：
```
http://localhost:8080/mcp
```

#### 客户端连接

支持 Streamable HTTP 的 MCP 客户端可以连接到上述 URL。

**连接信息**：
- URL: `http://localhost:8080/mcp`（或您配置的 host:port 和 base_path）
- 传输: Streamable HTTP
- 协议版本: 2025-03-26

**生产环境**：

对于生产环境，建议在对外公开 MCP 服务器时使用 HTTPS。您可以通过 Nginx 或 Caddy 等反向代理应用 SSL/TLS。

```yaml
# model-compose 使用 HTTP 在本地运行
controller:
  type: mcp-server
  host: 127.0.0.1
  port: 8080
  base_path: /mcp
```

Nginx 反向代理配置示例：
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

        # SSE 流式支持
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

MCP 客户端连接到：
```
https://mcp.example.com/mcp
```

---

## 6.3 并发控制

`max_concurrent_count` 设置适用于 HTTP 和 MCP 服务器，在控制器级别限制可以并发执行的工作流数量。

### 基本配置

```yaml
controller:
  type: http-server  # 或 mcp-server
  max_concurrent_count: 5  # 限制最多 5 个并发执行
```

### 工作原理

- `max_concurrent_count: 0`（默认）: 无限制并发执行，任务队列禁用
- `max_concurrent_count: 1`: 一次执行一个工作流（顺序执行）
- `max_concurrent_count: N`（N > 1）: 最多执行 N 个工作流并发，超出时排队

当任务队列激活时（`max_concurrent_count > 0`）：
1. 新的工作流执行请求被添加到队列
2. 最多 `max_concurrent_count` 个工作线程从队列中获取任务并执行
3. 即使使用 `wait_for_completion: true`，任务也会在执行前在队列中等待

### 用例

```yaml
# 默认: 无限制
controller:
  type: http-server
  max_concurrent_count: 0

# 当需要限制 GPU 资源时
controller:
  type: http-server
  max_concurrent_count: 3  # 将总工作流执行限制为 3 个
```

### 控制器级别 vs 组件级别控制

并发控制可以在两个级别上进行：

**控制器级别**（`controller.max_concurrent_count`）：
- 限制总工作流执行数量
- 通常应用于所有工作流
- 当保护整体系统资源（CPU、内存）时使用

**组件级别**（`component.max_concurrent_count`）：
- 限制对特定组件的并发调用
- 可以为每个组件独立设置
- 当保护特定资源（如 GPU、外部 API 速率限制）时使用

示例：
```yaml
controller:
  type: http-server
  max_concurrent_count: 0  # 无限制工作流执行

components:
  - id: image-model
    type: model
    max_concurrent_count: 2  # 由于 GPU 内存限制为 2 个并发执行
    model: stabilityai/stable-diffusion-2-1
    task: text-to-image

  - id: openai-api
    type: http-client
    max_concurrent_count: 10  # 考虑 API 速率限制限制为 10 个
    base_url: https://api.openai.com/v1
```

**建议**：
- 通常，组件级别控制提供更精细的资源管理
- 仅在需要防止整体系统过载时使用控制器级别控制
- 如果两个级别都设置，则两个限制都适用

---

## 6.4 端口和主机配置

### 主机

指定控制器绑定到的网络接口。

#### 仅允许从本地主机访问（默认）

```yaml
controller:
  type: http-server
  host: 127.0.0.1  # 默认
  port: 8080       # 默认
```

- 仅可从同一台机器访问
- 当在反向代理后运行或当安全性至关重要时使用

#### 允许从所有接口访问

```yaml
controller:
  type: http-server
  host: 0.0.0.0
  port: 8080
```

- 可从外部源访问
- 用于开发环境或当暴露到网络时

### 端口

指定控制器 API 服务器使用的端口。

```yaml
controller:
  type: http-server
  port: 8080  # 默认
```

### Base Path

设置所有 API 端点的前缀。

#### 无 Base Path（默认）

```yaml
controller:
  type: http-server
  port: 8080
  # 无 base_path
```

端点：
- `POST /workflows/runs`
- `GET /workflows`
- `GET /tasks/{task_id}`

#### 带 Base Path

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
```

端点：
- `POST /api/workflows/runs`
- `GET /api/workflows`
- `GET /api/tasks/{task_id}`

### 反向代理配置

当在 Nginx 或 Caddy 等反向代理后运行时。

#### model-compose 配置

```yaml
controller:
  type: http-server
  host: 127.0.0.1  # 仅可从代理访问
  port: 8080
  base_path: /ai   # 匹配代理路径
```

#### Nginx 配置示例

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

现在对 `http://example.com/ai/workflows/runs` 的外部访问由 Nginx 转发到内部 `http://127.0.0.1:8080/ai/workflows/runs`。

---

## 6.5 控制器最佳实践

### 1. 按环境配置端口

为开发、预发布和生产环境使用不同的端口：

```yaml
controller:
  type: http-server
  port: ${env.PORT | 8080}  # 环境变量或默认 8080
  base_path: /api
```

### 2. 适当的 CORS 配置

在生产环境中，仅允许特定域：

```yaml
# 开发环境
controller:
  type: http-server
  origins: "*"

# 生产环境
controller:
  type: http-server
  origins: "https://app.example.com,https://admin.example.com"
```

### 3. 并发限制配置

根据资源使用情况设置适当的 `max_concurrent_count`：

```yaml
# 使用 GPU 的工作流 - 有限并发
controller:
  type: http-server
  port: 8080
  max_concurrent_count: 2  # 考虑 GPU 内存限制

# 轻量级 API 调用工作流 - 高并发
controller:
  type: http-server
  port: 8080
  max_concurrent_count: 20
```

### 4. 利用异步执行

对执行时间较长的工作流使用异步执行：

```javascript
// 客户端代码示例
async function runLongWorkflow(input) {
  // 1. 异步启动工作流
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

  // 2. 轮询状态
  while (true) {
    const taskResponse = await fetch(`/api/tasks/${task_id}`);
    const task = await taskResponse.json();

    if (task.status === 'completed') {
      return task.output;
    } else if (task.status === 'failed') {
      throw new Error(task.error);
    }

    await new Promise(resolve => setTimeout(resolve, 2000)); // 等待 2 秒
  }
}
```

### 5. 正确使用 base_path

在反向代理后运行时一致设置 base_path：

```yaml
controller:
  type: http-server
  host: 127.0.0.1
  port: 8080
  base_path: /ai-service  # 精确匹配代理路径
```

### 6. 利用 output_only

当您想减少 API 响应大小时使用 `output_only`：

```yaml
# 当客户端不需要 task_id 时
POST /api/workflows/runs
{
  "workflow_id": "simple-chat",
  "input": { "prompt": "Hello" },
  "wait_for_completion": true,
  "output_only": true
}

# 响应: 仅返回输出，不包含 task_id 和 status
{ "message": "Hello! How can I help?" }
```

---

## 下一步

尝试以下内容：
- 使用 HTTP 服务器构建 REST API
- 使用 MCP 服务器构建 Streamable HTTP 服务器
- 利用异步执行和任务状态查询
- 在反向代理后运行

---

**下一章**: [7. Web UI 配置](./07-webui-configuration.md)
