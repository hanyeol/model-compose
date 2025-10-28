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

- 🎨 **无代码**：纯 YAML 配置—无需编写代码
- 🔄 **可组合**：可重用组件和多步骤工作流
- 🚀 **生产就绪**：HTTP/MCP 服务器 + Web UI + Docker 部署
- 🔌 **连接一切**：外部 AI 服务、本地模型、向量存储等
- ⚡ **流式 & 扩展**：实时流式传输和事件驱动自动化
- ⚙️ **配置**：环境变量、灵活设置
- 🔗 **集成**：Webhook、隧道、HTTP 服务器

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

> 💡 探索更多工作流请访问[示例](examples/README.md)，详细内容请阅读[用户指南](docs/user-guide/zh-cn/README.md)。

---
## 💡 核心能力

### 🖥️ 内置 Web UI
仅需 3 行 YAML 即可添加可视化界面：
```yaml
controller:
  webui:
    port: 8081
```
立即获得用户友好的界面来测试和监控您的工作流。支持 Gradio（默认）和自定义静态前端。

### 🛰️ MCP 服务器支持
只需更改一行即可将工作流转换为 MCP 工具：
```yaml
controller:
  type: mcp-server  # 从 http-server 改为 mcp-server
```
无需更改代码。您的工作流即可通过 Model Context Protocol 立即访问。

### 🐳 Docker 部署
内置 Docker 支持，随处部署：
```yaml
controller:
  runtime: docker
```
在隔离容器中运行工作流，完全控制镜像、卷、端口和环境变量。

> 📖 详细配置请参阅[用户指南](docs/user-guide/zh-cn/README.md)，可运行示例请访问[示例](examples/README.md)。

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
