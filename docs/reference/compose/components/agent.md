# Agent Component

The agent component builds autonomous AI agents that use workflows (and optionally external schemas) as tools. It implements a ReAct (Reasoning + Acting) loop where an LLM iteratively reasons about a task, calls tools, and processes results until a final answer is produced.

## Basic Configuration

```yaml
component:
  type: agent
  model:
    component: gpt-4o
    input:
      messages: ${messages}
      tools: ${tools}
  instructions: You are a helpful research assistant.
  tools:
    - search-web
    - analyze-image
  action:
    prompt: ${input.question}
```

The `model`, `instructions`, and `tools` fields are component-level and shared by every action. Each action defines its own `prompt` and may override `max_iteration_count`.

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `agent` |
| `model` | object | **required** | LLM backend used by every action (see [Model Configuration](#model-configuration)) |
| `instructions` | string | `null` | System-message text that sets the agent's persona and behavior. When set, a `system` message is prepended to the conversation. |
| `tools` | array | `[]` | Workflow IDs or inline tool schemas the agent may call (see [Tool Configuration](#tool-configuration)) |
| `max_iteration_count` | integer | `32` | Maximum number of ReAct loop iterations before the agent halts |
| `actions` | array | `[]` | Actions this component exposes to workflows (shorthand: `action:` for a single action) |

### Action Configuration

Agent actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | string | `null` | Prompt for this invocation, applied as a `user` message. Supports variable interpolation. |
| `max_iteration_count` | integer | `null` | Maximum iterations (overrides component-level setting) |
| `streaming` | bool/string | `false` | When true, the loop yields each assistant/tool message as it is produced |
| `output` | any | `null` | Output mapping that transforms and extracts values from the final message list |

If `prompt` is omitted, no `user` message is added — the first model call will contain only the `system` message from `instructions` (if any). Most chat templates require a `user` turn, so set `prompt` unless the upstream `model.component` already injects one.

### Model Configuration

The `model` object specifies which component handles LLM calls:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `component` | string | **required** | ID of the component that handles LLM calls for this agent |
| `action` | string | `__default__` | ID of the action invoked on that component |
| `input` | object | `{}` | Input mapping from the agent's internal state to the component's input fields |
| `output` | any | `null` | Output mapping that shapes the component's response into a [canonical assistant message](../chat-completion-message.md) |

### Model Input Variables

The `model.input` mapping supports the following variables:

| Variable | Type | Description |
|----------|------|-------------|
| `${messages}` | array | Full conversation message history (`system`, `user`, `assistant`, `tool` messages) in [canonical form](../chat-completion-message.md), re-sent on every iteration |
| `${tools}` | array | Tool schemas generated from `tools` (one entry per workflow tool or inline schema) |
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
    model:
      component: gpt-4o
      input:
        messages: ${messages}
        tools: ${tools}
      # Translate OpenAI's response shape into the canonical assistant message.
      # See docs/reference/compose/chat-completion-message.md for provider mappings.
      output:
        role: assistant
        content:
          "+":
            - "?":
                input: ${response.choices[0].message.content}
                operator: neq
                value: null
                if_true:
                  - type: text
                    text: ${response.choices[0].message.content}
            - "*": ${response.choices[0].message.tool_calls}
              type: tool_call
              id: ${item.id}
              name: ${item.function.name}
              arguments: ${item.function.arguments as json}
    instructions: You are a helpful research assistant.
    tools:
      - search-web
    action:
      prompt: ${input.question}

workflows:
  - id: search-web
    name: web_search
    description: Search the web for information.
    jobs:
      - component: tavily
        input:
          query: ${input.query @(description The search query string)}
```

### Multi-Action Agent

A single `agent` component shares `model`, `instructions`, and `tools` across all its actions; each action supplies its own `prompt` and may override `max_iteration_count`.

```yaml
component:
  type: agent
  model:
    component: gpt-4o
    input:
      messages: ${messages}
      tools: ${tools}
  instructions: You are a thorough research assistant.
  tools:
    - search-web
    - fetch-url
    - analyze-image
  max_iteration_count: 15
  actions:
    - id: research
      prompt: ${input.question}

    - id: summarize
      prompt: Summarize the following in two sentences:\n\n${input.text}
      max_iteration_count: 1
```

If one action needs a different LLM or a different system message, define a second `agent` component.

### Agent without Tools

An agent can operate without tools for single-turn inference:

```yaml
component:
  type: agent
  model:
    component: gpt-4o
    input:
      messages: ${messages}
  instructions: You are a helpful assistant.
  action:
    prompt: ${input.question}
    max_iteration_count: 1
```

### Streaming Agent

Set `streaming: true` to receive each assistant/tool message as the ReAct loop produces it. This streams whole messages, not tokens — token streaming on the underlying `model.component` is independent (see [user-guide/13-streaming-mode.md](../../../user-guide/13-streaming-mode.md)).

```yaml
component:
  type: agent
  model:
    component: gpt-4o
    input:
      messages: ${messages}
      tools: ${tools}
  instructions: You are a helpful assistant.
  tools:
    - search-web
  action:
    prompt: ${input.question}
    streaming: true
```

## Tool Configuration

Entries under `tools` may be either a workflow ID (string) or an inline tool schema (`ModelTool` object).

### Workflow as Tool

When a tool entry is a string, it is resolved as a workflow ID. The workflow becomes a callable function for the LLM, and its input schema is translated into a function-calling schema.

```yaml
workflows:
  - id: search-web
    name: web_search
    description: Search the web and return relevant results.
    jobs:
      - component: tavily-client
        input:
          query: ${input.query @(description The search query string)}
          max_results: ${input.max_results as integer | 5 @(description Maximum number of results to return)}
```

Translation rules for the workflow's input parameters:

- Parameter names come from `${input.<name>}` bindings
- Types are inferred from type annotations (e.g., `as integer`)
- Descriptions come from `@(description ...)` annotations
- Default values come from `| <default>` syntax
- Parameters without defaults are marked as required
- The tool name is `workflow.name` if set, otherwise the workflow ID (invalid function-name characters are replaced with `_`)

### Generated Tool Schema

The workflow above generates this schema (as passed to the model via `${tools}`):

```json
{
  "name": "web_search",
  "description": "Search the web and return relevant results.",
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
```

This is a flat `{name, description, parameters}` object (no `{"type": "function", "function": {...}}` wrapper). If your provider needs the wrapped shape, add it in the model component's `body` mapping, e.g. `tools: [{ type: function, function: ${item} } for item in ${input.tools}]`.

### Inline Tool Schema

A tool entry can also be an inline `ModelTool` object. The agent emits it to `${tools}` without any workflow resolution, but it cannot be invoked locally — the loop will raise `Unknown tool` if the model picks it. Use inline schemas when the tool is actually executed outside the loop (for example, through a Human-in-the-Loop interrupt that forwards tool calls to the caller).

```yaml
tools:
  - name: approve_action
    description: Ask the operator to approve a destructive action.
    parameters:
      type: object
      properties:
        reason:
          type: string
          description: Why approval is needed.
      required: [ reason ]
```

## How It Works

### ReAct Loop

The agent follows this execution cycle:

1. **Build initial messages**: Start a `messages` list containing a `system` message (from `instructions`, if set) and a `user` message (from `action.prompt`, if set).
2. **Call LLM**: Send the full `messages` and tool schemas to `model.component`.
3. **Append assistant message**: The response is reshaped by `model.output` into a canonical assistant message and appended to `messages`.
4. **Check for tool calls**: If the assistant message contains any `tool_call` blocks, continue; otherwise return.
5. **Execute tools**: Workflow tool calls run concurrently via workflow execution. Inline (external) tool calls pause the agent at an interrupt point until the caller resumes with results.
6. **Append tool results**: Each tool call produces a `tool` message with a `tool_result` block; these are appended to `messages`.
7. **Repeat**: Go back to step 2 (up to `max_iteration_count` iterations).

Every iteration re-sends the full conversation to the model, including the original `system` and `user` messages.

### Parallel Tool Execution

When the assistant message contains multiple `tool_call` blocks, workflow tools execute concurrently via `asyncio.gather`. Each tool result is appended as its own `tool` message (one `tool_result` per message) to preserve stateless mapping downstream.

### Model Component Contract

The `model.component` is invoked with:

- `${messages}` — list of canonical messages (full history, re-sent every call)
- `${tools}` — list of tool schemas (omitted when the agent has no tools)
- Any additional variables wired in `model.input`

It must return a response that, after applying `model.output`, matches a canonical assistant message:

```yaml
role: assistant
content:
  - { type: text, text: "..." }                                # 0 or 1
  - { type: tool_call, id: ..., name: ..., arguments: {...} }  # 0 or more
```

The agent inspects `content[*].type == "tool_call"` to decide whether to continue the tool loop. See [Chat Completion Message — Canonical Format](../chat-completion-message.md) for the full canonical shape and per-provider `output` mappings (OpenAI, Anthropic, Gemini).

### Action Result

By default an action returns the full `messages` list (`${result}`). Set `action.output` to reshape it — e.g. `output: ${result[-1].content[0].text}` to return just the final assistant text.

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
        raw_messages: ${agent-task.output}
      depends_on: [ agent-task ]
```

## Variable Interpolation

Agent components support dynamic configuration:

```yaml
component:
  type: agent
  model:
    component: ${env.DEFAULT_LLM | gpt-4o}
    input:
      messages: ${messages}
      tools: ${tools}
  instructions: ${env.SYSTEM_PROMPT | You are a helpful assistant.}
  tools:
    - search-web
    - analyze-data
  max_iteration_count: ${env.MAX_ITERATIONS as integer | 10}
  action:
    prompt: ${input.question}
```

## Best Practices

1. **Tool Design**: Give workflows clear descriptions and well-typed parameters for better LLM tool selection
2. **Iteration Limits**: Set appropriate `max_iteration_count` to prevent infinite loops and control costs
3. **Model Selection**: Choose model components that support function calling (e.g., GPT-4o, Claude, Llama 3.1+)
4. **Instructions**: Use component-level `instructions` to define the agent's role; keep action `prompt`s focused on the per-invocation task
5. **Output Mapping**: Translate the provider's response into the canonical assistant shape via `model.output` — see [Chat Completion Message](../chat-completion-message.md)
6. **Tool Granularity**: Keep tools focused on single responsibilities for better agent reasoning
7. **Error Handling**: Tools should return descriptive error messages; the agent surfaces them as `tool_result` blocks with `is_error: true`

## Common Use Cases

- **Research Agents**: Search the web, fetch URLs, and synthesize information
- **Coding Agents**: Read files, write code, and run tests autonomously
- **Data Analysis Agents**: Query databases, process data, and generate reports
- **Customer Support Agents**: Look up information, perform actions, and respond to users
- **Multi-Step Reasoning**: Break down complex tasks using tool-assisted reasoning
