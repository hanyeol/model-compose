<div align="center">

![model-compose - Compose Any AI, Deploy Anywhere](docs/images/main-banner.png)

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![PyPI version](https://img.shields.io/pypi/v/model-compose.svg)](https://pypi.org/project/model-compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/model-compose)](https://pepy.tech/project/model-compose)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

[English](README.md) | [한국어](README.ko.md)

</div>

---

# model-compose

**组合 AI 系统，部署到任何地方。**

使用 YAML 定义工作流、智能体、模型和综合 AI 服务。在本地运行，在生产环境中扩展，无需重写技术栈即可部署到任何环境。

受 `docker-compose` 启发 — 一个 YAML 文件定义整个 AI 系统。

<div align="center">

[用户指南](docs/user-guide/zh-cn/README.md) · [快速开始](#快速开始) · [示例](examples/README.md) · [贡献](#贡献)

</div>

---

## Highlights

- **Any model, anywhere** — 通过 HuggingFace、vLLM、llama.cpp 在本地运行模型，或连接 OpenAI、Anthropic、Google 等
- **20+ components ready** — 模型、智能体、HTTP 客户端、向量/图存储、Shell 命令等
- **Built-in data stores** — Chroma、FAISS、Milvus、Qdrant、Neo4j、ArangoDB、Redis
- **Deploy as container** — Docker、原生容器或独立进程，一套配置搞定
- **Serve any protocol** — HTTP REST、WebSocket 或 MCP，一行即可切换
- **Distributed execution** — 通过 Redis 队列分发扩展到多台机器
- **Instant Web UI** — 2 行 YAML 添加 Gradio 驱动的界面

---

## 安装

```
pip install model-compose
```

或从源代码安装：

```
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

> 要求：Python 3.10 或更高版本

---

## 快速开始

在 `model-compose.yml` 中定义 AI 运行时：

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  webui:
    port: 8081

workflows:
  - id: chat
    default: true
    jobs:
      - component: chatgpt

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.prompt}
```

创建 `.env` 文件：

```bash
OPENAI_API_KEY=your-key
```

运行：

```bash
model-compose up
```

AI 运行时在 `http://localhost:8080` 提供服务，Web UI 在 `http://localhost:8081`。

> 更多工作流请访问[示例](examples/README.md)，详细内容请阅读[用户指南](docs/user-guide/zh-cn/README.md)。

---

## Core Capabilities

### 声明式 YAML 配置
在单个 YAML 文件中定义整个 AI 系统。工作流、智能体、模型、API、向量/图存储和运行时 — 无需自定义代码，一起组合和部署。

```yaml
controller:
  adapter:
    type: http-server
    port: 8080

workflows:
  - id: chat
    default: true
    jobs:
      - component: chatgpt

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
```

### 灵活的组件系统
20+ 种可复用组件类型。自由组合 HTTP 客户端、本地模型、向量存储、Shell 命令和工作流。定义一次，随处使用。

```yaml
components:
  - id: chatgpt
    type: http-client

  - id: local-llm
    type: model

  - id: assistant
    type: agent

  - id: knowledge
    type: vector-store

  - id: cache
    type: key-value-store

  - id: runner
    type: shell
```

### 高级工作流组合
通过条件逻辑、并行执行和数据转换链接作业。通过变量绑定 — `${input}`、`${response}`、`${env}` — 在作业间传递数据，支持类型转换和默认值。

```yaml
workflows:
  - id: rag-pipeline
    jobs:
      - id: embed
        component: embedder
        input:
          text: ${input.query}

      - id: search
        component: vector-store
        action: search
        input:
          vector: ${jobs.embed.output}
        depends_on: [embed]

      - id: answer
        component: chatgpt
        input:
          context: ${jobs.search.output}
          question: ${input.query}
        depends_on: [search]
```

### AI 智能体组件
构建将工作流作为工具使用的自主 AI 智能体。智能体推理、规划并通过动态调用其他工作流执行多步骤任务 — 全部通过 YAML 声明式定义。

```yaml
components:
  - id: research-agent
    type: agent
    tools:
      - search-web
      - fetch-page
    max_iteration_count: 10
    action:
      model:
        component: chatgpt
        input:
          messages: ${messages}
          tools: ${tools}
      system_prompt: You are a web research assistant.
      user_prompt: ${input.question}
```

### Human-in-the-Loop
为任何工作流添加审批关卡和用户输入步骤。工作流暂停，通过 CLI、Web UI 或 API 提示用户输入，然后无缝恢复。

```yaml
workflows:
  - id: write-with-approval
    jobs:
      - id: write-file
        component: file-writer
        input:
          path: ${input.path}
          content: ${input.content}
        interrupt:
          before:
            message: "Approve file write to ${job.input.path}?"
```

### 本地模型执行
在本地运行 HuggingFace 等来源的模型，原生支持 transformers、vLLM 和 PyTorch。通过 YAML 配置使用 LoRA/PEFT 微调模型。

```yaml
components:
  - id: local-llm
    type: model
    task: chat-completion
    model: HuggingFaceTB/SmolLM3-3B
    action:
      messages:
        - role: user
          content: ${input.prompt}
```

### 通用 AI 服务集成
连接 OpenAI、Anthropic、Google、xAI、ElevenLabs 和任何自定义 HTTP API。在单个工作流中自由组合服务。

```yaml
components:
  - id: claude
    type: http-client
    base_url: https://api.anthropic.com/v1
    action:
      path: /messages
      method: POST
      headers:
        x-api-key: ${env.ANTHROPIC_API_KEY}
        anthropic-version: "2023-06-01"
      body:
        model: claude-opus-4-20250514
        max_tokens: 1024
        messages:
          - role: user
            content: ${input.prompt}
```

### 实时流式传输
内置 SSE（服务器发送事件）流式传输，实现实时 AI 响应。支持任何提供商或本地模型的自动分块和连接管理。

```yaml
workflows:
  - id: chat
    jobs:
      - component: chatgpt
        output: ${output as sse-text}

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      body:
        model: gpt-4o
        messages: ${input.messages}
        stream: true
      stream_format: json
      output: ${response[].choices[0].delta.content}
```

### 内置数据存储集成
Chroma、FAISS、Milvus、Qdrant 向量搜索原生集成。Neo4j、ArangoDB 图存储。Redis 键值存储。通过嵌入搜索和语义检索构建 RAG 系统。

```yaml
components:
  - id: knowledge
    type: vector-store
    driver: chroma
    actions:
      - id: insert
        collection: docs
        method: insert
        vector: ${input.vector}
        metadata:
          text: ${input.text}

      - id: search
        collection: docs
        method: search
        query: ${input.vector}
```

### Deploy in Any Runtime
在原生、进程、Docker 或原生容器模式下运行。相同的配置在所有运行时中通用 — 只需更改一行。

```yaml
controller:
  runtime:
    type: docker
    image: my-ai-service:latest
    ports:
      - "8080:8080"
  adapter:
    type: http-server
    port: 8080
```

### 协议适配器
通过更改一行即可切换 HTTP REST、WebSocket 或 MCP（模型上下文协议）。包括并发控制、健康检查和自动 API 文档。

```yaml
# HTTP REST
controller:
  adapter:
    type: http-server
    port: 8080

# MCP (Model Context Protocol)
controller:
  adapter:
    type: mcp-server
    port: 8080
```

### 分布式工作流执行
通过 Redis 队列分发将 AI 工作负载扩展到多台机器。无需共享文件系统或代码更改，添加工作节点即可水平扩展。

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  queue:
    driver: redis
    host: localhost
    port: 6379
    name: my-queue
```

### Webhook 和 Callback 监听器
用于异步工作流的 HTTP Callback 监听器和用于 Webhook 的 HTTP Trigger 监听器。构建响应真实世界事件的反应式 AI 系统。

```yaml
listener:
  type: http-trigger
  port: 8091
  triggers:
    - path: /webhook
      method: POST
      workflow: handle-message
      input:
        text: ${body.message.text}
```

### 网关和隧道支持
通过 ngrok、Cloudflare 或 SSH 隧道将本地服务暴露到互联网。无需复杂网络配置即可集成 Webhook 和部署公共 API。

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port:
    - 8090
```

### Instant Web UI
2 行 YAML 添加可视化界面。Gradio 驱动的聊天 UI 或自定义静态前端，用于测试和调试。

```yaml
controller:
  webui:
    driver: gradio
    port: 8081
```

---

## 架构

协议适配器 → 组合引擎 → 运行时执行器

![架构图](docs/images/architecture-diagram.png)

---

## 贡献

欢迎所有贡献！
无论是修复错误、改进文档还是添加示例 — 每一点帮助都很重要。

```
# 设置开发环境
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .[dev]
```

---

## 许可证

MIT License © 2025-2026 Hanyeol Cho.

---

## 联系

有问题、想法或反馈？[提交 Issue](https://github.com/hanyeol/model-compose/issues) 或在 [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions) 开始讨论。
