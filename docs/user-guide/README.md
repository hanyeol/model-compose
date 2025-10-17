# model-compose User Guide

Welcome to the **model-compose** user guide! This comprehensive documentation will help you master declarative AI workflow orchestration—from basic concepts to advanced deployment strategies.

## 📖 Documentation Languages

- **🌍 English**: You're reading it!
- **🇰🇷 한국어**: [한국어 사용자 가이드](./ko/README.md)

---

## 🚀 Quick Start

New to model-compose? Start here:

1. **[Getting Started](./01-getting-started.md)** - Installation, first workflow, and basic concepts
2. **[Core Concepts](./02-core-concepts.md)** - Understanding controllers, components, and workflows
3. **[CLI Usage](./03-cli-usage.md)** - Master the command-line interface

---

## 📚 Complete Table of Contents

**[→ Full Table of Contents](./00-table-of-contents.md)**

### Essential Topics

#### Foundation
- [Getting Started](./01-getting-started.md) - Install and run your first workflow
- [Core Concepts](./02-core-concepts.md) - Architecture and key components
- [CLI Usage](./03-cli-usage.md) - Command reference and examples

#### Building Workflows
- [Component Configuration](./04-component-configuration.md) - Define reusable components
- [Writing Workflows](./05-writing-workflows.md) - Create multi-step pipelines
- [Variable Binding](./12-variable-binding.md) - Data flow and transformations

#### Controllers & UI
- [Controller Configuration](./06-controller-configuration.md) - HTTP and MCP servers
- [Web UI Configuration](./07-webui-configuration.md) - Visual workflow management

#### AI Models
- [Working with Local AI Models](./08-local-ai-models.md) - Run models locally
- [External Service Integration](./10-external-service-integration.md) - Connect to OpenAI, Claude, etc.
- [Streaming Mode](./11-streaming-mode.md) - Real-time output streaming

#### System Integration
- [System Integration](./13-system-integration.md) - Listeners, triggers, and gateways
  - HTTP Callback Listeners - Handle async webhooks
  - HTTP Trigger Listeners - Event-driven workflows
  - Gateway Support - Expose local services securely

#### Deployment & Production
- [Deployment](./14-deployment.md) - Docker, cloud, and production best practices
- [Practical Examples](./15-practical-examples.md) - Real-world use cases
- [Troubleshooting](./16-troubleshooting.md) - Common issues and solutions

---

## 🎯 Learn By Example

Looking for hands-on examples? Check out:

- **[Practical Examples](./15-practical-examples.md)** - Complete working examples:
  - Chatbots (OpenAI, Claude)
  - Voice generation pipelines
  - Image analysis and editing
  - RAG systems with vector databases
  - Slack bots with MCP
  - Multimodal workflows

- **[Examples Directory](../../examples/)** - Ready-to-run YAML configurations

---

## 🔍 Quick Reference

### Common Tasks

| I want to... | Go to... |
|--------------|----------|
| Install and run my first workflow | [Getting Started](./01-getting-started.md) |
| Call external APIs (OpenAI, Claude) | [External Service Integration](./10-external-service-integration.md) |
| Run local AI models | [Local AI Models](./08-local-ai-models.md) |
| Create multi-step workflows | [Writing Workflows](./05-writing-workflows.md) |
| Stream real-time outputs | [Streaming Mode](./11-streaming-mode.md) |
| Handle webhooks and callbacks | [System Integration](./13-system-integration.md) |
| Deploy to production | [Deployment](./14-deployment.md) |
| Build a chatbot | [Practical Examples § 15.1](./15-practical-examples.md#151-building-a-chatbot) |
| Set up a RAG system | [Practical Examples § 15.4](./15-practical-examples.md#154-rag-system-using-vector-db) |
| Debug issues | [Troubleshooting](./16-troubleshooting.md) |

### Key Concepts

- **Controller**: HTTP or MCP server that hosts your workflows
- **Component**: Reusable definition (API call, model, command)
- **Workflow**: Named sequence of jobs
- **Job**: Single step that executes a component
- **Listener**: Receives HTTP callbacks or triggers workflows
- **Gateway**: Tunnels local services to the internet

---

## 🛠 Configuration Reference

Looking for specific configuration options?

- **[Complete Configuration Schema](./17-appendix.md#171-complete-configuration-file-schema)** - Full YAML reference
- **[Component Types](./04-component-configuration.md#41-component-types)** - All available component types
- **[Variable Binding Syntax](./12-variable-binding.md)** - Complete variable reference

---

## 💡 Tips for Learning

1. **Start Simple**: Begin with the [Getting Started](./01-getting-started.md) guide
2. **Hands-On**: Try the [Practical Examples](./15-practical-examples.md)
3. **Incremental**: Add features one at a time
4. **Explore**: Check the [examples directory](../../examples/) for inspiration
5. **Ask**: Open an [issue](https://github.com/hanyeol/model-compose/issues) if you're stuck

---

## 🤝 Contributing to Docs

Found a typo or want to improve the documentation?

1. Fork the repository
2. Edit the Markdown files in `docs/user-guide/`
3. Submit a pull request

We appreciate all contributions!

---

## 📬 Getting Help

- **Documentation Issues**: [File an issue](https://github.com/hanyeol/model-compose/issues)
- **Questions**: [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions)
- **Bug Reports**: [Issue Tracker](https://github.com/hanyeol/model-compose/issues)

---

**Happy composing! 🎉**
