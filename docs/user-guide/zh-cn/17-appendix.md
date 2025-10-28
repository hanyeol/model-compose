# 17. 附录

本章提供 model-compose 的高级参考资料。

---

## 17.1 完整配置文件架构

### 17.1.1 顶层结构

```yaml
controller:        # 必填：HTTP 或 MCP 服务器配置
  type: http-server | mcp-server
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
```

### 17.1.2 控制器架构

**HTTP 服务器**：
```yaml
controller:
  type: http-server
  port: 8080                           # 默认：8080
  host: 0.0.0.0                        # 默认：0.0.0.0
  base_path: /api                      # 默认：/
  max_concurrency: 10                  # 默认：无限制

  webui:                               # 可选：Web UI 配置
    driver: gradio | static
    port: 8081
    root: ./static                     # 用于 static 驱动

  runtime:                             # 可选：Docker 运行时
    type: docker
    image: python:3.11
    # ... Docker 选项
```

**MCP 服务器**：
```yaml
controller:
  type: mcp-server
  port: 8080                           # 可选
  base_path: /mcp                      # 默认：/

  webui:                               # 可选
    driver: gradio
    port: 8081
```

### 17.1.3 组件架构

**模型组件**：
```yaml
components:
  - id: model-id
    type: model
    task: text-generation | chat-completion | translation | ...
    model: model-name-or-path

    # 输入（根据任务而异）
    text: ${input.text as text}
    messages: [ ... ]
    image: ${input.image as image}

    # 模型配置
    device: cuda | cpu | mps
    dtype: float32 | float16 | bfloat16 | int8 | int4
    batch_size: 1
    streaming: false

    # 参数
    params:
      max_output_length: 100
      temperature: 0.7
      top_p: 0.9
      do_sample: true

    # LoRA 适配器
    peft_adapters:
      - type: lora
        name: adapter-name
        model: path/to/adapter
        weight: 1.0
```

**HTTP 客户端**：
```yaml
components:
  - id: http-client-id
    type: http-client

    # 端点
    base_url: https://api.example.com   # 或
    endpoint: https://api.example.com/v1/resource

    # HTTP 配置
    method: GET | POST | PUT | DELETE | PATCH
    path: /resource
    headers: { ... }
    params: { ... }
    body: { ... }

    # 流式传输
    stream_format: json | text

    # 高级配置
    timeout: 30
    max_retries: 3
    retry_delay: 1

    # 多个操作
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

    # 服务器启动命令
    start:
      - vllm
      - serve
      - model-name
      - --port
      - "8000"

    # 服务器配置
    port: 8000
    healthcheck:
      path: /health
      interval: 5s
      timeout: 10s
      retries: 3

    # HTTP 客户端配置（服务器启动后）
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
    command: echo
    args:
      - ${input.message}
```

### 17.1.4 工作流架构

**基本结构**：
```yaml
workflows:
  - id: workflow-id
    title: Workflow Title
    description: Workflow description

    # 单个组件
    component: component-id
    input: ${input}
    output: ${output}

    # 或多个作业
    jobs:
      - id: job-id
        component: component-id
        action: action-id        # 可选：用于多操作组件
        input: { ... }
        output: { ... }
        depends_on: [ job-id ]   # 可选：依赖关系
        condition: ${expression} # 可选：条件执行
```

**作业类型**：
```yaml
# 1. 操作作业（默认 - 执行组件）
- id: job1
  type: action           # 可以省略（默认）
  component: component-id
  action: action-id      # 可选：用于多操作组件
  input: ${input}
  output: ${output}

# 2. If 作业（条件分支）
- id: job2
  type: if
  operator: eq
  input: ${input.status}
  value: "active"
  if_true: job-success
  if_false: job-fail

# 3. 延迟作业（等待）
- id: job3
  type: delay
  duration: 5s           # 等待 5 秒
```

### 17.1.5 监听器架构

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

### 17.1.6 网关架构

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

### 17.1.7 日志记录器架构

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

### 17.1.8 运行时架构

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

**上一章**：[15. 实用示例](./15-practical-examples.md)
