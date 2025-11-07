<div align="center">

![model-compose - 声明式 AI 工作流编排器](docs/images/main-banner.png)

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![PyPI version](https://img.shields.io/pypi/v/model-compose.svg)](https://pypi.org/project/model-compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/model-compose)](https://pepy.tech/project/model-compose)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

[English](README.md) | [한국어](README.ko.md)

</div>

---

# 🤖 Model-Compose

**model-compose** 是受 `docker-compose` 启发创建的声明式工作流编排器。使用简单的 YAML 文件定义和运行 AI 模型管道 — 无需编写代码。轻松连接外部 AI 服务（OpenAI、Anthropic、Google 等）、运行本地 AI 模型、集成向量存储等 — 所有功能都在强大且可组合的工作流中实现。

**无需编写代码，只需 YAML 配置。**

<div align="center">

[📖 用户指南](docs/user-guide/zh-cn/README.md) · [🚀 快速开始](#-快速开始) · [💡 示例](examples/README.md) · [🤝 贡献](#-贡献)

</div>

---

## ✨ 主要特性

### 🎨 **无代码 AI 编排**
完全使用 YAML 定义复杂的 AI 工作流 — 无需 Python、JavaScript，无需编码。通过简单的声明式配置连接多个 AI 服务、模型和 API。

### 🔗 **通用 AI 服务集成**
开箱即用连接任何 AI 提供商 — OpenAI、Anthropic Claude、Google Gemini、ElevenLabs、Stability AI、Replicate 或任何自定义 HTTP API。在单个工作流中混合和匹配服务。

### 🖥️ **本地模型执行**
在本地运行 HuggingFace 等平台提供的模型，原生支持 transformers、PyTorch 和模型服务框架。通过 LoRA/PEFT 微调模型，使用自定义数据集训练，全部通过 YAML 配置完成。

### ⚡ **实时流式传输**
内置 SSE（服务器发送事件）流式传输，实现实时 AI 响应。支持 OpenAI、Claude、本地模型或任何流式 API 的自动分块和连接管理。

### 🔄 **高级工作流组合**
构建具有条件逻辑、数据转换和并行执行的多步骤管道。通过强大的变量绑定在作业之间传递数据 — `${input}`、`${response}`、`${env}`，支持类型转换和默认值。

### 🚀 **生产就绪控制器**
通过更改一行即可部署为 HTTP REST API 或 MCP（模型上下文协议）服务器。包括并发控制、健康检查和自动 API 文档。

### 🎯 **事件驱动架构**
用于异步工作流（图像生成、视频处理）的 HTTP 回调监听器。用于 Webhook 和外部事件的 HTTP 触发监听器。构建响应真实世界事件的反应式 AI 系统。

### 🌐 **智能隧道和网关**
使用 ngrok、Cloudflare 或 SSH 隧道立即将本地服务暴露到互联网。非常适合 Webhook 集成、Slack 机器人和公共 API 部署，无需复杂的网络配置。

### 🐳 **容器原生部署**
完善的 Docker 支持，包含运行时配置、卷挂载和环境管理。以最少的配置部署到任何云提供商或 Kubernetes 集群。

### 🎨 **即时 Web UI**
只需 2 行添加可视化界面 — 获得 Gradio 驱动的聊天 UI 或提供自定义静态前端。可视化测试工作流、监控执行和调试管道。

### 🗄️ **RAG 和向量数据库就绪**
与 ChromaDB、Milvus、Pinecone 和 Weaviate 原生集成。通过嵌入搜索、文档索引和语义检索构建检索增强生成（RAG）系统。

### 🔧 **灵活的组件系统**
具有多动作支持的可重用组件。定义一次，随处使用。以任何组合混合 HTTP 客户端、本地模型、向量存储、shell 命令和自定义工作流。

---


## 📦 安装

```bash
pip install model-compose
```

或从源代码安装：

```bash
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

> 要求：Python 3.9 或更高版本

---

## 🚀 快速开始

创建 `model-compose.yml` 文件：

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    port: 8081

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

workflows:
  - id: chat
    default: true
    jobs:
      - component: chatgpt
```

创建 `.env` 文件：

```bash
OPENAI_API_KEY=your-key
```

运行：

```bash
model-compose up
```

API 运行在 `http://localhost:8080`，Web UI 运行在 `http://localhost:8081` 🎉

---

## 🎯 强大而简单

### 🖥️ 2 行添加 Web UI
```yaml
controller:
  webui:
    port: 8081
```

### 🛰️ 1 行切换到 MCP 服务器
```yaml
controller:
  type: mcp-server
```

### 🔄 在独立进程中运行组件
```yaml
component:
  runtime: process
```

### 🐳 1 行部署到 Docker
```yaml
controller:
  runtime: docker
```

> 💡 探索更多工作流请访问[示例](examples/README.md)，详细内容请阅读[用户指南](docs/user-guide/zh-cn/README.md)。

---
## 🏗 架构

![架构图](docs/images/architecture-diagram.png)

---

## 🤝 贡献
欢迎所有贡献！
无论是修复错误、改进文档还是添加示例 — 每一点帮助都很重要。

```bash
# 设置开发环境
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .[dev]
```

---

## 📄 许可证
MIT License © 2025 Hanyeol Cho.

---

## 📬 联系
有问题、想法或反馈？[提交 Issue](https://github.com/hanyeol/model-compose/issues) 或在 [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions) 开始讨论。
