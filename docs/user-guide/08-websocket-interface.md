# Chapter 8: WebSocket Interface

This chapter explains how to use model-compose's WebSocket interface for real-time task monitoring, workflow execution, and bidirectional control over a persistent connection.

---

## 8.1 WebSocket Overview

### 8.1.1 What is the WebSocket Interface?

The WebSocket interface adds a `/ws` endpoint to the HTTP server controller, enabling real-time bidirectional communication between clients and the server. Instead of polling `GET /tasks/{task_id}` repeatedly, clients receive instant status updates as tasks progress.

**Benefits:**
- Real-time task status updates (no polling)
- Bidirectional communication (server push + client commands)
- Lower latency for status changes and interrupt handling
- Efficient resource usage with a single persistent connection
- Monitor multiple tasks simultaneously over one connection

**Use Cases:**
- Real-time dashboards monitoring workflow execution
- Interactive applications with interrupt/resume flows
- Chat applications requiring immediate feedback
- Multi-task monitoring from a single client

### 8.1.2 WebSocket vs REST API

Both interfaces support workflow execution. Choose based on your needs:

| Scenario | Recommended | Reason |
|----------|-------------|--------|
| Simple batch jobs | REST API | No WebSocket connection needed |
| Real-time UI (chat, generation) | WebSocket | Single connection handles everything |
| External system integration | REST API + WebSocket | Standard HTTP to start, monitor via WebSocket |
| Multi-task monitoring | WebSocket | One connection for all tasks |
| curl/Postman testing | REST API | Simple request/response |

### 8.1.3 Delivery Behavior

Subscribed clients receive task state changes and per-job lifecycle events in real time:

- **`task_state`** — pushed whenever the task's status changes (`pending → processing → completed`, etc.). On subscription, the current state is delivered once in the `task_subscribed` response so the client can catch up immediately.
- **`job_event`** — pushed for each `started` / `completed` / `failed` / `routed` transition of every job inside the workflow. If the client stays connected for the duration of the run, all events are delivered in the order they occur.

Both message types are sent at emission time and, under normal operation, arrive without loss. Messages are not buffered after they're emitted, so **events that happened before you subscribed are not replayed** — subscribe at workflow start (`run_workflow` with `subscribe_task: true`) to ensure full coverage.

### 8.1.4 How It Works

```
Client                          Server
  │                               │
  │──── WebSocket Connect ───────>│  ws://localhost:8080/ws
  │<─── Connection Accepted ──────│
  │                               │
  │──── run_workflow ────────────>│  Execute workflow
  │<─── workflow_started ─────────│  Returns task_id
  │                               │
  │<─── task_state (processing) ──│  Real-time updates
  │<─── task_state (interrupted) ─│  Interrupt notification
  │                               │
  │──── resume_task ─────────────>│  Resume workflow
  │<─── task_resumed ─────────────│
  │<─── task_state (completed) ───│  Final result
  │                               │
  │──── close ───────────────────>│
```

---

## 8.2 Configuration

### 8.2.1 Enabling WebSocket

WebSocket is enabled by default when using the HTTP server controller. No additional configuration is required for basic usage.

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
```

The WebSocket endpoint is available at `ws://localhost:8080/ws`.

### 8.2.2 WebSocket Configuration Options

The `websocket` field accepts either a boolean or a configuration object:

- `websocket: true` (default) — enable with default settings
- `websocket: false` — disable WebSocket support
- `websocket: { ... }` — enable with custom settings

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

**Configuration Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | `/ws` | WebSocket endpoint path |
| `max_connection_count` | integer | unlimited | Maximum concurrent WebSocket connections (best-effort; a small overrun is possible between the connection count check and accept) |
| `ping_interval` | integer | `30` | Server-side ping interval in seconds (`0` to disable) |
| `ping_timeout` | integer | `10` | Ping timeout in seconds |

### 8.2.3 Configuration Examples

#### Development Environment

```yaml
controller:
  adapter:
    type: http-server
    host: 0.0.0.0
    port: 8080
    origins: "*"
  # WebSocket enabled by default, no extra config needed
```

#### Production Environment

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

#### Disable WebSocket

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
    websocket: false
```

---

## 8.3 Connecting to WebSocket

### 8.3.1 Basic Connection

Connect to the WebSocket endpoint:

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};

ws.onclose = () => {
  console.log('Disconnected');
};
```

```python
import asyncio
import websockets
import json

async def connect():
    async with websockets.connect('ws://localhost:8080/ws') as ws:
        print('Connected')
        async for message in ws:
            data = json.loads(message)
            print('Received:', data)

asyncio.run(connect())
```

### 8.3.2 Session ID

You can specify a session ID via query parameter to identify your connection:

```javascript
const sessionId = crypto.randomUUID();
const ws = new WebSocket(`ws://localhost:8080/ws?session=${sessionId}`);
```

- If not specified, the server generates a UUID automatically.
- A session ID can only have one active connection. Duplicate connections with the same session ID are rejected (close code `4409`).
- Session IDs enable REST API integration (see [Section 8.5](#85-rest-api-integration)).

### 8.3.3 Auto-Subscribe on Connect

Subscribe to a task immediately on connection using the `task` query parameter:

```javascript
const ws = new WebSocket(`ws://localhost:8080/ws?task=${taskId}`);
```

This is equivalent to connecting and then sending a `subscribe_task` message.

---

## 8.4 WebSocket Messages

### 8.4.1 Message Format

All messages use a common JSON envelope:

```json
{
  "type": "message_type",
  "id": "optional_message_id",
  "data": { }
}
```

- `type` (string, required): Message type identifier
- `id` (string, optional): Unique message ID for request-response correlation
- `data` (object, optional per type): Message-specific payload. May be omitted for messages with no payload (e.g., `ping`); the server treats a missing `data` as `{}`.

### 8.4.2 Client → Server Messages

#### `run_workflow` — Execute a Workflow

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

**Fields:**
- `workflow_id` (string, optional): Workflow to execute (default: `__default__`)
- `input` (object, optional): Workflow input parameters
- `subscribe_task` (boolean, default: `true`): Automatically subscribe to task status updates

**Response:** `workflow_started` message. If `subscribe_task` is `true`, you'll also receive `task_state` updates.

#### `subscribe_task` — Subscribe to Task Updates

```json
{
  "type": "subscribe_task",
  "id": "msg-002",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

**Fields:**
- `task_id` (string, required): Task ID to monitor (ULID format)

**Response:** `task_subscribed` message with current state, followed by `task_state` updates on changes.

#### `unsubscribe_task` — Stop Monitoring a Task

```json
{
  "type": "unsubscribe_task",
  "id": "msg-003",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

**Response:** `task_unsubscribed` message.

#### `resume_task` — Resume an Interrupted Task

This is the WebSocket equivalent of `POST /tasks/{task_id}/resume`.

```json
{
  "type": "resume_task",
  "id": "msg-004",
  "data": {
    "task_id": "01HXYZ...",
    "job_id": "review-step",
    "run_id": null,
    "answer": {
      "approved": true
    }
  }
}
```

**Fields:**
- `task_id` (string, required): Task to resume
- `job_id` (string, required): Interrupted job ID (from `interrupt.job_id`)
- `run_id` (string, optional): Per-run ID from `interrupt.run_id`. Required only for `component` jobs with `repeat_count > 1`; pass `null` (or omit) otherwise.
- `answer` (any, optional): Response value to pass to the workflow

**Response:** `task_resumed` or `error` message.

#### `get_task` — Query Task State (One-time)

```json
{
  "type": "get_task",
  "id": "msg-005",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

**Response:** `task_state` message with current state. Does not create a subscription.

#### `ping` — Connection Health Check

```json
{
  "type": "ping",
  "id": "msg-006"
}
```

**Response:** `pong` message.

### 8.4.3 Server → Client Messages

#### `workflow_started` — Workflow Execution Started

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

Sent in response to `run_workflow`.

#### `task_subscribed` — Subscription Confirmed

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

Sent in response to `subscribe_task`. Includes the current task state at the time of subscription.

#### `task_unsubscribed` — Subscription Removed

```json
{
  "type": "task_unsubscribed",
  "id": "msg-003",
  "data": {
    "task_id": "01HXYZ..."
  }
}
```

#### `task_state` — Task Status Update

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
      "run_id": null,
      "phase": "before",
      "message": "Approval required",
      "metadata": { "cost": 0.5 }
    },
    "timestamp": "2026-02-06T12:34:56.789Z"
  }
}
```

**Fields:**
- `status`: `"pending"` | `"processing"` | `"interrupted"` | `"completed"` | `"failed"`
- `output`: Result data on completion (JSON-serializable values only; non-serializable outputs like images return `null`)
- `error`: Error message on failure
- `interrupt`: Interrupt details when status is `"interrupted"` (`job_id`, `run_id`, `phase`, `message`, `metadata`). `run_id` is non-null only for `component` jobs with `repeat_count > 1`.
- `timestamp`: State change time (ISO 8601)

#### `job_event` — Per-Job Lifecycle Event

Pushed for each job inside a workflow as it transitions through its lifecycle. Unlike `task_state` (which reflects the *workflow as a whole*), `job_event` provides fine-grained visibility into individual jobs.

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

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Task this job belongs to |
| `run_id` | string \| string[] \| null | Component action run id(s). A string for a single run, an array when `repeat_count` produces multiple runs, `null` for non-component jobs or when not yet issued (e.g. some `started` events) |
| `workflow_id` | string | Workflow id |
| `job_id` | string | Job id from the workflow config |
| `event` | string | `"started"` \| `"completed"` \| `"failed"` \| `"routed"` |
| `elapsed` | number | Seconds elapsed since job start (present on `completed` / `failed` / `routed`) |
| `output` | any | Job output on `completed` (only when JSON-serializable; non-serializable values become `null`) |
| `error` | string | Error message on `failed` |
| `next_job_id` | string | Target job id on `routed` (emitted by routing jobs like `switch` / `if` / `random_router`) |
| `timestamp` | string | Emission time (ISO 8601, UTC) |

**Event ordering for a typical job:**

```
started → completed
started → failed
started → routed → started(next_job) → ...
```

**Notes:**
- `job_event` is delivered to all clients subscribed to the parent `task_id` (no separate subscription needed).
- The `started` event may arrive before `run_id` is available — `run_id` is generated when a `ComponentJob` actually invokes its action, which happens after the job task is scheduled. The `completed` / `failed` event always carries `run_id`.
- For jobs that aren't backed by a component (e.g. `delay`, `filter`, `switch`), `run_id` stays `null`.

#### `task_resumed` — Task Resumed

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

Sent in response to `resume_task` on success.

#### `error` — Error Message

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

**Error Codes:**

| Code | Description |
|------|-------------|
| `WORKFLOW_NOT_FOUND` | Specified workflow does not exist |
| `TASK_NOT_FOUND` | Specified task does not exist |
| `INVALID_REQUEST` | Invalid message format or missing required fields |
| `TASK_NOT_INTERRUPTED` | Task is not in interrupted state |
| `JOB_ID_MISMATCH` | Job ID doesn't match current interrupt point |
| `INTERNAL_ERROR` | Unexpected server error |

#### `pong` — Ping Response

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

## 8.5 REST API Integration

WebSocket and REST API can be used together. This is useful when you want to start workflows via REST but monitor them in real time via WebSocket.

### 8.5.1 `subscribe_task` Parameter

The `POST /workflows/runs` endpoint supports a `subscribe_task` parameter:

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

**Requirements:**
- `session_id` query parameter is required when `subscribe_task: true`
- An active WebSocket connection with the matching session ID must exist
- `wait_for_completion` must be `false` (combining both is not allowed, returns 400)

### 8.5.2 `wait_for_completion` and `subscribe_task` Combinations

| wait_for_completion | subscribe_task | Behavior |
|---------------------|----------------|----------|
| `true` (default) | `false` (default) | HTTP waits until completion. No subscription. (Existing behavior) |
| `false` | `false` | Returns PENDING immediately. No subscription. |
| `false` | `true` | Returns PENDING immediately + auto-subscribes via WebSocket. **Recommended pattern.** |
| `true` | `true` | **Not allowed.** Returns 400 Bad Request. |

### 8.5.3 Pattern: WebSocket First + REST Execution

The recommended pattern for REST + WebSocket integration:

```javascript
// 1. Generate session ID and connect WebSocket
const sessionId = crypto.randomUUID();
const ws = new WebSocket(`ws://localhost:8080/ws?session=${sessionId}`);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'task_state') {
    console.log('Status:', msg.data.status);
    if (msg.data.status === 'completed') {
      console.log('Result:', msg.data.output);
    }
  }
};

// 2. Execute workflow via REST API (same session ID)
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
  console.log('Workflow started:', task_id);
  // Updates will arrive automatically via WebSocket
};
```

---

## 8.6 Usage Patterns

### 8.6.1 Pattern 1: Execute and Monitor via WebSocket

The simplest pattern — execute a workflow and receive updates over a single WebSocket connection.

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
      console.log('Started:', msg.data.task_id);
      break;

    case 'task_state':
      console.log('Status:', msg.data.status);
      if (msg.data.status === 'completed') {
        console.log('Output:', msg.data.output);
        ws.close();
      }
      break;

    case 'error':
      console.error('Error:', msg.data.message);
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
        # Execute workflow
        await ws.send(json.dumps({
            'type': 'run_workflow',
            'id': 'msg-001',
            'data': {
                'workflow_id': 'chat-completion',
                'input': {'prompt': 'Hello, AI!'},
                'subscribe_task': True
            }
        }))

        # Receive updates
        async for message in ws:
            msg = json.loads(message)

            if msg['type'] == 'workflow_started':
                print(f"Started: {msg['data']['task_id']}")

            elif msg['type'] == 'task_state':
                status = msg['data']['status']
                print(f"Status: {status}")
                if status == 'completed':
                    print(f"Output: {msg['data']['output']}")
                    break
                elif status == 'failed':
                    print(f"Error: {msg['data']['error']}")
                    break

asyncio.run(run_and_monitor())
```

### 8.6.2 Pattern 2: Interactive Interrupt/Resume

Handle workflows with human-in-the-loop interrupt points.

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
    console.log(`Interrupt at job '${interrupt.job_id}': ${interrupt.message}`);

    // Respond to the interrupt
    ws.send(JSON.stringify({
      type: 'resume_task',
      id: 'msg-002',
      data: {
        task_id: msg.data.task_id,
        job_id: interrupt.job_id,
        run_id: interrupt.run_id,
        answer: { approved: true }
      }
    }));
  }

  if (msg.type === 'task_state' && msg.data.status === 'completed') {
    console.log('Final output:', msg.data.output);
    ws.close();
  }
};
```

### 8.6.3 Pattern 3: Subscribe to Existing Task

Monitor a task that was started via REST API or another client.

```javascript
// 1. Start workflow via REST API
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

// 2. Later, connect WebSocket and subscribe
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
    console.log('Current state:', msg.data.state.status);
  }
  if (msg.type === 'task_state') {
    console.log('Updated:', msg.data.status);
  }
};
```

### 8.6.4 Pattern 4: Per-Job Progress Visualization

Render a progress timeline by listening to `job_event` messages alongside `task_state`. Useful when you need to show users *which job is running right now* instead of just an overall spinner.

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
      console.log(`▶ ${job_id} started`);
    } else if (phase === 'completed') {
      console.log(`✓ ${job_id} completed in ${elapsed.toFixed(2)}s (run_id=${run_id})`);
    } else if (phase === 'failed') {
      console.log(`✗ ${job_id} failed: ${msg.data.error}`);
    } else if (phase === 'routed') {
      console.log(`→ ${job_id} routed to ${msg.data.next_job_id}`);
    }
  }

  if (msg.type === 'task_state' && msg.data.status === 'completed') {
    console.log('Workflow done.');
    ws.close();
  }
};
```

### 8.6.5 Pattern 5: Multi-Task Dashboard

Monitor multiple tasks over a single WebSocket connection.

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
const tasks = {};

ws.onopen = async () => {
  // Start multiple workflows
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
    console.log(`[${msg.data.workflow_id}] Started: ${msg.data.task_id}`);
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

    // Check if all tasks are done
    const allDone = Object.values(tasks).every(
      t => t.status === 'completed' || t.status === 'failed'
    );
    if (allDone) {
      console.log('All tasks completed:', tasks);
      ws.close();
    }
  }
};
```

---

## 8.7 Connection Management

### 8.7.1 Session and Reconnection

- Each WebSocket connection is identified by a session ID (auto-generated or specified via `?session=`).
- If a connection drops, you can reconnect with the same session ID (after the previous connection is fully closed).
- To create a new session, simply omit the `?session=` parameter or use a new UUID.

### 8.7.2 Connection Lifecycle

When a WebSocket connection closes:
- All task subscriptions for that client are automatically removed.
- Running workflows are **not** affected — WebSocket is a monitoring/control channel, not tied to workflow execution.
- The client can reconnect and re-subscribe to continue monitoring.

### 8.7.3 Connection Limits

When `max_connection_count` is configured and the limit is reached, new connections are rejected with close code `4429` (Too Many Connections).

```yaml
controller:
  adapter:
    type: http-server
    websocket:
      max_connection_count: 50  # Reject connections beyond 50
```

### 8.7.4 Keep-Alive with Ping

Use the `ping` message to verify the connection is alive:

```javascript
// Send ping every 30 seconds
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'ping', id: 'heartbeat' }));
  }
}, 30000);
```

---

## 8.8 Security Considerations

### 8.8.1 Session ID Security

Session IDs (`?session=` and `?session_id=`) are not authentication mechanisms:
- Anyone who knows a session ID can link REST subscriptions to that session's WebSocket.
- In untrusted network environments, consider adding token-based authentication at the application level.

### 8.8.2 CORS and Origins

The `origins` setting in controller configuration applies to WebSocket connections from browsers:

```yaml
controller:
  adapter:
    type: http-server
    origins: "https://app.example.com"  # Restrict browser origins
```

Note: This only applies to browser-initiated connections. Server-to-server WebSocket connections are not restricted by CORS.

### 8.8.3 Production Recommendations

- Use WSS (WebSocket over TLS) via a reverse proxy
- Restrict origins to trusted domains
- Set `max_connection_count` to prevent resource exhaustion
- Consider adding application-level authentication

**Nginx reverse proxy for WebSocket:**

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
        proxy_read_timeout 3600s;  # Keep connection alive
    }
}
```

---

## 8.9 Best Practices

### 1. Use `subscribe_task: true` for Real-Time Monitoring

When executing workflows via WebSocket, always set `subscribe_task: true` to receive automatic updates:

```json
{
  "type": "run_workflow",
  "data": {
    "workflow_id": "my-workflow",
    "subscribe_task": true
  }
}
```

### 2. Handle All Message Types

Always include handlers for `error` messages and unexpected states:

```javascript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'workflow_started':
    case 'task_state':
    case 'job_event':
    case 'task_subscribed':
    case 'task_resumed':
      // Handle normally
      break;
    case 'error':
      console.error(`[${msg.data.code}] ${msg.data.message}`);
      break;
    default:
      console.warn('Unknown message type:', msg.type);
  }
};
```

### 3. Implement Reconnection Logic

WebSocket connections can drop. Implement exponential backoff reconnection:

```javascript
function connectWithRetry(url, maxRetries = 5) {
  let retries = 0;

  function connect() {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      retries = 0; // Reset on successful connection
      // Re-subscribe to tasks if needed
    };

    ws.onclose = () => {
      if (retries < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, retries), 30000);
        retries++;
        console.log(`Reconnecting in ${delay}ms...`);
        setTimeout(connect, delay);
      }
    };

    return ws;
  }

  return connect();
}
```

### 4. Use Message IDs for Correlation

Include `id` in request messages to correlate responses:

```javascript
const msgId = `msg-${Date.now()}`;
ws.send(JSON.stringify({
  type: 'run_workflow',
  id: msgId,
  data: { workflow_id: 'my-workflow' }
}));

// Response will include the same id
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id === msgId && msg.type === 'workflow_started') {
    // This is the response to our specific request
  }
};
```

### 5. Unsubscribe When Done

Unsubscribe from completed tasks to keep the connection clean:

```javascript
if (msg.data.status === 'completed' || msg.data.status === 'failed') {
  ws.send(JSON.stringify({
    type: 'unsubscribe_task',
    data: { task_id: msg.data.task_id }
  }));
}
```

---

## Next Steps

Try these:
- Connect to a WebSocket endpoint and execute a workflow
- Build a real-time monitoring dashboard
- Handle interrupt/resume flows interactively
- Combine REST API and WebSocket for hybrid architectures

---

**Previous Chapter**: [7. Controller Configuration](./07-controller-configuration.md) | **Next Chapter**: [9. Web UI Configuration](./09-webui-configuration.md)
