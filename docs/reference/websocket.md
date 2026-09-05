# WebSocket Interface Reference

The `http-server` controller exposes a WebSocket endpoint for real-time, bidirectional communication. This reference documents every message type sent over that connection.

For configuration options and usage patterns, see the [WebSocket Interface user guide](../user-guide/08-websocket-interface.md).

## Endpoint

```
ws://<host>:<port><base_path>/ws
```

The path component (default `/ws`) is configurable via `controller.websocket.path`. The `base_path` prefix (e.g. `/api`) applies if set on the controller. When the controller is configured with `base_path: /api`, the endpoint is `ws://host:port/api/ws`.

### Query Parameters

| Parameter | Description |
|-----------|-------------|
| `session` | Client-supplied session ID. Auto-generated UUID if omitted. Duplicate connections with the same session are rejected with close code `4409`. |
| `task` | Optional task ID to auto-subscribe to on connection. Equivalent to sending a `subscribe_task` message immediately after connect. |

## Message Envelope

All messages are JSON objects with this shape:

```json
{
  "type": "<message_type>",
  "id": "<optional_request_id>",
  "data": { ... }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | Message type identifier |
| `id` | string | no | Echoed back in responses for request-response correlation |
| `data` | object | varies | Message payload. Some types (e.g. `ping`) accept an empty body. |

## Client → Server Messages

### `run_workflow`

Execute a workflow.

```json
{
  "type": "run_workflow",
  "id": "msg-001",
  "data": {
    "workflow_id": "chat-completion",
    "input": { "prompt": "Hello" },
    "metadata": { "user": "alice" },
    "session_id": "session-abc",
    "subscribe_task": true
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workflow_id` | string | `__default__` | Workflow to execute |
| `input` | object | `{}` | Workflow input parameters |
| `metadata` | any | `null` | Free-form metadata stored on the task |
| `session_id` | string | connection session | Override the session id for this task |
| `subscribe_task` | boolean | `true` | Auto-subscribe to subsequent `task_state` / `job_event` updates |

**Response:** `workflow_started`, followed by `task_state` and `job_event` messages if subscribed.

### `subscribe_task`

Subscribe to updates for an existing task.

```json
{
  "type": "subscribe_task",
  "id": "msg-002",
  "data": { "task_id": "01HXYZ..." }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | yes | Target task ID (ULID) |

**Response:** `task_subscribed` with the current state, followed by future `task_state` and `job_event` messages.

### `unsubscribe_task`

Stop receiving updates for a task.

```json
{
  "type": "unsubscribe_task",
  "id": "msg-003",
  "data": { "task_id": "01HXYZ..." }
}
```

**Response:** `task_unsubscribed`.

### `resume_task`

Resume an interrupted workflow. Equivalent to `POST /tasks/{task_id}/resume`.

```json
{
  "type": "resume_task",
  "id": "msg-004",
  "data": {
    "task_id": "01HXYZ...",
    "job_id": "review-step",
    "run_id": null,
    "answer": { "approved": true }
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | yes | Task to resume |
| `job_id` | string | yes | Must match the interrupted job (`interrupt.job_id`) |
| `run_id` | string \| null | no | Must match `interrupt.run_id`. Non-null only for `component` jobs with `repeat_count > 1`; pass `null` (or omit) otherwise |
| `answer` | any | no | Value passed to the workflow as the interrupt answer |

**Response:** `task_resumed` on success, or `error`.

### `get_task`

Query a task's current state once. Does not create a subscription.

```json
{
  "type": "get_task",
  "id": "msg-005",
  "data": { "task_id": "01HXYZ..." }
}
```

**Response:** `task_state` with the current snapshot.

### `ping`

Connection liveness check.

```json
{ "type": "ping", "id": "msg-006" }
```

**Response:** `pong`.

### `stream_pull`

Request the next chunk of an outbound stream. Sent by the client for each chunk it wants to consume (credit-based backpressure).

```json
{ "type": "stream_pull", "data": { "id": "01HSTREAM..." } }
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stream ID from the `__variable__` marker in a `task_state` / `task_event` output |

**Response:** one `stream_chunk` (or a binary frame for `kind: "bytes"`), followed eventually by `stream_end` or `stream_abort`.

### `stream_end`

Signal end-of-input for an inbound stream. After this the server treats the stream as complete and the workflow's async iterator terminates normally.

```json
{ "type": "stream_end", "data": { "id": "01HSTREAM..." } }
```

### `stream_abort`

Abort an inbound stream. The workflow's iterator receives an `IOError` on the next pull.

```json
{ "type": "stream_abort", "data": { "id": "01HSTREAM...", "reason": "user cancelled" } }
```

### `stream_close`

Cancel consumption of an outbound stream. Instructs the server to stop producing chunks and release the underlying iterator.

```json
{ "type": "stream_close", "data": { "id": "01HSTREAM..." } }
```

## Server → Client Messages

### `workflow_started`

Sent in response to `run_workflow`. Acknowledges the task has been accepted and provides its identifier.

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

### `task_subscribed`

Confirms a subscription and includes the current state at the moment of subscription.

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

### `task_unsubscribed`

Confirms a subscription has been removed.

```json
{
  "type": "task_unsubscribed",
  "id": "msg-003",
  "data": { "task_id": "01HXYZ..." }
}
```

### `task_state`

Latest-state snapshot of the workflow as a whole. Pushed automatically to subscribers when the task transitions between states.

```json
{
  "type": "task_state",
  "data": {
    "task_id": "01HXYZ...",
    "status": "completed",
    "output": { "result": "..." },
    "error": null,
    "interrupt": null,
    "session_id": null,
    "metadata": null,
    "timestamp": "2026-02-06T12:34:56.789Z"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Task ID |
| `status` | string | `"pending"` \| `"processing"` \| `"interrupted"` \| `"completed"` \| `"failed"` |
| `output` | any \| null | Final output on `completed`. Only JSON-serializable values; non-serializable outputs (e.g. raw images) become `null` |
| `error` | string \| null | Error message on `failed` |
| `interrupt` | object \| null | Interrupt details on `interrupted` (`job_id`, `run_id`, `phase`, `message`, `metadata`) |
| `session_id` | string \| null | Session associated with the task |
| `metadata` | any \| null | Metadata supplied at `run_workflow` time |
| `timestamp` | string | ISO 8601 UTC timestamp of state change |

### `job_event`

Per-job lifecycle event. Pushed to subscribers as each job inside the workflow transitions through its lifecycle. Unlike `task_state` (which reflects the workflow as a whole), `job_event` provides fine-grained per-job visibility.

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

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Parent task ID |
| `run_id` | string \| string[] \| null | Component action run ID(s). String for a single run, array when `repeat_count` produces multiple. `null` for non-component jobs (`delay`, `filter`, `switch`, etc.) or when not yet issued. |
| `workflow_id` | string | Workflow ID |
| `job_id` | string | Job ID from the workflow config |
| `event` | string | `"started"` \| `"completed"` \| `"failed"` \| `"routed"` |
| `elapsed` | number \| null | Seconds elapsed since job start. Present on `completed`, `failed`, `routed`; `null` on `started`. |
| `output` | any \| null | Job output on `completed` (JSON-serializable only; otherwise `null`) |
| `error` | string \| null | Error message on `failed` |
| `next_job_id` | string \| null | Target job ID on `routed` (emitted by routing jobs like `switch`, `if`, `random_router`) |
| `timestamp` | string | ISO 8601 UTC timestamp of event emission |

**Event values:**

| `event` | When emitted |
|---------|--------------|
| `started` | Job has been scheduled and its task has begun. `run_id` may be `null` because component run IDs are issued only when the action actually executes. |
| `completed` | Job finished successfully. Carries `elapsed`, `output`, and `run_id` when applicable. |
| `failed` | Job raised an exception. Carries `elapsed`, `error`, and `run_id` when applicable. The workflow itself will transition to `failed` shortly after. |
| `routed` | A routing job returned a `RoutingTarget`. Carries `elapsed`, `next_job_id`, and `run_id`. The next job's own `started` event follows. |

**Typical sequences:**

```
started → completed
started → failed
started → routed → started(next_job) → ...
```

**Notes:**
- Delivered to every client subscribed to the parent `task_id`. No separate `subscribe_job_event` is needed.
- Unlike `task_state` (latest-state), `job_event` is a one-shot event stream. Subscribers connected throughout the task receive each event exactly once; there is no retransmission on reconnect.
- `output` on `completed` is omitted (or `null`) when the value isn't JSON-serializable.

### `task_resumed`

Sent in response to a successful `resume_task`.

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

### `pong`

Response to `ping`.

```json
{
  "type": "pong",
  "id": "msg-006",
  "data": { "timestamp": "2026-02-06T12:34:56.789Z" }
}
```

### `stream_pull`

Sent by the server to request the next chunk of an inbound stream (credit-based backpressure). The client must respond with either a binary chunk frame or a `stream_end` / `stream_abort` message for the same stream ID.

```json
{ "type": "stream_pull", "data": { "id": "01HSTREAM..." } }
```

### `stream_chunk`

Text/JSON chunk of an outbound stream. Only emitted for streams whose `kind` is `"text"` or `"object"`. For `kind: "bytes"`, chunks are delivered as binary WebSocket frames instead — see [Binary Chunk Frames](#binary-chunk-frames).

```json
{
  "type": "stream_chunk",
  "data": {
    "id": "01HSTREAM...",
    "seq": 3,
    "value": "..."
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Stream ID |
| `seq` | integer | Zero-based chunk sequence number |
| `value` | string \| object | Chunk payload. `string` for `kind: "text"`, JSON value for `kind: "object"`. |

### `stream_end`

End-of-stream marker for an outbound stream. No further chunks will follow.

```json
{ "type": "stream_end", "data": { "id": "01HSTREAM..." } }
```

### `stream_abort`

Abnormal termination of an outbound stream. The upstream iterator raised an error.

```json
{ "type": "stream_abort", "data": { "id": "01HSTREAM...", "reason": "connection reset" } }
```

### `stream_close`

Acknowledgement that an inbound stream has been released after the consuming workflow called `aclose()`. Emitted at most once per stream.

```json
{ "type": "stream_close", "data": { "id": "01HSTREAM..." } }
```

### `error`

Returned when a client request can't be processed. May carry the `id` of the request it failed.

```json
{
  "type": "error",
  "id": "msg-001",
  "data": {
    "code": "WORKFLOW_NOT_FOUND",
    "message": "Workflow 'invalid-workflow' not found",
    "details": { "workflow_id": "invalid-workflow" }
  }
}
```

**Error codes:**

| Code | Meaning |
|------|---------|
| `INVALID_REQUEST` | Malformed JSON or missing required fields |
| `WORKFLOW_NOT_FOUND` | The specified workflow does not exist |
| `TASK_NOT_FOUND` | The specified task does not exist |
| `TASK_NOT_INTERRUPTED` | `resume_task` was called on a task that isn't interrupted |
| `JOB_ID_MISMATCH` | `resume_task.job_id` doesn't match the current interrupt point |
| `STREAM_NOT_FOUND` | Referenced stream ID is not registered for this connection |
| `INTERNAL_ERROR` | Unexpected server-side error |

## Streaming Values

Workflow inputs and outputs may contain live byte streams (uploaded videos, generated audio, LLM token streams, etc.) that don't fit into a single JSON payload. These are represented in the JSON envelope as `__variable__` stream markers; the actual chunk data flows out-of-band over the same WebSocket connection.

### Stream Marker

Wherever a stream appears inside `input` (client → server) or `output` (server → client), it is encoded as:

```json
{
  "__variable__": {
    "type": "stream",
    "id": "01HSTREAM...",
    "kind": "bytes",
    "content_type": "video/mp4",
    "filename": "clip.mp4",
    "size": null,
    "attrs": {}
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"stream"` |
| `id` | string | Stream ID scoped to this connection. Used in every subsequent `stream_pull` / `stream_chunk` / `stream_end` / `stream_abort` / `stream_close` message. |
| `kind` | string | `"bytes"` (binary frames), `"text"` (JSON `stream_chunk.value` as string), or `"object"` (JSON `stream_chunk.value` as arbitrary JSON) |
| `content_type` | string \| null | MIME type — determines the domain resource type on the server (video, audio, image, …) |
| `filename` | string \| null | Original filename if applicable |
| `size` | integer \| null | Total byte size if known upfront |
| `attrs` | object | Domain-specific attributes (e.g. audio sample rate) |

Multiple streams may appear in the same payload; each has an independent `id` and its chunks may be interleaved.

### Inbound Streams (client → server)

1. Client sends `run_workflow` whose `input` contains one or more stream markers.
2. Server registers each stream and starts the workflow.
3. When the workflow consumes a stream, the server sends `stream_pull` for that stream ID.
4. Client responds with **one** chunk — a binary frame for `kind: "bytes"`, or (for text/object kinds, if supported) inline in a client-side message payload. In practice binary is the norm for uploads.
5. Steps 3–4 repeat. Client sends `stream_end` (normal completion) or `stream_abort` (error) to terminate.

### Outbound Streams (server → client)

1. Server sends `task_state` or `task_event` whose `output` contains one or more stream markers.
2. Client sends `stream_pull` for each chunk it wants to consume.
3. Server responds with a `stream_chunk` (text/object) or a binary chunk frame (bytes).
4. Steps 2–3 repeat. Server sends `stream_end` when the producer is exhausted, or `stream_abort` if the producer raised an error.
5. Client may cancel early with `stream_close`.

### Binary Chunk Frames

For `kind: "bytes"` streams, chunks travel as **WebSocket binary frames** rather than JSON messages. This avoids base64 overhead on the wire.

Each binary frame carries a single chunk with this layout (big-endian):

```
+------------+------------------------+---------+-------------+
| u16 id_len | stream_id UTF-8 bytes  | u32 seq | chunk bytes |
+------------+------------------------+---------+-------------+
```

| Field | Size | Description |
|-------|------|-------------|
| `id_len` | 2 bytes | Length of the stream_id in bytes (UTF-8 encoded) |
| `stream_id` | `id_len` bytes | Stream ID, UTF-8 |
| `seq` | 4 bytes | Zero-based chunk sequence number, incremented per chunk on the same stream |
| `chunk` | remaining | Raw chunk payload |

The receiver dispatches by `stream_id`, so multiple streams may interleave binary frames freely.

### Backpressure

Each stream uses a **credit=1** model: the consumer must send one `stream_pull` for each chunk it wants. The producer never sends a chunk unsolicited. This keeps memory bounded regardless of stream length or producer speed.

### Disconnect Handling

- **Client disconnect** — all inbound streams for that connection are aborted; workflow iterators raise `IOError`. All outbound stream iterators are closed.
- **Workflow completion with no consumer** — outbound streams that were never pulled are released when the connection closes.

## Close Codes

| Code | Reason |
|------|--------|
| `4409` | Session already connected (duplicate `session` parameter) |
| `4429` | Connection limit reached (`max_connection_count` exceeded) |

## Delivery Semantics

- **`task_state`** — emitted on every task status change. On subscription, the current state is delivered once via `task_subscribed.state`.
- **`job_event`** — emitted once per job lifecycle transition (`started` / `completed` / `failed` / `routed`). Subscribers connected throughout the run receive all events in emission order.
- **Replay** — neither message type is buffered after emission. Events emitted before a client subscribes are not replayed; subscribe at workflow start (e.g. `run_workflow` with `subscribe_task: true`) for full coverage.
- **Subscriptions** — scoped to the WebSocket connection. Closing the connection removes all subscriptions for that client. The underlying workflow is not affected.
- **Streams** — scoped to the WebSocket connection. Stream IDs are unique per connection but not globally; the same ID from a different connection refers to a different stream. Closing the connection aborts all inbound streams and closes all outbound iterators.
