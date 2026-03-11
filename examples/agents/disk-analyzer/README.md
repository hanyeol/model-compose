# Disk Analyzer Agent Example

This example demonstrates an autonomous agent that uses shell commands as tools to analyze system disk usage and provide detailed recommendations. It is an agent-powered version of the `analyze-disk-usage` example.

## Overview

The agent operates through a ReAct loop:

1. **Receive Question**: The user provides a disk analysis question (or uses the default)
2. **Investigate**: The agent autonomously runs shell commands to inspect disk usage, directory sizes, and file listings
3. **Analyze**: After gathering enough information, the agent produces a detailed analysis with recommendations

### Available Tools

| Tool | Description |
|------|-------------|
| `get_disk_usage` | Get overall disk usage for all mounted filesystems (`df -h`) |
| `get_directory_sizes` | Get the total size of a specific directory (`du -sh`) |
| `list_files` | List files and directories with details (`ls -la`) |

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- OpenAI API key

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/agents/disk-analyzer
   ```

2. Copy the sample environment file:
   ```bash
   cp .env.sample .env
   ```

3. Edit `.env` and add your OpenAI API key:
   ```env
   OPENAI_API_KEY=your-openai-api-key
   ```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"question": "Which directories under /home are using the most disk space?"}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your question and click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{"question": "Analyze disk usage and find large files"}'
   ```

## Component Details

### OpenAI GPT-4o Component (gpt-4o)
- **Type**: HTTP client component
- **Purpose**: LLM for agent reasoning and tool use
- **API**: OpenAI GPT-4o Chat Completions with function calling

### Shell Components (disk-usage, directory-sizes, file-lister)
- **Type**: Shell component
- **Purpose**: Execute system commands for disk analysis
- **Commands**: `df -h`, `du -sh`, `ls -la`

### Disk Analyzer Agent Component (disk-analyzer)
- **Type**: Agent component
- **Purpose**: Autonomous agent that investigates disk usage
- **Max Iterations**: 10

## Workflow Details

### Tool: get_disk_usage

**Description**: Get overall disk usage information for all mounted filesystems.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| - | - | - | - | This tool requires no input parameters |

### Tool: get_directory_sizes

**Description**: Get the total size of a specific directory.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | Absolute path of the directory to measure |

### Tool: list_files

**Description**: List files and directories with details in a given path.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | Absolute path of the directory to list |

## Customization

- Replace `gpt-4o` with other models that support function calling
- Add more shell tools (e.g., `find` for searching files, `top` for process info)
- Adjust `max_iteration_count` to allow deeper investigation
- Modify shell commands to suit your operating system
