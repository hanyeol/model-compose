# Shell Component

The shell component enables executing system commands and shell scripts within your model-compose workflows. It provides secure command execution with environment management, timeout controls, and output capture for integrating system operations with AI workflows.

## Basic Configuration

```yaml
component:
  type: shell
  command: [ ls, -la, /tmp ]
  working_dir: /home/user
  timeout: 30.0
  env:
    PATH: /usr/local/bin:/usr/bin:/bin
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `shell` |
| `base_dir` | string | `null` | Base working directory for all actions |
| `env` | object | `{}` | Environment variables for all actions |
| `manage` | object | `{}` | Configuration for environment setup and cleanup |
| `actions` | array | `[]` | List of shell command actions |

### Management Configuration

The `manage` configuration controls environment setup:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scripts` | object | `{}` | Shell scripts for setup and cleanup |
| `working_dir` | string | `null` | Working directory for management scripts |
| `env` | object | `{}` | Environment variables for management scripts |

#### Management Scripts

| Script | Type | Description |
|--------|------|-------------|
| `install` | array | One or more scripts to install dependencies |
| `clean` | array | One or more scripts to clean up environment |

### Action Configuration

Shell actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `command` | array | **required** | Shell command as list of arguments |
| `working_dir` | string | `null` | Working directory for the command |
| `env` | object | `{}` | Environment variables for the command |
| `timeout` | float | `null` | Maximum execution time in seconds |

## Usage Examples

### Simple Command Execution

```yaml
component:
  type: shell
  command: [df, -h]
  output:
    disk_usage: ${result.stdout}
    exit_code: ${result.exit_code}
```

### File System Operations

```yaml
component:
  type: shell
  command: [ find, /var/log, -name, "*.log", -mtime, "+7" ]
  working_dir: /tmp
  timeout: 60.0
  env:
    LANG: en_US.UTF-8
  output:
    old_log_files: ${result.stdout}
    error_output: ${result.stderr}
```

### Multiple Shell Actions

```yaml
component:
  type: shell
  base_dir: /opt/project
  env:
    PROJECT_ENV: production
    LOG_LEVEL: info
  actions:
    - id: backup-data
      command: [ rsync, -av, data/, backup/ ]
      timeout: 300.0
      output:
        backup_result: ${result.stdout}
        success: ${result.exit_code == 0}
    
    - id: check-disk-space
      command: [ du, -sh, backup/ ]
      output:
        backup_size: ${result.stdout}
        
    - id: cleanup-old-files
      command: [ find, backup/, -mtime, "+30", -delete ]
      timeout: 120.0
      output:
        cleanup_result: ${result.stdout}
        files_deleted: ${result.exit_code == 0}
        
    - id: verify-backup
      command: [ ls, -la, backup/ ]
      output:
        backup_contents: ${result.stdout}
```

### System Administration Tasks

```yaml
component:
  type: shell
  manage:
    scripts:
      install: 
        - [ apt, update ]
        - [ apt, install, -y, htop, iotop, nethogs ]
    working_dir: /tmp
    env:
      DEBIAN_FRONTEND: noninteractive
  actions:
    - id: system-info
      command: [ uname, -a ]
      output:
        system_info: ${result.stdout}
    
    - id: memory-usage
      command: [ free, -h ]
      output:
        memory_stats: ${result.stdout}
        
    - id: cpu-usage
      command: [ top, -bn1 ]
      timeout: 10.0
      output:
        cpu_stats: ${result.stdout}
        
    - id: network-stats
      command: [ ss, -tuln ]
      output:
        network_connections: ${result.stdout}
```

### Development and Build Tasks

```yaml
component:
  type: shell
  base_dir: /workspace/project
  env:
    NODE_ENV: production
    CI: true
  manage:
    scripts:
      install:
        - [ npm, install ]
        - [ npm, run, build ]
      clean: [ rm, -rf, node_modules, dist ]
  actions:
    - id: run-tests
      command: [ npm, test ]
      timeout: 300.0
      output:
        test_results: ${result.stdout}
        test_passed: ${result.exit_code == 0}
    
    - id: lint-code
      command: [ npm, run, lint ]
      output:
        lint_results: ${result.stdout}
        lint_passed: ${result.exit_code == 0}
        
    - id: build-project
      command: [ npm, run, build ]
      timeout: 600.0
      output:
        build_output: ${result.stdout}
        build_success: ${result.exit_code == 0}
```

### Data Processing Tasks

```yaml
component:
  type: shell
  base_dir: /data
  env:
    PYTHONPATH: /opt/scripts
  actions:
    - id: process-csv
      command: [ python3, process_data.py, --input, ${input.csv_file}, --output, ${input.output_file} ]
      timeout: 1800.0  # 30 minutes
      output:
        processing_result: ${result.stdout}
        rows_processed: ${result.stdout | extract_number}
        
    - id: validate-output
      command: [ python3, validate.py, ${input.output_file} ]
      output:
        validation_result: ${result.stdout}
        is_valid: ${result.exit_code == 0}
        
    - id: compress-data
      command: [ gzip, ${input.output_file} ]
      output:
        compressed_file: ${input.output_file}.gz
        compression_success: ${result.exit_code == 0}
```

### Docker and Container Operations

```yaml
component:
  type: shell
  env:
    DOCKER_HOST: unix:///var/run/docker.sock
  actions:
    - id: build-image
      command: [ docker, build, -t, ${input.image_name}, . ]
      working_dir: ${input.build_context}
      timeout: 900.0
      output:
        build_output: ${result.stdout}
        image_built: ${result.exit_code == 0}
    
    - id: run-container
      command: [ docker, run, -d, --name, ${input.container_name}, ${input.image_name} ]
      output:
        container_id: ${result.stdout}
        container_started: ${result.exit_code == 0}
        
    - id: check-container-status
      command: [ docker, ps, --filter, name=${input.container_name} ]
      output:
        container_status: ${result.stdout}
        
    - id: get-container-logs
      command: [ docker, logs, ${input.container_name} ]
      output:
        container_logs: ${result.stdout}
```

## Environment Management

### Environment Variables

Set environment variables at different scopes:

```yaml
component:
  type: shell
  # Component-level environment (applies to all actions)
  env:
    GLOBAL_VAR: global_value
    PATH: /custom/bin:${env.PATH}
  actions:
    - id: show-env
      command: [env]
      # Action-level environment (overrides component-level)
      env:
        ACTION_VAR: action_value
        GLOBAL_VAR: overridden_value
      output:
        environment: ${result.stdout}
```

### Working Directory Management

Control working directories for commands:

```yaml
component:
  type: shell
  base_dir: /opt/project  # Default for all actions
  actions:
    - id: list-project-files
      command: [ ls, -la ]
      # Uses base_dir: /opt/project
      
    - id: check-logs
      command: [ tail, -f, app.log ]
      working_dir: /var/log  # Override base_dir
      
    - id: run-script
      command: [ ./run_tests.sh ]
      working_dir: ${input.script_directory}  # Dynamic directory
```

## Command Output Handling

### Standard Output and Error

Access command output and error streams:

```yaml
component:
  type: shell
  command: [ python3, script.py ]
  output:
    stdout_content: ${result.stdout}
    stderr_content: ${result.stderr}
    exit_code: ${result.exit_code}
    success: ${result.exit_code == 0}
    command_duration: ${result.duration}
```

### Output Processing

Process command output with transformations:

```yaml
component:
  type: shell
  command: [ ps, aux ]
  output:
    # Extract specific information from ps output
    process_count: ${result.stdout | lines | length}
    cpu_usage_lines: ${result.stdout | lines | grep('python')}
    memory_info: ${result.stdout | extract_memory_info}
```

## Security and Safety

### Command Validation

Use parameterized commands to prevent injection:

```yaml
component:
  type: shell
  actions:
    - id: safe-file-operation
      # Safe: command is a list
      command: [ grep, ${input.pattern}, ${input.filename} ]
      
    - id: validate-input
      # Validate inputs before using
      command: [ find, ${input.directory | validate_path}, -name, ${input.filename | escape_shell} ]
```

### Timeout Protection

Set timeouts to prevent hanging processes:

```yaml
component:
  type: shell
  actions:
    - id: long-running-task
      command: [ rsync, -av, large_directory/, backup/ ]
      timeout: 3600.0  # 1 hour timeout
      
    - id: quick-check
      command: [ ping, -c, 1, ${input.hostname} ]
      timeout: 10.0    # 10 second timeout
```

### Resource Limits

Use system tools to limit resource usage:

```yaml
component:
  type: shell
  actions:
    - id: limited-process
      command: [ timeout, 300, nice, -n, 10, python3, heavy_script.py ]
      # Uses timeout and nice to limit execution time and priority
```

## Error Handling

### Exit Code Checking

Handle command failures appropriately:

```yaml
workflow:
  jobs:
    - id: backup-database
      component: shell-executor
      action: backup-db
      input:
        database_name: ${input.db_name}
      output:
        backup_file: ${output.backup_path}
      on_error:
        - id: cleanup-partial-backup
          component: shell-executor
          action: cleanup-files
          input:
            files_to_remove: ${backup-database.output.backup_path}

components:
  - id: shell-executor
    type: shell
    actions:
      - id: backup-db
        command: [ mysqldump, ${input.database_name} ]
        timeout: 1800.0
        output:
          backup_path: /tmp/backup_${now}.sql
          success: ${result.exit_code == 0}
          
      - id: cleanup-files
        command: [ rm, -f, ${input.files_to_remove} ]
```

## Integration Patterns

### System Monitoring

Monitor system resources and health:

```yaml
workflows:
  - id: system-health-check
    jobs:
      - id: check-disk-usage
        component: system-monitor
        action: disk-usage
        
      - id: check-memory
        component: system-monitor
        action: memory-stats
        
      - id: check-processes
        component: system-monitor
        action: process-list
        
      - id: generate-report
        component: report-generator
        input:
          disk_info: ${check-disk-usage.output.disk_usage}
          memory_info: ${check-memory.output.memory_stats}
          process_info: ${check-processes.output.process_list}

components:
  - id: system-monitor
    type: shell
    actions:
      - id: disk-usage
        command: [ df, -h ]
        output:
          disk_usage: ${result.stdout}
          
      - id: memory-stats
        command: [ free, -h ]
        output:
          memory_stats: ${result.stdout}
          
      - id: process-list
        command: [ ps, aux, --sort=-pcpu ]
        output:
          process_list: ${result.stdout}
```

### Data Pipeline Integration

Integrate shell commands in data processing pipelines:

```yaml
workflows:
  - id: data-processing-pipeline
    jobs:
      - id: download-data
        component: data-fetcher
        action: download-file
        input:
          url: ${input.data_url}
          
      - id: process-data
        component: data-processor
        action: transform-csv
        input:
          input_file: ${download-data.output.downloaded_file}
        depends_on: [ download-data ]
        
      - id: analyze-results
        component: ai-analyzer
        input:
          processed_data: ${process-data.output.processed_file}
        depends_on: [ process-data ]

components:
  - id: data-fetcher
    type: shell
    actions:
      - id: download-file
        command: [ curl, -o, /tmp/data.csv, ${input.url} ]
        timeout: 300.0
        output:
          downloaded_file: /tmp/data.csv
          download_success: ${result.exit_code == 0}
          
  - id: data-processor
    type: shell
    base_dir: /opt/data-tools
    actions:
      - id: transform-csv
        command: [ python3, transform.py, --input, ${input.input_file}, --output, /tmp/processed.csv ]
        timeout: 600.0
        output:
          processed_file: /tmp/processed.csv
          processing_success: ${result.exit_code == 0}
```

## Variable Interpolation

Shell components support dynamic configuration:

```yaml
component:
  type: shell
  command: [ ${env.BACKUP_TOOL | rsync}, -av, ${input.source_dir}, ${input.dest_dir} ]
  working_dir: ${env.WORK_DIR | /tmp}
  timeout: ${input.timeout as float | 300.0}
  env:
    BACKUP_DATE: ${now | date_format('%Y-%m-%d')}
    USER_ID: ${input.user_id}
```

## Best Practices

1. **Security**: Always use parameterized commands, never concatenate user input into shell strings
2. **Timeouts**: Set appropriate timeouts for all commands to prevent hanging
3. **Error Handling**: Check exit codes and handle command failures gracefully
4. **Resource Management**: Monitor CPU, memory, and disk usage for long-running commands
5. **Environment Isolation**: Use clean environments and avoid depending on system-specific configurations
6. **Logging**: Capture both stdout and stderr for debugging and monitoring
7. **Path Safety**: Validate and sanitize file paths before use
8. **Permissions**: Run commands with minimal required privileges

## Integration with Workflows

Reference shell components in workflow jobs:

```yaml
workflow:
  jobs:
    - id: prepare-environment
      component: shell-runner
      action: setup-env
      input:
        project_dir: ${input.project_path}
        
    - id: run-analysis
      component: shell-runner
      action: analyze-data
      input:
        data_file: ${input.data_file}
      depends_on: [ prepare-environment ]
      
    - id: cleanup
      component: shell-runner
      action: cleanup-temp
      depends_on: [ run-analysis ]
```

## Common Use Cases

- **System Administration**: Monitor system health, manage services, perform maintenance
- **Data Processing**: Execute data transformation scripts and tools
- **Build and Deployment**: Run build systems, deploy applications, manage containers
- **File Operations**: Manipulate files, directories, and archives
- **Network Operations**: Test connectivity, download files, interact with services
- **Testing and Validation**: Run test suites, validate outputs, check system state
- **Backup and Recovery**: Create backups, restore data, manage archives
- **Integration**: Bridge between different systems and tools
