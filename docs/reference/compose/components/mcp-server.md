# MCP Server Component

The MCP (Model Context Protocol) server component enables creating and hosting MCP-compliant servers that expose tools and services for AI agents and other MCP clients. It provides a standardized way to make your services accessible through the Model Context Protocol.

## Basic Configuration

```yaml
component:
  type: mcp-server
  port: 8080
  start: [ python, mcp_server.py ]
  action:
    tool: process-text
    arguments:
      text: ${input.text}
      operation: normalize
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `mcp-server` |
| `port` | integer | `8000` | Port on which the MCP server will listen (1-65535) |
| `base_path` | string | `null` | Base path to prefix all MCP routes exposed by this component |
| `manage` | object | `{}` | Configuration used to manage the MCP server lifecycle |
| `actions` | array | `[]` | List of MCP tool actions |

### Server Management

The `manage` configuration controls server lifecycle:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scripts` | object | `{}` | Shell scripts for server management |
| `working_dir` | string | `null` | Working directory for the scripts |
| `env` | object | `{}` | Environment variables to set when executing scripts |

#### Management Scripts

| Script | Type | Description |
|--------|------|-------------|
| `install` | array | One or more scripts to install dependencies |
| `build` | array | One or more scripts to build the server |
| `clean` | array | One or more scripts to clean the server environment |
| `start` | array | Script to start the server |

### Action Configuration

MCP server actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tool` | string | `__default__` | Name of the tool to expose via the MCP server |
| `arguments` | object | `{}` | Default arguments for the tool |
| `headers` | object | `{}` | Optional HTTP headers to include in tool responses |

## Usage Examples

### Simple MCP Tool Server

```yaml
component:
  type: mcp-server
  port: 8080
  manage:
    scripts:
      start: [ python, text_processor.py ]
    working_dir: ./mcp-tools
    env:
      MCP_PORT: 8080
  action:
    tool: process-text
    arguments:
      text: ${input.text}
      operation: ${input.operation | normalize}
    output:
      result: ${response.processed_text}
```

### Multi-Tool MCP Server

```yaml
component:
  type: mcp-server
  port: 9000
  base_path: /tools
  manage:
    scripts:
      install: [ pip, install, -r, requirements.txt ]
      start: [ python, -m, mcp_toolkit.server ]
    working_dir: ./toolkit
    env:
      DATABASE_URL: ${env.DATABASE_URL}
      API_KEY: ${env.TOOLKIT_API_KEY}
  actions:
    - id: file-operations
      tool: file-manager
      arguments:
        operation: ${input.file_operation}
        path: ${input.file_path}
        content: ${input.file_content}
      headers:
        Content-Type: application/json
      output:
        success: ${response.success}
        data: ${response.data}
        
    - id: database-query
      tool: db-query
      arguments:
        query: ${input.sql_query}
        parameters: ${input.query_params}
      output:
        rows: ${response.rows}
        affected: ${response.affected_rows}
        
    - id: text-analysis
      tool: analyze-text
      arguments:
        text: ${input.text}
        analysis_type: ${input.type | sentiment}
      output:
        result: ${response.analysis_result}
        confidence: ${response.confidence_score}
```

### Docker-Based MCP Server

```yaml
component:
  type: mcp-server
  port: 8080
  manage:
    scripts:
      build: 
        - [ docker, build, -t, mcp-ml-server, . ]
        - [ docker, network, create, mcp-network ]
      clean: 
        - [ docker, stop, mcp-ml-server ]
        - [ docker, network, rm, mcp-network ]
      start: [ docker, run, -d, -p, 8080:8080, --network, mcp-network, mcp-ml-server ]
    working_dir: ./ml-server
    env:
      MODEL_PATH: /models/trained_model.pkl
      CUDA_VISIBLE_DEVICES: 0
  actions:
    - id: image-classify
      tool: classify-image
      arguments:
        image_data: ${input.image_base64}
        model: ${input.model_name | resnet50}
        top_k: ${input.top_results as integer | 5}
      output:
        predictions: ${response.predictions}
        probabilities: ${response.probabilities}
        
    - id: text-generate
      tool: generate-text
      arguments:
        prompt: ${input.prompt}
        max_tokens: ${input.max_length as integer | 100}
        temperature: ${input.creativity as float | 0.7}
      output:
        generated_text: ${response.text}
        token_count: ${response.tokens_used}
```

### File System MCP Server

```yaml
component:
  type: mcp-server
  port: 3000
  base_path: /filesystem
  manage:
    scripts:
      start: [ node, filesystem-mcp-server.js ]
    working_dir: ./fs-server
    env:
      ALLOWED_PATHS: /home/user/documents,/tmp
      MAX_FILE_SIZE: 10MB
  actions:
    - id: read-file
      tool: read-file
      arguments:
        path: ${input.file_path}
        encoding: ${input.encoding | utf-8}
      output:
        content: ${response.file_content}
        size: ${response.file_size}
        modified: ${response.last_modified}
        
    - id: write-file
      tool: write-file
      arguments:
        path: ${input.file_path}
        content: ${input.content}
        encoding: ${input.encoding | utf-8}
        create_dirs: ${input.create_directories as boolean | true}
      output:
        success: ${response.written}
        bytes: ${response.bytes_written}
        
    - id: list-directory
      tool: list-files
      arguments:
        directory: ${input.dir_path}
        recursive: ${input.recursive as boolean | false}
        include_hidden: ${input.show_hidden as boolean | false}
      output:
        files: ${response.file_list}
        directories: ${response.dir_list}
        total_count: ${response.item_count}
```

## Server Lifecycle Management

### Installation and Dependencies

```yaml
manage:
  scripts:
    install:
      - [ pip, install, mcp-toolkit>=1.0.0 ]
      - [ pip, install, -r, requirements.txt ]
      - [ npm, install, "@mcp/server-sdk" ]
  working_dir: ./server
```

### Build Process

```yaml
manage:
  scripts:
    build:
      - [ npm, run, build ]
      - [ python, setup.py, build ]
    clean: [ rm, -rf, dist, build, node_modules ]
    start: [ node, dist/server.js ]
```

### Environment Configuration

```yaml
manage:
  env:
    MCP_SERVER_NAME: MyCustomServer
    MCP_SERVER_VERSION: 1.0.0
    LOG_LEVEL: info
    DATABASE_URL: ${env.DATABASE_URL}
    API_KEYS: ${env.EXTERNAL_API_KEYS}
  working_dir: ./mcp-server
```

## Tool Categories and Examples

### Data Processing Tools

```yaml
actions:
  - id: transform-data
    tool: data-transformer
    arguments:
      data: ${input.raw_data}
      transformations: ${input.transform_list}
      output_format: ${input.format | json}
    
  - id: validate-data
    tool: data-validator
    arguments:
      data: ${input.data}
      schema: ${input.validation_schema}
    output:
      valid: ${response.is_valid}
      errors: ${response.validation_errors}
```

### System Administration Tools

```yaml
actions:
  - id: system-info
    tool: get-system-info
    output:
      cpu_usage: ${response.cpu_percent}
      memory_usage: ${response.memory_percent}
      disk_usage: ${response.disk_usage}
    
  - id: process-management
    tool: manage-process
    arguments:
      action: ${input.action}  # start, stop, restart, status
      process_name: ${input.process}
    output:
      status: ${response.process_status}
      pid: ${response.process_id}
```

### API Integration Tools

```yaml
actions:
  - id: external-api-call
    tool: api-client
    arguments:
      endpoint: ${input.api_endpoint}
      method: ${input.http_method | GET}
      headers: ${input.request_headers}
      body: ${input.request_body}
    output:
      response_data: ${response.data}
      status_code: ${response.status}
      response_time: ${response.elapsed_ms}
```

## Authentication and Security

### Access Control

```yaml
component:
  type: mcp-server
  port: 8080
  headers:
    X-API-Version: 1.0
    Access-Control-Allow-Origin: "*"
  actions:
    - id: secure-operation
      tool: protected-tool
      headers:
        Authorization: required
        X-Client-ID: ${input.client_id}
      arguments:
        data: ${input.secure_data}
```

### Rate Limiting and Validation

```yaml
manage:
  env:
    RATE_LIMIT_PER_MINUTE: 100
    MAX_PAYLOAD_SIZE: 1MB
    ALLOWED_ORIGINS: localhost,myapp.com
```

## Integration Patterns

### As a Service Backend

```yaml
controller:
  type: mcp-server
  port: 8080
  base_path: /mcp

component:
  type: mcp-server
  port: 8080
  actions:
    - id: service-a
      tool: process-request
      arguments:
        service: service_a
        payload: ${input}
    
    - id: service-b
      tool: process-request
      arguments:
        service: service_b
        payload: ${input}
```

### Database Service Layer

```yaml
component:
  type: mcp-server
  port: 5432
  manage:
    scripts:
      start: [ python, db_mcp_server.py ]
    env:
      DB_CONNECTION: ${env.DATABASE_URL}
  actions:
    - id: query
      tool: execute-query
    - id: insert
      tool: execute-insert
    - id: update
      tool: execute-update
    - id: delete
      tool: execute-delete
```

### Microservice Architecture

```yaml
components:
  - id: auth-service
    type: mcp-server
    port: 8001
    base_path: /auth
    
  - id: data-service
    type: mcp-server
    port: 8002
    base_path: /data
    
  - id: notification-service
    type: mcp-server
    port: 8003
    base_path: /notify
```

## Error Handling and Monitoring

### Server Health Checks

```yaml
actions:
  - id: health-check
    tool: server-health
    output:
      status: ${response.health_status}
      uptime: ${response.server_uptime}
      version: ${response.server_version}
```

### Error Reporting

```yaml
manage:
  env:
    ERROR_REPORTING_ENDPOINT: ${env.ERROR_WEBHOOK_URL}
    LOG_ERRORS_TO_FILE: true
    ERROR_LOG_PATH: /var/log/mcp-server-errors.log
```

## Variable Interpolation

MCP server supports dynamic configuration:

```yaml
component:
  type: mcp-server
  port: ${env.MCP_PORT as integer | 8080}
  base_path: /api/${env.API_VERSION | v1}
  action:
    tool: ${input.tool_name}
    arguments:
      param1: ${input.value1}
      param2: ${input.value2 as number}
      timestamp: ${now}
    headers:
      X-Request-ID: ${generate_uuid}
```

## Best Practices

1. **Tool Documentation**: Provide clear descriptions for all exposed tools
2. **Error Handling**: Implement comprehensive error handling and reporting
3. **Security**: Validate all inputs and implement proper authentication
4. **Performance**: Monitor resource usage and implement appropriate limits
5. **Logging**: Log all tool invocations for debugging and auditing
6. **Versioning**: Version your MCP server and tools appropriately
7. **Dependencies**: Manage server dependencies and startup requirements
8. **Graceful Shutdown**: Implement proper cleanup on server shutdown

## Integration with Workflows

Reference MCP server in workflow jobs:

```yaml
workflow:
  jobs:
    - id: start-mcp-server
      component: my-mcp-server
      action: health-check
      
    - id: process-data
      component: my-mcp-server
      action: transform-data
      input:
        data: ${input.raw_data}
        
    - id: validate-result
      component: my-mcp-server
      action: validate-data
      input:
        data: ${process-data.output.result}
```

## Common Use Cases

- **AI Model Serving**: Expose machine learning models as MCP tools
- **Database Abstraction**: Provide standardized database access
- **File System Operations**: Enable file system access through MCP
- **API Gateway**: Create unified access to multiple backend services
- **Data Processing Pipeline**: Expose data transformation tools
- **System Administration**: Provide system management capabilities
- **Custom Business Logic**: Expose domain-specific operations
- **Integration Hub**: Centralize access to external services

## MCP Protocol Compliance

MCP servers must implement:

- **Tool Registration**: Register available tools and their schemas
- **Tool Execution**: Execute tools with proper parameter validation
- **Error Responses**: Return standardized error information
- **Resource Management**: Handle concurrent requests appropriately
- **Protocol Versioning**: Support MCP protocol version negotiation