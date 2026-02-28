# 17. Appendix

This chapter provides advanced reference materials for model-compose.

---

## 17.1 Complete Configuration File Schema

### 17.1.1 Top-Level Structure

```yaml
controller:        # Required: HTTP or MCP server configuration
  type: http-server | mcp-server
  # ... detailed configuration

components:        # Optional: Reusable component list
  - id: component-id
    type: model | http-client | http-server | ...
    # ... component-specific configuration

workflows:         # Optional: Workflow definitions
  - id: workflow-id
    title: Workflow Title
    # ... workflow configuration

listeners:         # Optional: Async callback listeners
  - id: listener-id
    type: http-callback
    # ... listener configuration

gateways:          # Optional: HTTP tunnel gateways
  - type: ngrok | cloudflare | ssh-tunnel
    # ... gateway configuration

loggers:           # Optional: Logger configuration
  - type: console | file
    # ... logger configuration
```

**Shorthand Syntax** (single item):
```yaml
component:         # Instead of components: [ ... ]
workflow:          # Instead of workflows: [ ... ]
listener:          # Instead of listeners: [ ... ]
gateway:           # Instead of gateways: [ ... ]
logger:            # Instead of loggers: [ ... ]
action:            # Instead of actions: [ ... ] (within a component)
```

### 17.1.2 Controller Schema

**HTTP Server**:
```yaml
controller:
  type: http-server
  port: 8080                           # Default: 8080
  host: 0.0.0.0                        # Default: 0.0.0.0
  base_path: /api                      # Default: /
  max_concurrency: 10                  # Default: unlimited

  webui:                               # Optional: Web UI configuration
    driver: gradio | static
    port: 8081
    root: ./static                     # For static driver

  runtime:                             # Optional: Docker runtime
    type: docker
    image: python:3.11
    # ... Docker options
```

**MCP Server**:
```yaml
controller:
  type: mcp-server
  port: 8080                           # Optional
  base_path: /mcp                      # Default: /

  webui:                               # Optional
    driver: gradio
    port: 8081
```

### 17.1.3 Component Schema

**Model Component**:
```yaml
components:
  - id: model-id
    type: model
    task: text-generation | chat-completion | translation | ...
    model: model-name-or-path

    # Model configuration
    device: cuda | cpu | mps
    dtype: float32 | float16 | bfloat16 | int8 | int4
    batch_size: 1
    streaming: false

    # Parameters
    params:
      max_output_length: 100
      temperature: 0.7
      top_p: 0.9
      do_sample: true

    # LoRA adapters
    peft_adapters:
      - type: lora
        name: adapter-name
        model: path/to/adapter
        weight: 1.0

    # Single action (action:) - input/output mapping
    action:
      text: ${input.text as text}
      messages: [ ... ]
      image: ${input.image as image}
```

**HTTP Client**:
```yaml
components:
  - id: http-client-id
    type: http-client

    # Endpoint
    base_url: https://api.example.com

    # Advanced configuration
    timeout: 30
    max_retries: 3
    retry_delay: 1

    # Single action (action:)
    action:
      endpoint: https://api.example.com/v1/resource
      method: GET | POST | PUT | DELETE | PATCH
      path: /resource
      headers: { ... }
      params: { ... }
      body: { ... }
      stream_format: json | text

    # Or multiple actions (actions:)
    actions:
      - id: action-id
        path: /action-path
        method: POST
        # ...
```

**HTTP Server** (Managed):
```yaml
components:
  - id: http-server-id
    type: http-server

    # Server start command
    start:
      - vllm
      - serve
      - model-name
      - --port
      - "8000"

    # Server configuration
    port: 8000
    healthcheck:
      path: /health
      interval: 5s
      timeout: 10s
      retries: 3

    # HTTP client configuration (after server starts)
    method: POST
    path: /v1/completions
    body: { ... }
    stream_format: json
```

**Vector Store**:
```yaml
components:
  - id: vector-store-id
    type: vector-store
    driver: chroma | milvus | qdrant | faiss

    # Driver-specific configuration
    host: localhost              # milvus, qdrant
    port: 19530                  # milvus, qdrant
    path: ./chroma_db            # chroma

    # Actions
    actions:
      - id: insert
        collection: collection-name
        method: insert
        vector: ${input.vector}
        metadata: ${input.metadata}

      - id: search
        collection: collection-name
        method: search
        query: ${input.vector}
        top_k: 5
        output_fields: [ field1, field2 ]
```

**Dataset**:
```yaml
components:
  - id: dataset-id
    type: datasets
    provider: huggingface | local

    # HuggingFace
    dataset: dataset-name
    split: train
    subset: subset-name

    # Local
    path: ./data
    format: json | csv | parquet

    # Operations
    select: [ column1, column2 ]
    filter: ${condition}
    map: ${transformation}
    shuffle: true
    sample: 100
```

**Text Splitter**:
```yaml
components:
  - id: text-splitter-id
    type: text-splitter
    text: ${input.text}
    chunk_size: 1000
    chunk_overlap: 200
    separator: "\n\n"
```

**Shell Command**:
```yaml
components:
  - id: shell-id
    type: shell
    command: echo
    args:
      - ${input.message}
```

### 17.1.4 Workflow Schema

**Basic Structure**:
```yaml
workflows:
  - id: workflow-id
    title: Workflow Title
    description: Workflow description

    # Single component
    component: component-id
    input: ${input}
    output: ${output}

    # Or multiple jobs
    jobs:
      - id: job-id
        component: component-id
        action: action-id        # Optional: for multi-action components
        input: { ... }
        output: { ... }
        depends_on: [ job-id ]   # Optional: dependencies
        condition: ${expression} # Optional: conditional execution
```

**Job Types**:
```yaml
# 1. Action job (default - executes component)
- id: job1
  type: action           # Can be omitted (default)
  component: component-id
  action: action-id      # Optional: for multi-action components
  input: ${input}
  output: ${output}

# 2. If job (conditional branching)
- id: job2
  type: if
  operator: eq
  input: ${input.status}
  value: "active"
  if_true: job-success
  if_false: job-fail

# 3. Delay job (wait)
- id: job3
  type: delay
  duration: 5s           # Wait 5 seconds
```

### 17.1.5 Listener Schema

```yaml
listeners:
  - id: listener-id
    type: http-callback

    # Webhook endpoint
    path: /webhook
    method: POST

    # Workflow trigger
    workflow: workflow-id

    # Callback configuration
    callback:
      url: https://api.example.com/callback
      method: POST
      headers: { ... }
      body: { ... }

    # Bulk processing
    bulk:
      enabled: true
      size: 10
      interval: 60
```

### 17.1.6 Gateway Schema

**ngrok**:
```yaml
gateways:
  - type: ngrok
    port: 8080
    authtoken: ${env.NGROK_AUTHTOKEN}
    region: us | eu | ap | au | sa | jp | in
    domain: custom-domain.ngrok.io
```

**Cloudflare**:
```yaml
gateways:
  - type: cloudflare
    port: 8080
    tunnel_id: ${env.CLOUDFLARE_TUNNEL_ID}
    credentials_file: ~/.cloudflared/credentials.json
```

**SSH Tunnel**:
```yaml
gateways:
  - type: ssh-tunnel
    port: 8080
    connection:
      host: remote-server.com
      port: 22
      auth:
        type: keyfile
        username: user
        keyfile: ~/.ssh/id_rsa
      # Or
      auth:
        type: password
        username: user
        password: ${env.SSH_PASSWORD}
```

### 17.1.7 Logger Schema

**Console Logger**:
```yaml
loggers:
  - type: console
    level: DEBUG | INFO | WARNING | ERROR
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

**File Logger**:
```yaml
loggers:
  - type: file
    level: INFO
    path: ./logs/app.log
    format: "%(asctime)s - %(levelname)s - %(message)s"
    rotation:
      max_bytes: 10485760        # 10MB
      backup_count: 5
```

### 17.1.8 Runtime Schema

**Docker Runtime**:
```yaml
controller:
  runtime:
    type: docker

    # Image
    image: python:3.11
    build:                       # Optional: custom build
      context: .
      dockerfile: Dockerfile
      args:
        ARG_NAME: value

    # Resources
    mem_limit: 4g
    cpus: "2.0"
    gpus: all | "device=0,1"
    shm_size: 1g

    # Volumes
    volumes:
      - ./data:/data
      - model-cache:/cache

    # Environment variables
    environment:
      VAR_NAME: value
      API_KEY: ${env.API_KEY}

    # Network
    network_mode: bridge | host
    ports:
      - "8080:8080"

    # Policy
    restart: no | always | on-failure | unless-stopped

    # Healthcheck
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://localhost:8080/health" ]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Next Steps

Try these exercises:
- Configure advanced settings using the complete schema reference
- Design components and workflows for your project

---

**Previous Chapter**: [15. Practical Examples](./15-practical-examples.md)
