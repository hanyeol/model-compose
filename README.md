<div align="center">

![model-compose - Declarative AI Workflow Orchestrator](docs/images/main-banner.png)

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![PyPI version](https://img.shields.io/pypi/v/model-compose.svg)](https://pypi.org/project/model-compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/model-compose)](https://pepy.tech/project/model-compose)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

[한국어](README.ko.md) | [中文](README.zh-cn.md)

</div>

---

# 🤖 Model-Compose

**model-compose** is a declarative AI workflow orchestrator inspired by `docker-compose`. It lets you define and run AI model pipelines using simple YAML files — no custom code required. Effortlessly connect external AI services (OpenAI, Anthropic, Google, etc.), run local AI models, integrate vector stores, and more — all within powerful, composable workflows.

**No custom code. Just YAML configuration.**

<div align="center">

[📖 User Guide](docs/user-guide/README.md) · [🚀 Quick Start](#-quick-start) · [💡 Examples](examples/README.md) · [🤝 Contributing](#-contributing)

</div>

---

## ✨ Features

### 🎨 **No-Code AI Orchestration**
Define complex AI workflows entirely in YAML—no Python, no JavaScript, no coding required. Connect multiple AI services, models, and APIs through simple declarative configuration.

### 🔗 **Universal AI Service Integration**
Connect to any AI provider out of the box—OpenAI, Anthropic Claude, Google Gemini, ElevenLabs, Stability AI, Replicate, or any custom HTTP API. Mix and match services in a single workflow.

### 🤖 **Agent Components**
Build autonomous AI agents that use workflows as tools. Agents can reason, plan, and execute multi-step tasks by dynamically invoking other workflows—all defined declaratively in YAML.

### ✋ **Human-in-the-Loop**
Add approval gates and user input steps to any workflow with interrupt configuration. Workflows pause, prompt for human input via CLI, Web UI, or API, and resume seamlessly—perfect for review, moderation, and supervised AI pipelines.

### 🖥️ **Local Model Execution**
Run models from HuggingFace and other sources locally with native support for transformers, PyTorch, and model serving frameworks. Fine-tune models with LoRA/PEFT, train with custom datasets, all through YAML configuration.

### ⚡ **Real-Time Streaming**
Built-in SSE (Server-Sent Events) streaming for real-time AI responses. Stream from OpenAI, Claude, local models, or any streaming API with automatic chunking and connection management.

### 🔄 **Advanced Workflow Composition**
Build multi-step pipelines with conditional logic, data transformation, and parallel execution. Pass data between jobs with powerful variable binding—`${input}`, `${response}`, `${env}`, with type conversion and defaults.

### 🚀 **Production-Ready Deployment**
Deploy as HTTP REST API or MCP (Model Context Protocol) server by changing one line. Includes concurrency control, health checks, and automatic API documentation.

### 🎯 **Event-Driven Architecture**
HTTP Callback listeners for async workflows (image generation, video processing). HTTP Trigger listeners for webhooks and external events. Build reactive AI systems that respond to real-world events.

### 🌐 **Smart Tunneling & Gateways**
Expose local services to the internet instantly with ngrok, Cloudflare, or SSH tunnels. Perfect for webhook integration and public API deployment without complex networking.

### 🐳 **Container-Native Deployment**
First-class Docker support with runtime configuration, volume mounting, and environment management. Deploy to any cloud provider or Kubernetes cluster with minimal configuration.

### 🎨 **Instant Web UI**
Add a visual interface with just 2 lines—get Gradio-powered chat UI or serve custom static frontends. Test workflows, monitor executions, and debug pipelines visually.

### 🗄️ **RAG & Vector Database Ready**
Native integration with ChromaDB, Milvus, Pinecone, and Weaviate. Build retrieval-augmented generation (RAG) systems with embedding search, document indexing, and semantic retrieval.

### 🔧 **Flexible Component System**
Reusable components with multi-action support. Define once, use everywhere. Mix HTTP clients, local models, vector stores, shell commands, and custom workflows in any combination.

---


## 📦 Installation

```
pip install model-compose
```

Or install from source:

```
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

> Requires: Python 3.9 or higher

---

## 🚀 Quick Start

Create a `model-compose.yml`:

```yaml
controller:
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

Create a `.env` file:

```bash
OPENAI_API_KEY=your-key
```

Run it:

```bash
model-compose up
```

Your API is now live at `http://localhost:8080` and Web UI at `http://localhost:8081` 🎉

---

## 🎯 Powerful Yet Simple

### 🖥️ Add Web UI with 2 Lines
```yaml
controller:
  webui:
    port: 8081
```

### 🛰️ Switch to MCP Server with 1 Line
```yaml
controller:
  type: mcp-server
```

### 🔄 Run Components in Separate Processes
```yaml
component:
  runtime: process
```

### 🐳 Deploy in Docker with 1 Line
```yaml
controller:
  runtime: docker
```

> 💡 Explore [examples](examples/README.md) for more workflows or read the [User Guide](docs/user-guide/README.md).

---
## 🏗 Architecture

![Archtecture Diagram](docs/images/architecture-diagram.png)

---

## 🤝 Contributing
We welcome all contributions!
Whether it's fixing bugs, improving docs, or adding examples — every bit helps.

```
# Setup for development
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .[dev]
```

---

## 📄 License
MIT License © 2025 Hanyeol Cho.

---

## 📬 Contact
Have questions, ideas, or feedback? [Open an issue](https://github.com/hanyeol/model-compose/issues) or start a discussion on [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions).
