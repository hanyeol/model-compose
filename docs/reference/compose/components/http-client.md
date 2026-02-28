# HTTP Client Component

The HTTP client component enables making HTTP requests to external APIs and services. It supports various HTTP methods, authentication, streaming responses, and asynchronous completion handling.

## Basic Configuration

```yaml
component:
  type: http-client
  base_url: https://api.example.com
  headers:
    Authorization: Bearer ${env.API_KEY}
    Content-Type: application/json
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `http-client` |
| `base_url` | string | `null` | Base URL for HTTP requests |
| `headers` | object | `{}` | Default HTTP headers to include in all requests |

### Action Configuration

HTTP client actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `endpoint` | string | `null` | Full URL endpoint (mutually exclusive with `path`) |
| `path` | string | `null` | URL path to append to `base_url` (mutually exclusive with `endpoint`) |
| `method` | string | `POST` | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH` |
| `headers` | object | `{}` | HTTP headers to include in the request |
| `body` | object | `{}` | Request body data |
| `params` | object | `{}` | URL query parameters |
| `stream_format` | string | `null` | Stream format: `server-sent-events`, `json-lines` |
| `completion` | object | `null` | Asynchronous completion configuration |

## Usage Examples

### Simple API Call

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  action:
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.prompt}
    output:
      message: ${response.choices[0].message.content}
```

### Multiple Actions Component

```yaml
component:
  type: http-client
  base_url: https://api.github.com
  headers:
    Authorization: token ${env.GITHUB_TOKEN}
    Accept: application/vnd.github.v3+json
  actions:
    - id: get-user
      path: /user
      method: GET
      output:
        username: ${response.login}
        
    - id: list-repos
      path: /user/repos
      method: GET
      params:
        type: owner
        sort: updated
      output:
        repositories: ${response[*].name}
        
    - id: create-repo
      path: /user/repos
      method: POST
      body:
        name: ${input.repo_name}
        description: ${input.description}
        private: false
```

### Full URL Endpoint

```yaml
component:
  type: http-client
  action:
    endpoint: https://httpbin.org/post
    method: POST
    headers:
      Content-Type: application/json
    body:
      data: ${input.payload}
```

### Query Parameters

```yaml
component:
  type: http-client
  base_url: https://api.weather.com
  action:
    path: /v1/current
    method: GET
    params:
      key: ${env.WEATHER_API_KEY}
      q: ${input.city}
      aqi: yes
    output:
      temperature: ${response.current.temp_c}
      condition: ${response.current.condition.text}
```

### Streaming Responses

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  action:
    path: /chat/completions
    method: POST
    stream_format: server-sent-events
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.prompt}
      stream: true
```

## Asynchronous Completion

HTTP client supports asynchronous request completion through polling or callbacks.

### Polling Completion

Monitor request status by polling a completion endpoint:

```yaml
component:
  type: http-client
  base_url: https://api.example.com
  action:
    path: /jobs
    method: POST
    body:
      task: ${input.task_type}
      data: ${input.data}
    completion:
      type: polling
      path: /jobs/${response.job_id}
      method: GET
      status: status
      success_when: [ completed, finished ]
      fail_when: [ failed, error ]
      interval: 5s
      timeout: 300s
    output:
      result: ${response.result}
```

**Polling Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `polling` |
| `endpoint` | string | `null` | Full URL for polling (mutually exclusive with `path`) |
| `path` | string | `null` | Path to append to `base_url` for polling |
| `method` | string | `GET` | HTTP method for polling requests |
| `headers` | object | `{}` | Headers for polling requests |
| `body` | object | `{}` | Body data for polling requests |
| `params` | object | `{}` | Query parameters for polling requests |
| `status` | string | `null` | Field path to check for completion status |
| `success_when` | array | `null` | Status values indicating success |
| `fail_when` | array | `null` | Status values indicating failure |
| `interval` | string | `null` | Time interval between polls (e.g., `5s`, `30s`) |
| `timeout` | string | `null` | Maximum time to wait (e.g., `300s`, `5m`) |

### Callback Completion

Wait for external callback notification:

```yaml
component:
  type: http-client
  base_url: https://api.example.com
  action:
    path: /jobs
    method: POST
    body:
      task: ${input.task_type}
      callback_url: https://myapp.com/callback
    completion:
      type: callback
      wait_for: ${response.job_id}
    output:
      result: ${response.result}
```

**Callback Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `callback` |
| `wait_for` | string | `null` | Callback identifier to wait for |

## Stream Formats

### Server-Sent Events

Handle Server-Sent Events (SSE) streams:

```yaml
stream_format: server-sent-events
```

### JSON Lines

Handle newline-delimited JSON streams:

```yaml
stream_format: json-lines
```

## Authentication Patterns

### Bearer Token

```yaml
headers:
  Authorization: Bearer ${env.API_TOKEN}
```

### API Key

```yaml
headers:
  X-API-Key: ${env.API_KEY}
```

### Basic Auth

```yaml
headers:
  Authorization: Basic ${env.BASIC_AUTH_TOKEN}
```

### Custom Headers

```yaml
headers:
  X-Custom-Auth: ${env.CUSTOM_TOKEN}
  X-Client-ID: ${env.CLIENT_ID}
```

## Error Handling

HTTP client automatically handles HTTP status codes:

- **2xx**: Success - response data is available
- **4xx/5xx**: Error - workflow execution stops with error

For custom error handling, use completion configuration with specific status checks.

## Variable Interpolation

HTTP client supports dynamic configuration:

```yaml
component:
  type: http-client
  base_url: ${env.API_BASE_URL}
  action:
    path: /users/${input.user_id}
    headers:
      Authorization: Bearer ${env.API_KEY}
    body:
      name: ${input.name}
      age: ${input.age as number}
      active: ${input.active as boolean | true}
```

## Best Practices

1. **Base URL**: Use `base_url` with `path` for better maintainability
2. **Environment Variables**: Store sensitive data like API keys in environment variables
3. **Headers**: Set common headers at the component level
4. **Error Handling**: Use completion configuration for long-running tasks
5. **Timeouts**: Set appropriate timeout values for asynchronous operations
6. **Rate Limiting**: Consider API rate limits when setting polling intervals

## Integration with Workflows

Reference HTTP client in workflow jobs:

```yaml
workflow:
  jobs:
    - id: api-call
      component: my-http-client
      action: get-data
      input:
        endpoint_id: users
        
    - id: process-result
      component: processor
      input:
        data: ${api-call.output}
```

## Common Use Cases

- **API Integration**: Connect to external REST APIs
- **Webhooks**: Send data to webhook endpoints
- **Authentication**: Obtain and use access tokens
- **Data Fetching**: Retrieve data from web services
- **File Upload**: Upload files via HTTP POST
- **Monitoring**: Check service health endpoints
