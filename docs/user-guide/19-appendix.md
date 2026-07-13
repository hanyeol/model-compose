# 19. Appendix

This chapter provides advanced reference materials for model-compose.

---

## 19.1 Complete Configuration File Schema

### 19.1.1 Top-Level Structure

```yaml
controller:        # Required: controller and adapter configuration
  adapter:         # or `adapters:` for multiple adapter types
    type: http-server | mcp-server | queue-subscriber
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

### 19.1.2 Controller Schema

**HTTP Server**:
```yaml
controller:
  adapter:
    type: http-server
    host: 127.0.0.1                      # Default: 127.0.0.1
    port: 8080                           # Default: 8080
    base_path: /api                      # Default: null
    origins: "*"                         # Default: "*" (CORS)
    websocket:                           # Default: enabled with defaults
      path: /ws                          # Default: /ws
      ping_interval: 30s                 # Default: 30s
      ping_timeout: 10s                  # Default: 10s
  max_concurrent_count: 10             # Default: 0 (unlimited)
  shutdown_timeout: 30s                # Default: 30s
  threaded: false                      # Default: false

  webui:                               # Optional: Web UI configuration
    driver: gradio | static | dynamic
    host: 127.0.0.1                    # Default: 127.0.0.1
    port: 8081                         # Default: 8081
    static_dir: webui                  # For static driver, default: "webui"

  runtime:                             # Optional: alternate runtime
    type: docker
    # ... Docker options
```

**MCP Server**:
```yaml
controller:
  adapter:
    type: mcp-server
    host: 127.0.0.1                      # Default: 127.0.0.1
    port: 8080                           # Default: 8080
    base_path: /mcp                      # Default: null

  webui:                               # Optional
    driver: gradio
    port: 8081
```

### 19.1.3 Component Schema

**Model Component**:
```yaml
components:
  - id: model-id
    type: model
    task: text-generation | chat-completion | text-to-text | text-embedding | text-classification | image-to-text | image-text-to-text | text-to-speech | speech-to-text | image-generation | image-upscale | face-detection | pose-detection | face-embedding | music-generation
    driver: huggingface | unsloth | vllm | llamacpp | custom  # Default: huggingface
    model: model-name-or-path          # Or a `{ provider, repository/path, ... }` object

    # Model configuration (component level)
    device: cuda | cpu | mps           # Default: cpu
    device_mode: auto | single         # Default: auto
    precision: auto | float32 | float16 | bfloat16   # Optional
    quantization: int8 | int4 | fp4 | nf4            # Optional; or a full ModelQuantizationConfig object
    low_cpu_mem_usage: false           # Default: false
    preload: true                      # Default: true
    on_demand: false                   # Default: false; or `{ priority, idle_timeout }`
    fast_tokenizer: true               # Language-model tasks only, default: true
    max_seq_length: 2048               # Language-model tasks only, default: 2048

    # LoRA / PEFT adapters
    peft_adapters:
      - type: lora
        name: adapter-name
        model: path/to/adapter
        weight: 1.0

    # Single action (action:) - input/output mapping and inference options
    action:
      prompt: ${input.prompt as text}  # text-generation, image-to-text, image-generation, ...
      text: ${input.text as text}      # text-to-text, text-embedding, text-classification, text-to-speech
      messages: [ ... ]                # chat-completion
      image: ${input.image as image}   # image-to-text, image-upscale, face-detection, ...
      batch_size: 1                    # Action-level
      streaming: false                 # Action-level (text-generation / chat-completion / text-to-text / image-to-text only)
      params:
        max_output_length: 100
        temperature: 0.7
        top_p: 0.9
        do_sample: true
```

**HTTP Client**:
```yaml
components:
  - id: http-client-id
    type: http-client

    # Endpoint
    base_url: https://api.example.com
    headers: { ... }                   # Default headers included in all requests

    # Optional rate limiting
    rate_limit: "10/s"                 # Shorthand, or a full RateLimitConfig

    # Single action (action:)
    action:
      method: GET | POST | PUT | DELETE | PATCH
      path: /resource                  # Combined with base_url
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

    # Server lifecycle scripts (also accessible as install/build/clean/start shorthand at the component root)
    manage:
      scripts:
        install:
          - [ pip, install, vllm ]
        start:
          - vllm
          - serve
          - model-name
          - --port
          - "8000"
      working_dir: .
      env: { }

    # Server configuration
    port: 8000
    base_path: /                 # Optional
    headers: { }                 # Default headers merged into each action

    # Action(s) called against the managed server after it starts
    action:
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

**Key-Value Store**:
```yaml
components:
  - id: kv-store-id
    type: key-value-store
    driver: redis

    # Connection (url or host/port)
    url: redis://localhost:6379/0
    # host: localhost
    # port: 6379
    # password: ${env.REDIS_PASSWORD}
    # database: 0

    # Actions
    actions:
      - id: set
        method: set
        key: "cache:${input.key}"
        value: ${input.value}
        ttl: 3600

      - id: get
        method: get
        key: "cache:${input.key}"
```

**File Store**:
```yaml
components:
  - id: file-store-id
    type: file-store
    driver: local | aws-s3 | gcp-storage | azure-blob

    # Common
    base_path: workflows/        # logical prefix (optional)

    # Driver-specific
    bucket: my-bucket            # aws-s3, gcp-storage
    container: my-container      # azure-blob
    region: us-east-1            # aws-s3
    access_key_id: ${env.AWS_ACCESS_KEY_ID}
    secret_access_key: ${env.AWS_SECRET_ACCESS_KEY}
    # endpoint_url: http://minio.local:9000   # S3-compatible
    # connection_string: ${env.AZURE_STORAGE_CONNECTION_STRING}  # azure-blob

    # Actions
    actions:
      - id: put
        method: put
        path: ${input.path}
        source: ${input.file}          # UploadFile / StreamResource / bytes / str
        content_type: image/png

      - id: get
        method: get
        path: ${input.path}
        # destination: /tmp/${input.path}     # save to local file
        # streaming: true                     # lazy stream to next job

      - id: delete
        method: delete
        path: ${input.path}

      - id: exists
        method: exists
        path: ${input.path}

      - id: list
        method: list
        path: images/
        max_results: 100
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
    action:
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
    base_dir: .                  # Optional
    env: { }                     # Optional
    action:
      command:
        - echo
        - ${input.message}
```

### 19.1.4 Workflow Schema

**Basic Structure**:
```yaml
workflows:
  - id: workflow-id
    title: Workflow Title
    description: Workflow description
    default: false                  # Optional
    private: false                  # Optional

    jobs:
      - id: job-id
        component: component-id
        action: action-id           # Optional: for multi-action components
        input: { ... }
        output: { ... }
        depends_on: [ other-job ]   # Optional: dependencies
        repeat_count: 1             # Optional: run N times

    output: { ... }                 # Optional: workflow-level output mapping
```

**Job Types**:
```yaml
# Common fields (available on every job type)
# - id, name, depends_on, max_run_count
# - interrupt: { before, after }     # each: false | true | { condition, message, metadata }
# - hook: { before, after }          # each: single hook or list of { script }

# 1. Component job (default - executes component)
- id: job1
  type: component        # Can be omitted (default)
  component: component-id
  action: action-id      # Optional: for multi-action components
  input: ${input}
  output: ${output}
  repeat_count: 1
  max_run_count: 5
  interrupt:
    before: false        # true or { condition, message, metadata }
    after: false
  hook:
    before:              # single hook or list of hooks
      script: |
        async def hook(input, **kwargs):
            return input
    after:
      - script: |
          async def hook(input, output, **kwargs):
              return output

# 2. If job (conditional branching)
- id: job2
  type: if
  input: ${input.status}
  operator: eq
  value: active
  if_true: job-success
  if_false: job-fail
  # Or with multiple conditions:
  #   conditions:
  #     - { operator: eq, value: a, if_true: job-a }
  #     - { operator: eq, value: b, if_true: job-b }
  #   otherwise: job-default

# 3. Switch job (multi-way branching)
- id: job3
  type: switch
  input: ${input.category}
  cases:
    - { value: image, then: process-image }
    - { value: video, then: process-video }
  otherwise: process-unknown

# 4. Random router (uniform or weighted)
- id: job4
  type: random-router
  mode: weighted           # or "uniform"
  routings:
    - { to: variant-a, weight: 0.7 }
    - { to: variant-b, weight: 0.3 }

# 5. Delay job (wait)
- id: job5
  type: delay
  mode: time-interval      # or "specific-time"
  duration: 5s             # For time-interval mode
  # For specific-time mode:
  #   time: "2026-01-01T09:00:00"
  #   timezone: Asia/Seoul

# 6. For-each job (iterate over items)
- id: job6
  type: for-each
  input: ${input.items}
  batch_size: 4
  streaming: false
  do:
    component: item-processor
    action: transform
    input: { item: ${item} }
    output: ${result}

# 7. Filter job (output-only reshaping)
- id: job7
  type: filter
  output:
    active: ${jobs.load.output.records}
```

Supported condition operators (for `if` jobs): `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not-in`, `starts-with`, `ends-with`, `match`.

### 19.1.5 Listener Schema

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

### 19.1.6 Gateway Schema

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

### 19.1.7 Logger Schema

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

### 19.1.8 Tracer Schema

**Langfuse Tracer**:
```yaml
tracers:
  - driver: langfuse
    public_key: ${env.LANGFUSE_PUBLIC_KEY}
    secret_key: ${env.LANGFUSE_SECRET_KEY}
    base_url: https://cloud.langfuse.com   # Optional
    timeout: 30                             # Optional (seconds)
    capture:
      input: true                          # Include input in traces
      output: true                         # Include output in traces
      redact_keys:                         # Keys to redact
        - Authorization
        - api_key
      max_payload_bytes: 1048576           # Max payload size (bytes)
```

### 19.1.9 Runtime Schema

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

**Previous Chapter**: [18. Troubleshooting](./18-troubleshooting.md)
