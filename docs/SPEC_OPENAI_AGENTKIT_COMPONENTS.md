# OpenAI AgentKit Components Specification

## Overview

This specification defines model-compose components that wrap OpenAI's AgentKit (Agents SDK) functionality. AgentKit provides a lightweight framework for building multi-agent workflows with features including agent orchestration, handoffs, guardrails, sessions, and tracing.

## Architecture

The OpenAI AgentKit integration consists of multiple components that map to different AgentKit primitives:

1. **Agent Component** - Core agent definition with instructions, tools, and configuration
2. **Agent Runner Component** - Executes agents and manages multi-agent workflows
3. **Agent Session Component** - Manages conversation history and state persistence
4. **Agent Guardrail Component** - Validates inputs and outputs with safety checks

## Component 1: OpenAI Agent (`openai-agent`)

### Purpose
Defines a single OpenAI agent with instructions, tools, handoffs, and configuration.

### Configuration Schema

```yaml
components:
  - id: my-agent
    type: openai-agent
    runtime: native

    # Core agent configuration
    name: "Agent Name"
    instructions: "Detailed instructions for agent behavior"
    model: "gpt-4o"  # Optional, defaults to gpt-4o

    # Agent capabilities
    tools:
      - type: function
        function:
          name: "tool_name"
          description: "Tool description"
          parameters:
            type: object
            properties:
              param1:
                type: string
                description: "Parameter description"

      - type: component
        component_id: "existing-component-id"  # Reference to existing component

      - type: mcp
        server_url: "http://localhost:3000"
        tools: ["tool1", "tool2"]  # Optional: specific tools from MCP server

    # Multi-agent handoffs
    handoffs:
      - agent_id: "specialist-agent-1"
        handoff_description: "Transfer to specialist for X tasks"
      - agent_id: "specialist-agent-2"
        handoff_description: "Transfer to specialist for Y tasks"

    # Output type validation (optional)
    output_type:
      type: object
      properties:
        result:
          type: string
        confidence:
          type: number
      required: ["result"]

    # Parallel tool calls
    parallel_tool_calls: true  # Default: true

    # Temperature and other model parameters
    temperature: 0.7
    max_tokens: 1000
    top_p: 1.0

    actions:
      - id: run
        input:
          messages: ${input.messages}  # List of message objects
          # OR
          prompt: ${input.prompt}  # Single string prompt

          # Optional context
          context: ${input.context}

        output: ${output}  # Agent's response
```

### Actions

#### `run` (default action)
Executes the agent with the provided input.

**Input:**
- `messages`: List of conversation messages (OpenAI format)
  ```yaml
  messages:
    - role: system
      content: "System message"
    - role: user
      content: "User message"
  ```
- `prompt`: Simple string prompt (automatically converted to messages)
- `context`: Optional context data passed to tools

**Output:**
- Agent's final response (string or structured based on `output_type`)

### Tool Integration

Tools can be defined in three ways:

1. **Function Tools**: Native function definitions with JSON schema
2. **Component Tools**: References to existing model-compose components
3. **MCP Tools**: Integration with Model Context Protocol servers

### Implementation Notes

- Uses `openai-agents-python` SDK
- Requires `openai` Python package
- API key configured via `OPENAI_API_KEY` environment variable
- Supports async execution via `Runner.run()`

---

## Component 2: OpenAI Agent Runner (`openai-agent-runner`)

### Purpose
Orchestrates multi-agent workflows, manages handoffs, and provides advanced execution control.

### Configuration Schema

```yaml
components:
  - id: my-runner
    type: openai-agent-runner
    runtime: native

    # Initial agent
    entry_agent_id: "triage-agent"

    # Session management
    session:
      type: memory  # memory | sqlite | sqlalchemy | encrypted

      # For sqlite/sqlalchemy
      connection_string: "sqlite:///sessions.db"

      # For encrypted sessions
      encryption_key: ${env.SESSION_ENCRYPTION_KEY}

    # Tracing configuration
    tracing:
      enabled: true
      export_to_openai: true  # Export to OpenAI Dashboard

    # Timeout settings
    timeout: 60  # seconds
    max_iterations: 20  # Max handoff iterations

    actions:
      - id: run
        input:
          prompt: ${input.prompt}
          session_id: ${input.session_id}  # Optional: for session continuity
          stream: false  # Stream responses

        output:
          final_output: ${output.final_output}
          conversation_history: ${output.messages}
          agent_path: ${output.agent_path}  # List of agents involved
          trace_id: ${output.trace_id}
```

### Actions

#### `run` (default action)
Executes a multi-agent workflow starting from the entry agent.

**Input:**
- `prompt`: User's input prompt
- `session_id`: Optional session ID for conversation continuity
- `stream`: Enable streaming responses (default: false)
- `max_iterations`: Override max handoff iterations

**Output:**
- `final_output`: Final response from the workflow
- `conversation_history`: Complete message history
- `agent_path`: List of agent IDs that handled the request
- `trace_id`: Tracing ID for debugging

#### `continue`
Continues an existing conversation session.

**Input:**
- `session_id`: Session ID to continue
- `prompt`: New user message

**Output:** Same as `run`

### Session Types

1. **Memory**: In-memory session (default, non-persistent)
2. **SQLite**: File-based persistent sessions
3. **SQLAlchemy**: Database-backed sessions (PostgreSQL, MySQL, etc.)
4. **Encrypted**: Encrypted session storage for sensitive data

### Implementation Notes

- Manages the full agent loop: tool invocation, result transmission, continuation
- Handles automatic handoffs between agents
- Provides built-in tracing and monitoring
- Supports streaming for real-time responses

---

## Component 3: OpenAI Agent Guardrail (`openai-agent-guardrail`)

### Purpose
Validates agent inputs and outputs using custom validation logic or guardrail agents.

### Configuration Schema

```yaml
components:
  - id: content-filter
    type: openai-agent-guardrail
    runtime: native

    # Guardrail type
    guardrail_type: input  # input | output | both

    # Validation approach
    validation:
      type: agent  # agent | function | rules

      # Agent-based validation
      agent:
        name: "Content Validator"
        instructions: |
          Analyze the provided content for policy violations.
          Return a structured response with is_valid (boolean) and reasoning (string).
        model: "gpt-4o-mini"  # Use cheaper model for guardrails
        output_type:
          type: object
          properties:
            is_valid:
              type: boolean
            reasoning:
              type: string
            severity:
              type: string
              enum: ["low", "medium", "high"]
          required: ["is_valid", "reasoning"]

      # Function-based validation
      function:
        component_id: "validation-component"

      # Rule-based validation
      rules:
        - type: regex
          pattern: "\\b(prohibited|banned|forbidden)\\b"
          reject_on_match: true
          message: "Content contains prohibited terms"

        - type: length
          max_length: 10000
          message: "Content exceeds maximum length"

        - type: pii
          check_email: true
          check_phone: true
          check_ssn: true
          message: "Content contains PII"

    # Guardrail behavior
    on_failure:
      action: reject  # reject | warn | sanitize
      message: "Input failed validation: ${validation.reasoning}"

    actions:
      - id: validate
        input:
          content: ${input.content}
          context: ${input.context}  # Optional context

        output:
          is_valid: ${output.is_valid}
          reasoning: ${output.reasoning}
          severity: ${output.severity}
          sanitized_content: ${output.sanitized_content}  # If action=sanitize
```

### Actions

#### `validate` (default action)
Validates input/output content against configured rules.

**Input:**
- `content`: Content to validate (string or structured)
- `context`: Optional context for validation

**Output:**
- `is_valid`: Boolean validation result
- `reasoning`: Explanation of validation decision
- `severity`: Severity level (if applicable)
- `sanitized_content`: Cleaned content (if using sanitize action)

### Validation Types

1. **Agent-based**: Uses LLM to validate with custom instructions
2. **Function-based**: Delegates to custom validation component
3. **Rule-based**: Simple regex, length, and PII checks

### Implementation Notes

- Can be used standalone or attached to agents
- Supports both input and output validation
- Agent-based validation uses structured outputs for reliability
- Rule-based validation is faster and cheaper for simple checks

---

## Component 4: OpenAI Agent Session (`openai-agent-session`)

### Purpose
Manages conversation history and state persistence for agent workflows.

### Configuration Schema

```yaml
components:
  - id: my-session-store
    type: openai-agent-session
    runtime: native

    # Backend configuration
    backend:
      type: sqlite  # memory | sqlite | sqlalchemy | encrypted

      # SQLite configuration
      database_path: ./sessions.db
      table_name: agent_sessions

      # SQLAlchemy configuration
      connection_string: postgresql://user:pass@localhost/db
      pool_size: 10

      # Encryption configuration
      encryption_key: ${env.SESSION_ENCRYPTION_KEY}
      encryption_algorithm: AES-256-GCM

    # Session settings
    ttl: 3600  # Session TTL in seconds (0 = no expiration)
    max_messages: 100  # Max messages per session
    auto_summarize: true  # Summarize old messages

    actions:
      - id: create
        input:
          initial_context: ${input.context}  # Optional initial context
        output:
          session_id: ${output.session_id}

      - id: get
        input:
          session_id: ${input.session_id}
        output:
          messages: ${output.messages}
          metadata: ${output.metadata}

      - id: update
        input:
          session_id: ${input.session_id}
          messages: ${input.messages}  # Append messages
          metadata: ${input.metadata}  # Update metadata
        output:
          success: ${output.success}

      - id: delete
        input:
          session_id: ${input.session_id}
        output:
          success: ${output.success}

      - id: list
        input:
          limit: ${input.limit}
          offset: ${input.offset}
        output:
          sessions: ${output.sessions}
          total: ${output.total}
```

### Actions

#### `create`
Creates a new session.

**Input:**
- `initial_context`: Optional initial context/metadata

**Output:**
- `session_id`: Unique session identifier

#### `get`
Retrieves session data.

**Input:**
- `session_id`: Session identifier

**Output:**
- `messages`: Conversation history
- `metadata`: Session metadata

#### `update`
Updates session with new messages or metadata.

**Input:**
- `session_id`: Session identifier
- `messages`: Messages to append
- `metadata`: Metadata to update

**Output:**
- `success`: Boolean result

#### `delete`
Deletes a session.

**Input:**
- `session_id`: Session identifier

**Output:**
- `success`: Boolean result

#### `list`
Lists all sessions (with pagination).

**Input:**
- `limit`: Max results
- `offset`: Pagination offset

**Output:**
- `sessions`: List of session objects
- `total`: Total session count

### Backend Types

1. **Memory**: In-memory storage (non-persistent)
2. **SQLite**: File-based persistent storage
3. **SQLAlchemy**: Database-backed storage (PostgreSQL, MySQL, etc.)
4. **Encrypted**: Encrypted persistent storage

---

## Example Workflow: Multi-Agent Customer Support

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Customer Support Agent
  description: Multi-agent customer support with triage, billing, and technical specialists

  jobs:
    - id: init-session
      component: session-store
      action: create
      input:
        initial_context:
          customer_id: ${input.customer_id}
      output:
        session_id: ${output.session_id}

    - id: validate-input
      component: content-filter
      input:
        content: ${input.message}
      output:
        is_valid: ${output.is_valid}
      depends_on: [init-session]

    - id: run-support-agent
      component: support-runner
      input:
        prompt: ${input.message}
        session_id: ${jobs.init-session.session_id}
      output:
        response: ${output.final_output}
        agent_path: ${output.agent_path}
      depends_on: [validate-input]
      condition: ${jobs.validate-input.is_valid}

components:
  # Session management
  - id: session-store
    type: openai-agent-session
    backend:
      type: sqlite
      database_path: ./support_sessions.db
    ttl: 7200

  # Input guardrail
  - id: content-filter
    type: openai-agent-guardrail
    guardrail_type: input
    validation:
      type: agent
      agent:
        name: "Content Validator"
        instructions: "Check for abusive language or security threats"
        model: "gpt-4o-mini"
        output_type:
          type: object
          properties:
            is_valid:
              type: boolean
            reasoning:
              type: string
    on_failure:
      action: reject
      message: "Your message violates our content policy"

  # Agent runner
  - id: support-runner
    type: openai-agent-runner
    entry_agent_id: triage-agent
    session:
      type: memory
    tracing:
      enabled: true
      export_to_openai: true
    max_iterations: 10

  # Triage agent
  - id: triage-agent
    type: openai-agent
    name: "Triage Agent"
    instructions: |
      You are a customer support triage agent.
      Route customers to the appropriate specialist:
      - Billing issues -> billing-agent
      - Technical problems -> tech-support-agent
      - General questions -> answer directly
    model: "gpt-4o"
    handoffs:
      - agent_id: billing-agent
        handoff_description: "Transfer for billing, payments, or subscription issues"
      - agent_id: tech-support-agent
        handoff_description: "Transfer for technical problems or bugs"
    tools:
      - type: component
        component_id: customer-db

  # Billing specialist
  - id: billing-agent
    type: openai-agent
    name: "Billing Specialist"
    instructions: |
      You are a billing specialist. Help customers with:
      - Payment issues
      - Subscription management
      - Invoices and receipts
      Access customer billing data and process requests.
    model: "gpt-4o"
    tools:
      - type: component
        component_id: billing-db
      - type: function
        function:
          name: "process_refund"
          description: "Process a refund for a customer"
          parameters:
            type: object
            properties:
              customer_id:
                type: string
              amount:
                type: number
              reason:
                type: string

  # Technical support specialist
  - id: tech-support-agent
    type: openai-agent
    name: "Technical Support"
    instructions: |
      You are a technical support specialist.
      Help customers troubleshoot technical issues.
      Search knowledge base and create tickets if needed.
    model: "gpt-4o"
    tools:
      - type: component
        component_id: knowledge-base
      - type: component
        component_id: ticket-system

  # Supporting components
  - id: customer-db
    type: http-client
    base_url: ${env.CUSTOMER_DB_URL}
    actions:
      - id: get-customer
        path: /customers/${input.customer_id}
        method: GET
        output: ${response}

  - id: billing-db
    type: http-client
    base_url: ${env.BILLING_API_URL}
    actions:
      - id: get-billing
        path: /billing/${input.customer_id}
        method: GET
        output: ${response}

  - id: knowledge-base
    type: http-client
    base_url: ${env.KB_URL}
    actions:
      - id: search
        path: /search
        method: POST
        body:
          query: ${input.query}
        output: ${response.results}

  - id: ticket-system
    type: http-client
    base_url: ${env.TICKET_API_URL}
    actions:
      - id: create-ticket
        path: /tickets
        method: POST
        body:
          title: ${input.title}
          description: ${input.description}
          priority: ${input.priority}
        output: ${response.ticket_id}
```

---

## Implementation Requirements

### Dependencies

```toml
[tool.poetry.dependencies]
openai-agents-python = "^0.1.0"
openai = "^1.0.0"
pydantic = "^2.0.0"
```

### Python Package Structure

```
src/mindor/
├── dsl/
│   └── schema/
│       ├── component/
│       │   └── impl/
│       │       ├── openai_agent.py          # Agent component
│       │       ├── openai_agent_runner.py   # Runner component
│       │       ├── openai_agent_guardrail.py # Guardrail component
│       │       └── openai_agent_session.py   # Session component
│       └── action/
│           └── impl/
│               ├── openai_agent_action.py
│               ├── openai_agent_runner_action.py
│               ├── openai_agent_guardrail_action.py
│               └── openai_agent_session_action.py
└── core/
    └── component/
        └── services/
            └── openai_agent/
                ├── agent.py        # Agent service implementation
                ├── runner.py       # Runner service implementation
                ├── guardrail.py    # Guardrail service implementation
                ├── session.py      # Session service implementation
                └── tools.py        # Tool integration helpers
```

### Key Implementation Classes

```python
# Component schemas
class OpenAiAgentComponentConfig(CommonComponentConfig)
class OpenAiAgentRunnerComponentConfig(CommonComponentConfig)
class OpenAiAgentGuardrailComponentConfig(CommonComponentConfig)
class OpenAiAgentSessionComponentConfig(CommonComponentConfig)

# Action schemas
class OpenAiAgentActionConfig(CommonActionConfig)
class OpenAiAgentRunnerActionConfig(CommonActionConfig)
class OpenAiAgentGuardrailActionConfig(CommonActionConfig)
class OpenAiAgentSessionActionConfig(CommonActionConfig)

# Service implementations
class OpenAiAgentService
class OpenAiAgentRunnerService
class OpenAiAgentGuardrailService
class OpenAiAgentSessionService
```

---

## Testing Strategy

### Unit Tests

1. Test agent configuration parsing
2. Test tool integration (function, component, MCP)
3. Test handoff configuration
4. Test guardrail validation logic
5. Test session CRUD operations

### Integration Tests

1. Test single agent execution
2. Test multi-agent workflow with handoffs
3. Test guardrail integration with agents
4. Test session persistence across requests
5. Test streaming responses
6. Test tracing and monitoring

### Example Test Cases

```python
def test_agent_basic_execution():
    """Test basic agent execution with simple prompt"""

def test_agent_with_tools():
    """Test agent with function tools"""

def test_multi_agent_handoff():
    """Test agent handoff between specialists"""

def test_guardrail_input_validation():
    """Test input guardrail rejection"""

def test_session_persistence():
    """Test session save and retrieve"""

def test_agent_with_structured_output():
    """Test agent with Pydantic output type"""
```

---

## Migration and Compatibility

### Backward Compatibility

These new components do not break existing model-compose functionality. They are additive and can coexist with existing components.

### Migration from Existing OpenAI Integration

Existing `http-client` components calling OpenAI Chat Completions API can be gradually migrated to use `openai-agent` components for enhanced capabilities:

**Before (http-client):**
```yaml
- id: gpt-4o
  type: http-client
  base_url: https://api.openai.com/v1
  path: /chat/completions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  body:
    model: gpt-4o
    messages: ${input.messages}
```

**After (openai-agent):**
```yaml
- id: gpt-4o
  type: openai-agent
  name: "GPT-4o Agent"
  instructions: "You are a helpful assistant"
  model: "gpt-4o"
```

---

## Performance Considerations

1. **Agent Execution**: Async by default, leverages Python asyncio
2. **Session Storage**: Choose appropriate backend based on scale
   - Memory: Fastest, but not persistent
   - SQLite: Good for single-server deployments
   - SQLAlchemy: Best for distributed systems
3. **Guardrails**: Use cheaper models (gpt-4o-mini) for validation
4. **Tracing**: Minimal overhead, but can be disabled for production
5. **Tool Parallelization**: Enabled by default for better performance

---

## Security Considerations

1. **API Key Management**: Use environment variables, never hardcode
2. **Input Validation**: Always use guardrails for user-facing agents
3. **PII Protection**: Use encrypted sessions for sensitive data
4. **Rate Limiting**: Configure at controller level
5. **Audit Logging**: Enable tracing for compliance requirements

---

## Future Enhancements

1. **Voice Integration**: Support for OpenAI Realtime API
2. **Fine-tuning Integration**: Reference fine-tuned models
3. **Advanced Tracing**: Integration with external observability platforms
4. **Agent Templates**: Pre-built agent configurations for common use cases
5. **Agent Marketplace**: Share and reuse agent configurations
6. **Cost Optimization**: Automatic model selection based on complexity
7. **Multimodal Support**: Image and audio inputs/outputs

---

## References

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK GitHub](https://github.com/openai/openai-agents-python)
- [OpenAI AgentKit Announcement](https://openai.com/index/introducing-agentkit/)
- [model-compose Documentation](../README.md)
- [Model Context Protocol (MCP) Specification](https://modelcontextprotocol.io/)
