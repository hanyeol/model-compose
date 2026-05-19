# Model Memory Component

The model-memory component provides session-based conversation history management for AI models. It declaratively handles storing, loading, summarizing, and windowing of chat messages, enabling stateful multi-turn conversations without custom code.

## Basic Configuration

```yaml
component:
  type: model-memory
  storage:
    driver: sqlite
    path: ./memory.db
  window: 20
  actions:
    - id: load
      method: load
    - id: save
      method: save
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `model-memory` |
| `buffer` | object | `{driver: memory}` | In-memory buffer settings. Temporarily holds appended data before save |
| `storage` | object | `{driver: sqlite}` | Persistent storage settings. Target for save/load/delete |
| `window` | int \| object | - | Window settings. If int, inflates to `{max_turn_count: N}`. If omitted, returns all messages |
| `summary` | object | - | Summary settings. If omitted, no summarization is performed |

### Buffer Settings

The buffer temporarily holds unsaved messages added via `append`. Messages exist only here until `save` is called.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | `memory` | Buffer driver: `memory` (process memory) |

> **Constraint**: Within the same workflow execution, `append` → `save` must run in the same process. The buffer is process-local and not shared across processes.

### Storage Settings

Persistent storage. On `save`, buffered turns are persisted here. `load` and `delete` also target this storage.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | `sqlite` | Storage driver: `sqlite` (default), `redis` |

#### SQLite Storage (Default)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | `.model-memory.db` | SQLite database file path |

```yaml
component:
  type: model-memory
  storage:
    driver: sqlite
    path: ./memory.db
```

#### Redis Storage

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | string | `localhost` | Redis host |
| `port` | int | `6379` | Redis port |
| `url` | string | - | Redis URL (use instead of host/port) |
| `password` | string | - | Redis password |
| `database` | int | `0` | Redis database number |
| `secure` | bool | `false` | Whether to use TLS |

```yaml
component:
  type: model-memory
  storage:
    driver: redis
    host: redis-server
    port: 6379
    password: ${env.REDIS_PASSWORD}
    database: 1
```

### Window Settings

Controls how many recent messages are retained. Can be specified as an integer (shorthand for `max_turn_count`) or as an object.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_turn_count` | int | - | Keep only the most recent N turns |
| `max_message_count` | int | - | Keep only the most recent N messages (respects turn boundaries) |

When both fields are set, the **first exceeded condition** takes effect.

- `max_turn_count`: Limits by turn count. Simply `turns[-N:]`.
- `max_message_count`: Limits by message count, but never splits a turn. Accumulates from the newest turn backwards until the limit would be exceeded.

```yaml
# Shorthand (most recent 10 turns)
window: 10

# Object form
window:
  max_turn_count: 10

# Message count based
window:
  max_message_count: 20

# Combined (whichever limit is exceeded first)
window:
  max_turn_count: 10
  max_message_count: 40
```

### Summary Settings

The `summary` block follows the same component invoke pattern as `AgentModelConfig`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `component` | string | **required** | Component ID to use for summarization |
| `action` | string | `__default__` | Action ID of the component |
| `input` | object | `{messages: ${messages}}` | Input mapping when invoking the component |
| `instruction` | string | `"Summarize the following conversation concisely:"` | Summarization instruction |

#### How Summary Works

Summary is **updated incrementally at append time**:

1. When `append` is called, if turns exceed the window, excess turns are pruned in-memory
2. Pruned turns + existing summary are sent to the LLM to generate a new summary (in-memory)
3. When `save` is called, the current in-memory state (turns + summary) is persisted to storage
4. `load` is read-only — even if unsummarized turns exist in storage, they are not modified (auto-summarized on next `append`)

#### Summary Internal Variables

Variables provided by model-memory when invoking the summary component:

| Variable | Type | Description |
|----------|------|-------------|
| `${messages}` | array | Messages array including the instruction as a system message |
| `${instruction}` | string | The configured summarization instruction |
| `${previous_summary}` | string | Existing summary text (for incremental updates) |

## Behavior Matrix

| window | summary | Behavior |
|--------|---------|----------|
| not set | not set | Returns all raw messages |
| set | not set | Returns only messages within window range; excess is permanently deleted |
| not set | set | Summarizes everything; returns `messages: []` |
| set | set | Returns recent messages within window + summary of the rest |

### Message Storage Model

- Messages are treated as **opaque objects**. Fields like role, content, etc. are not validated.
- Storage unit is individual message objects.
- 1 turn = the messages bundle passed in a single `append` or `save` call.
- Window **respects turn boundaries** (never splits in the middle of a turn).

## Actions

### append

Adds 1 turn (message bundle) to the buffer. Does not persist to storage. Performs in-memory prune + summarize if window is exceeded.

> **Precondition**: `load` must have been called first with the same `session_id`.

**Input:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Session identifier |
| `messages` | array | yes | Array of messages for 1 turn (opaque objects) |

**Output:**

```json
{"success": true, "buffer_turn_count": 3}
```

### save

Persists the buffer's current state (turns + summary) to storage. If `messages` is provided, performs an implicit append (with prune + summarize) before persisting.

> If `save(messages)` is called without a prior `load`, it implicitly performs load → append → persist. Without messages and without a prior load, it's a no-op.

**Input:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Session identifier |
| `messages` | array | no | Array of messages for 1 turn — if provided, appends then persists |

**Output:**

```json
{"success": true, "total_turn_count": 15}
```

### load

Reads the session's memory from storage and returns it (read-only, no storage modification). Return format varies based on window/summary settings. Data read from storage is cached in the buffer's session cache, so subsequent `save` operations work without re-querying storage.

**Input:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Session identifier |

**Output:**

```json
{
  "summary": "The user asked about the weather...",
  "messages": [
    {"role": "user", "content": "What should I have for lunch?"},
    {"role": "assistant", "content": "How about pasta?"}
  ],
  "total_message_count": 42,
  "window_message_count": 20
}
```

| Field | Type | Description |
|-------|------|-------------|
| `summary` | string | Summary text. Empty string if summary is not configured |
| `messages` | array | Raw messages within window range. All messages if neither window nor summary is set. Empty array if only summary is configured |
| `total_message_count` | int | Total raw message count in storage (excludes pruned messages) |
| `window_message_count` | int | Number of messages included in the window |

### clear

Rolls back to the state at the last persist point. Restores to the snapshot from right after `load` or `save`, canceling all subsequent append/prune/summarize operations. Does not affect persisted data in storage.

**Input:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Session identifier |

**Output:**

```json
{"success": true}
```

### delete

Deletes the session's entire history from storage, including summary.

**Input:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | Session identifier |

**Output:**

```json
{"success": true}
```

## Usage Examples

### Simple Chat with Memory (Shortcut Mode)

The most common pattern: load → generate → save(messages).

```yaml
components:
  - id: gpt-4o
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
        Content-Type: application/json
      body:
        model: gpt-4o
        messages: ${input.messages}
      output: ${response.choices[0].message.content}

  - id: chat-memory
    type: model-memory
    storage:
      driver: sqlite
      path: ./memory.db
    window: 20
    summary:
      component: gpt-4o
      input:
        messages: ${messages}
      instruction: "Summarize the following conversation concisely:"
    actions:
      - id: load
        method: load
      - id: save
        method: save

workflows:
  - id: chat-turn
    jobs:
      - id: load-memory
        component: chat-memory
        action: load
        input:
          session_id: ${input.session_id}

      - id: generate
        component: gpt-4o
        input:
          messages:
            - role: system
              content: ${input.system_prompt}
            - role: system
              content: ${jobs.load-memory.output.summary}
            - ...${jobs.load-memory.output.messages}
            - role: user
              content: ${input.user_message}
        depends_on: [load-memory]

      - id: save-memory
        component: chat-memory
        action: save
        input:
          session_id: ${input.session_id}
          messages:
            - role: user
              content: ${input.user_message}
            - role: assistant
              content: ${jobs.generate.output}
        depends_on: [generate]
```

### Flexible Mode (Separate Append Steps)

For fine-grained control: load → append(user) → generate → append(assistant) → save.

```yaml
workflows:
  - id: chat-turn-flexible
    jobs:
      - id: load-memory
        component: chat-memory
        action: load
        input:
          session_id: ${input.session_id}

      - id: append-user
        component: chat-memory
        action: append
        input:
          session_id: ${input.session_id}
          messages:
            - role: user
              content: ${input.user_message}
        depends_on: [load-memory]

      - id: generate
        component: gpt-4o
        input:
          messages:
            - role: system
              content: ${input.system_prompt}
            - role: system
              content: ${jobs.load-memory.output.summary}
            - ...${jobs.load-memory.output.messages}
            - role: user
              content: ${input.user_message}
        depends_on: [load-memory]

      - id: append-ai
        component: chat-memory
        action: append
        input:
          session_id: ${input.session_id}
          messages:
            - role: assistant
              content: ${jobs.generate.output}
        depends_on: [generate, append-user]

      - id: save-memory
        component: chat-memory
        action: save
        input:
          session_id: ${input.session_id}
        depends_on: [append-ai]
```

> **Note (flexible mode)**: Since `append-user` and `append-ai` create separate turns, a small window may prune the user turn while keeping only the assistant turn. To guarantee "1 conversation turn = user + assistant bundle", use the shortcut mode with `save(messages: [user, assistant])`, or set a sufficiently large window in flexible mode.

### Redis Storage for Production

```yaml
component:
  type: model-memory
  storage:
    driver: redis
    url: ${env.REDIS_URL}
    password: ${env.REDIS_PASSWORD}
  window:
    max_turn_count: 50
    max_message_count: 200
  summary:
    component: gpt-4o
    instruction: "Provide a brief summary of this conversation:"
  actions:
    - id: load
      method: load
    - id: save
      method: save
    - id: delete
      method: delete
```

### Memory with All Actions

```yaml
component:
  type: model-memory
  storage:
    driver: sqlite
    path: ./chat.db
  window: 30
  actions:
    - id: append
      method: append
    - id: save
      method: save
    - id: load
      method: load
    - id: clear
      method: clear
    - id: delete
      method: delete
```

## Best Practices

1. **Choose the right mode**: Use shortcut mode (`save` with messages) for simple chatbots; use flexible mode (separate `append` steps) when you need fine-grained control
2. **Set appropriate windows**: Balance between context quality and token costs. 20-50 turns is typical for most chatbots
3. **Enable summarization**: For long conversations, combine `window` + `summary` to retain context without losing important information
4. **Use Redis in production**: SQLite works well for development and single-instance deployments; switch to Redis for multi-instance or distributed setups
5. **Session management**: Use meaningful session IDs (e.g., user ID + conversation ID) to support multiple concurrent conversations
6. **Clean up sessions**: Use the `delete` action to remove completed or abandoned conversation histories
