# Tracer Configuration Reference

Tracers send structured tracing data from workflow and job executions to external observability tools. They provide visibility into execution flow, performance metrics, and debugging information through dedicated tracing backends like Langfuse.

## Basic Structure

### Single Tracer

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
```

### Multiple Tracers

```yaml
tracers:
  - driver: langfuse
    public_key: ${env.LANGFUSE_PUBLIC_KEY}
    secret_key: ${env.LANGFUSE_SECRET_KEY}

  - driver: langfuse
    public_key: ${env.LANGFUSE_PUBLIC_KEY_2}
    secret_key: ${env.LANGFUSE_SECRET_KEY_2}
    url: http://localhost:3000
```

## Tracer Drivers

### Langfuse (`langfuse`)

Sends traces to [Langfuse](https://langfuse.com), an open-source LLM observability platform.

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
```

**Requirements:** `langfuse>=4.0` (installed automatically on first use)

## Common Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | **required** | Tracer backend driver (currently: `langfuse`) |
| `capture` | object | `{input: true, output: true}` | Controls what data is included in traces |
| `timeout` | integer | `30` | Timeout in seconds for API requests to the tracing backend |

## Capture Settings

The `capture` section controls what data is included in trace payloads.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `capture.input` | boolean | `true` | Include input data in traces |
| `capture.output` | boolean | `true` | Include output data in traces |
| `capture.redact_keys` | list[string] | `[]` | Keys to redact from payloads (case-insensitive, recursive) |
| `capture.max_payload_bytes` | integer | none | Maximum payload size in bytes; payloads exceeding this are replaced with `[truncated]` |

### Redaction

Keys listed in `redact_keys` are replaced with `[redacted]` recursively throughout the entire payload, regardless of nesting depth. Matching is case-insensitive.

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  capture:
    redact_keys:
      - Authorization
      - secret_key
      - api_key
```

### Payload Size Limit

When `max_payload_bytes` is set, payloads that exceed the limit (in UTF-8 bytes) are replaced with `[truncated]`.

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  capture:
    max_payload_bytes: 1048576    # 1MB
```

## Langfuse Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | **required** | Must be `langfuse` |
| `public_key` | string | **required** | Langfuse public key |
| `secret_key` | string | **required** | Langfuse secret key |
| `url` | string | none | Langfuse server URL (e.g., `https://cloud.langfuse.com`, `http://localhost:3000`). Cannot be used with `host`. |
| `host` | string | `cloud.langfuse.com` | Langfuse server hostname or IP address. Cannot be used with `url`. |
| `port` | integer | `443` | Langfuse server port number (1–65535). |
| `secure` | boolean | `true` | Use HTTPS for connections. |

> **Note:** Use either `url` or `host`/`port`/`secure`, not both. When neither is specified, defaults to `https://cloud.langfuse.com`.

## Tracing Data Model

Tracers capture a two-level hierarchy: **Trace** (workflow execution) and **Span** (job execution).

```
Trace (workflow execution)
├── Span (job execution)
├── Span (job execution)
└── ...
```

### Trace (Workflow)

| Field | Value |
|-------|-------|
| `name` | Workflow ID |
| `id` | Task ID (deterministic, seeded from task_id) |
| `session_id` | Session ID (if provided at workflow execution) |
| `input` | Workflow input (when `capture.input: true`) |
| `output` | Workflow output (when `capture.output: true`) |
| `status` | `SUCCESS` or `ERROR` |
| `metadata` | `{workflow_id, metadata}` |

### Span (Job)

| Field | Value |
|-------|-------|
| `name` | Job ID |
| `input` | Rendered job input (when `capture.input: true`) |
| `output` | Job output (when `capture.output: true`) |
| `status` | `SUCCESS` or `ERROR` |

## Configuration Examples

### Basic Langfuse Tracer

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
```

Sends all workflow and job traces to Langfuse Cloud with full input/output capture.

### Self-Hosted Langfuse (URL)

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  url: http://localhost:3000
```

### Self-Hosted Langfuse (Host/Port)

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  host: localhost
  port: 3000
  secure: false
```

Connects to a self-hosted Langfuse instance.

### Output-Only Tracing

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  capture:
    input: false
    output: true
```

Only captures output data, excluding potentially sensitive input payloads.

### Tracing with Redaction

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  capture:
    redact_keys:
      - Authorization
      - api_key
      - secret_key
      - password
    max_payload_bytes: 1048576
```

Redacts sensitive keys and limits payload size to 1MB.

### Minimal Tracing (No Payloads)

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  capture:
    input: false
    output: false
```

Captures only trace structure (workflow/job names, timing, status) without any payload data.

## Session Grouping

Tracers support `session_id` for grouping multiple workflow executions into a single session. When provided, traces are grouped in the Langfuse UI by session.

```bash
# CLI
model-compose run chat --session-id my-session -i '{"prompt": "hello"}'

# HTTP API
# POST /workflows/runs
# {"workflow_id": "chat", "input": {...}, "session_id": "my-session"}
```

In Langfuse, traces with the same `session_id` appear grouped together, making it easy to track multi-turn conversations or related workflow executions.

## Complete Example

```yaml
controller:
  type: http-server
  port: 8080

tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  url: http://localhost:3000
  capture:
    input: true
    output: true
    redact_keys:
      - Authorization
      - api_key

logger:
  type: console
  level: info

components:
  - id: gpt-4o
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
      output: ${response.choices[0].message.content}

workflows:
  - id: chat
    jobs:
      - id: generate
        component: gpt-4o
        input:
          prompt: ${input.prompt}
```

## Behavior

- **Non-blocking**: Tracer event methods are synchronous and return immediately. Events are queued internally and sent asynchronously by a background worker.
- **Fault-tolerant**: Tracer failures never impact workflow execution. Errors are logged as warnings and the affected event is dropped.
- **No-op when unconfigured**: If no tracers are configured, tracing calls are no-ops with zero performance impact.
- **Optional dependency**: The `langfuse` package is an optional dependency, installed automatically when a Langfuse tracer is configured.

## Best Practices

### Development Environment
```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  url: http://localhost:3000
```

Use a self-hosted Langfuse instance for full visibility during development.

### Production Environment
```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  capture:
    redact_keys:
      - Authorization
      - api_key
      - password
      - secret_key
    max_payload_bytes: 1048576
```

Enable redaction for sensitive keys and set payload size limits in production.

### High-Volume Environments
```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  capture:
    input: false
    output: false
```

Disable payload capture to minimize overhead while still tracking execution structure and timing.

## Troubleshooting

### Common Issues

**Traces not appearing in Langfuse:**
- Verify `public_key` and `secret_key` are correct
- Check `url` (or `host`/`port`/`secure`) points to the correct Langfuse instance
- Ensure the Langfuse server is accessible from the model-compose host
- Check logs for tracer warning messages

**Missing input/output data:**
- Verify `capture.input` and `capture.output` are `true`
- Check if `max_payload_bytes` is set too low (data may be truncated)
- Verify `redact_keys` isn't matching keys you want to see

**Langfuse package not found:**
- The `langfuse>=4.0` package is installed automatically on first use
- If auto-install fails, install manually: `pip install "langfuse>=4.0"`

**Connection timeouts:**
- Increase the `timeout` value (default: 30 seconds)
- Check network connectivity to the Langfuse server
- Verify firewall rules allow outbound connections
