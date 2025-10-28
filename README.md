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

- 🎨 **No-Code**: Pure YAML configuration—no scripting required
- 🔄 **Composable**: Reusable components and multi-step workflows
- 🚀 **Production Ready**: HTTP/MCP servers + Web UI + Docker deployment
- 🔌 **Connect Anything**: External AI services, local models, vector stores, and more
- ⚡ **Stream & Scale**: Real-time streaming and event-driven automation
- ⚙️ **Configuration**: Environment variables, flexible settings
- 🔗 **Integration**: Webhooks, tunneling, HTTP servers

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

Create a `.env` file:

```bash
OPENAI_API_KEY=your-key
```

Run it:

```bash
model-compose up
```

Your API is now live at `http://localhost:8080` and Web UI at `http://localhost:8081` 🎉

> 💡 Explore [examples](examples/README.md) for more workflows or read the [User Guide](docs/user-guide/README.md).

---
## 💡 Key Capabilities

### 🖥️ Built-in Web UI
Add a web interface by adding just 2 lines to your YAML:
```yaml
controller:
  webui:
    port: 8081
```
Instantly get a user-friendly interface to test and monitor your workflows. Supports both Gradio (default) and custom static frontends.

### 🛰️ MCP Server Ready
Transform your workflows into MCP tools by changing one line:
```yaml
controller:
  type: mcp-server
```
Just set the type to `mcp-server`. Your workflows become instantly accessible via the Model Context Protocol.

### 🐳 Docker Deployment
Deploy anywhere with built-in Docker support:
```yaml
controller:
  runtime: docker
```
Run your workflows in isolated containers with full control over images, volumes, ports, and environment variables.

> 📖 See the [User Guide](docs/user-guide/README.md) for detailed configuration and [Examples](examples/README.md) for ready-to-run samples.

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
