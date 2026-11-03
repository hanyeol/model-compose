# 16. 部署

本章说明如何在本地环境中运行 model-compose 应用程序或将其部署为 Docker 容器。

---

## 16.1 本地执行

### 16.1.1 基本执行

model-compose 默认使用原生运行时直接在本地环境中运行。

**启动控制器：**

```bash
model-compose up
```

默认行为：
- 从当前目录加载 `model-compose.yml`
- 使用原生运行时启动服务
- 在前台模式运行（日志输出）
- 使用 Ctrl+C 退出

**后台执行：**

```bash
model-compose up -d
```

后台模式下：
- 服务在单独的进程中运行
- 使用 `model-compose down` 停止

**停止控制器：**

```bash
model-compose down
```

停止进程：
1. 创建 `.stop` 文件
2. 控制器检测文件（每 1 秒轮询一次）
3. 优雅关闭服务
4. 资源清理

### 16.1.2 环境变量管理

**使用 `.env` 文件：**

```bash
# 创建 .env 文件
cat > .env <<EOF
OPENAI_API_KEY=sk-proj-...
MODEL_CACHE_DIR=/models
LOG_LEVEL=info
EOF

# 自动加载 .env 文件
model-compose up
```

**自定义 `.env` 文件：**

```bash
model-compose up --env-file .env.production
```

**单个环境变量覆盖：**

```bash
model-compose up -e OPENAI_API_KEY=sk-proj-... -e LOG_LEVEL=debug
```

环境变量优先级：
1. 通过 `--env` / `-e` 标志传递的值（最高优先级）
2. 使用 `--env-file` 指定的文件
3. 默认 `.env` 文件
4. 系统环境变量

### 16.1.3 指定配置文件

**使用自定义配置文件：**

```bash
model-compose up -f custom-compose.yml
```

**合并多个配置文件：**

```bash
model-compose up -f base.yml -f override.yml
```

### 16.1.4 独立运行工作流

仅运行工作流而不启动控制器：

```bash
model-compose run my-workflow --input '{"text": "Hello"}'
```

功能：
- 不启动控制器
- 执行工作流一次后退出
- 适用于 CI/CD 管道或批处理作业

**从 JSON 文件传递输入：**

```bash
model-compose run my-workflow --input @input.json
```

### 16.1.5 调试选项

**详细日志输出：**

在配置文件中指定日志级别：

```yaml
controller:
  adapter:
    type: http-server
    port: 8080

logger:
  - type: console
    level: debug        # debug, info, warning, error, critical
```

---

## 16.2 Docker 运行时

### 16.2.1 基本 Docker 配置

**简单 Docker 运行时配置：**

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  runtime: docker                 # 字符串格式
```

此配置扩展为：

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  runtime:
    type: docker
    # 使用默认镜像（自动构建）
```

**指定镜像：**

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  runtime:
    type: docker
    image: my-registry/model-compose:latest
    container_name: my-controller
```

执行流程：
1. 尝试从注册表拉取镜像
2. 如果拉取失败，则回退到本地构建
3. 创建并启动容器
4. 流式传输日志（前台）或分离（后台）

**端口映射：**

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  runtime:
    type: docker
    ports:
      - "5000:8080"                # host:container
      - 8081                       # 相同端口（8081:8081）
```

端口格式：
- 字符串：`"host_port:container_port"`
- 整数：`port`（主机和容器相同）
- 对象：高级配置（见下文）

### 16.2.2 高级 Docker 选项

**镜像构建配置：**

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  runtime:
    type: docker
    build:
      context: .                   # 构建上下文路径
      dockerfile: Dockerfile       # 自定义 Dockerfile
      args:                        # 构建参数
        PYTHON_VERSION: "3.11"
        MODEL_NAME: "llama-2"
      target: production           # 多阶段构建目标
      cache_from:                  # 缓存镜像
        - my-registry/cache:latest
      labels:
        app: model-compose
        version: "1.0"
      network: host                # 构建期间的网络模式
      pull: true                   # 始终拉取基础镜像
```

**高级端口配置：**

```yaml
controller:
  runtime:
    type: docker
    ports:
      - target: 8080               # 容器端口
        published: 5000            # 主机端口
        protocol: tcp              # tcp 或 udp
        mode: host                 # host 或 ingress
```

**网络配置：**

```yaml
controller:
  runtime:
    type: docker
    networks:
      - my-network                 # 连接到现有网络
      - bridge                     # Docker 默认 bridge
```

**容器运行选项：**

```yaml
controller:
  runtime:
    type: docker
    hostname: model-compose-host   # 容器主机名
    command:                       # 覆盖 CMD
      - python
      - -m
      - mindor.cli.compose
      - up
      - --verbose
    entrypoint: /bin/bash          # 覆盖 ENTRYPOINT
    working_dir: /app              # 工作目录
    user: "1000:1000"              # 用户:组 ID
```

**资源限制：**

```yaml
controller:
  runtime:
    type: docker
    mem_limit: 2g                  # 内存限制（512m、2g 等）
    memswap_limit: 4g              # 内存 + 交换限制
    cpus: "2.0"                    # CPU 分配（0.5、2.0 等）
    cpu_shares: 1024               # 相对 CPU 权重
```

**重启策略：**

```yaml
controller:
  runtime:
    type: docker
    restart: always                # no, always, on-failure, unless-stopped
```

重启策略说明：
- `no`：不重启（默认）
- `always`：始终重启
- `on-failure`：仅在错误退出时重启
- `unless-stopped`：重启直到手动停止

**健康检查：**

```yaml
controller:
  runtime:
    type: docker
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://localhost:8080/health" ]
      interval: 30s                # 检查间隔
      timeout: 10s                 # 超时
      max_retry_count: 3           # 最大重试次数
      start_period: 40s            # 宽限期
```

或简单地：

```yaml
controller:
  runtime:
    type: docker
    healthcheck:
      test: "curl -f http://localhost:8080/health || exit 1"
```

**安全选项：**

```yaml
controller:
  runtime:
    type: docker
    privileged: false              # 特权模式（不推荐）
    security_opt:
      - apparmor=unconfined
      - seccomp=unconfined
```

**日志配置：**

```yaml
controller:
  runtime:
    type: docker
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

**标签：**

```yaml
controller:
  runtime:
    type: docker
    labels:
      environment: production
      team: ml-ops
      version: "1.0.0"
```

### 16.2.3 卷和环境变量

**卷挂载 - 简单格式：**

```yaml
controller:
  runtime:
    type: docker
    volumes:
      - ./models:/models           # 绑定挂载
      - ./cache:/cache:ro          # 只读
      - model-data:/data           # 命名卷
```

**卷挂载 - 详细格式：**

```yaml
controller:
  runtime:
    type: docker
    volumes:
      # 绑定挂载
      - type: bind
        source: ./models           # 主机路径
        target: /models            # 容器路径
        read_only: false
        bind:
          propagation: rprivate

      # 命名卷
      - type: volume
        source: model-data         # 卷名称
        target: /data
        volume:
          nocopy: false

      # tmpfs（临时内存）
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 1073741824         # 1GB（字节）
          mode: 1777
```

卷类型说明：
- `bind`：将主机目录/文件挂载到容器
- `volume`：Docker 管理的命名卷
- `tmpfs`：基于内存的临时文件系统（容器停止时删除）

**环境变量配置：**

```yaml
controller:
  runtime:
    type: docker
    environment:
      OPENAI_API_KEY: ${env.OPENAI_API_KEY}   # 传递主机环境变量
      MODEL_CACHE_DIR: /models
      LOG_LEVEL: info
      WORKERS: 4
```

**环境变量文件：**

```yaml
controller:
  runtime:
    type: docker
    env_file:
      - .env                       # 单个文件
      - .env.production            # 多个文件
```

---

## 16.3 Docker 容器构建和部署

### 16.3.1 自动构建流程

model-compose 在使用 Docker 运行时时会自动构建镜像。

**构建上下文准备：**

运行 `model-compose up` 时：
1. 创建 `.docker/` 目录
2. 复制源代码（mindor 包）
3. 复制/创建 `requirements.txt`
4. 创建 `model-compose.yml`（转换为原生运行时）
5. 复制 webui 目录（如果已配置）
6. 复制 Dockerfile 或使用默认 Dockerfile

**默认 Dockerfile：**

```dockerfile
FROM ubuntu:22.04

WORKDIR /app

# 安装 Python 3.11
RUN apt update && apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 符号链接
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# 安装基础依赖
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir \
    click pyyaml pydantic python-dotenv \
    aiohttp requests fastapi uvicorn \
    'mcp>=1.10.1' pyngrok ulid gradio Pillow

# 安装项目依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用程序文件
COPY src .
COPY webui ./webui
COPY model-compose.yml .

# 默认命令
CMD [ "python", "-m", "mindor.cli.compose", "up" ]
```

### 16.3.2 使用自定义 Dockerfile

要使用特定于项目的 Docker 镜像，您可以创建自定义 Dockerfile。

**项目目录结构：**

```
my-project/
├── model-compose.yml    # 工作流配置
├── Dockerfile           # 自定义 Docker 镜像
├── requirements.txt     # Python 依赖（可选）
└── .env                 # 环境变量（可选）
```

**注意**：要使用自定义 Dockerfile，您必须在 `build` 部分中明确指定它。Dockerfile 可以放在项目根目录或任何所需位置。

**Dockerfile 示例：**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt update && apt install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 model-compose
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预下载模型
RUN python -c "from transformers import AutoModel; AutoModel.from_pretrained('bert-base-uncased')"

# 复制应用程序
COPY . .

CMD [ "model-compose", "up" ]
```

**在配置中指定自定义 Dockerfile：**

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  runtime:
    type: docker
    build:
      context: .
      dockerfile: Dockerfile       # 自定义 Dockerfile
```

### 16.3.3 多阶段构建

**分离开发/生产：**

```dockerfile
# 阶段 1：构建环境
FROM python:3.11 AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY src ./src

# 阶段 2：运行时环境
FROM python:3.11-slim AS runtime

WORKDIR /app

# 从构建器复制包
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app/src ./src

# 更新 PATH
ENV PATH=/root/.local/bin:$PATH

COPY model-compose.yml .

CMD [ "model-compose", "up" ]

# 阶段 3：开发环境
FROM runtime AS development

RUN pip install --no-cache-dir pytest black flake8

CMD [ "model-compose", "up", "--verbose" ]
```

**在配置中指定目标：**

```yaml
# 生产
controller:
  runtime:
    type: docker
    build:
      context: .
      target: runtime

---
# 开发
controller:
  runtime:
    type: docker
    build:
      context: .
      target: development
```

### 16.3.4 使用镜像注册表

**构建并推送镜像：**

```bash
# 本地构建
docker build -t my-registry.com/model-compose:1.0 .

# 推送到注册表
docker push my-registry.com/model-compose:1.0
```

**在配置中使用注册表镜像：**

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  runtime:
    type: docker
    image: my-registry.com/model-compose:1.0
    container_name: model-compose-prod
```

执行时：
1. 从注册表拉取镜像
2. 创建并启动容器
3. 跳过本地构建过程

### 16.3.5 私有注册表认证

**Docker 登录：**

```bash
docker login my-registry.com
```

或使用环境变量：

```bash
export DOCKER_USERNAME=myuser
export DOCKER_PASSWORD=mypass
docker login -u $DOCKER_USERNAME -p $DOCKER_PASSWORD my-registry.com
```

**认证凭据存储在 `~/.docker/config.json` 中。**

---

## 16.4 生产环境注意事项

### 16.4.1 并发控制

**控制器级并发：**

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  max_concurrent_count: 10         # 最多 10 个并发工作流
  threaded: false                  # 基于线程的执行（默认：false）
```

并发设置：
- `max_concurrent_count: 0`：无限制（默认，谨慎使用）
- `max_concurrent_count: N`：最多 N 个并发执行
- `threaded: true`：在单独的线程中运行每个工作流

**组件级并发：**

```yaml
components:
  - id: api-client
    type: http-client
    base_url: https://api.example.com
    max_concurrent_count: 5        # 此组件最多 5 个并发请求
```

### 16.4.2 资源限制

**内存限制：**

```yaml
controller:
  runtime:
    type: docker
    mem_limit: 4g                  # 最大 4GB 内存
    memswap_limit: 6g              # 内存 + 交换 6GB
```

内存单位：
- `b`：字节
- `k`：千字节
- `m`：兆字节
- `g`：千兆字节

**CPU 限制：**

```yaml
controller:
  runtime:
    type: docker
    cpus: "2.0"                    # 最多 2 个 CPU 核心
    cpu_shares: 1024               # 相对 CPU 权重
```

CPU 设置：
- `cpus`：绝对 CPU 限制（0.5 = 50%，2.0 = 200%）
- `cpu_shares`：相对权重（默认 1024）

### 16.4.3 重启策略

**自动重启配置：**

```yaml
controller:
  runtime:
    type: docker
    restart: unless-stopped        # 始终重启直到手动停止
```

生产建议：
- `always`：始终重启（包括系统重启）
- `unless-stopped`：重启直到手动停止
- `on-failure`：仅在错误时重启

### 16.4.4 健康检查

**HTTP 端点健康检查：**

model-compose 默认提供 `/health` 端点。

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  runtime:
    type: docker
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://localhost:8080/health" ]
      interval: 30s
      timeout: 10s
      max_retry_count: 3
      start_period: 40s
```

健康检查响应：

```json
{
  "status": "ok"
}
```

**自定义健康检查：**

```yaml
controller:
  runtime:
    type: docker
    healthcheck:
      test: [ "CMD-SHELL", "python -c 'import requests; requests.get(\"http://localhost:8080/health\")' || exit 1" ]
      interval: 20s
```

### 16.4.5 安全考虑

**在非特权模式下运行：**

```yaml
controller:
  runtime:
    type: docker
    privileged: false              # 始终建议使用 false
    user: "1000:1000"              # 非 root 用户
```

**密钥管理：**

通过环境变量传递敏感信息：

```yaml
controller:
  runtime:
    type: docker
    environment:
      OPENAI_API_KEY: ${env.OPENAI_API_KEY}     # 从主机注入
      DB_PASSWORD: ${env.DB_PASSWORD}
```

执行时：

```bash
export OPENAI_API_KEY=sk-proj-...
export DB_PASSWORD=secret
model-compose up
```

或使用 `.env` 文件（不要提交到仓库）：

```bash
# .env.production
OPENAI_API_KEY=sk-proj-...
DB_PASSWORD=secret
```

```bash
model-compose up --env-file .env.production
```

**网络隔离：**

```yaml
controller:
  runtime:
    type: docker
    networks:
      - isolated-network           # 使用隔离网络
```

### 16.4.6 数据持久化

**使用卷挂载保留数据：**

```yaml
controller:
  runtime:
    type: docker
    volumes:
      - ./data:/data               # 本地数据目录
      - model-cache:/cache         # 命名卷
      - ./logs:/app/logs           # 日志目录
```

创建命名卷：

```bash
docker volume create model-cache
```

检查卷：

```bash
docker volume ls
docker volume inspect model-cache
```

---

## 16.5 监控和日志

### 16.5.1 日志器配置

**控制台日志器：**

```yaml
logger:
  - type: console
    level: info                    # debug, info, warning, error, critical
```

日志级别：
- `debug`：所有日志（用于开发）
- `info`：一般信息（默认）
- `warning`：警告消息
- `error`：错误消息
- `critical`：严重错误

**文件日志器：**

```yaml
logger:
  - type: file
    path: ./logs/run.log           # 日志文件路径
    level: info
```

目录会自动创建。

**使用多个日志器：**

```yaml
logger:
  - type: console
    level: warning                 # 仅警告到控制台

  - type: file
    path: ./logs/all.log
    level: debug                   # 所有日志到文件

  - type: file
    path: ./logs/errors.log
    level: error                   # 仅错误日志
```

### 16.5.2 Docker 容器日志

**实时查看日志：**

```bash
# 前台模式下自动流式传输
model-compose up

# 后台执行后检查日志
docker logs -f <container-name>
```

**保存日志：**

```yaml
controller:
  runtime:
    type: docker
    container_name: model-compose-prod
    logging:
      driver: json-file
      options:
        max-size: "10m"            # 每个文件的最大大小
        max-file: "5"              # 最大文件数
```

日志位置：`/var/lib/docker/containers/<container-id>/<container-id>-json.log`

**日志驱动选项：**

```yaml
controller:
  runtime:
    type: docker
    logging:
      driver: syslog               # json-file, syslog, journald, gelf, fluentd 等
      options:
        syslog-address: "tcp://192.168.0.42:514"
        tag: "model-compose"
```

### 16.5.3 工作流执行日志

**使用 logger 组件记录日志：**

```yaml
components:
  - id: logger
    type: logger
    level: info

  - id: api-client
    type: http-client
    base_url: https://api.example.com

workflows:
  - id: process-with-logging
    jobs:
      - id: log-start
        component: logger
        input:
          message: "Workflow started: ${context.run_id}"

      - id: api-call
        component: api-client
        input: ${input}

      - id: log-result
        component: logger
        input:
          message: "Result: ${output}"

      - id: log-end
        component: logger
        input:
          message: "Workflow completed"
```

### 16.5.4 指标收集

**跟踪执行时间：**

```yaml
workflows:
  - id: timed-workflow
    jobs:
      - id: start-time
        component: shell
        command: echo $(date +%s%3N)       # 毫秒时间戳
        output: ${stdout.trim()}

      - id: process
        component: api-client
        input: ${input}

      - id: end-time
        component: shell
        command: echo $(date +%s%3N)
        output: ${stdout.trim()}

      - id: log-duration
        component: logger
        input:
          message: "Execution time: ${output.end-time - output.start-time}ms"
```

**性能指标日志：**

```yaml
workflows:
  - id: metrics-workflow
    jobs:
      - id: api-call
        component: api-client
        input: ${input}

      - id: log-metrics
        component: logger
        input:
          run_id: ${context.run_id}
          status: ${output.status}
          response_time: ${output.response_time_ms}
          tokens_used: ${output.usage.total_tokens}
```

### 16.5.5 外部监控系统

**Prometheus 集成示例：**

```yaml
components:
  - id: prometheus-push
    type: http-client
    base_url: http://prometheus-pushgateway:9091
    path: /metrics/job/model-compose
    method: POST
    headers:
      Content-Type: text/plain

workflows:
  - id: monitored-workflow
    jobs:
      - id: process
        component: my-component
        input: ${input}

      - id: push-metrics
        component: prometheus-push
        input:
          body: |
            workflow_execution_duration_seconds ${output.duration}
            workflow_execution_total 1
```

**日志聚合系统（ELK Stack）：**

```yaml
controller:
  runtime:
    type: docker
    logging:
      driver: gelf                 # Graylog Extended Log Format
      options:
        gelf-address: "udp://logstash:12201"
        tag: "model-compose"
        labels: "environment,service"
    labels:
      environment: production
      service: model-compose
```

### 16.5.6 追踪器配置

追踪器将工作流和作业执行的结构化追踪数据发送到 Langfuse 等外部可观测性工具。

**基本 Langfuse 追踪器：**

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
```

将工作流级别和作业级别的追踪数据发送到 Langfuse Cloud。

**自托管 Langfuse：**

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  base_url: http://localhost:3000
```

**捕获设置：**

```yaml
tracer:
  driver: langfuse
  public_key: ${env.LANGFUSE_PUBLIC_KEY}
  secret_key: ${env.LANGFUSE_SECRET_KEY}
  capture:
    input: true
    output: true
    redact_keys:                     # 脱敏敏感键
      - Authorization
      - api_key
    max_payload_bytes: 1048576       # 1MB 限制
```

捕获设置：
- `input`：在追踪中包含输入数据（默认：`true`）
- `output`：在追踪中包含输出数据（默认：`true`）
- `redact_keys`：替换为 `[redacted]` 的键列表（不区分大小写，递归应用）
- `max_payload_bytes`：最大负载大小，超过时替换为 `[truncated]`

**会话分组：**

```bash
model-compose run chat --session-id my-session -i '{"prompt": "hello"}'
```

具有相同 `session_id` 的追踪在 Langfuse UI 中分组显示。

**关键行为：**
- 追踪器事件是非阻塞的（排队后异步发送）
- 追踪器故障不会影响工作流执行
- `langfuse>=4.0` 在首次使用时自动安装

---

## 16.6 Vast.ai 运行时

在远程 [Vast.ai](https://vast.ai/) GPU 实例上运行组件。控制器仍在本地
主机上，只有繁重的计算（模型权重、推理、GPU 显存）在实例上运行。请求之间
的计费通过 `idle_timeout` 自动暂停。Vast.ai 市场在相同 GPU 条件下通常比
RunPod 便宜约 30–50%，并覆盖 RunPod 不提供的消费级显卡（4090/5090）。

### 16.6.1 工作原理

当带有 `runtime.type: vastai` 的组件被 `model-compose up` 启动时，
model-compose 会：

1. 销毁来自之前会话的、标签为 `mindor-<component_id>` 的孤立实例以回收
   资源。网络卷会保留，所以模型权重得以保存。
2. 通过官方 `vastai` SDK 在 Vast.ai 市场中搜索与所配置的 GPU、主机层级
   和价格上限匹配的最便宜报价。当设置了 `network_volume_id` 时，搜索
   会被固定到该卷所在的主机 —— Vast 卷是机器本地的。
3. 使用配置的镜像租用所选报价，并在 `volume_mount_path` 链接网络卷（如有）。
4. 实例启动 CUDA 基础镜像，apt 安装 `ffmpeg`，将当前 `model-compose`
   从 GitHub 安装到卷上的缓存 venv 中，并在配置的端口上启动一个
   WebSocket IPC 服务器。Vast 通过主机端口映射向外暴露。
5. model-compose 使用按会话生成的 bearer token 连接到
   `ws://<public_ip>:<mapped_port>`。此时组件即可使用，请求通过 IPC
   代理流向嵌入式 worker。

最后一个在途请求完成且 `idle_timeout` 过去后，model-compose 会调用
`stop_instance` 以暂停 GPU 计费。下一个请求会在数秒内恢复同一个实例，
网络卷仍然链接 —— 模型权重不会重新下载。

### 16.6.2 基本配置

**Vast.ai 组件的最小可用配置：**

```yaml
component:
  type: model
  task: speech-to-text
  driver: huggingface
  architecture: whisper
  model: openai/whisper-large-v3-turbo
  runtime:
    type: vastai
    api_key: ${env.VASTAI_API_KEY}
    gpu_type: RTX 4090              # Vast.ai GPU 名称；允许空格
    network_volume_id: 58912451     # 通过 `vastai create volume` 预先创建
```

必填字段：

- `api_key` —— Vast.ai API 密钥，通常从环境变量读取。
- `gpu_type` —— Vast GPU 目录名称（如 `RTX 4090`、`H100 SXM`、
  `H100 PCIE`、`A100 80GB`）。允许空格；客户端会按市场查询语法编码。

可选但推荐：

- `network_volume_id` —— 模型权重的持久化存储。不设置则每个新实例都会
  将模型重新下载到临时磁盘。Vast 网络卷是**机器本地**的（与 RunPod 的
  数据中心范围卷不同），因此设置此字段还会把市场搜索限定到该主机。

### 16.6.3 完整配置

```yaml
component:
  type: model
  task: text-to-video
  driver: custom
  family: minimax-h3
  model: MiniMaxAI/MiniMax-H3
  runtime:
    type: vastai
    api_key: ${env.VASTAI_API_KEY}

    # 实例规格
    gpu_type: H100 SXM
    gpu_count: 1
    cloud_type: VERIFIED              # DATACENTER | VERIFIED | UNVERIFIED | ALL
    max_price: 3.00                   # 每小时美元上限；超过的报价会被跳过

    # 镜像（默认：pytorch/pytorch:*-cuda*-cudnn*-runtime）
    image: pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

    # 存储
    network_volume_id: 58912451
    volume_mount_path: /workspace     # 默认；pip 缓存也在此处
    container_disk_gb: 20

    # 网络
    worker_port: 8000                 # 通过 Vast 的主机端口映射对外暴露

    # 注入到实例容器的额外环境变量
    environment:
      HF_TOKEN: ${env.HF_TOKEN}

    # 生命周期
    idle_timeout: 15m                 # 最后一次请求后 stop_instance 的延迟
    start_timeout: 30m                # 实例启动 + WS 接入的最大时间
    stop_timeout: 2m                  # stop_instance 的宽限时间
```

### 16.6.4 字段参考

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `api_key` | string | — | **必填。** Vast.ai API 密钥。 |
| `gpu_type` | string | — | **必填。** Vast GPU 目录名称。 |
| `gpu_count` | int | `1` | 实例上附加的 GPU 数量。 |
| `cloud_type` | enum | `VERIFIED` | `DATACENTER`（严格的商业数据中心）\| `VERIFIED`（Vast 验证主机，DC 或非 DC）\| `UNVERIFIED`（仅对等主机）\| `ALL`。 |
| `max_price` | float | `null` | 每小时价格上限（美元）；超过的报价会被过滤。 |
| `image` | string | `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime` | 实例容器镜像。 |
| `network_volume_id` | int | `null` | 要链接的 Vast.ai 网络卷 ID。仅为整数 —— Vast 将卷显示为 `V.<整数>`；只传整数部分。 |
| `volume_mount_path` | string | `/workspace` | 容器内网络卷的挂载路径。 |
| `container_disk_gb` | int | `20` | 临时根磁盘大小。 |
| `worker_port` | int | `8000` | Vast 将主机端口映射到公网 IP 的容器端口。 |
| `environment` | map | `null` | 注入到实例容器的额外环境变量。 |
| `idle_timeout` | duration | `15m` | 最后一次请求后实例停止的延迟。`0s` 禁用自动停止。 |
| `start_timeout` | duration | `30m` | 实例启动 + 镜像拉取 + WS 接入的最大时间。 |
| `stop_timeout` | duration | `2m` | 优雅停止的截止时间。 |

### 16.6.5 生命周期与计费保障

Vast.ai 实例遵循与 `docker-compose up / create / start / stop / down`
对齐的标准 `setup / start / stop / teardown` 生命周期：

- **`setup`（在 `model-compose up` 时）。** 回收之前会话的孤立实例，
  创建新实例并等待它进入 `running` 状态，持久化
  `(instance_id, auth_token)` 以便下个会话可以 claim 而无需再付创建成本。
- **`start`。** 将 `stopped` 实例恢复到 `running`（数秒）并连接 WS
  传输。网络卷仍然链接，所以模型权重已经是热的。
- **`stop`。** 分离传输并调用 `stop_instance`。实例在账号中仍被预留，
  下一次 `start` 又是便宜的恢复。
- **`teardown`（在 `model-compose down` 时）。** `destroy_instance` ——
  此调用返回后实例就不存在了。网络卷**不会被删除**，请从控制台或用
  `vastai delete volume <id>` 自行管理。

Vast 实例按秒计费，还有额外的保障以防止费用失控：

- **上传前的接入探测。** 每次 `start` 时，model-compose 先用较短超时
  探测 WS 端口。如果上一会话的 worker 还在服务，就跳过完整的上传 + pip
  安装路径，直接接入。
- **接入失败即停止。** 若在引导启动后 WS 握手失败（镜像拉取过慢超出
  `start_timeout`、引导崩溃等），实例会被 `stop` 而不是 destroy —— 瞬时
  失败很常见，恢复的实例通常可以继续。销毁只留给 `teardown`。
- **恢复失败的回退。** `start_instance` 永久失败时（例如宿主在实例停止
  期间收回了 GPU），死实例会被 destroy 并重新预配一个。网络卷上的权重
  会被复用。
- **共享秘密认证。** 实例一旦 `running`，Vast 暴露的主机端口就能从公网
  访问。每个会话都在实例环境中注入新的随机 bearer token；没有正确
  `Authorization: Bearer <token>` 头的连接会在 WS 升级阶段被拒绝。

### 16.6.6 网络卷

Vast 网络卷相比实例的临时磁盘有两个好处：

1. **模型持久化。** HuggingFace 缓存下载的权重在 `stop_instance` 和
   `destroy_instance` 之后仍然保留，所以重新启动是数秒而不是数分钟。
2. **pip 缓存。** 引导脚本把 wheel 缓存到 `/workspace/.pip-cache`，
   因此恢复的实例上重新安装 model-compose 会跳过缓慢的依赖构建。

Vast 卷**今天还不能从控制面板创建** —— Vast 存储页只列出已有的卷，没有
"Create Network Volume" 表单。请使用 CLI：

```bash
# 1) 搜索你想要绑定的主机上的卷报价
vastai search volumes "verified=true disk_space>=20" -o storage_cost

# 2) 在所选主机上创建 20 GB 卷（使用步骤 1 的报价 ID）
vastai create volume <OFFER_ID> -s 20 -n mindor_whisper_vol

# 3) 确认卷的整数 ID（Vast 显示为 V.<整数>）
vastai show volumes

# 4) 在 compose 配置中引用整数部分
```

```yaml
runtime:
  type: vastai
  # ...
  network_volume_id: 58912451
  volume_mount_path: /workspace
```

注意：

- **卷名必须是字母数字或下划线**（最长 64 个字符）。连字符会被拒绝。
- Vast 卷是**机器本地**的 —— 任何链接该卷的实例都会被固定到那台机器。
  设置 `network_volume_id` 时运行时会自动在报价搜索中加入
  `machine_id=<宿主>` 过滤。
- 卷在实例的停止/恢复/销毁后仍然保留。完成后用
  `vastai delete volume <id>` 显式删除。

### 16.6.7 何时 Vast.ai 不合适

Vast.ai 用价格换取运维上的复杂度。以下情况请选择 RunPod 或本地运行时：

- 需要每个实例的内置 HTTPS 代理 —— Vast 通过原始主机端口暴露容器
  （目前为 `ws://`，由认证 token 保护）。RunPod 的
  `*.proxy.runpod.net` 开箱即用是 `wss://`。
- 无法创建 Vast 网络卷（控制面板流程尚未上线），而模型权重过大导致
  销毁后重新下载不可接受 —— RunPod 的卷通过控制面板管理，并且是
  数据中心范围的。
- 需要严格的 SLA 保证 —— Vast 的可靠性因主机而异；`VERIFIED` 层级会
  将其收窄到 Vast 验证的主机，但不同机器仍有差异。

---

## 16.7 部署最佳实践

### 特定于环境的部署策略

**本地开发环境：**
- 使用原生运行时进行快速迭代
- 使用 `.env` 文件管理环境变量
- 使用控制台日志器（`level: debug`）

**测试/预发布环境：**
- 使用 Docker 运行时模拟生产
- 使用文件日志器进行日志保留
- 验证资源限制和健康检查

**生产环境：**
- 需要 Docker 运行时
- `restart: unless-stopped` 用于自动恢复
- 应用资源限制（`mem_limit`、`cpus`）
- 配置健康检查和监控
- 使用卷确保数据持久化
- 通过环境变量管理密钥
- 与日志聚合系统集成
- 配置并发控制

### 性能优化

1. **并发调优**：根据工作负载配置 `max_concurrent_count`
2. **资源分配**：监控 CPU/内存使用情况并设置适当的限制
3. **日志级别**：在生产中使用 `info` 或更高级别（排除调试日志）
4. **日志轮换**：使用 Docker 日志选项控制磁盘使用
5. **卷挂载**：对性能关键数据考虑使用 tmpfs

### 安全加固

1. **最小权限原则**：以非 root 用户运行容器
2. **密钥分离**：使用环境变量，永远不要将密钥提交到仓库
3. **网络隔离**：在需要时使用专用网络
4. **定期更新**：定期更新基础镜像和依赖
5. **安全扫描**：在镜像构建期间使用漏洞扫描工具

### 可靠性改进

1. **健康检查**：始终配置健康检查
2. **重启策略**：在生产中使用 `always` 或 `unless-stopped`
3. **优雅关闭**：通过信号处理确保正确终止
4. **备份**：定期备份关键数据
5. **监控**：设置实时指标和警报

---

## 下一步

尝试一下：
- 将控制器部署到生产环境
- 使用 Docker Compose 进行多容器配置
- Kubernetes 集群部署
- CI/CD 管道集成
- 构建监控仪表板

---

**下一章**：[第17章：实际示例](./17-practical-examples.md)
