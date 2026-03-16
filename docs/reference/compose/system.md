# System Configuration Reference

Systems provide declarative management of infrastructure services required by your components. They are automatically started before components during `model-compose up` and stopped after components during `model-compose down`.

## Basic Structure

### Single System

```yaml
system:
  type: docker-compose
  file: docker-compose.yml
  wait: true
  wait_timeout: 60s
```

### Multiple Systems

```yaml
systems:
  - id: database
    type: docker-compose
    file: docker-compose.db.yml
    wait: true

  - id: browser-infra
    type: docker-compose
    file: docker-compose.browser.yml
    wait: true
    wait_timeout: 120s
```

## System Types

### Docker Compose (`docker-compose`)

Manages services defined in Docker Compose files. Runs `docker compose up -d` on start and `docker compose down` on stop.

```yaml
system:
  type: docker-compose
  file: docker-compose.yml
  project_name: my-project
  build: true
  wait: true
  wait_timeout: 60s
```

## Common Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | `__system__` | Unique identifier for the system |
| `type` | string | **required** | System type: `docker-compose` |

## Docker Compose Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file` | string | - | Path to a single docker-compose file (shorthand for `files`) |
| `files` | array | `[]` | Paths to docker-compose files. Multiple files are merged in order |
| `project_name` | string | - | Docker Compose project name (`-p` flag) |
| `profiles` | array | - | Docker Compose profiles to activate (`--profile` flag) |
| `env_file` | string | - | Path to environment file for docker-compose (`--env-file` flag) |
| `build` | boolean | `false` | Whether to build images before starting (`--build` flag) |
| `wait` | boolean | `true` | Whether to wait for services to be healthy before proceeding (`--wait` flag) |
| `wait_timeout` | string | `60s` | Timeout for waiting for services to be ready. Supports duration format (e.g., `30s`, `2m`, `1m30s`) |

> **Note**: You can use either `file` (single file) or `files` (multiple files). If neither is specified, Docker Compose uses its default file discovery (`docker-compose.yml`).

## Configuration Examples

### Simple Docker Compose

```yaml
system:
  type: docker-compose
  file: docker-compose.yml
```

Starts services defined in `docker-compose.yml` and waits for them to be healthy.

### Multiple Compose Files

```yaml
system:
  type: docker-compose
  files:
    - docker-compose.yml
    - docker-compose.override.yml
  project_name: my-app
```

Merges multiple compose files, equivalent to `docker compose -f docker-compose.yml -f docker-compose.override.yml -p my-app up -d`.

### Build and Start

```yaml
system:
  type: docker-compose
  file: docker-compose.yml
  build: true
  wait: true
  wait_timeout: 120s
```

Builds images before starting, useful when compose files reference custom Dockerfiles.

### With Profiles

```yaml
system:
  type: docker-compose
  file: docker-compose.yml
  profiles:
    - development
    - debug
```

Activates specific Docker Compose profiles.

### With Environment File

```yaml
system:
  type: docker-compose
  file: docker-compose.yml
  env_file: .env.production
```

Uses a specific environment file for variable substitution in the compose file.

### Multiple Systems

```yaml
systems:
  - id: database
    type: docker-compose
    file: docker-compose.db.yml
    wait: true
    wait_timeout: 30s

  - id: browser
    type: docker-compose
    file: docker-compose.browser.yml
    wait: true
    wait_timeout: 60s
```

Manages multiple independent infrastructure stacks. All systems are started before components and stopped after components.

### Complete Example with Components

```yaml
systems:
  - id: browser-infra
    type: docker-compose
    file: docker-compose.yml
    wait: true
    wait_timeout: 60s

components:
  - id: browser
    type: web-browser
    host: localhost
    port: 9222

workflows:
  - id: scrape
    jobs:
      - id: navigate
        component: browser
        action: navigate
        input:
          url: ${input.url}
```

The system starts the Docker Compose services (e.g., Chromium browser) before the web-browser component connects to it.

## Lifecycle

Systems follow this lifecycle order relative to other configuration sections:

**Startup (`model-compose up`):**
```
1. Systems start (docker compose up -d)
2. Gateways start
3. Listeners start
4. Components start
5. Controller starts accepting requests
```

**Shutdown (`model-compose down`):**
```
1. Controller stops accepting requests
2. Components stop
3. Listeners stop
4. Gateways stop
5. Systems stop (docker compose down)
```

## Prerequisites

- **Docker**: The `docker` CLI must be installed and available in PATH
- **Docker Compose**: The `docker compose` subcommand must be available (Docker Desktop or standalone plugin)

## Troubleshooting

### Docker Not Found
```
RuntimeError: 'docker' command not found. Please install Docker to use docker-compose systems.
```
Install Docker Desktop or Docker Engine with the Compose plugin.

### Wait Timeout
If services take longer than `wait_timeout` to become healthy, increase the timeout value or check your Docker Compose health check configurations.

### Compose File Not Found
Ensure the `file` or `files` paths are relative to the directory containing `model-compose.yml`.

## Next Steps

- [Component Configuration](component.md) - Define components that use system-managed infrastructure
- [Gateway Configuration](gateway.md) - Expose services through tunnels
- [Workflow Configuration](workflow.md) - Orchestrate jobs using components
