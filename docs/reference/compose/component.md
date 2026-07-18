# Component Configuration Reference

Components are reusable service definitions that perform specific tasks within workflows. They encapsulate functionality such as HTTP requests, AI model inference, data processing, and external service integration.

## Basic Structure

### Single Component

```yaml
component:
  type: agent | http-client | http-server | websocket-client | websocket-server | mcp-server | mcp-client | model | model-memory | model-tokenizer | model-trainer | datasets | vector-store | graph-store | search-engine | key-value-store | file-store | workflow | shell | text-splitter | image-processor | video-scene-detector | video-converter | video-frame-extractor | audio-extractor | audio-converter | audio-feature-extractor | web-scraper | web-browser | screen-capture
  id: component-id
  runtime: native | embedded | process | virtualenv | docker | apple-container  # default: native
  max_concurrent_count: 0
  default: false
  # ... type-specific configuration
```

### Multiple Components

```yaml
components:
  - id: api-client
    type: http-client
    base_url: https://api.example.com
    
  - id: local-model
    type: model
    model: microsoft/DialoGPT-medium
    
  - id: data-processor
    type: shell
    command: python process.py
```

## Component Types

Model-compose supports the following component types:

| Type | Description | Documentation |
|------|-------------|---------------|
| `agent` | Autonomous AI agent with tool use | [agent.md](components/agent.md) |
| `http-client` | HTTP client for making API requests | [http-client.md](components/http-client.md) |
| `http-server` | HTTP server for hosting services | [http-server.md](components/http-server.md) |
| `websocket-client` | WebSocket client for real-time connections | [websocket-client.md](components/websocket-client.md) |
| `websocket-server` | WebSocket server for real-time services | [websocket-server.md](components/websocket-server.md) |
| `mcp-server` | MCP server for protocol support | [mcp-server.md](components/mcp-server.md) |
| `mcp-client` | MCP (Model Context Protocol) client | [mcp-client.md](components/mcp-client.md) |
| `model` | AI model inference (local/remote) | [model.md](components/model.md) |
| `model-memory` | Session-based conversation memory | [model-memory.md](components/model-memory.md) |
| `model-tokenizer` | Model tokenization (encode, decode, count) | [model-tokenizer.md](components/model-tokenizer.md) |
| `model-trainer` | Model fine-tuning (SFT, classification, LoRA) | [model-trainer.md](components/model-trainer.md) |
| `datasets` | Dataset loading and transformation | [datasets.md](components/datasets.md) |
| `vector-store` | Vector database operations | [vector-store.md](components/vector-store.md) |
| `graph-store` | Graph database operations | [graph-store.md](components/graph-store.md) |
| `search-engine` | Full-text search engine (SQLite FTS5) | [search-engine.md](components/search-engine.md) |
| `key-value-store` | Key-value data storage | [key-value-store.md](components/key-value-store.md) |
| `file-store` | File/object storage (local, AWS S3, GCP Storage, Azure Blob) | [file-store.md](components/file-store.md) |
| `workflow` | Sub-workflow execution | [workflow.md](components/workflow.md) |
| `shell` | Shell command execution | [shell.md](components/shell.md) |
| `text-splitter` | Text processing and splitting | [text-splitter.md](components/text-splitter.md) |
| `image-processor` | Image transformation and processing | [image-processor.md](components/image-processor.md) |
| `video-scene-detector` | Video scene change detection | [video-scene-detector.md](components/video-scene-detector.md) |
| `video-converter` | Video format/codec conversion | [video-converter.md](components/video-converter.md) |
| `video-frame-extractor` | Decode video and extract frames as images | [video-frame-extractor.md](components/video-frame-extractor.md) |
| `audio-extractor` | Extract audio streams from media | [audio-extractor.md](components/audio-extractor.md) |
| `audio-converter` | Audio format/codec conversion | [audio-converter.md](components/audio-converter.md) |
| `audio-feature-extractor` | Per-frame audio features for visualization (spectrum, waveform) | [audio-feature-extractor.md](components/audio-feature-extractor.md) |
| `web-scraper` | Web page scraping with CSS/XPath | [web-scraper.md](components/web-scraper.md) |
| `web-browser` | Browser automation via Chrome DevTools Protocol | [web-browser.md](components/web-browser.md) |
| `screen-capture` | Live screen and system/microphone audio capture as continuous streams | [screen-capture.md](components/screen-capture.md) |

## Common Configuration Properties

All components inherit these common properties from `CommonComponentConfig`:

### Core Properties

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | `__component__` | Unique identifier for the component |
| `type` | string | **required** | Component type (see table above) |
| `runtime` | string | `native` | Runtime environment: `native`, `embedded`, `process`, `virtualenv`, `docker`, or `apple-container` |
| `max_concurrent_count` | integer | `0` | Maximum concurrent actions this component can handle (`0` = unlimited) |
| `default` | boolean | `false` | Whether to use this component when none is explicitly specified |

### Actions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `action` | object | - | Single action definition for the component (shorthand for single-action components) |
| `actions` | array | `[]` | List of actions available within this component (for multi-action components) |

Components can define a single action using `action:` (singular) or multiple actions using `actions:` (plural). This is consistent with the `component:` / `components:` pattern used elsewhere.

## Component Usage Patterns

### Single Action Component

For simple components with one primary action, wrap the action-specific fields under `action:`:

```yaml
component:
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

### Multi-Action Component

For components supporting multiple operations:

```yaml
component:
  type: http-client
  base_url: https://api.slack.com
  actions:
    - id: send-message
      path: /chat.postMessage
      method: POST
      body:
        channel: ${input.channel}
        text: ${input.text}
        
    - id: list-channels
      path: /conversations.list
      method: GET
      params:
        limit: 200
```

### Default Component

Mark a component as default to use it when no specific component is referenced:

```yaml
components:
  - id: primary-model
    type: model
    model: gpt-4o
    default: true
    
  - id: backup-model
    type: model
    model: gpt-3.5-turbo
```

## Runtime Configuration

Components can run in different runtime environments. The runtime determines where and how the component executes.

### Embedded Runtime (Default)

The default runtime that executes components in the current process.

```yaml
component:
  type: model
  runtime: embedded  # or omit this line (embedded is default)
  model: microsoft/DialoGPT-medium
```

**Characteristics:**
- Runs in the same process as the controller
- Fastest startup time and lowest overhead
- Shares memory space with the main application
- Best for lightweight tasks and quick operations

**Use Cases:**
- Simple API calls and HTTP requests
- Lightweight data transformations
- Quick model inference with small models
- Components that need fast response times

### Process Runtime

Runs components in separate Python processes for process isolation while maintaining faster startup than Docker.

```yaml
component:
  type: model
  runtime: process
  model: meta-llama/Llama-3.1-70B
```

**Characteristics:**
- Runs in a separate Python process
- Process-level memory and resource isolation
- Faster startup than Docker, slower than embedded
- Independent crash handling (one component crash won't affect others)

**Use Cases:**
- Heavy models that could consume significant memory
- Multiple GPU utilization (separate processes for each GPU)
- Blocking operations that shouldn't block the main event loop
- Components that need isolation but don't require containers

**Advanced Configuration:**

```yaml
component:
  type: model
  runtime:
    type: process
    env:
      CUDA_VISIBLE_DEVICES: "0"
      PYTORCH_CUDA_ALLOC_CONF: "max_split_size_mb:512"
    start_timeout: 120
    stop_timeout: 30
  model: stabilityai/stable-diffusion-xl-base-1.0
```

### Virtualenv Runtime

Runs components inside an isolated Python virtual environment, giving each component its own dependency stack without containerization.

```yaml
component:
  type: shell
  runtime: virtualenv
  command: [python, train.py]
```

**Characteristics:**
- Creates a per-component venv at `.runtime/components/<id>/venv` (configurable)
- Injects the host's `mindor` source and installs `requirements.txt` into the venv
- Reinjection is skipped automatically when the host `mindor` version is unchanged
- Worker runs on the venv's Python interpreter and communicates with the parent over a pipe-based JSON channel

**Use Cases:**
- Components that need a specific Python version (via `pyenv`)
- Components with conflicting Python package requirements
- Lighter-weight isolation than Docker, with dependency separation

**Advanced Configuration:**

```yaml
component:
  type: shell
  runtime:
    type: virtualenv
    driver: pyenv          # 'python' (current interpreter) or 'pyenv' (specific version)
    python: "3.12.0"       # required when driver is 'pyenv'
    path: .venv/training   # custom venv directory (default: .runtime/components/<id>/venv)
    env:
      CUDA_VISIBLE_DEVICES: "0"
    start_timeout: 300s
    stop_timeout: 30s
  command: [python, train.py]
```

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | `python` | `python` uses the current interpreter; `pyenv` uses a pyenv-managed version |
| `python` | string | - | Python version (pyenv driver only, e.g. `3.12.0`) |
| `path` | string | - | Virtualenv directory (relative to CWD); defaults to `.runtime/components/<id>/venv` |
| `env` | object | `{}` | Environment variables for the worker subprocess |
| `start_timeout` | string \| number | `60s` | Worker start timeout |
| `stop_timeout` | string \| number | `30s` | Worker stop timeout |

The venv directory contains a `mindor/.version` marker recording the injected mindor version; matching versions skip reinjection on subsequent starts. To force a clean reinstall, delete the venv directory.

### Docker Runtime

Runs components in isolated Docker containers for enhanced security and reproducibility.

```yaml
component:
  type: model
  runtime: docker
  model: meta-llama/Llama-3.1-70B
```

**Characteristics:**
- Complete process and resource isolation
- Reproducible environment across deployments
- Better security through containerization
- Higher startup overhead

**Use Cases:**
- Production deployments requiring isolation
- Large models that need resource limits
- Components with specific dependency requirements
- Multi-tenant scenarios requiring security

### Choosing a Runtime

| Runtime | Startup Speed | Isolation | Overhead | Best For |
|---------|--------------|-----------|----------|----------|
| **embedded** | Fast | None | Minimal | Default choice, lightweight tasks |
| **process** | Medium | Process | Medium | Heavy models, GPU isolation, crash isolation |
| **virtualenv** | Medium (slow first run) | Process + dependencies | Medium | Per-component Python versions or conflicting packages |
| **docker** | Slow | High | High | Production, security-critical workloads |

## Concurrency Control

Control how many actions can run simultaneously:

```yaml
component:
  type: http-client
  max_concurrent_count: 5
  base_url: https://api.example.com
```

This allows up to 5 concurrent HTTP requests from this component.

## Component Lifecycle

Components follow this lifecycle:

1. **Initialization**: Component is created and configured
2. **Setup**: Runtime environment is prepared (Docker images pulled, dependencies installed)
3. **Ready**: Component is available to handle actions
4. **Execution**: Actions are processed according to workflow requirements
5. **Shutdown**: Component resources are cleaned up

## Integration with Workflows

Components are referenced in workflows through jobs:

```yaml
workflow:
  jobs:
    - id: api-call
      component: http-client-id
      action: post-data
      input:
        data: ${input.payload}
        
    - id: process-result
      component: shell-processor
      input:
        result: ${api-call.output}
```

## Variable Interpolation

Components support dynamic configuration through variable interpolation:

- **Environment Variables**: `${env.API_KEY}`
- **Input Data**: `${input.field}`
- **Previous Results**: `${previous-job.output}`
- **Type Conversion**: `${input.count as number}`
- **Default Values**: `${input.optional | default-value}`

## Error Handling

Components can be configured with error handling strategies:

```yaml
component:
  type: http-client
  retry_count: 3
  timeout: 30
  base_url: https://api.example.com
```

## Security Considerations

- **Credentials**: Store sensitive data in environment variables
- **Network**: Use HTTPS endpoints when possible
- **Isolation**: Consider Docker runtime for untrusted code execution
- **Access Control**: Limit file system access and network permissions

## Best Practices

1. **Naming**: Use descriptive component IDs that indicate their purpose
2. **Modularity**: Design components for specific, well-defined tasks
3. **Reusability**: Create generic components that can be used across workflows
4. **Configuration**: Use environment variables for deployment-specific settings
5. **Documentation**: Document custom actions and expected inputs/outputs
6. **Error Handling**: Implement appropriate retry and timeout strategies
7. **Resource Management**: Set appropriate concurrency limits for resource-intensive operations

## Next Steps

- Browse individual component documentation in the [components/](components/) directory
- See [workflow.md](workflow.md) for information on using components in workflows
- Check [examples/](../../examples/) for real-world component configurations