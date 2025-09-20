# Logger Configuration Reference

Loggers control how model-compose records and outputs log messages during workflow execution. They provide visibility into workflow progress, debugging information, and error tracking.

## Basic Structure

### Single Logger

```yaml
logger:
  type: console | file
  level: debug | info | warning | error | critical
  # ... type-specific configuration
```

### Multiple Loggers

```yaml
loggers:
  - type: console
    level: info
    
  - type: file
    level: debug
    path: ./logs/debug.log
```

## Logger Types

### Console Logger (`console`)

Outputs log messages to the console/terminal where model-compose is running.

```yaml
logger:
  type: console
  level: info
```

### File Logger (`file`)

Writes log messages to a specified file on disk.

```yaml
logger:
  type: file
  level: info
  path: ./logs/run.log
```

## Common Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Logger type: `console` or `file` |
| `level` | string | `info` | Minimum logging level to capture |

## Logging Levels

Logging levels determine which messages are captured and output. Each level includes all higher priority levels:

| Level | Description | Includes |
|-------|-------------|----------|
| `debug` | Detailed diagnostic information | All messages |
| `info` | General information about workflow progress | info, warning, error, critical |
| `warning` | Warning messages about potential issues | warning, error, critical |
| `error` | Error messages for failures | error, critical |
| `critical` | Critical errors that may cause system failure | critical only |

## File Logger Configuration

### Path Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | `"./logs/run.log"` | File path where logs will be written |

**Path Options:**
- **Relative paths**: Resolved relative to the model-compose.yml directory
- **Absolute paths**: Full system paths
- **Environment variables**: Use `${env.LOG_PATH}` for dynamic paths
- **Directory creation**: Parent directories are created automatically if they don't exist

## Configuration Examples

### Console Logger

```yaml
logger:
  type: console
  level: info
```

Basic console logging that outputs INFO level and above messages to the terminal.

### Console Debug Logger

```yaml
logger:
  type: console
  level: debug
```

Detailed console logging including DEBUG messages for troubleshooting.

### File Logger with Default Path

```yaml
logger:
  type: file
  level: info
```

Writes logs to the default file location at `./logs/run.log`.

### File Logger with Custom Path

```yaml
logger:
  type: file
  level: debug
  path: /var/log/model-compose/app.log
```

Writes detailed logs to a custom absolute path.

### File Logger with Environment Variable

```yaml
logger:
  type: file
  level: info
  path: ${env.LOG_FILE_PATH}
```

Uses an environment variable to specify the log file path dynamically.

### Error-Only File Logger

```yaml
logger:
  type: file
  level: error
  path: ./logs/errors.log
```

Only captures ERROR and CRITICAL messages for error tracking.

## Log Message Format

Model-compose log messages follow a structured format:

```
YYYY-MM-DD HH:MM:SS,mmm LEVEL: [task-ID] Message content
```

**Format Components:**
- **Timestamp**: Date and time with millisecond precision
- **Level**: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)  
- **Task ID**: Unique identifier for the workflow execution
- **Message**: Descriptive log message

**Example Log Messages:**
```
2025-07-30 08:20:25,922 INFO: [task-01K1C7SEJ0G010ZZ1M398DDCXA] Workflow '__default__' started.
2025-07-30 08:20:25,924 DEBUG: [task-01K1C7SEJ0G010ZZ1M398DDCXA] Action 'run-01K1C7SEJ41AFFMPJG6Z8FTJ5C' started for job 'gpt-image-1'
2025-07-30 08:21:16,492 DEBUG: [task-01K1C7SEJ0G010ZZ1M398DDCXA] Action 'run-01K1C7SEJ41AFFMPJG6Z8FTJ5C' completed in 50.57 seconds.
2025-07-30 08:21:16,493 INFO: [task-01K1C7SEJ0G010ZZ1M398DDCXA] Workflow '__default__' completed in 50.57 seconds.
```

## Multiple Logger Configuration

You can configure multiple loggers to output to different destinations:

```yaml
loggers:
  - type: console
    level: info
    
  - type: file
    level: debug
    path: ./logs/debug.log
    
  - type: file
    level: error
    path: ./logs/errors.log
```

This configuration:
- Shows INFO+ messages on console for real-time monitoring
- Captures DEBUG+ messages to a detailed log file
- Separates ERROR+ messages to a dedicated error log

## Best Practices

### Development Environment
```yaml
logger:
  type: console
  level: debug
```

Use console logging with DEBUG level during development for immediate feedback.

### Production Environment
```yaml
loggers:
  - type: console
    level: info
    
  - type: file
    level: info
    path: /var/log/model-compose/app.log
    
  - type: file
    level: error
    path: /var/log/model-compose/errors.log
```

Combine console and file logging in production with separate error tracking.

### High-Volume Environments
```yaml
logger:
  type: file
  level: warning
  path: ${env.LOG_PATH}/model-compose.log
```

Use WARNING+ level in high-volume environments to reduce log noise while capturing issues.

## Log Management

### File Rotation
Model-compose doesn't provide built-in log rotation. Use system tools for log management:

- **Linux**: `logrotate` utility
- **Docker**: Configure logging drivers with rotation
- **Kubernetes**: Use log aggregation solutions

### Log Analysis
Common log analysis patterns:

```bash
# Filter by task ID
grep "task-01K1C7SEJ0G010ZZ1M398DDCXA" logs/run.log

# Show only errors
grep "ERROR\|CRITICAL" logs/run.log

# Workflow completion times
grep "completed in" logs/run.log

# Action performance analysis
grep "Action.*completed" logs/run.log | sort -k9 -n
```

## Integration with Monitoring

### Structured Logging
For integration with log aggregation systems, consider parsing the structured format:

- **Task ID**: Extract for tracing workflow executions
- **Timestamps**: Parse for performance analysis
- **Levels**: Filter by severity for alerting
- **Execution Times**: Monitor for performance regressions

### Alerting
Set up alerts based on log patterns:
- Critical errors: `CRITICAL` level messages
- Workflow failures: Error patterns in workflow completion
- Performance issues: Execution times exceeding thresholds
- System issues: Connection failures, timeouts

## Troubleshooting

### Common Issues

**Log file not created:**
- Check directory permissions
- Verify parent directory exists
- Ensure sufficient disk space

**Missing log messages:**
- Verify log level configuration
- Check if logger is properly configured
- Ensure workflow is actually executing

**Permission errors:**
- Check write permissions for log directory
- Consider using relative paths in containerized environments
- Verify user context has appropriate file system access

### Debug Configuration
To troubleshoot logging issues, temporarily use:

```yaml
logger:
  type: console
  level: debug
```

This ensures you can see all log messages and verify logger functionality.