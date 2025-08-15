# model-compose: Declarative AI Model and Workflow Orchestrator

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

**model-compose** is an open-source, declarative workflow orchestrator inspired by `docker-compose`. It lets you define and run AI model pipelines using simple YAML files — no custom code required. Effortlessly connect external AI services or run local AI models, all within powerful, composable workflows.

---

## ✨ Features

- **Declarative by Design**: Define complete AI workflows using simple YAML files—no complex scripting required.
- **Compose Anything**: Combine multiple AI models, APIs, and tools into a single, unified pipeline.
- **Built for Orchestration**:  Orchestrate multi-step model interactions with ease. Transform individual API calls into maintainable, end-to-end systems.
- **Multi-Workflow Support**: Define multiple named workflows in one project. Run them by name or set a default for quick execution.
- **Modular Components**: Break down logic into reusable components and jobs. Easily plug, swap, and extend them across workflows.
- **Flexible I/O Routing**: Connect inputs and outputs between jobs using clean, scoped variables—no glue code needed.
- **Streaming Mode Support**: Stream real-time outputs from models and APIs, enabling interactive applications and faster feedback loops.
- **Run Locally, Serve Remotely**: Execute workflows from the CLI or expose them as HTTP or MCP endpoints with an optional Web UI.
- **Docker Deployment**: Build and deploy your workflow controller as a Docker container for consistent and portable execution environments.
- **Environment Variable Support**: Easily inject secrets and configuration via `.env` files or environment variables to keep your YAML clean and secure.

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

## 🚀 How to Run

**model-compose** provides a CLI interface to launch and manage your AI workflows — inspired by `docker-compose`.

#### 🔼 Starting the Workflow Controller (`up`)
Use the `up` command to launch the workflow controller, which hosts your workflows as HTTP or MCP endpoints and optionally provides a Web UI.

```
model-compose up
```

By default, this command will:

- Look for a file named `model-compose.yml` in the **current working directory**
- Automatically load environment variables from a `.env` file in the **same directory**, if it exists
- Start the workflow controller (default: `http://localhost:8080`)
- Optionally launch the Web UI (default: `http://localhost:8081`, if configured)

To run in the background (detached mode):

```
model-compose up -d
```

You can specify one or more configuration files using `-f`:

```
model-compose -f base.yml -f override.yml up
```

If needed, you can override or extend environment variables with:

```
model-compose up --env-file .env
```

or

```
model-compose up --env OPENAI_API_KEY=... --env ELEVENLABS_API_KEY=...
```

> 💡 Once the controller is running, you can trigger workflows via the REST API or, if using MCP, via JSON-RPC. You can also access them through the Web UI.

#### 🔽 Shutting Down the Server (`down`)
To gracefully stop and remove the workflow controller and all associated services:

```
model-compose down
```

#### ▶️ Running a Workflow Once (`run`)
Run a workflow directly from the CLI without starting the controller:

```
model-compose run <workflow-name> --input '{"key": "value"}'
```

This is useful for testing, automation, or scripting.

#### 🧪 Lifecycle Commands

| Command              | Description                          |
|----------------------|--------------------------------------|
| `model-compose up`   | Launch the workflow controller and load defined workflows |
| `model-compose down` | Gracefully stop and remove the controller and all related services |
| `model-compose start`| Start the controller if it has been previously configured |
| `model-compose stop` | Temporarily pause the currently running controller |

---
## 🧾 `model-compose.yml`

The `model-compose.yml` file is the central configuration file that defines how your workflows are composed and executed.

It includes:

- **Controller**: configures the HTTP/MCP server, API endpoints, and optional Web UI
- **Components**: reusable definitions for calling APIs, running local AI models, or executing commands
- **Workflows**: named sets of jobs that define the flow of data
- **Jobs**: steps that execute specific components, with support for inputs, outputs, and dependencies
- **Listeners**: optional callback listeners that handle asynchronous responses from external services
- **Gateways**: optional tunneling services that expose your local controller to the public internet

By default, `model-compose` automatically looks for a file named `model-compose.yml` in the current working directory when running commands like `up` or `run`.

#### 🧪 Minimal Example (with Components and Workflows)

```
controller:
  type: http-server
  port: 8080
  base_path: /api
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
      Content-Type: application/json
    body:
      model: gpt-4o
      messages:
        - role: user
          content: "Write an inspiring quote."
    output:
      quote: ${response.choices[0].message.content}

workflows:
  - id: generate-quote
    default: true
    jobs:
      - id: get-quote
        component: chatgpt
```

This minimal example defines a simple workflow that calls the OpenAI ChatGPT API to generate an inspiring quote.

- The `controller` section starts an HTTP server on port `8080` and enables a Web UI on port `8081`.
- The `components` section defines a reusable HTTP client named `chatgpt` that makes a `POST` request to the OpenAI Chat Completions API. It uses an environment variable `OPENAI_API_KEY` for authentication and extracts the quote from the API response.
- The `workflows` section defines a single workflow called `generate-quote`. It contains one job, `get-quote`, which uses the `chatgpt` component to fetch a quote from the API.
- Since `default: true` is set, the workflow is selected by default if no workflow name is specified during execution.

You can easily expand this example by adding more components (e.g., text-to-speech, image generation) and connecting them through additional jobs.

#### 📡 Listener Example

```
listener:
  type: http-callback
  port: 8090
  base_path: /callbacks
  callbacks:
    - path: /chat-ai
      method: POST
      item: ${body.data}
      identify_by: ${item.task_id}
      result: ${item.choices[0].message.content}
```

This listener sets up an HTTP callback endpoint at `http://localhost:8090/callbacks/chat-ai` to handle asynchronous responses from an external service that behaves like ChatGPT but supports delayed or push-based results. This is useful when integrating with services that notify results via webhook-style callbacks.

#### 🌐 Gateway Example

```
gateway:
  type: http-tunnel
  driver: ngrok
  port: 8090
```

This gateway configuration exposes the local listener defined above to the public internet using an HTTP tunnel powered by ngrok. It forwards incoming traffic from a secure, public URL (e.g., `https://abc123.ngrok.io`) directly to your local callback endpoint at `http://localhost:8090`. This is essential when integrating with third-party services that need to push data back to your workflow via webhooks or asynchronous callbacks.

> 📁 For more example model-compose.yml configurations, check the [examples directory](examples) in the source code.

---
## 🖥 Web UI
**model-compose** optionally provides a lightweight **Web UI** to help you visually trigger workflows, inspect inputs and outputs, and monitor execution logs.

![Screenshots](docs/images/webui.png)

#### ✅ Enabling the Web UI
To enable the Web UI, simply add the `webui` section under your `controller` in the `model-compose.yml` file:
```
controller:
  type: http-server
  port: 8080
  webui:
    port: 8081
```

Once enabled, the Web UI will be available at:
```
http://localhost:8081
```

## 🎨 Custom Web UI
You can fully customize the Web UI experience by specifying a different driver or serving your own frontend.

By default, `model-compose` uses [Gradio](https://www.gradio.app) as the interactive UI. However, if you prefer to use your own static frontend (e.g., a custom React/Vite app), you can switch to the `static` driver.

Here’s how you can do it:

```
controller:
  type: http-server
  port: 8080
  webui:
    driver: static
    static_dir: webui
    port: 8081
```
Your frontend should be a prebuilt static site (e.g., using `vite build`, `next export`, or `react-scripts` build) and placed in the specified `static_dir`.
Make sure `index.html` exists in that directory.

#### 📁 Example Directory Structure
```
project/
├── model-compose.yml
├── webui/
│   ├── index.html
│   ├── assets/
│   └── ...
```

#### 🔧 Notes
* Ensure the `static_dir` path is relative to the project root or an absolute path.
* You can use environment variables inside `model-compose.yml` to make this path configurable.

Support for additional drivers (e.g., `dynamic`) may be added in future versions.

Once configured, the Web UI will be available at:
```
http://localhost:8081
```

---
## 🛰 MCP Server Support
You can also expose your workflows via the **Model Context Protocol (MCP)** server to enable remote execution, automation, or system integration using a lightweight JSON-RPC interface.

#### ✅ Minimal MCP Server Example

```
controller:
  type: mcp-server
  port: 8080
  base_path: /mcp

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: gpt-4o
      messages:
        - role: user
          content: "Write an inspiring quote."
    output:
      quote: ${response.choices[0].message.content}

workflows:
  - id: generate-quote
    default: true
    jobs:
      - id: get-quote
        component: chatgpt
```
This configuration launches the controller as an **MCP server**, which listens on port 8080 and exposes your workflows over a **JSON-RPC API**.

Once running, you can invoke workflows remotely using a standard MCP request:

```
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "callTool",
  "params": {
    "name": "generate-quote",
    "arguments": {}
  }
}
```

You can send this request via any HTTP client to:
```
POST http://localhost:8080/mcp
```

---
## 🐳 Docker Runtime Support
You can run the workflow controller inside a Docker container by specifying the runtime option in your `model-compose.yml` file.

#### ✅ Minimal Docker Runtime Example

```
controller:
  type: http-server
  port: 8080
  runtime: docker
```

This configuration will launch the controller inside a lightweight Docker container automatically managed by **model-compose**. It uses default settings such as container name, image, and volume mappings.

#### ⚙️ Advanced Docker Runtime Options
You can fully configure the Docker runtime by using an object under the `runtime` key:

```
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    image: 192.168.0.23/custom-image:latest
    container_name: my-controller
    volumes:
      - ./models:/models
      - ./cache:/cache
    ports:
      - "5000:8080"
      - "5001:8081"
    env:
      MODEL_STORAGE_PATH: /models
    command: [ "python", "-m", "mindor.cli.compose", "up" ]
    ...
```

This gives you full control over:

- **container_name**: Custom name for the container
- **image**: Docker image to use
- **volumes**: Bind mounts for sharing files between host and container
- **ports**: Port mappings for host ↔ container communication
- **env**: Environment variables to inject
- **command**: Override the default entrypoint
- *and many more*

All of these are optional, allowing you to start simple and customize only what you need.

#### 🐳 Benefits of Docker Runtime

- Run your controller in a clean, isolated environment
- Avoid dependency conflicts with your host Python setup
- Easily deploy your project to remote servers or CI pipelines
- Share reproducible workflows with others

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
