# 19. 附录

本章提供 model-compose 的高级参考资料。

---

## 19.1 完整配置文件架构

### 19.1.1 顶层结构

```yaml
controller:        # 必填：控制器和适配器配置
  adapter:         # 多个适配器请使用 `adapters:`
    type: http-server | mcp-server | queue-subscriber
    # ... 详细配置

components:        # 可选：可重用组件列表
  - id: component-id
    type: model | http-client | http-server | ...
    # ... 组件特定配置

workflows:         # 可选：工作流定义
  - id: workflow-id
    title: Workflow Title
    # ... 工作流配置

listeners:         # 可选：异步回调监听器
  - id: listener-id
    type: http-callback
    # ... 监听器配置

gateways:          # 可选：HTTP 隧道网关
  - type: ngrok | cloudflare | ssh-tunnel
    # ... 网关配置

loggers:           # 可选：日志记录器配置
  - type: console | file
    # ... 日志记录器配置
```

**简写语法**（单项）：
```yaml
component:         # 替代 components: [ ... ]
workflow:          # 替代 workflows: [ ... ]
listener:          # 替代 listeners: [ ... ]
gateway:           # 替代 gateways: [ ... ]
logger:            # 替代 loggers: [ ... ]
action:            # 替代 actions: [ ... ]（在组件内部）
```

### 19.1.2 控制器架构

**HTTP 服务器**：
```yaml
controller:
  adapter:
    type: http-server
    host: 127.0.0.1                      # 默认：127.0.0.1
    port: 8080                           # 默认：8080
    base_path: /api                      # 默认：null
    origins: "*"                         # 默认："*"（CORS）
    websocket:                           # 默认启用
      path: /ws
      ping_interval: 30s
      ping_timeout: 10s
  max_concurrent_count: 10             # 默认：0（无限制）
  shutdown_timeout: 30s
  threaded: false

  webui:                               # 可选：Web UI 配置
    driver: gradio | static | dynamic
    host: 127.0.0.1
    port: 8081
    static_dir: webui                  # 用于 static 驱动，默认："webui"

  runtime:                             # 可选：替代运行时
    type: docker
    # ... Docker 选项
```

**MCP 服务器**：
```yaml
controller:
  adapter:
    type: mcp-server
    host: 127.0.0.1                      # 默认：127.0.0.1
    port: 8080                           # 默认：8080
    base_path: /mcp                      # 默认：null

  webui:                               # 可选
    driver: gradio
    port: 8081
```

### 19.1.3 组件架构

**模型组件**：
```yaml
components:
  - id: model-id
    type: model
    task: text-generation | chat-completion | text-to-text | text-embedding | text-classification | image-to-text | image-text-to-text | text-to-speech | speech-to-text | voice-activity-detection | image-generation | image-upscale | face-detection | pose-detection | face-embedding | music-generation
    driver: huggingface | unsloth | vllm | llamacpp | custom  # 默认：huggingface
    model: model-name-or-path          # 或 `{ provider, repository/path, ... }` 对象

    # 模型配置（组件级别）
    device: cuda | cpu | mps           # 默认：cpu
    device_mode: auto | single         # 默认：auto
    precision: auto | float32 | float16 | bfloat16   # 可选
    quantization: int8 | int4 | fp4 | nf4            # 可选；或完整的 ModelQuantizationConfig 对象
    low_cpu_mem_usage: false           # 默认：false
    preload: true                      # 默认：true
    on_demand: false                   # 默认：false；或 `{ priority, idle_timeout }`
    fast_tokenizer: true               # 仅语言模型任务，默认：true
    max_seq_length: 2048               # 仅语言模型任务，默认：2048

    # LoRA / PEFT 适配器
    peft_adapters:
      - type: lora
        name: adapter-name
        model: path/to/adapter
        weight: 1.0

    # 单个 action（输入/输出映射与推理参数）
    action:
      # 输入（根据任务而异）
      prompt: ${input.prompt as text}
      text: ${input.text as text}
      messages: [ ... ]
      image: ${input.image as image}
      batch_size: 1                    # action 级别
      streaming: false                 # action 级别（仅适用于 text-generation / chat-completion / text-to-text / image-to-text）
      params:
        max_output_length: 100
        temperature: 0.7
        top_p: 0.9
        do_sample: true
```

**HTTP 客户端**：
```yaml
components:
  - id: http-client-id
    type: http-client

    # 组件级别
    base_url: https://api.example.com
    headers: { ... }
    rate_limit: "10/s"                 # 可选；简写或完整 RateLimitConfig

    # 单个 action
    action:
      method: GET | POST | PUT | DELETE | PATCH
      path: /resource                  # 与 base_url 组合
      headers: { ... }
      params: { ... }
      body: { ... }
      stream_format: json | text

    # 或多个 action
    actions:
      - id: action-id
        path: /action-path
        method: POST
        # ...
```

**HTTP 服务器**（托管）：
```yaml
components:
  - id: http-server-id
    type: http-server

    # 服务器生命周期脚本（install/build/clean/start 简写也可放在组件根级）
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

    # 服务器配置
    port: 8000
    base_path: /                 # 可选
    headers: { }                 # 合并到每个 action

    # 服务器启动后调用的 action
    action:
      method: POST
      path: /v1/completions
      body: { ... }
      stream_format: json
```

**向量存储**：
```yaml
components:
  - id: vector-store-id
    type: vector-store
    driver: chroma | milvus | qdrant | faiss

    # 驱动特定配置
    host: localhost              # milvus, qdrant
    port: 19530                  # milvus, qdrant
    path: ./chroma_db            # chroma

    # 操作
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

**键值存储**：
```yaml
components:
  - id: kv-store-id
    type: key-value-store
    driver: redis

    # 连接配置（url 或 host/port）
    url: redis://localhost:6379/0
    # host: localhost
    # port: 6379
    # password: ${env.REDIS_PASSWORD}
    # database: 0

    # 操作
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

**数据集**：
```yaml
components:
  - id: dataset-id
    type: datasets
    provider: huggingface | local

    # HuggingFace
    dataset: dataset-name
    split: train
    subset: subset-name

    # 本地
    path: ./data
    format: json | csv | parquet

    # 操作
    select: [ column1, column2 ]
    filter: ${condition}
    map: ${transformation}
    shuffle: true
    sample: 100
```

**文本分割器**：
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

**Shell 命令**：
```yaml
components:
  - id: shell-id
    type: shell
    base_dir: .                  # 可选
    env: { }                     # 可选
    action:
      command:
        - echo
        - ${input.message}
```

### 19.1.4 工作流架构

**基本结构**：
```yaml
workflows:
  - id: workflow-id
    title: Workflow Title
    description: Workflow description
    default: false                  # 可选
    private: false                  # 可选

    jobs:
      - id: job-id
        component: component-id
        action: action-id           # 可选：用于多操作组件
        input: { ... }
        output: { ... }
        depends_on: [ other-job ]   # 可选：依赖关系
        repeat_count: 1             # 可选：重复次数

    output: { ... }                 # 可选：工作流级输出映射
```

**作业类型**：
```yaml
# 通用字段（适用于每种作业类型）
# - id、name、depends_on、max_run_count
# - interrupt: { before, after }     # 每个：false | true | { condition, message, metadata }
# - hook: { before, after }          # 每个：单个钩子或 { script } 列表

# 1. Component 作业（默认 - 执行组件）
- id: job1
  type: component        # 可以省略（默认）
  component: component-id
  action: action-id      # 可选：用于多操作组件
  input: ${input}
  output: ${output}
  repeat_count: 1
  max_run_count: 5
  interrupt:
    before: false        # true 或 { condition, message, metadata }
    after: false
  hook:
    before:              # 单个钩子或钩子列表
      script: |
        async def hook(input, **kwargs):
            return input
    after:
      - script: |
          async def hook(input, output, **kwargs):
              return output

# 2. If 作业（条件分支）
- id: job2
  type: if
  input: ${input.status}
  operator: eq
  value: active
  if_true: job-success
  if_false: job-fail
  # 或使用多个条件：
  #   conditions:
  #     - { operator: eq, value: a, if_true: job-a }
  #     - { operator: eq, value: b, if_true: job-b }
  #   otherwise: job-default

# 3. Switch 作业（多路分支）
- id: job3
  type: switch
  input: ${input.category}
  cases:
    - { value: image, then: process-image }
    - { value: video, then: process-video }
  otherwise: process-unknown

# 4. Random router（均匀或加权）
- id: job4
  type: random-router
  mode: weighted           # 或 "uniform"
  routings:
    - { to: variant-a, weight: 0.7 }
    - { to: variant-b, weight: 0.3 }

# 5. Delay 作业（延迟）
- id: job5
  type: delay
  mode: time-interval      # 或 "specific-time"
  duration: 5s             # time-interval 模式
  # specific-time 模式：
  #   time: "2026-01-01T09:00:00"
  #   timezone: Asia/Seoul

# 6. For-each 作业（迭代）
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

# 7. Filter 作业（仅输出重塑）
- id: job7
  type: filter
  output:
    active: ${jobs.load.output.records}
```

If 作业支持的条件运算符：`eq`、`neq`、`gt`、`gte`、`lt`、`lte`、`in`、`not-in`、`starts-with`、`ends-with`、`match`。

### 19.1.5 监听器架构

```yaml
listeners:
  - id: listener-id
    type: http-callback

    # Webhook 端点
    path: /webhook
    method: POST

    # 工作流触发器
    workflow: workflow-id

    # 回调配置
    callback:
      url: https://api.example.com/callback
      method: POST
      headers: { ... }
      body: { ... }

    # 批量处理
    bulk:
      enabled: true
      size: 10
      interval: 60
```

### 19.1.6 网关架构

**ngrok**：
```yaml
gateways:
  - type: ngrok
    port: 8080
    authtoken: ${env.NGROK_AUTHTOKEN}
    region: us | eu | ap | au | sa | jp | in
    domain: custom-domain.ngrok.io
```

**Cloudflare**：
```yaml
gateways:
  - type: cloudflare
    port: 8080
    tunnel_id: ${env.CLOUDFLARE_TUNNEL_ID}
    credentials_file: ~/.cloudflared/credentials.json
```

**SSH 隧道**：
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
      # 或
      auth:
        type: password
        username: user
        password: ${env.SSH_PASSWORD}
```

### 19.1.7 日志记录器架构

**控制台日志记录器**：
```yaml
loggers:
  - type: console
    level: DEBUG | INFO | WARNING | ERROR
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

**文件日志记录器**：
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

### 19.1.8 追踪器架构

**Langfuse 追踪器**：
```yaml
tracers:
  - driver: langfuse
    public_key: ${env.LANGFUSE_PUBLIC_KEY}
    secret_key: ${env.LANGFUSE_SECRET_KEY}
    base_url: https://cloud.langfuse.com   # 可选
    timeout: 30                             # 可选（秒）
    capture:
      input: true                          # 在追踪中包含输入
      output: true                         # 在追踪中包含输出
      redact_keys:                         # 要脱敏的键
        - Authorization
        - api_key
      max_payload_bytes: 1048576           # 最大负载大小（字节）
```

### 19.1.9 运行时架构

**Docker 运行时**：
```yaml
controller:
  runtime:
    type: docker

    # 镜像
    image: python:3.11
    build:                       # 可选：自定义构建
      context: .
      dockerfile: Dockerfile
      args:
        ARG_NAME: value

    # 资源
    mem_limit: 4g
    cpus: "2.0"
    gpus: all | "device=0,1"
    shm_size: 1g

    # 卷
    volumes:
      - ./data:/data
      - model-cache:/cache

    # 环境变量
    environment:
      VAR_NAME: value
      API_KEY: ${env.API_KEY}

    # 网络
    network_mode: bridge | host
    ports:
      - "8080:8080"

    # 策略
    restart: no | always | on-failure | unless-stopped

    # 健康检查
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://localhost:8080/health" ]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 下一步

尝试这些练习：
- 使用完整的架构参考配置高级设置
- 为您的项目设计组件和工作流

---

**上一章**：[第18章：故障排除](./18-troubleshooting.md)
