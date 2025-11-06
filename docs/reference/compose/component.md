# Component Configuration Reference

Components are reusable service definitions that perform specific tasks within workflows. They encapsulate functionality such as HTTP requests, AI model inference, data processing, and external service integration.

## Basic Structure

### Single Component

```yaml
component:
  type: http-client | http-server | model | vector-store | shell | workflow | mcp-client | mcp-server | text-splitter
  id: component-id
  runtime: embedded | docker  # default: embedded
  max_concurrent_count: 1
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
| `http-client` | HTTP client for making API requests | [http-client.md](components/http-client.md) |
| `http-server` | HTTP server for hosting services | [http-server.md](components/http-server.md) |
| `mcp-client` | MCP (Model Context Protocol) client | [mcp-client.md](components/mcp-client.md) |
| `mcp-server` | MCP server for protocol support | [mcp-server.md](components/mcp-server.md) |
| `model` | AI model inference (local/remote) | [model.md](components/model.md) |
| `vector-store` | Vector database operations | [vector-store.md](components/vector-store.md) |
| `workflow` | Sub-workflow execution | [workflow.md](components/workflow.md) |
| `shell` | Shell command execution | [shell.md](components/shell.md) |
| `text-splitter` | Text processing and splitting | [text-splitter.md](components/text-splitter.md) |

## Common Configuration Properties

All components inherit these common properties from `CommonComponentConfig`:

### Core Properties

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | `__default__` | Unique identifier for the component |
| `type` | string | **required** | Component type (see table above) |
| `runtime` | string | `embedded` | Runtime environment: `embedded` or `docker` |
| `max_concurrent_count` | integer | `1` | Maximum concurrent actions this component can handle |
| `default` | boolean | `false` | Whether to use this component when none is explicitly specified |

### Actions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `actions` | array | `[]` | List of actions available within this component |

Components can define multiple actions, each with specific configurations for different operations.

## Component Usage Patterns

### Single Action Component

For simple components with one primary action:

```yaml
component:
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