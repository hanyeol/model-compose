# Model-Compose CLI Reference

model-compose provides a command-line interface for managing AI model workflows and orchestration.

## Installation

```bash
# Install for development
pip install -e .

# Install with development dependencies  
pip install -e .[dev]
```

## Commands

### `model-compose up`

Start the workflow controller in the current directory.

```bash
# Start the workflow controller
model-compose up

# Run in detached mode
model-compose up -d
```

The controller will look for a `model-compose.yml` file in the current directory and start the defined services, workflows, and listeners.

### `model-compose down`

Stop the running workflow controller.

```bash
model-compose down
```

### `model-compose start`

Start existing services that were previously created.

```bash
model-compose start
```

### `model-compose stop`

Stop running services without removing them.

```bash
model-compose stop
```

### `model-compose run`

Execute a specific workflow once with optional input parameters.

```bash
# Run a workflow with input
model-compose run <workflow-name> --input '{"key": "value"}'

# Run without input
model-compose run <workflow-name>
```

## Configuration

The CLI reads configuration from `model-compose.yml` files in the current directory. These files define:

- **Controllers**: HTTP/MCP servers
- **Components**: Reusable API calls and model tasks
- **Workflows**: Job sequences with data flow
- **Listeners**: Webhook callbacks
- **Gateways**: Tunneling services

## Examples

```bash
# Start a workflow controller
cd examples/openai-chat-completions
model-compose up

# Run a specific workflow
cd examples/model-tasks/chat-completion
model-compose run chat-workflow --input '{"message": "Hello, world!"}'

# Stop all services
model-compose down
```

## Options and Flags

- `-d, --detach`: Run in detached mode (for `up` command)
- `--input`: Provide JSON input for workflow execution (for `run` command)
- `--help`: Show help information for any command

## Environment Variables

The CLI respects standard environment variables for model API keys and configurations as defined in your workflow components.

## Troubleshooting

- Ensure `model-compose.yml` exists in the current directory
- Check that required environment variables are set for external model APIs
- Use `--help` flag with any command for detailed usage information