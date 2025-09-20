# Listener Configuration Reference

Listeners are services that wait for external callbacks and webhook notifications. They enable asynchronous workflows where external systems can notify your model-compose application when certain events occur or tasks are completed.

## Basic Structure

### Single Listener

```yaml
listener:
  type: http-callback
  runtime: native | docker
  max_concurrent_count: 0
  host: 0.0.0.0
  port: 8090
  base_path: /callbacks
  callbacks:
    - path: /webhook
      method: POST
      # ... callback configuration
```

### Multiple Listeners

```yaml
listeners:
  - type: http-callback
    port: 8090
    callbacks:
      - path: /payment-webhook
        method: POST
        # ... payment callback configuration
        
  - type: http-callback
    port: 8091
    callbacks:
      - path: /notification-webhook
        method: POST
        # ... notification callback configuration
```

## Listener Types

### HTTP Callback (`http-callback`)

Creates an HTTP server that receives webhook callbacks from external services.

```yaml
listener:
  type: http-callback
  host: 0.0.0.0           # Host address to bind the HTTP server to
  port: 8090                # Port number for the callback server
  base_path: /callbacks   # Base path prefix for callback endpoints
  callbacks:                # List of callback endpoint configurations
    - path: /webhook
      method: POST
      # ... additional callback options
```

## Common Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Listener type: `http-callback` |
| `runtime` | string | `native` | Runtime environment: `native` or `docker` |
| `max_concurrent_count` | integer | `0` | Maximum concurrent callback requests (0 = unlimited) |

## HTTP Callback Configuration

### Server Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | string | `"0.0.0.0"` | Host address to bind the HTTP server to |
| `port` | integer | `8090` | Port number on which the HTTP server will listen |
| `base_path` | string | `null` | Base path prefix for all callback endpoints |

### Callback Endpoint Configuration

Each callback endpoint in the `callbacks` array can be configured with the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | **required** | URL path for this callback endpoint |
| `method` | string | `"POST"` | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH` |
| `bulk` | boolean | `false` | Whether this callback handles multiple items in a single request |
| `item` | string | `null` | Field path to extract individual items from bulk payload |
| `identify_by` | string | `null` | Field path used to match callback responses to pending requests |
| `status` | string | `null` | Field path to check for completion status in callback payload |
| `success_when` | array | `null` | Status values that indicate successful completion |
| `fail_when` | array | `null` | Status values that indicate failed completion |
| `result` | any | `null` | Field path or transformation to extract final result from payload |

## Configuration Examples

### Simple Webhook Listener

```yaml
listener:
  type: http-callback
  port: 8090
  callbacks:
    - path: /webhook
      method: POST
```

This creates a simple webhook endpoint at `http://localhost:8090/webhook` that accepts POST requests.

### Advanced Status-Based Callback

```yaml
listener:
  type: http-callback
  port: 8090
  base_path: "/api/callbacks"
  max_concurrent_count: 10
  callbacks:
    - path: /job-status
      method: POST
      identify_by: job_id
      status: status
      success_when: ["completed", "finished"]
      fail_when: ["failed", "error", "cancelled"]
      result: result.data
```

This configuration:
- Creates endpoint at `/api/callbacks/job-status`
- Limits to 10 concurrent callback requests
- Uses `job_id` field to match callbacks to pending requests
- Considers job complete when status is "completed" or "finished"
- Considers job failed when status is "failed", "error", or "cancelled"
- Extracts final result from `result.data` field

### Bulk Processing Callback

```yaml
listener:
  type: http-callback
  port: 8090
  callbacks:
    - path: /batch-results
      method: POST
      bulk: true
      item: results[]
      identify_by: request_id
      status: processing_status
      success_when: success
      fail_when: ["failed", "timeout"]
      result: output
```

This configuration:
- Processes multiple results in a single callback request
- Extracts individual items from the `results` array
- Uses `request_id` to match each result to its original request
- Checks `processing_status` field for completion status

### Multiple Callback Endpoints

```yaml
listener:
  type: http-callback
  port: 8090
  runtime: docker
  callbacks:
    - path: /payment-webhook
      method: POST
      identify_by: transaction_id
      status: payment_status
      success_when: completed
      fail_when: ["failed", "cancelled"]
      result: payment_details
    
    - path: /notification-callback
      method: POST
      identify_by: message_id
      status: delivery_status
      success_when: delivered
      fail_when: failed
      result: delivery_info
```

This configuration creates two different callback endpoints on the same listener service.

### Simplified Single Callback Syntax

For listeners with only one callback endpoint, you can use a simplified syntax:

```yaml
listener:
  type: http-callback
  port: 8090
  path: /webhook
  method: POST
  identify_by: id
  status: "status"
  success_when: done
  result: data
```

This is equivalent to:

```yaml
listener:
  type: http-callback
  port: 8090
  callbacks:
    - path: /webhook
      method: POST
      identify_by: id
      status: status
      success_when: done
      result: data
```

## Usage Patterns

### Asynchronous Job Processing

Listeners are commonly used for asynchronous job processing where:

1. Your workflow submits a job to an external service
2. The external service immediately returns a job ID
3. The external service processes the job asynchronously
4. When complete, the external service sends a webhook to your listener
5. Your workflow continues with the job results

### Event-Driven Workflows

Listeners enable event-driven architectures where external events trigger workflow execution:

1. Configure listener with appropriate callback endpoints
2. Register webhook URLs with external services
3. External events trigger callbacks to your listener
4. Listener processes the callback and continues workflow execution

## Runtime Considerations

- **Concurrency**: Set `max_concurrent_count` based on your expected callback load
- **Port Management**: Ensure listener ports don't conflict with controller or other services
- **Security**: Consider implementing authentication/authorization for webhook endpoints
- **Network**: Listeners need to be accessible from external services sending callbacks
- **Timeouts**: Configure appropriate timeouts for long-running callback processing

## Integration with Workflows

Listeners work seamlessly with workflows to enable asynchronous processing patterns. The listener automatically matches incoming callbacks to pending workflow executions based on the `identify_by` field configuration.