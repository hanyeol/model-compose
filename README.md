<div align="center">

![model-compose - Compose Any AI, Deploy Anywhere](docs/images/main-banner.png)

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![PyPI version](https://img.shields.io/pypi/v/model-compose.svg)](https://pypi.org/project/model-compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/model-compose)](https://pepy.tech/project/model-compose)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

[한국어](README.ko.md) | [中文](README.zh-cn.md)

</div>

---

# model-compose

**Compose AI Systems, Deploy Anywhere.**

Build AI agents, RAG pipelines, MCP servers, and multi-model workflows in a single YAML file. Run the same system locally, in containers, or in production without rewriting your stack.

Inspired by `docker-compose`, model-compose provides a portable runtime for AI systems — combining cloud APIs and local models without vendor lock-in.

<div align="center">

[Documentation](docs/user-guide/README.md) · [Quick Start](#quick-start) · [Examples](examples/README.md) · [Contributing](#contributing)

</div>

---

## Philosophy

AI systems should not be locked into a single provider, runtime, or cloud. They should remain portable, inspectable, and able to run anywhere.

Today, many AI applications are tightly coupled to provider-specific APIs, managed runtimes, and closed ecosystems. While convenient at first, this coupling introduces vendor lock-in — components can't be swapped without rewriting, systems can't move between environments, and teams are forced to choose between cloud convenience and local control.

**model-compose** takes a fundamentally different approach based on four core principles:

* **Composable** — Models, agents, workflows, tools, memory, and protocols are treated as modular, interchangeable building blocks.

* **Portable** — Define your AI system once, then deploy it locally, in containers, or across distributed production environments without re-engineering the core architecture.

* **Hybrid-First** — Bridge cloud APIs and local models on your own terms. Swap infrastructure layers seamlessly to optimize for privacy, latency, or cost without changing how your system behaves.

* **Stream-Native** — Data flows through workflows as it arrives. Tokens, audio chunks, video frames, and live events are first-class values — no buffering an entire response before the next stage begins.

The goal of model-compose is not to build another closed platform, but to restore architectural autonomy to developers.

---

## Why model-compose?

| Feature | **model-compose** | Managed APIs (OpenAI, etc.) | Code Frameworks (LangChain, etc.) |
|---|---|---|---|
| **Provider Coupling** | **Multi-provider via config** | Single provider per SDK | Multi-provider via abstractions |
| **Code Coupling** | **Declarative YAML — no application code** | Application code required | Framework-specific code required |
| **Infrastructure Control** | **Full Sovereignty** | Provider-controlled | Heavy Abstraction |
| **Runtime Flexibility** | **Hybrid-First (Local + Cloud)** | Cloud Only | Complex to customize |
| **Protocol Support** | **HTTP / WebSocket / MCP** | Provider-specific | Limited |
| **Data Streaming** | **First-class across all stages** | Response-only (SSE tokens) | Framework-wrapped generators |
| **Deployment** | **Docker / Native / Process** | Provider-managed | Manual integration |

---

## Highlights

- **Any model, anywhere** — run models locally via HuggingFace, vLLM, or llama.cpp for privacy, offline use, or zero API cost — or connect to OpenAI, Anthropic, Google, and more
- **AI agents in YAML** — build autonomous agents with tool use, planning, and multi-step reasoning — all declarative
- **Human-in-the-loop** — workflows can pause for approval gates, user input, or manual review before continuing
- **Real-time streaming** — built-in SSE streaming for live AI responses from any provider or local model
- **20+ components ready** — models, agents, HTTP/WebSocket clients, vector/graph stores, shell commands, and more
- **Deploy as container** — same YAML runs as a Docker container, native process, or standalone service — switch runtime with one line
- **Serve any protocol** — HTTP REST, WebSocket, or MCP with one line change
- **Distributed execution** — dispatch workflows to remote workers via Redis queues — scale horizontally by adding servers
- **Instant Web UI** — add a Gradio-powered interface with 2 lines of YAML

---

## Installation

Using pip:

```
pip install model-compose
```

Or using [uv](https://docs.astral.sh/uv/):

```
uv pip install model-compose
```

Or install from source:

```
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .   # or: uv pip install -e .
```

> Requires: Python 3.10 or higher

---

## Quick Start

Define your AI runtime in a `model-compose.yml`:

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

Create a `.env` file:

```bash
OPENAI_API_KEY=your-key
```

Run it:

```bash
model-compose up
```

Your AI runtime is now serving at `http://localhost:8080` with Web UI at `http://localhost:8081`.

> Explore [examples](examples/README.md) for more workflows or read the [Documentation](docs/user-guide/README.md).

---

## Core Capabilities

### Declarative YAML Configuration
Define your entire AI system in a single YAML file. Workflows, agents, models, APIs, vector/graph stores, and runtimes — all composed and deployed together without custom code.

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

### Flexible Component System
20+ reusable component types. Mix HTTP clients, local models, vector stores, shell commands, and workflows in any combination. Define once, use everywhere.

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

### Advanced Workflow Composition
Chain jobs with conditional logic, parallel execution, and data transformation. Pass data between jobs with variable binding — `${input}`, `${response}`, `${env}` — with type conversion and defaults.

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

### AI Agent Components
Build autonomous AI agents that use workflows as tools. Agents reason, plan, and execute multi-step tasks by dynamically invoking other workflows — all defined declaratively in YAML.

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
Add approval gates and user input steps to any workflow. Workflows pause, prompt for human input via CLI, Web UI, or API, and resume seamlessly.

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

### Local Model Execution
Run models from HuggingFace and other sources locally with native support for transformers, vLLM, and PyTorch. Fine-tune models with LoRA/PEFT through YAML configuration.

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

### Universal AI Service Integration
Connect to OpenAI, Anthropic, Google, xAI, ElevenLabs, and any custom HTTP API. Mix and match providers in a single workflow.

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

### Real-Time Streaming
Built-in SSE (Server-Sent Events) streaming for real-time AI responses. Stream from any provider or local model with automatic chunking and connection management.

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

### Built-in Data Store Integration
Native integration with Chroma, FAISS, Milvus, Qdrant for vector search. Neo4j and ArangoDB for graph stores. Redis for key-value storage. Build RAG systems with embedding search and semantic retrieval.

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
Run in native, process, Docker, or native container mode. The same configuration works across all runtimes — switch with one line.

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

### Protocol Adapters
Serve over HTTP REST, WebSocket, or MCP (Model Context Protocol) by changing a single line. Includes concurrency control, health checks, and automatic API documentation.

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

### Distributed Workflow Execution
Scale AI workloads across multiple machines using Redis-backed queue dispatch. Add workers to scale horizontally without shared filesystem or code changes.

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

### Webhook and Callback Listeners
HTTP callback listeners for async workflows and HTTP trigger listeners for webhooks. Build reactive AI systems that respond to real-world events.

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

### Gateway and Tunnel Support
Expose local services to the internet with ngrok, Cloudflare, or SSH tunnels. Integrate webhooks and deploy public APIs without complex networking.

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port:
    - 8090
```

### Instant Web UI
Add a visual interface with 2 lines of YAML. Get a Gradio-powered chat UI or serve custom static frontends for testing and debugging.

```yaml
controller:
  webui:
    driver: gradio
    port: 8081
```

---

## Architecture

Protocol adapters → Composition engine → Runtime executors

![Architecture Diagram](docs/images/architecture-diagram.png)

---

## Contributing

We welcome all contributions!
Whether it's fixing bugs, improving docs, or adding examples — every bit helps.

```
# Setup for development
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

---

## License

MIT License © 2025-2026 Hanyeol Cho.

---

## Contact

Have questions, ideas, or feedback? [Open an issue](https://github.com/hanyeol/model-compose/issues) or start a discussion on [GitHub Discussions](https://github.com/hanyeol/model-compose/discussions).
