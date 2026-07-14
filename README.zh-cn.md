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

**在几分钟内部署生产级 AI 服务。**

一个 YAML 文件。任意模型、任意协议、任意运行时。无需编写应用代码即可构建聊天 API、RAG 管道、自主智能体和 MCP 服务器 —— 像 `docker-compose` 一样将同一份文件部署到任何地方。

AI 系统不应被锁定在单一提供商、运行时或云平台中。model-compose 建立在四个原则之上：

- **Composable** —— 模型、智能体、工作流、工具、记忆和协议都是可互换的构建块。
- **Portable** —— 只需定义一次 AI 系统，无需重新设计即可部署到任何地方。
- **Hybrid-First** —— 按照您自己的条件连接云端 API 和本地模型。
- **Stream-Native** —— 数据一到达就沿着工作流流动 —— 令牌、音频、帧和事件都是一等值。

<div align="center">

[Quick Start](#quick-start) · [What You Can Build](#what-you-can-build) · [Documentation](docs/user-guide/README.md) · [Examples](examples/README.md)

</div>

---

## Quick Start

使用 pip 安装：

```bash
pip install model-compose
```

或使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv pip install model-compose
```

创建 `model-compose.yml`：

```yaml
controller:
  adapter:
    type: http-server
    port: 8080
  webui:
    port: 8081

workflow:
  job:
    component: chatgpt
    input:
      prompt: ${input.prompt}

component:
  id: chatgpt
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
```

运行：

```bash
export OPENAI_API_KEY=your-key
model-compose up
```

**就这样。** 您在 `http://localhost:8080` 上提供 GPT-4o 服务，并在 `http://localhost:8081` 上运行 Web UI。无需应用代码，无需框架样板。同一份文件可在本地、Docker 或生产环境中运行。

---

## What You Can Build

一个 YAML 文件今天就能提供的服务 —— 这只是几个示例。

### 🤖 自主智能体

以声明式方式构建能够规划、使用工具并完成多步骤任务的 ReAct 智能体。

```yaml
component:
  id: research-agent
  type: agent
  tools: [search-web, fetch-page]
  max_iteration_count: 10
  action:
    model:
      component: chatgpt
    system_prompt: You are a web research assistant.
    user_prompt: ${input.question}
```

[agents/](examples/agents/) 下有 10 个可运行的智能体，包括代码审查、RAG 助手、Web3 空投猎手等。

### 🔍 RAG 管道

将嵌入、向量搜索和生成组合到一个工作流中 —— 无需胶水代码。

```yaml
workflow:
  jobs:
    - id: embed
      component: embedder
      input: { text: ${input.query} }

    - id: retrieve
      component: knowledge
      action: search
      input: { vector: ${jobs.embed.output} }

    - id: answer
      component: chatgpt
      input:
        context: ${jobs.retrieve.output}
        question: ${input.query}
```

Chroma、Milvus、Qdrant、FAISS、Neo4j、ArangoDB、Redis 的原生驱动开箱即用。

### 🌐 MCP 服务器

将任何工作流变成 Claude、ChatGPT 或 Cursor 可以使用的 MCP 服务器 —— 只需一行更改。

```yaml
controller:
  adapter:
    type: mcp-server   # ← 之前是: http-server
    port: 8080
```

完整示例位于 [mcp-servers/](examples/mcp-servers/)，包括 Korea DART MCP 和 Slack 机器人 MCP。

### ⚡ 流式多模态工作流

端到端流式传输令牌、音频块、视频帧 —— 所有阶段一等支持。

```yaml
workflow:
  job:
    component: chatgpt
    output: ${output as sse-text}

component:
  id: chatgpt
  type: http-client
  action:
    body: { stream: true, ... }
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

实时 TTS、video-to-frames、实时聊天等示例位于 [data-streaming/](examples/data-streaming/) 和 [showcase/](examples/showcase/)。

---

## Why model-compose?

| | **model-compose** | Managed APIs (OpenAI 等) | Code Frameworks (LangChain 等) |
|---|---|---|---|
| **首个 API 上线时间** | **几分钟**（一个 YAML） | 几小时（SDK + 服务器代码） | 几天（框架 + 集成） |
| **Provider Coupling** | **仅通过配置实现多提供商** | 每个 SDK 绑定单一提供商 | 通过抽象支持多提供商 |
| **Code Coupling** | **声明式 YAML —— 无需应用代码** | 需要应用代码 | 需要框架专用代码 |
| **Infrastructure Control** | **完全自主权** | 提供商控制 | 重度抽象 |
| **Runtime Flexibility** | **Hybrid-First（本地 + 云端）** | 仅限云端 | 定制复杂 |
| **Protocol Support** | **HTTP / WebSocket / MCP** | 提供商限定 | 有限 |
| **Data Streaming** | **所有阶段一等支持** | 仅响应（SSE 令牌） | 框架封装的生成器 |
| **Deployment** | **Docker / Native / Process** | 提供商管理 | 手动集成 |

---

## 从开发到生产

在您笔记本上运行的同一份 YAML 无需重写即可扩展。

### 1. 本地开发

```bash
model-compose up
```

在您的机器上运行，`:8081` 端口自带 Gradio Web UI —— 完美支持迭代开发。

### 2. 以容器方式部署

添加 `runtime:` 块。同一份文件，同样的行为：

```yaml
controller:
  runtime:
    type: docker
    image: my-ai-service:latest
    ports: [ "8080:8080" ]
```

### 3. 水平扩展

添加一个队列。分发器接收任务，订阅者在 N 台机器上处理：

```yaml
controller:
  adapter: { type: http-server, port: 8080 }
  queue:
    driver: redis
    host: redis.internal
    name: my-queue
```

无需共享文件系统。无需代码变更。只需添加更多订阅者即可扩展。

---

## Highlights

- **任意模型，任意地方** —— 本地使用 HuggingFace、vLLM、llama.cpp，或通过 HTTP 连接 OpenAI/Anthropic/Google/xAI
- **YAML 中的智能体** —— ReAct 循环、工具使用、多步推理 —— 无需代码
- **Human-in-the-loop** —— 暂停工作流以获得审批，通过 CLI/UI/API 恢复
- **20+ 组件** —— 模型、智能体、HTTP/WebSocket 客户端、向量/图存储、shell、浏览器等
- **任意协议** —— HTTP REST、WebSocket 或 MCP 只需一行
- **任意运行时** —— Docker、原生、进程、嵌入式 —— 一行切换
- **分布式** —— 基于 Redis 队列的分发实现水平扩展
- **即时 Web UI** —— 2 行 YAML 即可获得 Gradio UI
- **随处流式传输** —— SSE、WebSocket 和作业间流作为一等值

---

## Real-World Examples

超过 100 个可直接运行的示例，按分类组织：

| 分类 | 内容 |
|---|---|
| [`agents/`](examples/agents/) | 代码审查、RAG 助手、网络研究员、Web3 空投猎手等 |
| [`showcase/`](examples/showcase/) | 端到端管道：磁盘分析、基于人脸的场景搜索、实时 TTS |
| [`model-providers/`](examples/model-providers/) | OpenAI、Anthropic、xAI、Google、ElevenLabs、vLLM |
| [`model-tasks/`](examples/model-tasks/) | 本地聊天、嵌入、TTS、VLM、人脸嵌入等 |
| [`mcp-servers/`](examples/mcp-servers/) | 构建暴露给 Claude、Cursor、ChatGPT 的 MCP 服务器 |
| [`workflow-queue/`](examples/workflow-queue/) | 基于 Redis 的分布式分发（流式 + 非流式） |
| [`data-streaming/`](examples/data-streaming/) | video-to-frames、YouTube 实时聊天、流式输入 |
| [`integrations/`](examples/integrations/) | 向量/图/KV 存储、搜索引擎、通道、隧道 |

完整目录位于 [examples/README.md](examples/README.zh-cn.md)。

---

## Architecture

Protocol adapters → Composition engine → Runtime executors

![Architecture Diagram](docs/images/architecture-diagram.png)

---

## Contributing

我们欢迎所有贡献 —— bug 修复、文档改进、新示例。

```bash
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

如果有 CONTRIBUTING 指南请参考，或直接提交 PR。

---

## License

MIT License © 2025-2026 Hanyeol Cho.

---

## Contact

有问题、想法或反馈？[打开一个 issue](https://github.com/hanyeol/model-compose/issues) 或在 [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions) 上发起讨论。
