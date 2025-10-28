# 2. 核心概念

本章介绍 model-compose 的核心概念和术语。

---

## 2.1 Controller(控制器)

Controller 是 model-compose 的核心组件,管理整个系统的运行。

### 支持的 Controller 类型

**1. HTTP Server**
- 提供 REST API 接口
- 支持 Gradio/Static Web UI
- 适用于标准 Web 应用

**2. MCP Server**
- 实现 Model Context Protocol
- 与 Claude Desktop 等 MCP 客户端集成
- 通过标准协议暴露工具

### Controller 配置示例

```yaml
controller:
  type: http-server    # 或 mcp-server
  port: 8080
  base_path: /api
```

---

## 2.2 Component(组件)

Component 是可重用的功能单元,代表特定的服务或操作。

### Component 类型

**1. 本地 AI 模型 (`model`)**
- 加载和运行 HuggingFace 模型
- 支持各种任务:文本生成、图像分类等
- GPU/CPU 执行

**2. HTTP 客户端 (`http-client`)**
- 调用外部 API
- 支持 OpenAI、Anthropic 等
- 可配置请求/响应处理

**3. HTTP 服务器 (`http-server`)**
- 管理外部服务器进程
- 适用于 vLLM、Ollama 等
- 健康检查和生命周期管理

**4. MCP 客户端 (`mcp-client`)**
- 连接到 MCP 服务器
- 访问外部工具和资源

**5. MCP 服务器 (`mcp-server`)**
- 将组件暴露为 MCP 工具
- 供 MCP 客户端使用

**6. Vector Store (`vector-store`)**
- 向量数据库集成
- 支持 ChromaDB、Milvus、Qdrant、FAISS
- 嵌入存储和搜索

**7. 数据集 (`datasets`)**
- 加载 HuggingFace 数据集
- 本地数据集支持
- 数据采样和转换

**8. 文本分割器 (`text-splitter`)**
- 将长文本分割成块
- 用于 RAG 系统
- 可配置块大小和重叠

**9. 图像处理器 (`image-processor`)**
- 图像转换和处理
- 格式转换、调整大小、滤镜

**10. Shell 命令 (`shell`)**
- 执行系统命令
- 脚本集成
- 捕获 stdout/stderr

**11. Workflow (`workflow`)**
- 调用其他工作流
- 组合和重用
- 模块化设计

### Component 配置示例

```yaml
components:
  - id: my-model
    type: model
    task: text-generation
    model: gpt2

  - id: openai-client
    type: http-client
    base_url: https://api.openai.com/v1
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
```

---

## 2.3 Workflow(工作流)

Workflow 定义了一系列按顺序执行的 job。

### Workflow 结构

```yaml
workflows:
  - id: my-workflow
    title: My Workflow
    description: Description of what this workflow does

    # 单个组件(简单工作流)
    component: component-id
    input: ${input}
    output: ${output}

    # 或多个 job(复杂工作流)
    jobs:
      - id: job1
        component: component-id
        input: ${input}
        output: ${output}

      - id: job2
        component: another-component
        input: ${jobs.job1.output}
        output: ${output}
        depends_on: [job1]
```

### Job 类型

**1. Action Job(操作作业 - 默认)**
- 执行组件
- 处理输入/输出
- 最常见的类型

```yaml
- id: process-data
  component: my-component
  input: ${input}
  output: ${output}
```

**2. If Job(条件作业)**
- 条件分支
- 基于条件路由到不同的 job

```yaml
- id: check-status
  type: if
  operator: eq
  input: ${input.status}
  value: "active"
  if_true: job-success
  if_false: job-fail
```

**3. Delay Job(延迟作业)**
- 暂停执行
- 速率限制或等待

```yaml
- id: wait
  type: delay
  duration: 5s
```

---

## 2.4 Listener(监听器)

Listener 接收来自外部系统的 HTTP 请求。

### Listener 类型

**1. HTTP Callback**
- 接收异步回调
- 将结果传递给等待的工作流
- 用于异步 API 集成

```yaml
listener:
  type: http-callback
  port: 8090
  path: /callback
  identify_by: ${body.task_id}
  result: ${body.result}
```

**2. HTTP Trigger**
- 触发新的工作流
- 处理 webhook
- 提供 REST API 端点

```yaml
listener:
  type: http-trigger
  port: 8091
  path: /trigger
  workflow: my-workflow
  input: ${body}
```

---

## 2.5 Gateway(网关)

Gateway 通过公共 URL 暴露本地服务。

### Gateway 类型

**1. ngrok**
```yaml
gateway:
  type: ngrok
  port: 8080
```

**2. Cloudflare Tunnel**
```yaml
gateway:
  type: cloudflare
  port: 8080
```

**3. SSH Tunnel**
```yaml
gateway:
  type: ssh-tunnel
  port: 8080
  connection:
    host: remote-server.com
    auth:
      type: keyfile
      keyfile: ~/.ssh/id_rsa
```

---

## 2.6 Variable Binding(变量绑定)

Variable binding 使用 `${...}` 语法在配置中引用和转换数据。

### 基本语法

```yaml
${key.path}                          # 简单引用
${key.path as type}                  # 类型转换
${key.path | default}                # 默认值
${key.path as type | default}        # 类型转换 + 默认值
```

### 常见示例

```yaml
# 输入引用
${input.message}
${input.user.email}
${input.data[0].id}

# 环境变量
${env.OPENAI_API_KEY}

# Job 输出
${jobs.job-id.output}
${jobs.job-id.output.field}

# 类型转换
${input.text as text}
${input.count as integer}
${input.image as image/jpg}

# 默认值
${input.temperature | 0.7}
${env.API_KEY | "default-key"}
```

---

## 2.7 Runtime(运行时)

Runtime 决定了代码的执行位置。

### Runtime 类型

**1. Native(原生)**
- 直接在本地环境运行
- 快速迭代
- 默认模式

```yaml
controller:
  type: http-server
  # runtime: native (默认,可省略)
```

**2. Docker**
- 在 Docker 容器中运行
- 隔离和可重现性
- 生产部署

```yaml
controller:
  type: http-server
  runtime: docker
  # 或
  runtime:
    type: docker
    image: python:3.11
    volumes:
      - ./models:/models
```

---

## 下一步

现在您已经了解了核心概念,让我们学习如何使用 CLI。

---

**下一章**: [3. CLI 使用](./03-cli-usage.md)
