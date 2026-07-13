# 第8章：WebSocket 接口

本章介绍如何使用 model-compose 的 WebSocket 接口进行实时任务监控、工作流执行和通过持久连接进行双向控制。

---

## 8.1 WebSocket 概述

### 8.1.1 什么是 WebSocket 接口？

WebSocket 接口在 HTTP 服务器控制器上添加 `/ws` 端点，实现客户端与服务器之间的实时双向通信。客户端无需反复轮询 `GET /tasks/{task_id}`，而是在任务进展时即时收到状态更新。

**优势：**
- 实时任务状态更新（无需轮询）
- 双向通信（服务器推送 + 客户端命令）
- 状态变更和中断处理的更低延迟
- 单个持久连接的高效资源使用
- 通过一个连接同时监控多个任务

**使用场景：**
- 监控工作流执行的实时仪表板
- 带中断/恢复流程的交互式应用
- 需要即时反馈的聊天应用
- 单个客户端的多任务监控

### 8.1.2 WebSocket vs REST API

两种接口都支持工作流执行。根据需求选择：

| 场景 | 推荐 | 原因 |
|------|------|------|
| 简单批处理任务 | REST API | 无需 WebSocket 连接 |
| 实时 UI（聊天、生成） | WebSocket | 单连接处理所有事务 |
| 外部系统集成 | REST API + WebSocket | 标准 HTTP 启动，WebSocket 监控 |
| 多任务监控 | WebSocket | 一个连接监控所有任务 |
| curl/Postman 测试 | REST API | 简单的请求/响应 |

### 8.1.3 传递行为

已订阅的客户端会实时收到任务状态变更和单 job 生命周期事件：

- **`task_state`** — 任务状态变更时推送（`pending → processing → completed` 等）。订阅时，当前状态会通过 `task_subscribed` 响应一次性返回，使客户端可以立即跟上最新状态。
- **`job_event`** — 工作流内每个 job 的 `started` / `completed` / `failed` / `routed` 转换时推送。如果客户端在整个运行期间保持连接，所有事件按其发生顺序传递。

两种消息均在发出时即时发送，正常运行时无丢失。消息发出后不会保留，因此**订阅之前发生的事件不会重放** — 请在工作流启动时即订阅（`run_workflow` 配合 `subscribe_task: true`），以确保完整覆盖。

### 8.1.4 工作原理

```
客户端                          服务器
  │                               │
  │──── WebSocket 连接 ──────────>│  ws://localhost:8080/ws
  │<─── 连接已接受 ──────────────│
  │                               │
  │──── run_workflow ────────────>│  执行工作流
  │<─── workflow_started ─────────│  返回 task_id
  │                               │
  │<─── task_state (processing) ──│  实时更新
  │<─── task_state (interrupted) ─│  中断通知
  │                               │
  │──── resume_task ─────────────>│  恢复工作流
  │<─── task_resumed ─────────────│
  │<─── task_state (completed) ───│  最终结果
  │                               │
  │──── close ───────────────────>│
```

---

## 8.2 配置

### 8.2.1 启用 WebSocket

使用 HTTP 服务器控制器时，WebSocket 默认启用。基本使用无需额外配置。

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
```

WebSocket 端点可通过 `ws://localhost:8080/ws` 访问。

### 8.2.2 WebSocket 配置选项

`websocket` 字段接受布尔值或配置对象：

- `websocket: true`（默认） — 使用默认设置启用
- `websocket: false` — 禁用 WebSocket 支持
- `websocket: { ... }` — 使用自定义设置启用

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
    origins: "*"
    websocket:
      path: /ws
      max_connection_count: 100
```

**配置字段：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | string | `/ws` | WebSocket 端点路径 |
| `max_connection_count` | integer | 无限制 | 最大并发 WebSocket 连接数（尽力保证；连接计数检查与接受之间可能出现小幅超限） |
| `ping_interval` | integer | `30` | 服务器端 ping 间隔（秒）（`0` 禁用） |
| `ping_timeout` | integer | `10` | Ping 超时时间（秒） |

### 8.2.3 配置示例

#### 开发环境

```yaml
controller:
  adapter:
    type: http-server
    host: 0.0.0.0
    port: 8080
    origins: "*"
  # WebSocket 默认启用，无需额外配置
```

#### 生产环境

```yaml
controller:
  adapter:
    type: http-server
    host: 127.0.0.1
    port: 8080
    origins: "https://app.example.com"
    websocket:
      path: /ws
      max_connection_count: 100
```

#### 禁用 WebSocket

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
    websocket: false
```

---

## 8.3 连接 WebSocket

### 8.3.1 基本连接

连接到 WebSocket 端点：

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  console.log('已连接');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('收到:', message);
};

ws.onclose = () => {
  console.log('已断开');
};
```

```python
import asyncio
import websockets
import json

async def connect():
    async with websockets.connect('ws://localhost:8080/ws') as ws:
        print('已连接')
        async for message in ws:
            data = json.loads(message)
            print('收到:', data)

asyncio.run(connect())
```

### 8.3.2 会话 ID

可通过查询参数指定会话 ID 来标识连接：

```javascript
const sessionId = crypto.randomUUID();
const ws = new WebSocket(`ws://localhost:8080/ws?session=${sessionId}`);
```

- 未指定时，服务器自动生成 UUID。
- 一个会话 ID 只能有一个活跃连接。使用相同会话 ID 的重复连接会被拒绝（关闭代码 `4409`）。
- 会话 ID 支持 REST API 集成（见[第 8.5 节](#85-rest-api-集成)）。

### 8.3.3 连接时自动订阅

使用 `task` 查询参数在连接时立即订阅任务：

```javascript
const ws = new WebSocket(`ws://localhost:8080/ws?task=${taskId}`);
```

这等同于连接后发送 `subscribe_task` 消息。

---

## 8.4 WebSocket 消息

### 8.4.1 消息格式

所有消息使用通用 JSON 信封：

```json
{
  "type": "message_type",
  "id": "optional_message_id",
  "data": { }
}
```

- `type`（string，必填）：消息类型标识符
- `id`（string，可选）：用于请求-响应关联的唯一消息 ID
- `data`（object，按类型可选）：消息特定负载。对于无负载的消息（如 `ping`）可省略；服务器将缺失的 `data` 视为 `{}`。

### 8.4.2 客户端 → 服务器消息

#### `run_workflow` — 执行工作流

```json
{
  "type": "run_workflow",
  "id": "msg-001",
  "data": {
    "workflow_id": "chat-completion",
    "input": {
      "prompt": "Hello, AI!"
    },
    "subscribe_task": true
  }
}
```

**字段：**
- `workflow_id`（string，可选）：要执行的工作流（默认：`__default__`）
- `input`（object，可选）：工作流输入参数
- `subscribe_task`（boolean，默认：`true`）：自动订阅任务状态更新

**响应：** `workflow_started` 消息。如果 `subscribe_task` 为 `true`，还会收到 `task_state` 更新。

#### `subscribe_task` — 订阅任务更新

```json
{
  "type": "subscribe_task",
  "id": "msg-002",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

**字段：**
- `task_id`（string，必填）：要监控的任务 ID（ULID 格式）

**响应：** `task_subscribed` 消息（附带当前状态），之后在状态变更时收到 `task_state` 更新。

#### `unsubscribe_task` — 停止监控任务

```json
{
  "type": "unsubscribe_task",
  "id": "msg-003",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

**响应：** `task_unsubscribed` 消息。

#### `resume_task` — 恢复中断的任务

这是 `POST /tasks/{task_id}/resume` 的 WebSocket 等价操作。

```json
{
  "type": "resume_task",
  "id": "msg-004",
  "data": {
    "task_id": "01HXYZ...",
    "job_id": "review-step",
    "answer": {
      "approved": true
    }
  }
}
```

**字段：**
- `task_id`（string，必填）：要恢复的任务
- `job_id`（string，必填）：中断的作业 ID（来自 `interrupt.job_id`）
- `answer`（any，可选）：传递给工作流的响应值

**响应：** `task_resumed` 或 `error` 消息。

#### `get_task` — 查询任务状态（一次性）

```json
{
  "type": "get_task",
  "id": "msg-005",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

**响应：** 附带当前状态的 `task_state` 消息。不创建订阅。

#### `ping` — 连接健康检查

```json
{
  "type": "ping",
  "id": "msg-006"
}
```

**响应：** `pong` 消息。

### 8.4.3 服务器 → 客户端消息

#### `workflow_started` — 工作流执行已开始

```json
{
  "type": "workflow_started",
  "id": "msg-001",
  "data": {
    "task_id": "01HXYZ...",
    "workflow_id": "chat-completion",
    "status": "pending"
  }
}
```

作为 `run_workflow` 的响应发送。

#### `task_subscribed` — 订阅已确认

```json
{
  "type": "task_subscribed",
  "id": "msg-002",
  "data": {
    "task_id": "01HXYZ...",
    "state": {
      "task_id": "01HXYZ...",
      "status": "processing",
      "output": null,
      "error": null,
      "interrupt": null
    }
  }
}
```

作为 `subscribe_task` 的响应发送。包含订阅时的当前任务状态。

#### `task_unsubscribed` — 订阅已移除

```json
{
  "type": "task_unsubscribed",
  "id": "msg-003",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

#### `task_state` — 任务状态更新

```json
{
  "type": "task_state",
  "data": {
    "task_id": "01HXYZ...",
    "status": "interrupted",
    "output": null,
    "error": null,
    "interrupt": {
      "job_id": "review-step",
      "phase": "before",
      "message": "Approval required",
      "metadata": { "cost": 0.5 }
    },
    "timestamp": "2026-02-06T12:34:56.789Z"
  }
}
```

**字段：**
- `status`：`"pending"` | `"processing"` | `"interrupted"` | `"completed"` | `"failed"`
- `output`：完成时的结果数据（仅 JSON 可序列化的值；不可序列化的输出如图像返回 `null`）
- `error`：失败时的错误消息
- `interrupt`：状态为 `"interrupted"` 时的中断详情（`job_id`、`phase`、`message`、`metadata`）
- `timestamp`：状态变更时间（ISO 8601）

#### `job_event` — 单 Job 生命周期事件

工作流中的每个 job 经历其生命周期转换时推送。与反映*整个工作流*的 `task_state` 不同，`job_event` 提供单个 job 的细粒度可见性。

```json
{
  "type": "job_event",
  "data": {
    "task_id": "01HXYZ...",
    "run_id": "01HRUN...",
    "workflow_id": "chat-completion",
    "job_id": "job-quote",
    "event": "completed",
    "elapsed": 1.78,
    "output": { "quote": "..." },
    "error": null,
    "next_job_id": null,
    "timestamp": "2026-02-06T12:34:56.789Z"
  }
}
```

**字段：**

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `task_id` | string | 此 job 所属的任务 |
| `run_id` | string \| string[] \| null | 组件 action 的 run id。单次运行为字符串；`repeat_count` 产生多次运行时为数组；非组件 job 或尚未发放时为 `null`（例如部分 `started` 事件） |
| `workflow_id` | string | 工作流 id |
| `job_id` | string | 工作流配置中的 job id |
| `event` | string | `"started"` \| `"completed"` \| `"failed"` \| `"routed"` |
| `elapsed` | number | job 启动后经过的秒数（出现在 `completed` / `failed` / `routed`） |
| `output` | any | `completed` 时 job 的输出（仅当 JSON 可序列化时；不可序列化值为 `null`） |
| `error` | string | `failed` 时的错误信息 |
| `next_job_id` | string | `routed` 时的目标 job id（由 `switch` / `if` / `random_router` 等路由 job 发出） |
| `timestamp` | string | 发出时间（ISO 8601, UTC） |

**典型 job 的事件顺序：**

```
started → completed
started → failed
started → routed → started(next_job) → ...
```

**注意：**
- `job_event` 自动发送给订阅父 `task_id` 的所有客户端（无需单独订阅）。
- `started` 事件可能在 `run_id` 可用之前到达 — `run_id` 在 `ComponentJob` 实际调用其 action 时生成，发生在 job task 被调度之后。`completed` / `failed` 事件始终携带 `run_id`。
- 对于不由组件支持的 job（例如 `delay`、`filter`、`switch`），`run_id` 保持为 `null`。

#### `task_resumed` — 任务已恢复

```json
{
  "type": "task_resumed",
  "id": "msg-004",
  "data": {
    "task_id": "01HXYZ...",
    "status": "processing"
  }
}
```

成功响应 `resume_task` 时发送。

#### `error` — 错误消息

```json
{
  "type": "error",
  "id": "msg-001",
  "data": {
    "code": "WORKFLOW_NOT_FOUND",
    "message": "Workflow 'invalid-workflow' not found",
    "details": {
      "workflow_id": "invalid-workflow"
    }
  }
}
```

**错误代码：**

| 代码 | 说明 |
|------|------|
| `WORKFLOW_NOT_FOUND` | 指定的工作流不存在 |
| `TASK_NOT_FOUND` | 指定的任务不存在 |
| `INVALID_REQUEST` | 无效的消息格式或缺少必填字段 |
| `TASK_NOT_INTERRUPTED` | 任务不在中断状态 |
| `JOB_ID_MISMATCH` | 作业 ID 与当前中断点不匹配 |
| `INTERNAL_ERROR` | 意外的服务器错误 |

#### `pong` — Ping 响应

```json
{
  "type": "pong",
  "id": "msg-006",
  "data": {
    "timestamp": "2026-02-06T12:34:56.789Z"
  }
}
```

---

## 8.5 REST API 集成

WebSocket 和 REST API 可以配合使用。当您想通过 REST 启动工作流但通过 WebSocket 实时监控时非常有用。

### 8.5.1 `subscribe_task` 参数

`POST /workflows/runs` 端点支持 `subscribe_task` 参数：

```bash
curl -X POST "http://localhost:8080/workflows/runs?session_id=my-session-id" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "chat-completion",
    "input": { "prompt": "Hello" },
    "wait_for_completion": false,
    "subscribe_task": true
  }'
```

**要求：**
- 当 `subscribe_task: true` 时需要 `session_id` 查询参数
- 必须存在具有匹配会话 ID 的活跃 WebSocket 连接
- `wait_for_completion` 必须为 `false`（不允许同时使用两者，返回 400）

### 8.5.2 `wait_for_completion` 和 `subscribe_task` 组合

| wait_for_completion | subscribe_task | 行为 |
|---------------------|----------------|------|
| `true`（默认） | `false`（默认） | HTTP 等待完成。无订阅。（现有行为） |
| `false` | `false` | 立即返回 PENDING。无订阅。 |
| `false` | `true` | 立即返回 PENDING + 通过 WebSocket 自动订阅。**推荐模式。** |
| `true` | `true` | **不允许。** 返回 400 Bad Request。 |

### 8.5.3 模式：WebSocket 优先 + REST 执行

REST + WebSocket 集成的推荐模式：

```javascript
// 1. 生成会话 ID 并连接 WebSocket
const sessionId = crypto.randomUUID();
const ws = new WebSocket(`ws://localhost:8080/ws?session=${sessionId}`);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'task_state') {
    console.log('状态:', msg.data.status);
    if (msg.data.status === 'completed') {
      console.log('结果:', msg.data.output);
    }
  }
};

// 2. 通过 REST API 执行工作流（相同会话 ID）
ws.onopen = async () => {
  const response = await fetch(`/workflows/runs?session_id=${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflow_id: 'chat-completion',
      input: { prompt: 'Hello' },
      wait_for_completion: false,
      subscribe_task: true
    })
  });

  const { task_id } = await response.json();
  console.log('工作流已启动:', task_id);
  // 更新将通过 WebSocket 自动到达
};
```

---

## 8.6 使用模式

### 8.6.1 模式 1：通过 WebSocket 执行并监控

最简单的模式 — 执行工作流并通过单个 WebSocket 连接接收更新。

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'run_workflow',
    id: 'msg-001',
    data: {
      workflow_id: 'chat-completion',
      input: { prompt: 'Hello, AI!' },
      subscribe_task: true
    }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'workflow_started':
      console.log('已启动:', msg.data.task_id);
      break;

    case 'task_state':
      console.log('状态:', msg.data.status);
      if (msg.data.status === 'completed') {
        console.log('输出:', msg.data.output);
        ws.close();
      }
      break;

    case 'error':
      console.error('错误:', msg.data.message);
      break;
  }
};
```

```python
import asyncio
import websockets
import json

async def run_and_monitor():
    async with websockets.connect('ws://localhost:8080/ws') as ws:
        # 执行工作流
        await ws.send(json.dumps({
            'type': 'run_workflow',
            'id': 'msg-001',
            'data': {
                'workflow_id': 'chat-completion',
                'input': {'prompt': 'Hello, AI!'},
                'subscribe_task': True
            }
        }))

        # 接收更新
        async for message in ws:
            msg = json.loads(message)

            if msg['type'] == 'workflow_started':
                print(f"已启动: {msg['data']['task_id']}")

            elif msg['type'] == 'task_state':
                status = msg['data']['status']
                print(f"状态: {status}")
                if status == 'completed':
                    print(f"输出: {msg['data']['output']}")
                    break
                elif status == 'failed':
                    print(f"错误: {msg['data']['error']}")
                    break

asyncio.run(run_and_monitor())
```

### 8.6.2 模式 2：交互式中断/恢复

处理带有人工介入中断点的工作流。

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'run_workflow',
    id: 'msg-001',
    data: {
      workflow_id: 'content-review',
      input: { text: 'Generate a blog post about AI' },
      subscribe_task: true
    }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'task_state' && msg.data.status === 'interrupted') {
    const interrupt = msg.data.interrupt;
    console.log(`作业 '${interrupt.job_id}' 中断: ${interrupt.message}`);

    // 响应中断
    ws.send(JSON.stringify({
      type: 'resume_task',
      id: 'msg-002',
      data: {
        task_id: msg.data.task_id,
        job_id: interrupt.job_id,
        answer: { approved: true }
      }
    }));
  }

  if (msg.type === 'task_state' && msg.data.status === 'completed') {
    console.log('最终输出:', msg.data.output);
    ws.close();
  }
};
```

### 8.6.3 模式 3：订阅已有任务

监控通过 REST API 或其他客户端启动的任务。

```javascript
// 1. 通过 REST API 启动工作流
const response = await fetch('/workflows/runs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    workflow_id: 'batch-processing',
    input: { data: '...' },
    wait_for_completion: false
  })
});

const { task_id } = await response.json();

// 2. 稍后，连接 WebSocket 并订阅
const ws = new WebSocket('ws://localhost:8080/ws');
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe_task',
    id: 'msg-001',
    data: { task_id }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'task_subscribed') {
    console.log('当前状态:', msg.data.state.status);
  }
  if (msg.type === 'task_state') {
    console.log('已更新:', msg.data.status);
  }
};
```

### 8.6.4 模式 4：单 Job 进度可视化

通过同时监听 `job_event` 和 `task_state` 消息渲染进度时间线。当您需要向用户展示*当前正在运行的具体 job*，而不仅仅是整体进度条时非常有用。

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'run_workflow',
    id: 'msg-001',
    data: {
      workflow_id: 'inspire-with-voice',
      input: {},
      subscribe_task: true
    }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'job_event') {
    const { job_id, event: phase, elapsed, run_id } = msg.data;
    if (phase === 'started') {
      console.log(`▶ ${job_id} 已开始`);
    } else if (phase === 'completed') {
      console.log(`✓ ${job_id} 在 ${elapsed.toFixed(2)} 秒内完成 (run_id=${run_id})`);
    } else if (phase === 'failed') {
      console.log(`✗ ${job_id} 失败：${msg.data.error}`);
    } else if (phase === 'routed') {
      console.log(`→ ${job_id} 路由到 ${msg.data.next_job_id}`);
    }
  }

  if (msg.type === 'task_state' && msg.data.status === 'completed') {
    console.log('工作流完成。');
    ws.close();
  }
};
```

### 8.6.5 模式 5：多任务仪表板

通过单个 WebSocket 连接监控多个任务。

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
const tasks = {};

ws.onopen = async () => {
  // 启动多个工作流
  for (const workflow of ['translate', 'summarize', 'classify']) {
    ws.send(JSON.stringify({
      type: 'run_workflow',
      id: `run-${workflow}`,
      data: {
        workflow_id: workflow,
        input: { text: 'Some input text' },
        subscribe_task: true
      }
    }));
  }
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'workflow_started') {
    tasks[msg.data.task_id] = { workflow: msg.data.workflow_id, status: 'pending' };
    console.log(`[${msg.data.workflow_id}] 已启动: ${msg.data.task_id}`);
  }

  if (msg.type === 'task_state') {
    const task = tasks[msg.data.task_id];
    if (task) {
      task.status = msg.data.status;
      console.log(`[${task.workflow}] ${msg.data.status}`);

      if (msg.data.status === 'completed') {
        task.output = msg.data.output;
      }
    }

    // 检查所有任务是否完成
    const allDone = Object.values(tasks).every(
      t => t.status === 'completed' || t.status === 'failed'
    );
    if (allDone) {
      console.log('所有任务已完成:', tasks);
      ws.close();
    }
  }
};
```

---

## 8.7 连接管理

### 8.7.1 会话与重连

- 每个 WebSocket 连接由会话 ID 标识（自动生成或通过 `?session=` 指定）。
- 连接断开后，可以使用相同会话 ID 重连（需要前一个连接完全关闭后）。
- 要创建新会话，只需省略 `?session=` 参数或使用新的 UUID。

### 8.7.2 连接生命周期

WebSocket 连接关闭时：
- 该客户端的所有任务订阅会自动移除。
- 正在运行的工作流**不受影响** — WebSocket 是监控/控制通道，与工作流执行无关。
- 客户端可以重连并重新订阅以继续监控。

### 8.7.3 连接限制

配置 `max_connection_count` 并达到限制时，新连接将以关闭代码 `4429`（Too Many Connections）被拒绝。

```yaml
controller:
  adapter:
    type: http-server
    websocket:
      max_connection_count: 50  # 超过 50 个连接将被拒绝
```

### 8.7.4 Ping 保活

使用 `ping` 消息验证连接是否存活：

```javascript
// 每 30 秒发送 ping
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'ping', id: 'heartbeat' }));
  }
}, 30000);
```

---

## 8.8 安全注意事项

### 8.8.1 会话 ID 安全

会话 ID（`?session=` 和 `?session_id=`）不是认证机制：
- 任何知道会话 ID 的人都可以将 REST 订阅链接到该会话的 WebSocket。
- 在不受信任的网络环境中，考虑在应用层添加基于令牌的认证。

### 8.8.2 CORS 和来源

控制器配置中的 `origins` 设置适用于来自浏览器的 WebSocket 连接：

```yaml
controller:
  adapter:
    type: http-server
    origins: "https://app.example.com"  # 限制浏览器来源
```

注意：这仅适用于浏览器发起的连接。服务器到服务器的 WebSocket 连接不受 CORS 限制。

### 8.8.3 生产环境建议

- 通过反向代理使用 WSS（WebSocket over TLS）
- 将来源限制为可信域名
- 设置 `max_connection_count` 防止资源耗尽
- 考虑添加应用层认证

**Nginx 反向代理 WebSocket 配置：**

```nginx
server {
    listen 443 ssl;
    server_name app.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /ws {
        proxy_pass http://127.0.0.1:8080/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;  # 保持连接存活
    }
}
```

---

## 8.9 最佳实践

### 1. 使用 `subscribe_task: true` 进行实时监控

通过 WebSocket 执行工作流时，始终设置 `subscribe_task: true` 以接收自动更新：

```json
{
  "type": "run_workflow",
  "data": {
    "workflow_id": "my-workflow",
    "subscribe_task": true
  }
}
```

### 2. 处理所有消息类型

始终包含 `error` 消息和意外状态的处理器：

```javascript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'workflow_started':
    case 'task_state':
    case 'job_event':
    case 'task_subscribed':
    case 'task_resumed':
      // 正常处理
      break;
    case 'error':
      console.error(`[${msg.data.code}] ${msg.data.message}`);
      break;
    default:
      console.warn('未知消息类型:', msg.type);
  }
};
```

### 3. 实现重连逻辑

WebSocket 连接可能断开。实现指数退避重连：

```javascript
function connectWithRetry(url, maxRetries = 5) {
  let retries = 0;

  function connect() {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      retries = 0; // 成功连接时重置
      // 如需要则重新订阅任务
    };

    ws.onclose = () => {
      if (retries < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, retries), 30000);
        retries++;
        console.log(`${delay}ms 后重连...`);
        setTimeout(connect, delay);
      }
    };

    return ws;
  }

  return connect();
}
```

### 4. 使用消息 ID 进行关联

在请求消息中包含 `id` 以关联响应：

```javascript
const msgId = `msg-${Date.now()}`;
ws.send(JSON.stringify({
  type: 'run_workflow',
  id: msgId,
  data: { workflow_id: 'my-workflow' }
}));

// 响应将包含相同的 id
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id === msgId && msg.type === 'workflow_started') {
    // 这是对我们特定请求的响应
  }
};
```

### 5. 完成后取消订阅

取消订阅已完成的任务以保持连接整洁：

```javascript
if (msg.data.status === 'completed' || msg.data.status === 'failed') {
  ws.send(JSON.stringify({
    type: 'unsubscribe_task',
    data: { task_id: msg.data.task_id }
  }));
}
```

---

## 下一步

尝试以下操作：
- 连接 WebSocket 端点并执行工作流
- 构建实时监控仪表板
- 交互式处理中断/恢复流程
- 结合 REST API 和 WebSocket 构建混合架构

---

**上一章**：[第7章：控制器配置](./07-controller-configuration.md) | **下一章**：[第9章：Web UI 配置](./09-webui-configuration.md)
