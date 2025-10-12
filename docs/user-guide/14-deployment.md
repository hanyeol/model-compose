# 14. Deployment

This chapter explains how to run model-compose applications in local environments or deploy them as Docker containers.

---

## 14.1 Local Execution

### 14.1.1 Basic Execution

model-compose runs directly in the local environment using native runtime by default.

**Starting the controller:**

```bash
model-compose up
```

Default behavior:
- Loads `model-compose.yml` from current directory
- Starts services with native runtime
- Runs in foreground mode (log output)
- Exit with Ctrl+C

**Background execution:**

```bash
model-compose up -d
```

In background mode:
- Services run in a separate process
- Stop with `model-compose down`

**Stopping the controller:**

```bash
model-compose down
```

Stop process:
1. Creates `.stop` file
2. Controller detects file (polls every 1 second)
3. Graceful service shutdown
4. Resource cleanup

### 14.1.2 Environment Variable Management

**Using `.env` file:**

```bash
# Create .env file
cat > .env <<EOF
OPENAI_API_KEY=sk-proj-...
MODEL_CACHE_DIR=/models
LOG_LEVEL=info
EOF

# Automatically loads .env file
model-compose up
```

**Custom `.env` file:**

```bash
model-compose up --env-file .env.production
```

**Individual environment variable override:**

```bash
model-compose up -e OPENAI_API_KEY=sk-proj-... -e LOG_LEVEL=debug
```

Environment variable priority:
1. Values passed via `--env` / `-e` flag (highest priority)
2. File specified with `--env-file`
3. Default `.env` file
4. System environment variables

### 14.1.3 Specifying Configuration File

**Using custom configuration file:**

```bash
model-compose up -f custom-compose.yml
```

**Merging multiple configuration files:**

```bash
model-compose up -f base.yml -f override.yml
```

### 14.1.4 Running Workflow Standalone

Run workflow only without controller:

```bash
model-compose run my-workflow --input '{"text": "Hello"}'
```

Features:
- Does not start controller
- Executes workflow once and exits
- Useful for CI/CD pipelines or batch jobs

**Passing input from JSON file:**

```bash
model-compose run my-workflow --input @input.json
```

### 14.1.5 Debugging Options

**Detailed log output:**

Specify logger level in configuration file:

```yaml
controller:
  type: http-server
  port: 8080

logger:
  - type: console
    level: debug        # debug, info, warning, error, critical
```

---

## 14.2 Docker Runtime

### 14.2.1 Basic Docker Configuration

**Simple Docker runtime configuration:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime: docker                 # String format
```

This configuration expands to:

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    # Uses default image (auto-build)
```

**Specifying image:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    image: my-registry/model-compose:latest
    container_name: my-controller
```

Execution flow:
1. Attempts to pull image from registry
2. Falls back to local build if pull fails
3. Creates and starts container
4. Streams logs (foreground) or detaches (background)

**Port mapping:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    ports:
      - "5000:8080"                # host:container
      - 8081                       # Same port (8081:8081)
```

Port formats:
- String: `"host_port:container_port"`
- Integer: `port` (same for host and container)
- Object: Advanced configuration (see below)

### 14.2.2 Advanced Docker Options

**Image build configuration:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    build:
      context: .                   # Build context path
      dockerfile: Dockerfile       # Custom Dockerfile
      args:                        # Build arguments
        PYTHON_VERSION: "3.11"
        MODEL_NAME: "llama-2"
      target: production           # Multi-stage build target
      cache_from:                  # Cache images
        - my-registry/cache:latest
      labels:
        app: model-compose
        version: "1.0"
      network: host                # Network mode during build
      pull: true                   # Always pull base images
```

**Advanced port configuration:**

```yaml
controller:
  runtime:
    type: docker
    ports:
      - target: 8080               # Container port
        published: 5000            # Host port
        protocol: tcp              # tcp or udp
        mode: host                 # host or ingress
```

**Network configuration:**

```yaml
controller:
  runtime:
    type: docker
    networks:
      - my-network                 # Connect to existing network
      - bridge                     # Docker default bridge
```

**Container run options:**

```yaml
controller:
  runtime:
    type: docker
    hostname: model-compose-host   # Container hostname
    command:                       # Override CMD
      - python
      - -m
      - mindor.cli.compose
      - up
      - --verbose
    entrypoint: /bin/bash          # Override ENTRYPOINT
    working_dir: /app              # Working directory
    user: "1000:1000"              # User:group ID
```

**Resource limits:**

```yaml
controller:
  runtime:
    type: docker
    mem_limit: 2g                  # Memory limit (512m, 2g, etc.)
    memswap_limit: 4g              # Memory + swap limit
    cpus: "2.0"                    # CPU allocation (0.5, 2.0, etc.)
    cpu_shares: 1024               # Relative CPU weight
```

**Restart policy:**

```yaml
controller:
  runtime:
    type: docker
    restart: always                # no, always, on-failure, unless-stopped
```

Restart policy descriptions:
- `no`: Do not restart (default)
- `always`: Always restart
- `on-failure`: Restart only on error exit
- `unless-stopped`: Restart until manually stopped

**Health check:**

```yaml
controller:
  runtime:
    type: docker
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s                # Check interval
      timeout: 10s                 # Timeout
      max_retry_count: 3           # Maximum retry count
      start_period: 40s            # Grace period
```

Or simply:

```yaml
controller:
  runtime:
    type: docker
    healthcheck:
      test: "curl -f http://localhost:8080/health || exit 1"
```

**Security options:**

```yaml
controller:
  runtime:
    type: docker
    privileged: false              # Privileged mode (not recommended)
    security_opt:
      - apparmor=unconfined
      - seccomp=unconfined
```

**Logging configuration:**

```yaml
controller:
  runtime:
    type: docker
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

**Labels:**

```yaml
controller:
  runtime:
    type: docker
    labels:
      environment: production
      team: ml-ops
      version: "1.0.0"
```

### 14.2.3 Volumes and Environment Variables

**Volume mount - simple format:**

```yaml
controller:
  runtime:
    type: docker
    volumes:
      - ./models:/models           # Bind mount
      - ./cache:/cache:ro          # Read-only
      - model-data:/data           # Named volume
```

**Volume mount - detailed format:**

```yaml
controller:
  runtime:
    type: docker
    volumes:
      # Bind mount
      - type: bind
        source: ./models           # Host path
        target: /models            # Container path
        read_only: false
        bind:
          propagation: rprivate

      # Named volume
      - type: volume
        source: model-data         # Volume name
        target: /data
        volume:
          nocopy: false

      # tmpfs (temporary memory)
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 1073741824         # 1GB (bytes)
          mode: 1777
```

Volume type descriptions:
- `bind`: Mount host directory/file to container
- `volume`: Named volume managed by Docker
- `tmpfs`: Memory-based temporary filesystem (deleted on container stop)

**Environment variable configuration:**

```yaml
controller:
  runtime:
    type: docker
    environment:
      OPENAI_API_KEY: ${env.OPENAI_API_KEY}   # Pass host environment variable
      MODEL_CACHE_DIR: /models
      LOG_LEVEL: info
      WORKERS: 4
```

**Environment variable file:**

```yaml
controller:
  runtime:
    type: docker
    env_file:
      - .env                       # Single file
      - .env.production            # Multiple files
```

---

## 14.3 Docker Container Build and Deployment

### 14.3.1 Automatic Build Process

model-compose automatically builds images when using Docker runtime.

**Build context preparation:**

When running `model-compose up`:
1. Creates `.docker/` directory
2. Copies source code (mindor package)
3. Copies/creates `requirements.txt`
4. Creates `model-compose.yml` (converted to native runtime)
5. Copies webui directories (if configured)
6. Copies Dockerfile or uses default Dockerfile

**Default Dockerfile:**

```dockerfile
FROM ubuntu:22.04

WORKDIR /app

# Install Python 3.11
RUN apt update && apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python symlinks
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# Install base dependencies
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir \
    click pyyaml pydantic python-dotenv \
    aiohttp requests fastapi uvicorn \
    'mcp>=1.10.1' pyngrok ulid gradio Pillow

# Install project dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY src .
COPY webui ./webui
COPY model-compose.yml .

# Default command
CMD [ "python", "-m", "mindor.cli.compose", "up" ]
```

### 14.3.2 Using Custom Dockerfile

To use a project-specific Docker image, you can create a custom Dockerfile.

**Project directory structure:**

```
my-project/
├── model-compose.yml    # Workflow configuration
├── Dockerfile           # Custom Docker image
├── requirements.txt     # Python dependencies (optional)
└── .env                 # Environment variables (optional)
```

**Note**: To use a custom Dockerfile, you must explicitly specify it in the `build` section. The Dockerfile can be placed in the project root or any desired location.

**Dockerfile example:**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt update && apt install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install model-compose
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download models
RUN python -c "from transformers import AutoModel; AutoModel.from_pretrained('bert-base-uncased')"

# Copy application
COPY . .

CMD [ "model-compose", "up" ]
```

**Specifying custom Dockerfile in configuration:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    build:
      context: .
      dockerfile: Dockerfile       # Custom Dockerfile
```

### 14.3.3 Multi-stage Build

**Separating development/production:**

```dockerfile
# Stage 1: Build environment
FROM python:3.11 AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY src ./src

# Stage 2: Runtime environment
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy packages from builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app/src ./src

# Update PATH
ENV PATH=/root/.local/bin:$PATH

COPY model-compose.yml .

CMD [ "model-compose", "up" ]

# Stage 3: Development environment
FROM runtime AS development

RUN pip install --no-cache-dir pytest black flake8

CMD [ "model-compose", "up", "--verbose" ]
```

**Specifying target in configuration:**

```yaml
# Production
controller:
  runtime:
    type: docker
    build:
      context: .
      target: runtime

---
# Development
controller:
  runtime:
    type: docker
    build:
      context: .
      target: development
```

### 14.3.4 Using Image Registry

**Building and pushing image:**

```bash
# Local build
docker build -t my-registry.com/model-compose:1.0 .

# Push to registry
docker push my-registry.com/model-compose:1.0
```

**Using registry image in configuration:**

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    image: my-registry.com/model-compose:1.0
    container_name: model-compose-prod
```

On execution:
1. Pulls image from registry
2. Creates and starts container
3. Skips local build process

### 14.3.5 Private Registry Authentication

**Docker login:**

```bash
docker login my-registry.com
```

Or with environment variables:

```bash
export DOCKER_USERNAME=myuser
export DOCKER_PASSWORD=mypass
docker login -u $DOCKER_USERNAME -p $DOCKER_PASSWORD my-registry.com
```

**Authentication credentials are stored in `~/.docker/config.json`.**

---

## 14.4 Production Environment Considerations

### 14.4.1 Concurrency Control

**Controller-level concurrency:**

```yaml
controller:
  type: http-server
  port: 8080
  max_concurrent_count: 10         # Maximum 10 concurrent workflows
  threaded: false                  # Thread-based execution (default: false)
```

Concurrency settings:
- `max_concurrent_count: 0`: Unlimited (default, use with caution)
- `max_concurrent_count: N`: Maximum N concurrent executions
- `threaded: true`: Run each workflow in separate thread

**Component-level concurrency:**

```yaml
components:
  - id: api-client
    type: http-client
    base_url: https://api.example.com
    max_concurrent_count: 5        # Max 5 concurrent requests for this component
```

### 14.4.2 Resource Limits

**Memory limits:**

```yaml
controller:
  runtime:
    type: docker
    mem_limit: 4g                  # Maximum 4GB memory
    memswap_limit: 6g              # Memory + swap 6GB
```

Memory units:
- `b`: bytes
- `k`: kilobytes
- `m`: megabytes
- `g`: gigabytes

**CPU limits:**

```yaml
controller:
  runtime:
    type: docker
    cpus: "2.0"                    # Maximum 2 CPU cores
    cpu_shares: 1024               # Relative CPU weight
```

CPU settings:
- `cpus`: Absolute CPU limit (0.5 = 50%, 2.0 = 200%)
- `cpu_shares`: Relative weight (default 1024)

### 14.4.3 Restart Policy

**Auto-restart configuration:**

```yaml
controller:
  runtime:
    type: docker
    restart: unless-stopped        # Always restart until manually stopped
```

Production recommendations:
- `always`: Always restart (including system reboot)
- `unless-stopped`: Restart until manually stopped
- `on-failure`: Restart only on error

### 14.4.4 Health Check

**HTTP endpoint health check:**

model-compose provides `/health` endpoint by default.

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      max_retry_count: 3
      start_period: 40s
```

Health check response:

```json
{
  "status": "ok"
}
```

**Custom health check:**

```yaml
controller:
  runtime:
    type: docker
    healthcheck:
      test: ["CMD-SHELL", "python -c 'import requests; requests.get(\"http://localhost:8080/health\")' || exit 1"]
      interval: 20s
```

### 14.4.5 Security Considerations

**Running in non-privileged mode:**

```yaml
controller:
  runtime:
    type: docker
    privileged: false              # Always false recommended
    user: "1000:1000"              # Non-root user
```

**Secret management:**

Passing sensitive information via environment variables:

```yaml
controller:
  runtime:
    type: docker
    environment:
      OPENAI_API_KEY: ${env.OPENAI_API_KEY}     # Injected from host
      DB_PASSWORD: ${env.DB_PASSWORD}
```

On execution:

```bash
export OPENAI_API_KEY=sk-proj-...
export DB_PASSWORD=secret
model-compose up
```

Or using `.env` file (do not commit to repository):

```bash
# .env.production
OPENAI_API_KEY=sk-proj-...
DB_PASSWORD=secret
```

```bash
model-compose up --env-file .env.production
```

**Network isolation:**

```yaml
controller:
  runtime:
    type: docker
    networks:
      - isolated-network           # Use isolated network
```

### 14.4.6 Data Persistence

**Preserving data with volume mounts:**

```yaml
controller:
  runtime:
    type: docker
    volumes:
      - ./data:/data               # Local data directory
      - model-cache:/cache         # Named volume
      - ./logs:/app/logs           # Log directory
```

Creating named volume:

```bash
docker volume create model-cache
```

Checking volumes:

```bash
docker volume ls
docker volume inspect model-cache
```

---

## 14.5 Monitoring and Logging

### 14.5.1 Logger Configuration

**Console logger:**

```yaml
logger:
  - type: console
    level: info                    # debug, info, warning, error, critical
```

Log levels:
- `debug`: All logs (for development)
- `info`: General information (default)
- `warning`: Warning messages
- `error`: Error messages
- `critical`: Critical errors

**File logger:**

```yaml
logger:
  - type: file
    path: ./logs/run.log           # Log file path
    level: info
```

Directories are created automatically.

**Using multiple loggers:**

```yaml
logger:
  - type: console
    level: warning                 # Only warnings to console

  - type: file
    path: ./logs/all.log
    level: debug                   # All logs to file

  - type: file
    path: ./logs/errors.log
    level: error                   # Error-only log
```

### 14.5.2 Docker Container Logs

**Viewing logs in real-time:**

```bash
# Automatic streaming in foreground mode
model-compose up

# Check logs after background execution
docker logs -f <container-name>
```

**Saving logs:**

```yaml
controller:
  runtime:
    type: docker
    container_name: model-compose-prod
    logging:
      driver: json-file
      options:
        max-size: "10m"            # Maximum size per file
        max-file: "5"              # Maximum file count
```

Log location: `/var/lib/docker/containers/<container-id>/<container-id>-json.log`

**Log driver options:**

```yaml
controller:
  runtime:
    type: docker
    logging:
      driver: syslog               # json-file, syslog, journald, gelf, fluentd, etc.
      options:
        syslog-address: "tcp://192.168.0.42:514"
        tag: "model-compose"
```

### 14.5.3 Workflow Execution Logging

**Logging with logger component:**

```yaml
components:
  - id: logger
    type: logger
    level: info

  - id: api-client
    type: http-client
    base_url: https://api.example.com

workflows:
  - id: process-with-logging
    jobs:
      - id: log-start
        component: logger
        input:
          message: "Workflow started: ${context.run_id}"

      - id: api-call
        component: api-client
        input: ${input}

      - id: log-result
        component: logger
        input:
          message: "Result: ${output}"

      - id: log-end
        component: logger
        input:
          message: "Workflow completed"
```

### 14.5.4 Metrics Collection

**Tracking execution time:**

```yaml
workflows:
  - id: timed-workflow
    jobs:
      - id: start-time
        component: shell
        command: echo $(date +%s%3N)       # Millisecond timestamp
        output: ${stdout.trim()}

      - id: process
        component: api-client
        input: ${input}

      - id: end-time
        component: shell
        command: echo $(date +%s%3N)
        output: ${stdout.trim()}

      - id: log-duration
        component: logger
        input:
          message: "Execution time: ${output.end-time - output.start-time}ms"
```

**Performance metrics logging:**

```yaml
workflows:
  - id: metrics-workflow
    jobs:
      - id: api-call
        component: api-client
        input: ${input}

      - id: log-metrics
        component: logger
        input:
          run_id: ${context.run_id}
          status: ${output.status}
          response_time: ${output.response_time_ms}
          tokens_used: ${output.usage.total_tokens}
```

### 14.5.5 External Monitoring Systems

**Prometheus integration example:**

```yaml
components:
  - id: prometheus-push
    type: http-client
    base_url: http://prometheus-pushgateway:9091
    path: /metrics/job/model-compose
    method: POST
    headers:
      Content-Type: text/plain

workflows:
  - id: monitored-workflow
    jobs:
      - id: process
        component: my-component
        input: ${input}

      - id: push-metrics
        component: prometheus-push
        input:
          body: |
            workflow_execution_duration_seconds ${output.duration}
            workflow_execution_total 1
```

**Log aggregation system (ELK Stack):**

```yaml
controller:
  runtime:
    type: docker
    logging:
      driver: gelf                 # Graylog Extended Log Format
      options:
        gelf-address: "udp://logstash:12201"
        tag: "model-compose"
        labels: "environment,service"
    labels:
      environment: production
      service: model-compose
```

---

## 14.6 Best Practices

### Environment-specific Deployment Strategies

**Local development environment:**
- Native runtime for rapid iteration
- Manage environment variables with `.env` file
- Use console logger (`level: debug`)

**Staging/testing environment:**
- Docker runtime to mimic production
- File logger for log retention
- Validate resource limits and health checks

**Production environment:**
- Docker runtime required
- `restart: unless-stopped` for auto-recovery
- Apply resource limits (`mem_limit`, `cpus`)
- Configure health checks and monitoring
- Ensure data persistence with volumes
- Manage secrets via environment variables
- Integrate with log aggregation system
- Configure concurrency control

### Performance Optimization

1. **Concurrency tuning**: Configure `max_concurrent_count` for workload
2. **Resource allocation**: Monitor CPU/memory usage and set appropriate limits
3. **Log level**: Use `info` or higher in production (exclude debug logs)
4. **Log rotation**: Control disk usage with Docker logging options
5. **Volume mounts**: Consider tmpfs for performance-critical data

### Security Hardening

1. **Least privilege principle**: Run containers as non-root user
2. **Secret separation**: Use environment variables, never commit secrets to repository
3. **Network isolation**: Use dedicated networks when needed
4. **Regular updates**: Regularly update base images and dependencies
5. **Security scanning**: Use vulnerability scanning tools during image builds

### Reliability Improvements

1. **Health checks**: Always configure health checks
2. **Restart policy**: Use `always` or `unless-stopped` in production
3. **Graceful shutdown**: Ensure proper termination via signal handling
4. **Backups**: Regular backups for critical data
5. **Monitoring**: Set up real-time metrics and alerts

---

## Next Steps

Try it out:
- Deploy controller to production environment
- Multi-container configuration with Docker Compose
- Kubernetes cluster deployment
- CI/CD pipeline integration
- Build monitoring dashboards

---

**Next Chapter**: [15. Practical Examples](./15-practical-examples.md)
