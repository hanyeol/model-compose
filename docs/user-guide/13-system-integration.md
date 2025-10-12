# 13. System Integration

This chapter covers listeners and gateways for integrating with external systems.

---

## 13.1 Listeners - Async Callbacks

Listeners are HTTP servers for receiving asynchronous callbacks from external systems. They are useful when integrating with external services that send results to a callback URL after task completion.

### 13.1.1 Listener Overview

Many external services don't return results immediately, but queue tasks and send results to a callback URL later:

1. Client sends task request to external service (including callback URL)
2. External service returns task ID immediately
3. External service processes task in background
4. After completion, sends results to callback URL
5. Listener receives callback and delivers results to waiting workflow

### 13.1.2 Basic HTTP Callback Listener Configuration

**Simple callback listener:**

```yaml
listener:
  type: http-callback
  host: 0.0.0.0
  port: 8090
  path: /callback
  method: POST
```

This creates an endpoint at `http://0.0.0.0:8090/callback` that accepts POST requests.

### 13.1.3 Callback Endpoint Configuration

**Single callback endpoint:**

```yaml
listener:
  type: http-callback
  host: 0.0.0.0
  port: 8090
  path: /webhook/completed           # Callback path
  method: POST                        # HTTP method
  identify_by: ${body.task_id}       # Task identifier
  status: ${body.status}              # Status field
  success_when:                       # Success status values
    - "completed"
    - "success"
  fail_when:                          # Failure status values
    - "failed"
    - "error"
  result: ${body.result}              # Result extraction path
```

**Multiple callback endpoints:**

```yaml
listener:
  type: http-callback
  host: 0.0.0.0
  port: 8090
  base_path: /webhooks                # Common base path
  callbacks:
    # Image generation completion callback
    - path: /image/completed
      method: POST
      identify_by: ${body.request_id}
      status: ${body.status}
      success_when: ["completed"]
      fail_when: ["failed"]
      result: ${body.image_url}

    # Video processing completion callback
    - path: /video/completed
      method: POST
      identify_by: ${body.task_id}
      status: ${body.state}
      success_when: ["done"]
      fail_when: ["error", "timeout"]
      result: ${body.output}

    # General task completion callback
    - path: /task/callback
      method: POST
      identify_by: ${body.id}
      result: ${body.data}
```

### 13.1.4 Callback Field Descriptions

| Field | Description | Required | Default |
|-------|-------------|----------|---------|
| `path` | Callback endpoint path | Yes | - |
| `method` | HTTP method | No | `POST` |
| `identify_by` | Task identification field path | No | `__callback__` |
| `status` | Status check field path | No | - |
| `success_when` | Success status value list | No | - |
| `fail_when` | Failure status value list | No | - |
| `result` | Result extraction field path | No | Entire body |
| `bulk` | Handle multiple items in single request | No | `false` |
| `item` | Item extraction path in bulk mode | No | - |

### 13.1.5 Bulk Callback Processing

When receiving results for multiple tasks in a single callback request:

```yaml
listener:
  type: http-callback
  host: 0.0.0.0
  port: 8090
  path: /batch/completed
  method: POST
  bulk: true                          # Enable bulk mode
  item: ${body.results}               # Results array path
  identify_by: ${item.task_id}        # Identifier for each item
  status: ${item.status}
  success_when: ["completed"]
  result: ${item.data}
```

Callback request example:
```json
{
  "results": [
    {
      "task_id": "task-1",
      "status": "completed",
      "data": {"url": "https://example.com/result1.png"}
    },
    {
      "task_id": "task-2",
      "status": "completed",
      "data": {"url": "https://example.com/result2.png"}
    }
  ]
}
```

### 13.1.6 Advanced Listener Configuration

**Concurrency control:**

```yaml
listener:
  type: http-callback
  host: 0.0.0.0
  port: 8090
  max_concurrent_count: 10            # Maximum concurrent callback processing
  path: /callback
  method: POST
```

**Runtime configuration:**

```yaml
listener:
  type: http-callback
  runtime: native                     # or docker
  host: 0.0.0.0
  port: 8090
  path: /callback
```

### 13.1.7 How Listeners Work

Listeners receive callbacks from external services and deliver results to waiting workflows.

**Basic structure:**

```yaml
listener:
  type: http-callback
  host: 0.0.0.0
  port: 8090
  path: /callback
  identify_by: ${body.task_id}        # Identify which workflow
  result: ${body.result}              # Extract result
```

**Workflow execution flow:**

```mermaid
sequenceDiagram
    participant W as Workflow
    participant L as Listener<br/>(Port 8090)
    participant E as External Service

    Note over W,E: 1. Task Request
    W->>E: POST /api/process<br/>{data, callback_url: "http://localhost:8090/callback"}
    E-->>W: 202 Accepted<br/>{task_id: "task-123"}

    Note over W: 2. Waiting for Callback<br/>(Workflow paused)

    Note over E: 3. Background Processing<br/>(Async task execution)

    Note over E,L: 4. Callback After Completion
    E->>L: POST http://localhost:8090/callback<br/>{task_id: "task-123", status: "completed", result: {...}}

    Note over L: 5. Callback Processing
    L->>L: Search waiting workflow<br/>by identify_by<br/>(task_id: "task-123")

    Note over L,W: 6. Result Delivery
    L->>W: Deliver result

    Note over W: 7. Workflow Resumes<br/>(Execute next step)
```

**Step-by-step explanation:**

1. **Workflow start**: Send request to external service (including callback URL)
2. **Immediate response**: External service returns task ID
3. **Waiting state**: Workflow pauses waiting for callback
4. **Background processing**: External service performs async task
5. **Callback sent**: After completion, sends result to callback URL
6. **Listener receives**: Listener receives callback and finds workflow using `identify_by`
7. **Workflow resumes**: Delivers result to workflow and executes next step

**Important**: Listeners only run on local ports. To access from external sources, you need a **gateway** (Section 13.2). Complete examples using gateways are covered in **Section 13.3**.

### 13.1.8 Callback Data Mapping

Listeners can extract and map various fields from callback requests.

**Single field extraction:**

```yaml
listener:
  path: /webhook
  identify_by: ${body.task_id}
  result: ${body.output.url}          # Nested field access
```

**Multiple field extraction:**

```yaml
listener:
  path: /webhook
  identify_by: ${body.task_id}
  result:
    url: ${body.output.url}
    width: ${body.output.width}
    height: ${body.output.height}
    size: ${body.output.file_size}
```

**Using query parameters:**

```yaml
listener:
  path: /webhook
  identify_by: ${query.task_id}       # Extract from URL query
  result: ${body}
```

Callback request example:
```
POST http://localhost:8090/webhook?task_id=task-123
Content-Type: application/json

{
  "status": "completed",
  "output": {
    "url": "https://example.com/result.png"
  }
}
```

---

## 13.2 Gateways - HTTP Tunneling

Gateways are tunneling services for exposing locally running services to the internet. Useful for testing webhooks in development or when external access to local services is needed.

### 13.2.1 Gateway Overview

Gateways are needed in these scenarios:

- Testing external webhooks in local development
- Exposing services behind firewalls
- Temporary public URLs needed
- External services require callback URLs

**Supported gateways:**
- HTTP tunnels: ngrok, Cloudflare Tunnel
- SSH tunnels: SSH reverse tunnels

### 13.2.2 HTTP Tunnel - ngrok

ngrok is a tunneling service that exposes local servers with public URLs.

**Basic configuration:**

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port: 8080                          # Local port to tunnel
```

This exposes local port 8080 through ngrok public URL.

**Complete example:**

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port: 8090                          # Same as listener port

listener:
  type: http-callback
  host: 0.0.0.0
  port: 8090
  path: /callback
  identify_by: ${body.task_id}
  result: ${body.result}

components:
  external-service:
    type: http-client
    base_url: https://api.external-service.com
    path: /process
    method: POST
    body:
      data: ${input.data}
      # Use gateway:8090.public_url to generate public URL
      callback_url: ${gateway:8090.public_url}/callback
      callback_id: ${context.run_id}
    output: ${response}

workflow:
  title: External Service with Gateway
  jobs:
    - id: process
      component: external-service
      input: ${input}
      output: ${output}
```

Execution flow:
1. Gateway starts: ngrok exposes local port 8090 with public URL (e.g., `https://abc123.ngrok.io`)
2. Listener starts: Waiting for callbacks on port 8090
3. Workflow executes: `${gateway:8090.public_url}` is replaced with `https://abc123.ngrok.io`
4. Callback URL `https://abc123.ngrok.io/callback` sent to external service
5. External service sends callback to public URL after completion
6. ngrok forwards request to local port 8090
7. Listener receives callback and delivers result to workflow

### 13.2.3 HTTP Tunnel - Cloudflare

Cloudflare Tunnel is a stable tunneling service available for free.

**Basic configuration:**

```yaml
gateway:
  type: http-tunnel
  driver: cloudflare
  port: 8080
```

**ngrok vs Cloudflare comparison:**

| Feature | ngrok | Cloudflare |
|---------|-------|------------|
| Free plan | Limited (request limit per hour) | Unlimited |
| Setup difficulty | Easy | Medium (account required) |
| URL format | `https://random.ngrok.io` | `https://random.trycloudflare.com` |
| Stability | High | Very high |
| Speed | Fast | Very fast |

### 13.2.4 SSH Tunnel

Use SSH reverse tunnels to expose local services through remote servers.

**SSH key authentication:**

```yaml
gateway:
  type: ssh-tunnel
  port: 8080
  connection:
    host: remote-server.com
    port: 22
    auth:
      type: keyfile
      username: user
      keyfile: ~/.ssh/id_rsa
```

**SSH password authentication:**

```yaml
gateway:
  type: ssh-tunnel
  port: 8080
  connection:
    host: remote-server.com
    port: 22
    auth:
      type: password
      username: user
      password: ${env.SSH_PASSWORD}
```

SSH tunnels are useful when:
- Using custom domains
- Firewalls block ngrok/Cloudflare
- Corporate environments require approved servers only

### 13.2.5 Advanced Gateway Configuration

**Runtime configuration:**

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  runtime: native                     # or docker
  port: 8080
```

**Using gateway variables:**

When gateway is configured, these variables are available:

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port: 8080

components:
  service:
    type: http-client
    body:
      # Use public URL (gateway:port.public_url format)
      webhook_url: ${gateway:8080.public_url}/webhook

      # Port information
      local_port: ${gateway:8080.port}
```

### 13.2.6 Real-world Example: Slack Bot Webhook

```yaml
gateway:
  type: http-tunnel
  driver: cloudflare
  port: 8090                          # Same as listener port

listener:
  type: http-callback
  host: 0.0.0.0
  port: 8090
  base_path: /slack
  callbacks:
    - path: /events
      method: POST
      identify_by: ${body.event.client_msg_id}
      result: ${body.event}

components:
  slack-responder:
    type: http-client
    base_url: https://slack.com/api
    path: /chat.postMessage
    method: POST
    headers:
      Authorization: Bearer ${env.SLACK_BOT_TOKEN}
      Content-Type: application/json
    body:
      channel: ${input.channel}
      text: ${input.text}
    output: ${response}

workflow:
  title: Slack Event Handler
  jobs:
    - id: respond
      component: slack-responder
      input:
        channel: ${input.event.channel}
        text: "Processing complete: ${input.event.text}"
      output: ${output}
```

Slack app setup:
1. Create Slack app (https://api.slack.com/apps)
2. Run `model-compose up` and check gateway logs for public URL
3. Enable Event Subscriptions
4. Enter gateway public URL + listener path in Request URL (e.g., `https://abc123.trycloudflare.com/slack/events`)
5. Issue bot token and set `SLACK_BOT_TOKEN` environment variable

---

## 13.3 Using Listeners and Gateways Together

Using listeners and gateways together allows safe testing of external webhooks in local environments.

### 13.3.1 Integration Example: Async Image Processing

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port: 8090                          # Same as listener port

listener:
  type: http-callback
  host: 0.0.0.0
  port: 8090
  base_path: /webhooks
  max_concurrent_count: 5
  callbacks:
    - path: /image/completed
      method: POST
      identify_by: ${body.task_id}
      status: ${body.status}
      success_when: ["completed", "success"]
      fail_when: ["failed", "error"]
      result:
        url: ${body.output.url}
        width: ${body.output.width}
        height: ${body.output.height}

components:
  image-generator:
    type: http-client
    base_url: https://api.image-ai.com/v1
    path: /generate
    method: POST
    headers:
      Authorization: Bearer ${env.IMAGE_AI_KEY}
    body:
      prompt: ${input.prompt}
      size: ${input.size | "1024x1024"}
      # Gateway public URL + listener path
      callback_url: ${gateway:8090.public_url}/webhooks/image/completed
      task_id: ${context.run_id}
    output:
      task_id: ${response.task_id}
      status: ${response.status}

  image-optimizer:
    type: http-client
    base_url: https://api.imageoptim.com
    path: /optimize
    method: POST
    headers:
      Authorization: Bearer ${env.IMAGEOPTIM_KEY}
    body:
      url: ${input.url}
      quality: 85
    output:
      optimized_url: ${response.url}
      original_size: ${response.original_size}
      compressed_size: ${response.compressed_size}

workflow:
  title: Image Generation and Optimization
  description: Generate image with AI and optimize it
  jobs:
    # Step 1: AI image generation (async)
    - id: generate
      component: image-generator
      input:
        prompt: ${input.prompt}
        size: ${input.size}
      output:
        task_id: ${output.task_id}
        image_url: ${output.url}        # URL from callback
        width: ${output.width}
        height: ${output.height}

    # Step 2: Image optimization (sync)
    - id: optimize
      component: image-optimizer
      input:
        url: ${jobs.generate.output.image_url}
      output:
        final_url: ${output.optimized_url}
        original_size: ${output.original_size}
        compressed_size: ${output.compressed_size}
        savings: ${output.original_size - output.compressed_size}
```

### 13.3.2 Architecture Diagram

```mermaid
sequenceDiagram
    participant User as User/Workflow
    participant Gateway as Gateway<br/>(ngrok, Port 8090)
    participant Listener as Listener<br/>(Port 8090)
    participant External as External AI Service<br/>(api.image-ai.com)

    Note over User,External: 1. Image Generation Request
    User->>External: POST /generate<br/>callback_url: https://abc123.ngrok.io/webhooks/image/completed
    External-->>User: 202 Accepted<br/>task_id: task-123

    Note over User: 2. Waiting for Callback

    Note over External: 3. Background Processing (AI Image Generation)

    Note over External,Listener: 4. Callback After Completion
    External->>Gateway: POST https://abc123.ngrok.io/webhooks/image/completed<br/>{task_id, status, image_url}
    Gateway->>Listener: Forward to local port 8090

    Note over Listener: 5. Callback Processing
    Listener->>Listener: Find waiting workflow by task_id
    Listener->>User: Deliver result (image_url)

    Note over User: 6. Workflow Continues
```

**Flow explanation:**

1. **Request stage**: Workflow sends image generation request to external AI service (gateway public URL as callback URL)
2. **Wait stage**: Workflow waits until callback is received
3. **Processing stage**: External service generates image in background
4. **Callback stage**: After completion, sends callback to gateway public URL → gateway forwards to local listener
5. **Matching stage**: Listener finds waiting workflow by task_id
6. **Completion stage**: Delivers result to workflow and proceeds to next step

### 13.3.3 Production Environment Considerations

**Local development:**
```yaml
gateway:
  type: http-tunnel
  driver: ngrok                       # Use ngrok during development
  port: 8080

listener:
  host: 0.0.0.0
  port: 8090
```

**Production environment:**
```yaml
# Remove gateway configuration (use public IP/domain)

controller:
  type: http-server
  host: 0.0.0.0
  port: 443                           # HTTPS
  # Add SSL configuration

listener:
  host: 0.0.0.0
  port: 8090

components:
  service:
    body:
      # Use production domain
      callback_url: https://api.yourdomain.com/webhooks/callback
      callback_id: ${context.run_id}
```

---

## 13.4 Best Practices

### 1. Listener Security

**Timeout configuration:**

Set timeouts so async tasks don't wait indefinitely:

```yaml
components:
  service:
    type: http-client
    timeout: 300000                   # 5 minute timeout
    body:
      callback_url: ${gateway:8090.public_url}/callback
```

**Signature verification:**

Verify signatures to confirm authenticity of callback requests:

```yaml
listener:
  callbacks:
    - path: /webhook
      # Signature verification requires custom logic
      identify_by: ${body.id}
      # Verify signature in header: ${header.X-Signature}
```

### 2. Gateway Usage

**Use in development only:**

Use gateways primarily in development/test environments. Use public IPs/domains in production.

**Free plan limitations:**

- ngrok free plan: Connection limits, hourly request limits
- Cloudflare: Unlimited on free plan

### 3. Error Handling

**Callback failure handling:**

```yaml
workflow:
  jobs:
    - id: async-task
      component: async-service
      input: ${input}
      on_error:
        - id: retry
          component: async-service
          input: ${input}
          retry:
            max_attempts: 3
            delay: 5000
```

**Retry logic:**

Implement retry logic as external services may fail to send callbacks.

### 4. Logging and Monitoring

**Callback logging:**

Store all callback request information for debugging and troubleshooting:

```yaml
listener:
  callbacks:
    - path: /webhook
      identify_by: ${body.task_id}
      result:
        task_id: ${body.task_id}                              # Task ID
        status: ${body.status}                                # Task status
        timestamp: ${body.timestamp}                          # Callback receipt time
        data: ${body}                                         # Store full payload (for debugging)
```

This stored information is used for:
- Root cause analysis when callbacks fail
- Monitoring external service response times
- Data integrity verification
- Audit log generation

**Workflow execution tracking:**

Track entire flow of each workflow execution:

```yaml
workflow:
  jobs:
    - id: request
      component: external-api
      input: ${input}
      output:
        request_time: ${context.timestamp}
        task_id: ${output.task_id}

    - id: log-request
      component: logger
      input:
        level: info
        message: "Task requested: task_id=${jobs.request.output.task_id}"
        data: ${jobs.request.output}

    # Wait for callback and receive result

    - id: log-result
      component: logger
      input:
        level: info
        message: "Task completed: task_id=${jobs.request.output.task_id}"
        data: ${output}
```

**Gateway URL verification:**

Verify and record public URL after gateway starts:

```bash
model-compose up
# Check gateway URL in logs
# [Gateway] Public URL: https://abc123.ngrok.io

# Register public URL with external service
# e.g., Slack Event Subscriptions, GitHub Webhooks, etc.
```

Since gateway may generate new URLs each startup, recommend extracting URL from automated deployment scripts and auto-registering with external services.

**Performance metrics collection:**

```yaml
listener:
  callbacks:
    - path: /webhook
      identify_by: ${body.task_id}
      result:
        task_id: ${body.task_id}                              # Task ID
        result: ${body.result}                                # Actual result data
        metrics:
          processing_time: ${body.processing_time_ms}         # Actual processing time (ms)
          queue_time: ${body.queue_time_ms}                   # Queue wait time (ms)
          total_time: ${body.processing_time_ms + body.queue_time_ms}  # Total time
```

Use these metrics to:
- Calculate average processing time of external services
- Detect performance degradation and send alerts
- Monitor SLA (Service Level Agreement) compliance

---

## Next Steps

Experiment with these scenarios:
- External async API integration
- Testing webhooks in local environment
- Slack/Discord bot development
- Payment gateway webhook handling

---

**Next Chapter**: [14. Deployment](./14-deployment.md)
