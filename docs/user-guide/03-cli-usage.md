# Chapter 3: CLI Usage

This chapter provides detailed coverage of all model-compose CLI commands and options.

---

## 3.1 Basic Commands

model-compose provides five core commands:

- `up` - Start and run services
- `down` - Stop and clean up services
- `start` - Start services
- `stop` - Stop services
- `run` - Execute workflow once

### Command Structure

```bash
model-compose [global-options] <command> [command-options] [arguments]
```

### Global Options

Available for all commands:

```bash
model-compose --file <config-file> <command>
model-compose -f <config-file> <command>
```

**Options:**
- `--file`, `-f`: Specify configuration file (repeatable, merges multiple files)
- `--version`: Display version information
- `--help`: Display help

**Examples:**
```bash
# Single configuration file
model-compose -f config.yml up

# Merge multiple configuration files
model-compose -f base.yml -f override.yml up

# Check version
model-compose --version
```

---

## 3.2 up Command

Starts and runs services. Sets up a new environment and starts all necessary services.

### Usage

```bash
model-compose up [options]
```

### Options

- `-d`, `--detach`: Run in detached mode (background)
- `--env-file <file>`: Specify environment variable file (repeatable)
- `-e`, `--env <KEY=VALUE>`: Set environment variable directly (repeatable)
- `-v`, `--verbose`: Enable verbose output

### Examples

**Basic execution:**
```bash
model-compose up
```

**Run in background:**
```bash
model-compose up -d
```

**Use environment file:**
```bash
model-compose up --env-file .env --env-file .env.production
```

**Set environment variables directly:**
```bash
model-compose up -e OPENAI_API_KEY=sk-xxx -e PORT=9000
```

**Verbose logging:**
```bash
model-compose up --verbose
```

**Combine multiple options:**
```bash
model-compose -f config.yml up -d --env-file .env -v
```

### Operations

1. Load and validate configuration files
2. Load and merge environment variables
3. Set up and start components
4. Set up listeners and gateways
5. Start controller
6. Start Web UI (if configured)

---

## 3.3 down Command

Stops running services and cleans up all resources.

### Usage

```bash
model-compose down [options]
```

### Options

- `--env-file <file>`: Specify environment variable file (repeatable)
- `-e`, `--env <KEY=VALUE>`: Set environment variable directly (repeatable)
- `-v`, `--verbose`: Enable verbose output

### Examples

**Basic shutdown:**
```bash
model-compose down
```

**With environment variables:**
```bash
model-compose down --env-file .env
```

**Verbose logging:**
```bash
model-compose down --verbose
```

### Operations

1. Load configuration files
2. Identify running services
3. Stop controller
4. Clean up components
5. Clean up listeners and gateways
6. Release resources

---

## 3.4 start Command

Starts already configured services. Unlike `up`, only performs startup without new configuration.

### Usage

```bash
model-compose start [options]
```

### Options

- `--env-file <file>`: Specify environment variable file (repeatable)
- `-e`, `--env <KEY=VALUE>`: Set environment variable directly (repeatable)
- `-v`, `--verbose`: Enable verbose output

### Examples

```bash
model-compose start
model-compose start --verbose
model-compose start --env-file .env
```

### up vs start

| Command | Purpose | Operation |
|---------|---------|-----------|
| `up` | Initial setup and start | Create configuration + start services |
| `start` | Start existing services | Start services only |

---

## 3.5 stop Command

Stops running services. Configuration is preserved and can be restarted with `start`.

### Usage

```bash
model-compose stop [options]
```

### Options

- `--env-file <file>`: Specify environment variable file (repeatable)
- `-e`, `--env <KEY=VALUE>`: Set environment variable directly (repeatable)
- `-v`, `--verbose`: Enable verbose output

### Examples

```bash
model-compose stop
model-compose stop --verbose
```

### stop vs down

| Command | Purpose | Operation |
|---------|---------|-----------|
| `stop` | Pause | Stop services (keep configuration) |
| `down` | Complete shutdown | Stop services + clean up resources |

---

## 3.6 run Command

Executes a workflow once. Ideal for testing workflows from CLI or using in scripts.

### Usage

```bash
model-compose run [workflow-id] [options]
```

### Arguments

- `workflow-id`: ID of workflow to execute (optional, defaults to default workflow)

### Options

- `-i`, `--input <JSON>`: Workflow input data (JSON format)
- `--env-file <file>`: Specify environment variable file (repeatable)
- `-e`, `--env <KEY=VALUE>`: Set environment variable directly (repeatable)
- `-o`, `--output <file>`: Save output to file
- `-v`, `--verbose`: Enable verbose output

### Examples

**Run default workflow:**
```bash
model-compose run
```

**Run specific workflow:**
```bash
model-compose run generate-text
```

**With input data:**
```bash
model-compose run generate-text --input '{"prompt": "Hello"}'
```

**Formatted JSON input:**
```bash
model-compose run generate-text --input '{
  "prompt": "Explain AI",
  "temperature": 0.7
}'
```

**Save output to file:**
```bash
model-compose run generate-text \
  --input '{"prompt": "Hello"}' \
  --output result.json
```

**Specify environment variables:**
```bash
model-compose run generate-text \
  --input '{"prompt": "Test"}' \
  --env OPENAI_API_KEY=sk-xxx
```

**Combine multiple options:**
```bash
model-compose -f config.yml run my-workflow \
  --input '{"data": "test"}' \
  --env-file .env \
  --output output.json \
  --verbose
```

### Output Format

Workflow execution results are output in JSON format:

```json
{
  "response": "Workflow execution result..."
}
```

On error:
```json
{
  "error": "Error message..."
}
```

---

## 3.7 Environment Variable Management

model-compose supports various methods for managing environment variables.

### Method 1: .env File

Define environment variables in a `.env` file:

```bash
# .env
OPENAI_API_KEY=sk-your-key-here
ELEVENLABS_API_KEY=your-elevenlabs-key
PORT=8080
```

Usage:
```bash
model-compose up --env-file .env
```

### Method 2: Multiple .env Files

Use separate files for different environments:

```bash
# .env.base
PORT=8080
LOG_LEVEL=info

# .env.production
OPENAI_API_KEY=sk-prod-key
```

Usage (later files take precedence):
```bash
model-compose up --env-file .env.base --env-file .env.production
```

### Method 3: Command Line Direct Specification

```bash
model-compose up -e OPENAI_API_KEY=sk-xxx -e PORT=9000
```

### Method 4: System Environment Variables

Reference system environment variables directly in configuration:

```bash
export OPENAI_API_KEY=sk-xxx
model-compose up
```

### Priority Order

Environment variables are applied in the following order (highest priority first):

1. **Command line `-e` option** - Highest priority
2. **Current shell environment variables** - Medium priority
3. **`--env-file` files** (later files override earlier ones) - Lowest priority

This means:
- Shell environment variables override `.env` file values
- Command line `-e` arguments override everything
- This allows flexible configuration across different deployment scenarios

### Security Recommendations

- Add `.env` files to `.gitignore`
- Manage production keys in separate files
- Don't enter sensitive information directly in command line
- Use system environment variables in CI/CD

---

## 3.8 Configuration File Specification

### Single Configuration File

```bash
model-compose -f model-compose.yml up
```

### Merge Multiple Configuration Files

Later files take precedence over earlier files:

```bash
model-compose -f base.yml -f override.yml up
```

**Example:**

`base.yml`:
```yaml
controller:
  type: http-server
  port: 8080

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
```

`override.yml`:
```yaml
controller:
  port: 9000  # Overrides base.yml port

components:
  - id: custom-component
    type: http-client
```

Result: Port is 9000, both components are included

### Default Configuration File

If no configuration file is specified, searches current directory in this order:

1. `model-compose.yml`
2. `model-compose.yaml`

```bash
# Automatically uses model-compose.yml
model-compose up
```

### Environment-Specific Configuration

```bash
# Development environment
model-compose -f base.yml -f dev.yml up

# Staging environment
model-compose -f base.yml -f staging.yml up

# Production environment
model-compose -f base.yml -f production.yml up
```

---

## 3.9 Debugging Options

### Verbose Mode

All commands support the `-v` or `--verbose` flag to enable detailed logging:

```bash
model-compose up --verbose
model-compose run my-workflow --input '{}' --verbose
```

**Information displayed in verbose mode:**
- Configuration file loading process
- Environment variable merging process
- Component initialization logs
- HTTP request/response details
- Workflow execution step-by-step logs
- Error stack traces

### Error Messages

model-compose provides clear error messages:

```bash
❌ Invalid JSON provided for --input
❌ Configuration file not found: config.yml
❌ Environment variable OPENAI_API_KEY is required
```

### Common Troubleshooting

**Issue: Configuration file not found**
```bash
# Solution: Check file path
model-compose -f ./configs/model-compose.yml up
```

**Issue: Missing environment variable**
```bash
# Solution: Specify environment variable
model-compose up --env-file .env
```

**Issue: JSON parsing error**
```bash
# Incorrect
model-compose run --input '{prompt: "test"}'  # ❌

# Correct
model-compose run --input '{"prompt": "test"}'  # ✅
```

---

## 3.10 Practical Examples

### Development Workflow

```bash
# 1. Prepare development configuration
# dev.yml

# 2. Start services
model-compose -f base.yml -f dev.yml up

# 3. Test workflow
model-compose run test-workflow --input '{"test": true}' --verbose

# 4. Restart after changes
model-compose stop
model-compose start
```

### Production Deployment

```bash
# 1. Set production environment variables
export OPENAI_API_KEY=sk-prod-xxx
export ELEVENLABS_API_KEY=prod-xxx

# 2. Start with production configuration
model-compose -f base.yml -f production.yml up -d

# 3. Check status (view logs)
docker logs <container-id>  # For Docker runtime
```

### CI/CD Pipeline

```bash
#!/bin/bash
# deploy.sh

# Load environment variables
source .env.production

# Deploy service
model-compose -f base.yml -f production.yml up -d

# Health check
curl http://localhost:8080/health

# Run tests
model-compose run smoke-test --input '{}' --verbose
```

### Scripting

```bash
#!/bin/bash
# batch-process.sh

# Run workflow for multiple inputs
for file in inputs/*.json; do
  echo "Processing $file..."
  model-compose run process-data \
    --input "$(cat $file)" \
    --output "outputs/$(basename $file)" \
    --verbose
done
```

---

## 3.11 Command Quick Reference

### Basic Commands

| Command | Description | Main Options |
|---------|-------------|--------------|
| `up` | Start and run services | `-d`, `--env-file`, `-v` |
| `down` | Stop and clean up services | `--env-file`, `-v` |
| `start` | Start services | `--env-file`, `-v` |
| `stop` | Stop services | `--env-file`, `-v` |
| `run` | Execute workflow | `-i`, `-o`, `--env-file`, `-v` |

### Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--file` | `-f` | Specify configuration file |
| `--version` | - | Display version |
| `--help` | - | Display help |

### Common Options

| Option | Short | Description |
|--------|-------|-------------|
| `--env-file` | - | Environment variable file |
| `--env` | `-e` | Set environment variable directly |
| `--verbose` | `-v` | Verbose output |

### run Command Specific Options

| Option | Short | Description |
|--------|-------|-------------|
| `--input` | `-i` | Input JSON data |
| `--output` | `-o` | Output file path |

---

## Next Steps

Try it out:
- Experiment with various command combinations
- Organize environment-specific configuration files
- Use model-compose in scripts

---

**Next Chapter**: [4. Component Configuration](./04-component-configuration.md)
