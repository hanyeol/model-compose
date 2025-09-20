# Model-Compose Configuration Reference

This reference guide provides comprehensive documentation for all configuration options in model-compose. Use this as your authoritative source for YAML configuration syntax, available options, and usage patterns.

## Quick Navigation

### Core Configuration
- [Controller](compose/controller.md) - HTTP and MCP server configuration
- [Workflow](compose/workflow.md) - Job orchestration and execution logic
- [Component](compose/component.md) - Reusable service definitions and common properties

### Infrastructure & Services
- [Listener](compose/listener.md) - Webhook and callback handling
- [Gateway](compose/gateway.md) - Tunneling and external access
- [Logger](compose/logger.md) - Logging configuration and output management

### Components
- [HTTP Client](compose/components/http-client.md) - External API integration
- [HTTP Server](compose/components/http-server.md) - Web server hosting
- [MCP Client](compose/components/mcp-client.md) - Model Context Protocol client
- [MCP Server](compose/components/mcp-server.md) - Model Context Protocol server
- [Model](compose/components/model.md) - AI/ML model inference
- [Vector Store](compose/components/vector-store.md) - Vector database operations
- [Shell](compose/components/shell.md) - System command execution
- [Text Splitter](compose/components/text-splitter.md) - Document processing
- [Workflow](compose/components/workflow.md) - Nested workflow execution

## Configuration Structure Overview

A complete model-compose.yml file typically includes these top-level sections:

```yaml
# Server configuration
controller:
  type: http-server | mcp-server
  # ... controller settings

# Workflow definitions
workflow:  # or workflows: for multiple
  # ... workflow configuration

# Component definitions  
component:  # or components: for multiple
  # ... component configuration

# Infrastructure services (optional)
listener:   # or listeners: for multiple
  # ... listener configuration
  
gateway:    # or gateways: for multiple  
  # ... gateway configuration

logger:     # or loggers: for multiple
  # ... logging configuration
```

## Configuration Patterns

### Single vs Multiple Definitions

Most configuration sections support both singular and plural forms:

```yaml
# Single definition
controller:
  type: http-server
  port: 8080

# Multiple definitions  
components:
  - id: api-client
    type: http-client
  - id: local-model
    type: model
```

### Variable Interpolation

All configuration sections support dynamic values through variable interpolation:

- **Environment Variables**: `${env.API_KEY}`
- **Input Data**: `${input.field}`  
- **Job Results**: `${job-name.output}`
- **Type Conversion**: `${input.count as number}`
- **Default Values**: `${input.optional | default}`

### Common Properties

Many configuration objects share common properties:

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `id` | string | varies | Unique identifier |
| `type` | string | required | Configuration type |
| `runtime` | string | `native` | Runtime environment (`native` or `docker`) |
| `max_concurrent_count` | integer | varies | Maximum concurrent operations |

## Getting Started

1. **Choose Your Controller**: Start with [Controller](compose/controller.md) to set up your server
2. **Define Your Workflow**: Use [Workflow](compose/workflow.md) to orchestrate your logic
3. **Add Components**: Select from [Component](compose/component.md) types for your functionality
4. **Configure Infrastructure**: Add [Listener](compose/listener.md), [Gateway](compose/gateway.md), or [Logger](compose/logger.md) as needed

## Examples Directory

For working examples of these configurations, see the `examples/` directory in the repository:

- `examples/openai-chat-completions/` - Simple HTTP client workflow
- `examples/make-inspiring-quote-voice/` - Multi-step workflow with dependencies
- `examples/model-tasks/` - Various local model configurations
- `examples/vector-store/` - Vector database usage patterns
- `examples/mcp-servers/` - MCP server implementations

## Configuration Validation

Model-compose validates all configuration at startup. Common validation errors include:

- **Missing required fields**: Ensure all required properties are specified
- **Invalid types**: Check data types match expected values (string, integer, boolean)
- **Invalid references**: Verify component IDs and job names exist
- **Conflicting options**: Some fields are mutually exclusive (e.g., `endpoint` vs `path`)

## Best Practices

1. **Environment Variables**: Store sensitive data like API keys in environment variables
2. **Descriptive IDs**: Use clear, descriptive names for components, jobs, and workflows
3. **Modular Design**: Break complex configurations into smaller, reusable pieces  
4. **Documentation**: Use `title` and `description` fields to document your configurations
5. **Version Control**: Keep your model-compose.yml files in version control
6. **Testing**: Test configurations with different input scenarios

## Need Help?

- **Issues**: Report problems at [GitHub Issues](https://github.com/anthropics/claude-code/issues)
- **Examples**: Browse the `examples/` directory for working configurations
- **Field Definitions**: Check the source code for detailed field definitions and constraints