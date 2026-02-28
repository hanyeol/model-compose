# MCP Client Component

The MCP (Model Context Protocol) client component enables invoking tools and services from external MCP servers. MCP is a standardized protocol for AI agents to interact with external tools, databases, and services in a consistent way.

## Basic Configuration

```yaml
component:
  type: mcp-client
  url: http://localhost:8080/mcp
  action:
    tool: list-files
    arguments:
      directory: ${input.path}
    headers:
      Authorization: Bearer ${env.MCP_TOKEN}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `mcp-client` |
| `url` | string | **required** | URL of the MCP server to invoke tools |
| `headers` | object | `{}` | HTTP headers to include when connecting to the MCP server |
| `actions` | array | `[]` | List of MCP tool actions |

### Action Configuration

MCP client actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tool` | string | `__default__` | Name of the tool to invoke on the MCP server |
| `arguments` | object | `{}` | Arguments to pass to the tool |
| `headers` | object | `{}` | Optional HTTP headers to include in the tool call |

## Usage Examples

### Simple Tool Invocation

```yaml
component:
  type: mcp-client
  url: http://localhost:8080/mcp
  action:
    tool: get-weather
    arguments:
      location: ${input.city}
      units: metric
    output:
      temperature: ${response.current.temp}
      condition: ${response.current.condition}
```

### File System Operations

```yaml
component:
  type: mcp-client
  url: http://localhost:3000/mcp
  headers:
    Authorization: Bearer ${env.FILE_SERVER_TOKEN}
  actions:
    - id: list-files
      tool: list-directory
      arguments:
        path: ${input.directory}
        recursive: false
      output:
        files: ${response.files}
        
    - id: read-file
      tool: read-file
      arguments:
        path: ${input.file_path}
      output:
        content: ${response.content}
        encoding: ${response.encoding}
        
    - id: write-file
      tool: write-file
      arguments:
        path: ${input.output_path}
        content: ${input.file_content}
        encoding: utf-8
      output:
        success: ${response.success}
        bytes_written: ${response.bytes_written}
```

### Database Operations

```yaml
component:
  type: mcp-client
  url: http://database-server:8080/mcp
  headers:
    Authorization: Bearer ${env.DB_ACCESS_TOKEN}
  actions:
    - id: query-users
      tool: execute-query
      arguments:
        sql: SELECT * FROM users WHERE active = ?
        parameters: [ true ]
      output:
        users: ${response.rows}
        count: ${response.row_count}
        
    - id: create-user
      tool: execute-insert
      arguments:
        table: users
        data:
          name: ${input.user_name}
          email: ${input.user_email}
          created_at: ${now}
      output:
        user_id: ${response.inserted_id}
        success: ${response.success}
```

### API Gateway Pattern

```yaml
component:
  type: mcp-client
  url: http://api-gateway:9000/mcp
  headers:
    X-API-Key: ${env.GATEWAY_API_KEY}
    Content-Type: application/json
  actions:
    - id: send-notification
      tool: send-email
      arguments:
        to: ${input.recipient}
        subject: ${input.subject}
        body: ${input.message}
        template: notification
      output:
        message_id: ${response.message_id}
        status: ${response.delivery_status}
        
    - id: log-event
      tool: create-log-entry
      arguments:
        level: info
        message: ${input.log_message}
        metadata:
          user_id: ${input.user_id}
          session_id: ${input.session_id}
          timestamp: ${now}
      output:
        log_id: ${response.log_id}
```

### Machine Learning Tools

```yaml
component:
  type: mcp-client
  url: http://ml-server:8080/mcp
  headers:
    Authorization: Bearer ${env.ML_API_TOKEN}
  actions:
    - id: image-classification
      tool: classify-image
      arguments:
        image_url: ${input.image_url}
        model: resnet50
        top_k: 5
      output:
        predictions: ${response.predictions}
        confidence_scores: ${response.scores}
        
    - id: text-sentiment
      tool: analyze-sentiment
      arguments:
        text: ${input.text}
        language: en
      output:
        sentiment: ${response.sentiment}
        confidence: ${response.confidence}
        scores: ${response.detailed_scores}
```

## Authentication Patterns

### Bearer Token

```yaml
headers:
  Authorization: Bearer ${env.MCP_TOKEN}
```

### API Key

```yaml
headers:
  X-API-Key: ${env.MCP_API_KEY}
```

### Custom Authentication

```yaml
headers:
  X-Auth-Token: ${env.MCP_AUTH_TOKEN}
  X-Client-ID: ${env.CLIENT_ID}
```

## Tool Discovery and Validation

MCP clients can discover available tools from servers:

```yaml
component:
  type: mcp-client
  url: http://localhost:8080/mcp
  actions:
    - id: list-tools
      tool: __list_tools__
      output:
        available_tools: ${response.tools}
        
    - id: describe-tool
      tool: __describe_tool__
      arguments:
        tool_name: ${input.tool_name}
      output:
        description: ${response.description}
        parameters: ${response.parameters}
        examples: ${response.examples}
```

## Error Handling

MCP client handles various error conditions:

### Connection Errors

- **Server Unavailable**: Component fails if MCP server is unreachable
- **Authentication Failed**: Invalid credentials result in workflow failure
- **Network Timeouts**: Configurable timeout handling

### Tool Execution Errors

```yaml
component:
  type: mcp-client
  url: http://localhost:8080/mcp
  action:
    tool: risky-operation
    arguments:
      data: ${input.data}
    # Tool errors are propagated as workflow failures
    # Use workflow error handling to manage failures
```

## Variable Interpolation

MCP client supports dynamic configuration:

```yaml
component:
  type: mcp-client
  url: ${env.MCP_SERVER_URL}
  action:
    tool: ${input.operation_type}
    arguments:
      param1: ${input.value1}
      param2: ${input.value2 as number}
      param3: ${input.flag as boolean | false}
    headers:
      X-Request-ID: ${generate_uuid}
      X-Timestamp: ${now}
```

## Best Practices

1. **Service Discovery**: Use tool discovery to understand available capabilities
2. **Error Handling**: Implement proper error handling for network and tool failures
3. **Authentication**: Store sensitive credentials in environment variables
4. **Timeouts**: Configure appropriate timeout values for long-running tools
5. **Validation**: Validate tool arguments before making calls
6. **Logging**: Log tool invocations for debugging and monitoring
7. **Resource Management**: Be mindful of rate limits and resource usage

## Integration with Workflows

Reference MCP client in workflow jobs:

```yaml
workflow:
  jobs:
    - id: discover-tools
      component: mcp-client
      action: list-tools
      
    - id: process-data
      component: mcp-client
      action: transform-data
      input:
        data: ${input.raw_data}
        transformation: normalize
        
    - id: store-result
      component: mcp-client
      action: save-to-database
      input:
        table: processed_data
        records: ${process-data.output.result}
```

## Common Tool Categories

### File System Tools

- `read-file`: Read file contents
- `write-file`: Write data to files
- `list-directory`: List directory contents
- `create-directory`: Create directories
- `delete-file`: Remove files

### Database Tools

- `execute-query`: Run SQL queries
- `execute-insert`: Insert records
- `execute-update`: Update records
- `execute-delete`: Delete records
- `get-schema`: Retrieve table schema

### HTTP Tools

- `make-request`: Perform HTTP requests
- `download-file`: Download files from URLs
- `upload-file`: Upload files to endpoints

### System Tools

- `execute-command`: Run system commands
- `get-environment`: Retrieve environment variables
- `check-process`: Monitor process status

### AI/ML Tools

- `text-generation`: Generate text using language models
- `image-classification`: Classify images
- `sentiment-analysis`: Analyze text sentiment
- `translation`: Translate text between languages

## MCP Protocol Standards

The Model Context Protocol defines standard interfaces for:

- **Tool Discovery**: Enumerate available tools and their schemas
- **Tool Execution**: Invoke tools with typed parameters
- **Resource Management**: Access files, databases, and external services
- **Session Management**: Maintain context across tool calls
- **Error Reporting**: Standardized error responses and handling

## Common Use Cases

- **External Service Integration**: Connect to third-party APIs and services
- **Database Operations**: Perform CRUD operations on databases
- **File System Access**: Read, write, and manage files
- **System Administration**: Execute system commands and scripts
- **AI/ML Model Inference**: Run predictions using external models
- **Data Processing**: Transform and validate data using external tools
- **Notification Services**: Send emails, SMS, and push notifications