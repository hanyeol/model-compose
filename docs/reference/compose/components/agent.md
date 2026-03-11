# Agent Component

The agent component enables building autonomous AI agents that use workflows as tools. It implements a ReAct (Reasoning + Acting) loop where an LLM iteratively reasons about a task, calls tools, and processes results until a final answer is produced.

## Basic Configuration

```yaml
component:
  type: agent
  tools:
    - search-web
    - analyze-image
  action:
    model:
      component: gpt-4o
      input:
        messages: ${messages}
        tools: ${tools}
    system_prompt: You are a helpful research assistant.
    user_prompt: ${input.question}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `agent` |
| `tools` | array | `[]` | List of workflow IDs to use as tools |
| `max_iteration_count` | integer | `10` | Maximum number of ReAct loop iterations |
| `actions` | array | `[]` | List of agent actions |

### Action Configuration

Agent actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | object | **required** | LLM model configuration for this action |
| `system_prompt` | any | `null` | System prompt. When set, a system message is prepended to the conversation |
| `user_prompt` | any | `null` | User prompt. Supports variable interpolation |
| `max_iteration_count` | integer | `null` | Maximum iterations (overrides component-level setting) |

If `user_prompt` is not specified, the agent's component input is used as the user message.

### Model Configuration

The `model` object specifies which component to use for LLM calls:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `component` | string | **required** | ID of the component to use for LLM calls |
| `action` | string | `__default__` | ID of the action to invoke on the component |
| `input` | object | `{}` | Input mapping from agent internal state to component input |

### Model Input Variables

The `model.input` mapping supports the following variables:

| Variable | Type | Description |
|----------|------|-------------|
| `${messages}` | array | Conversation message history (user, assistant, tool messages) managed by the agent |
| `${tools}` | array | Function calling schemas automatically generated from workflow tool definitions |
| `${input.*}` | any | Agent's original input variables (e.g., `${input.question}`) |

## Usage Examples

### Simple Agent with Tools

```yaml
components:
  - id: gpt-4o
    type: http-client
    base_url: https://api.openai.com/v1
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    action:
      path: /chat/completions
      body:
        model: gpt-4o
        messages: ${input.messages}
        tools: ${input.tools}
      output: ${response.choices[0].message}

  - id: research-agent
    type: agent
    tools:
      - search-web
    action:
      model:
        component: gpt-4o
        input:
          messages: ${messages}
          tools: ${tools}
      system_prompt: You are a helpful research assistant.
      user_prompt: ${input.question}

workflows:
  - id: search-web
    description: "Search the web for information"
    jobs:
      - component: tavily
        input:
          query: ${input.query}
```

### Multi-Action Agent

```yaml
component:
  type: agent
  tools:
    - search-web
    - fetch-url
    - analyze-image
  max_iteration_count: 15
  actions:
    - id: research
      model:
        component: gpt-4o
        input:
          messages: ${messages}
          tools: ${tools}
      system_prompt: You are a thorough research assistant.
      user_prompt: ${input.question}

    - id: summarize
      model:
        component: claude-sonnet
        input:
          messages: ${messages}
      system_prompt: You are a concise summarizer.
      user_prompt: ${input.text}
      max_iteration_count: 1
```

### Agent with Custom Model Action

```yaml
components:
  - id: llm-server
    type: http-client
    base_url: http://localhost:8000/v1
    actions:
      - id: chat
        path: /chat/completions
        body:
          model: llama-3.1-70b
          messages: ${input.messages}
          tools: ${input.tools}
          temperature: 0.7
        output: ${response.choices[0].message}

      - id: chat-precise
        path: /chat/completions
        body:
          model: llama-3.1-70b
          messages: ${input.messages}
          tools: ${input.tools}
          temperature: 0.1
        output: ${response.choices[0].message}

  - id: coding-agent
    type: agent
    tools:
      - read-file
      - write-file
      - run-tests
    action:
      model:
        component: llm-server
        action: chat-precise
        input:
          messages: ${messages}
          tools: ${tools}
      system_prompt: You are an expert coding assistant. Read files, write code, and run tests to complete the task.
      user_prompt: ${input.task}
```

### Agent without Tools

An agent can operate without tools for single-turn inference:

```yaml
component:
  type: agent
  action:
    model:
      component: gpt-4o
      input:
        messages: ${messages}
    system_prompt: You are a helpful assistant.
    user_prompt: ${input.question}
    max_iteration_count: 1
```

## Tool Configuration

### Workflow as Tool

Agent tools are defined as workflows. Each workflow becomes a callable function for the LLM.

```yaml
workflows:
  - id: search-web
    name: web_search
    description: "Search the web and return relevant results"
    jobs:
      - component: tavily-client
        input:
          query: ${input.query @(description The search query string)}
          max_results: ${input.max_results as integer | 5 @(description Maximum number of results to return)}
```

The workflow's input parameters are automatically converted to a function calling schema:

- Parameter names come from `${input.<name>}` bindings
- Types are inferred from type annotations (e.g., `as integer`)
- Descriptions come from `@(description ...)` annotations
- Default values come from `| <default>` syntax
- Parameters without defaults are marked as required

### Generated Function Schema

The above workflow generates the following function calling schema:

```json
{
  "type": "function",
  "function": {
    "name": "web_search",
    "description": "Search the web and return relevant results",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "The search query string"
        },
        "max_results": {
          "type": "integer",
          "description": "Maximum number of results to return",
          "default": 5
        }
      },
      "required": ["query"]
    }
  }
}
```

## How It Works

### ReAct Loop

The agent follows this execution cycle:

1. **Build Messages**: Construct initial messages from `system_prompt` and `user_prompt`
2. **Call LLM**: Send messages and tool schemas to the model component
3. **Check Response**: If the response contains tool calls, continue; otherwise return the content
4. **Execute Tools**: Run all tool calls in parallel via workflow execution
5. **Append Results**: Add tool results to the message history
6. **Repeat**: Go back to step 2 (up to `max_iteration_count` times)

### Parallel Tool Execution

When the LLM returns multiple tool calls in a single response, the agent executes them concurrently for optimal performance.

### Model Component Requirements

The model component must return a response in the following format:

```json
{
  "content": "The response text",
  "tool_calls": [
    {
      "id": "call_abc123",
      "function": {
        "name": "web_search",
        "arguments": "{\"query\": \"model-compose documentation\"}"
      }
    }
  ]
}
```

This is compatible with the OpenAI Chat Completions API response format. Use an `http-client` component with appropriate `output` mapping to extract the message object.

## Integration with Workflows

Reference agent components in workflow jobs:

```yaml
workflow:
  jobs:
    - id: agent-task
      component: research-agent
      action: research
      input:
        question: ${input.user_question}

    - id: format-output
      component: formatter
      input:
        raw_answer: ${agent-task.output}
      depends_on: [ agent-task ]
```

## Variable Interpolation

Agent components support dynamic configuration:

```yaml
component:
  type: agent
  tools:
    - search-web
    - analyze-data
  action:
    model:
      component: ${env.DEFAULT_LLM | gpt-4o}
      input:
        messages: ${messages}
        tools: ${tools}
    system_prompt: ${env.SYSTEM_PROMPT | You are a helpful assistant.}
    user_prompt: ${input.question}
    max_iteration_count: ${env.MAX_ITERATIONS as integer | 10}
```

## Best Practices

1. **Tool Design**: Design workflows with clear descriptions and well-typed parameters for better LLM tool selection
2. **Iteration Limits**: Set appropriate `max_iteration_count` to prevent infinite loops and control costs
3. **Model Selection**: Choose model components that support function calling (e.g., GPT-4o, Claude, Llama 3.1+)
4. **Input Mapping**: Use `model.input` to pass agent-managed state (`${messages}`, `${tools}`) to the model component
5. **System Prompts**: Use `system_prompt` to define the agent's role and behavior guidelines
6. **Tool Granularity**: Keep tools focused on single responsibilities for better agent reasoning
7. **Error Handling**: Tools should return descriptive error messages to help the agent recover

## Common Use Cases

- **Research Agents**: Search the web, fetch URLs, and synthesize information
- **Coding Agents**: Read files, write code, and run tests autonomously
- **Data Analysis Agents**: Query databases, process data, and generate reports
- **Customer Support Agents**: Look up information, perform actions, and respond to users
- **Multi-Step Reasoning**: Break down complex tasks using tool-assisted reasoning
