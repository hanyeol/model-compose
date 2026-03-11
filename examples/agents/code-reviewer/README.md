# Code Reviewer Agent Example

This example demonstrates an autonomous agent that reads files, lists directories, and searches code to perform code reviews and provide improvement suggestions.

## Overview

The agent operates through a ReAct loop:

1. **Receive Request**: The user provides a code review request with a target path
2. **Explore**: The agent lists directories and reads relevant files
3. **Search**: The agent searches for specific patterns across the codebase
4. **Review**: After understanding the code, the agent produces a detailed review

### Available Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read the contents of a file |
| `list_directory` | List files and directories with details |
| `search_code` | Search for patterns in files using grep |

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- OpenAI API key

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/agents/code-reviewer
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
     -d '{"request": "Review this code for potential bugs and suggest improvements", "target_path": "/path/to/project/src"}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your review request and target path, then click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{"request": "Find security vulnerabilities", "target_path": "./src"}'
   ```

## Component Details

### OpenAI GPT-4o Component (gpt-4o)
- **Type**: HTTP client component
- **Purpose**: LLM for agent reasoning and code analysis
- **API**: OpenAI GPT-4o Chat Completions with function calling

### Shell Components (file-reader, dir-lister, code-searcher)
- **Type**: Shell component
- **Purpose**: File system operations for code exploration
- **Commands**: `cat`, `ls -la`, `grep -rn`

### Code Reviewer Agent Component (code-reviewer)
- **Type**: Agent component
- **Purpose**: Autonomous agent that explores and reviews code
- **Max Iterations**: 15

## Workflow Details

### Tool: read_file

**Description**: Read and return the contents of a file.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | Path of the file to read |

### Tool: list_directory

**Description**: List all files and directories with details at the given path.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | Path of the directory to list |

### Tool: search_code

**Description**: Search for a pattern in files recursively using grep.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | string | Yes | - | The search pattern or regex to look for |
| `path` | string | No | `.` | Directory path to search in |

## Customization

- Replace `gpt-4o` with other models that support function calling
- Add more tools (e.g., `wc` for line counting, `diff` for file comparison)
- Adjust `max_iteration_count` to allow deeper code exploration
- Modify shell commands to suit your needs (e.g., use `rg` instead of `grep`)
