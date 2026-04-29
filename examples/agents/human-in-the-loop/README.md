# Human-in-the-Loop Agent Example

This example demonstrates a file management agent that requires human approval before executing dangerous operations (write, delete), while allowing safe operations (read, list) to run without interruption.

## Overview

The agent operates through a ReAct loop with an interrupt mechanism:

1. **Receive Request**: The user asks the agent to perform file operations
2. **Select Tools**: The agent decides which tools to use
3. **Safe Operations**: Read and list execute immediately without interruption
4. **Dangerous Operations**: Write and delete pause for human approval before execution
5. **Answer**: Produces a result summary after completing the operations

### Available Tools

| Tool | Description | Requires Approval |
|------|-------------|:-----------------:|
| `read_file` | Read the contents of a file | No |
| `list_directory` | List files and directories | No |
| `write_file` | Write content to a file | Yes |
| `delete_file` | Delete a file | Yes |

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- OpenAI API key

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/agents/human-in-the-loop
   ```

2. Copy the sample environment file:
   ```bash
   cp .env.sample .env
   ```

3. Edit `.env` and add your API key:
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
     -d '{"request": "List the files in the current directory."}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your request and click "Run Workflow"
   - When a dangerous operation is triggered, a confirmation dialog will appear

   **Using CLI:**
   ```bash
   model-compose run --input '{"request": "Create a file called hello.txt with the content Hello World"}'
   ```

## Component Details

### OpenAI GPT-4o Component (gpt-4o)
- **Type**: HTTP client component
- **Purpose**: LLM for agent reasoning and tool selection
- **API**: OpenAI GPT-4o Chat Completions with function calling

### File Reader Component (file-reader)
- **Type**: Shell component
- **Purpose**: Read file contents using `cat`

### Directory Lister Component (directory-lister)
- **Type**: Shell component
- **Purpose**: List directory contents using `ls -la`

### File Writer Component (file-writer)
- **Type**: Shell component
- **Purpose**: Write content to a file using shell redirection

### File Deleter Component (file-deleter)
- **Type**: Shell component
- **Purpose**: Delete a file using `rm`

### File Manager Agent Component (file-manager)
- **Type**: Agent component
- **Purpose**: Orchestrates file operations with human approval for dangerous actions
- **Max Iterations**: 15

## How Interrupts Work

The `interrupt` feature pauses workflow execution before a dangerous job runs:

```yaml
interrupt:
  before:
    message: "The agent wants to write to a file. Please review and approve."
    metadata:
      path: ${job.input.path}
      content: ${job.input.content}
```

- **`before`**: The job pauses before execution and shows the message to the user
- **`metadata`**: Additional context displayed in the approval dialog (e.g., file path, content)
- The user can **approve** to proceed or **reject** to cancel the operation

This pattern ensures that the agent cannot perform destructive actions without explicit human consent.

## Customization

- Replace `gpt-4o` with other models that support function calling
- Add more tools (e.g., rename, move, copy) with or without interrupt guards
- Adjust `max_iteration_count` to control how many tool calls the agent can make
- Modify the `system_prompt` to change the agent's behavior or restrict allowed paths
