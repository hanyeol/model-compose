# ACP (Agent Client Protocol) Integration Specification

## Overview

This document specifies the integration of Agent Client Protocol (ACP) support into model-compose, enabling workflows to be exposed as AI coding agents that can interact with code editors like Zed.

### Goals

1. Add ACP Server as a third controller type alongside HTTP Server and MCP Server
2. Enable workflows to function as coding agents accessible from compatible editors
3. Maintain consistency with existing controller architecture patterns
4. Support both local (stdio) and remote (HTTP/WebSocket) agent deployment models

### Non-Goals

- Replacing existing HTTP or MCP server implementations
- Implementing editor/client-side functionality (only agent-side)
- Supporting all ACP features in initial implementation (see phased approach)

## Background

### What is ACP?

Agent Client Protocol (ACP) is a standardized protocol for agent-editor communication, similar to LSP (Language Server Protocol). It enables:

- Decoupling between AI coding agents and code editors
- Standardized communication for agentic coding tasks
- Multiple transport mechanisms (JSON-RPC over stdio, HTTP, WebSocket)

### Relationship to MCP

While model-compose already supports MCP (Model Context Protocol), ACP serves a different purpose:

- **MCP**: Generic context protocol for tools, resources, and prompts
- **ACP**: Specialized for IDE-agent interactions with coding-specific features (diffs, file operations, terminal access)

Both protocols share some JSON representations where applicable, making dual support natural.

### Current Architecture

model-compose uses a controller-based architecture where:

```yaml
controller:
  type: http-server | mcp-server  # Adding: acp-server
  # controller-specific configuration

workflows:
  - id: example-workflow
    # workflow definition
```

Controllers expose workflows through different interfaces:
- **HTTP Server**: REST API endpoints
- **MCP Server**: MCP tools callable by LLMs
- **ACP Server** (proposed): Agent capabilities for code editors

## Detailed Design

### 1. Configuration Schema

#### 1.1 Controller Type Enum Extension

**File**: `src/mindor/dsl/schema/controller/impl/types.py`

```python
class ControllerType(str, Enum):
    HTTP_SERVER = "http-server"
    MCP_SERVER  = "mcp-server"
    ACP_SERVER  = "acp-server"  # NEW
```

#### 1.2 ACP Server Configuration

**File**: `src/mindor/dsl/schema/controller/impl/acp_server.py`

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field
from .common import ControllerType, CommonControllerConfig

class AcpTransportType(str, Enum):
    STDIO = "stdio"       # JSON-RPC over stdio (local agents)
    HTTP = "http"         # HTTP transport (remote agents)
    WEBSOCKET = "ws"      # WebSocket transport (remote agents)

class AcpServerControllerConfig(CommonControllerConfig):
    type: Literal[ControllerType.ACP_SERVER]

    # Transport configuration
    transport: AcpTransportType = Field(
        default=AcpTransportType.STDIO,
        description="Transport mechanism for ACP communication"
    )

    # For HTTP/WebSocket transports
    host: Optional[str] = Field(
        default="127.0.0.1",
        description="Host address for HTTP/WebSocket transports"
    )
    port: Optional[int] = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Port for HTTP/WebSocket transports"
    )
    base_path: Optional[str] = Field(
        default=None,
        description="Base path prefix for HTTP endpoints"
    )

    # Agent metadata
    agent_name: Optional[str] = Field(
        default=None,
        description="Agent display name for editors"
    )
    agent_version: Optional[str] = Field(
        default="1.0.0",
        description="Agent version string"
    )
    agent_description: Optional[str] = Field(
        default=None,
        description="Agent description shown in editors"
    )

    # Capability flags
    supports_file_operations: bool = Field(
        default=True,
        description="Enable file read/write/list operations"
    )
    supports_terminal: bool = Field(
        default=False,
        description="Enable terminal command execution"
    )
    supports_diff_display: bool = Field(
        default=True,
        description="Enable diff content blocks"
    )
```

#### 1.3 Configuration Example

**File**: `examples/acp-agent/model-compose.yml`

```yaml
controller:
  type: acp-server
  transport: stdio  # or http, ws
  agent_name: "Code Review Agent"
  agent_description: "AI-powered code review and refactoring agent"
  supports_file_operations: true
  supports_terminal: false
  supports_diff_display: true

  # For HTTP/WebSocket transports
  # host: 127.0.0.1
  # port: 8080
  # base_path: /acp

workflows:
  - id: review-code
    title: "Review Code"
    description: "Analyze code for bugs, style issues, and improvements"
    input:
      - name: file_path
        type: string
        annotations:
          description: "Path to the file to review"
      - name: context
        type: string
        annotations:
          description: "Additional context about what to review"
    jobs:
      - id: analyze
        component: code-analyzer
        input:
          file: ${input.file_path}
          context: ${input.context}
      - id: generate-suggestions
        component: suggestion-generator
        input:
          analysis: ${analyze.output}
    output:
      - name: suggestions
        type: object[]

  - id: refactor-code
    title: "Refactor Code"
    description: "Suggest refactoring improvements with diffs"
    input:
      - name: file_path
        type: string
      - name: refactoring_goal
        type: string
    jobs:
      - id: analyze-structure
        component: structure-analyzer
      - id: generate-diff
        component: diff-generator
    output:
      - name: diff
        type: string
        format: diff

components:
  - id: code-analyzer
    type: model
    # ... model configuration

  - id: suggestion-generator
    type: model
    # ... model configuration
```

### 2. Controller Service Implementation

#### 2.1 Architecture

The ACP Server Controller follows the same pattern as HTTP and MCP controllers:

```
AcpServerController
├── Inherits from: ControllerService
├── Uses: ACP Python SDK (agentclientprotocol library)
├── Manages: AgentSideConnection
└── Converts: Workflows → ACP Agent Capabilities
```

#### 2.2 Implementation

**File**: `src/mindor/core/controller/services/acp_server.py`

```python
from typing import Optional, List, Dict, Any, Callable, Awaitable
from mindor.dsl.schema.controller import AcpServerControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.logger import LoggerConfig
from mindor.dsl.schema.workflow import WorkflowConfig, WorkflowVariableType
from mindor.core.workflow.schema import WorkflowSchema
from ..base import ControllerService, ControllerType, TaskState, register_controller

# ACP SDK imports (to be added as dependency)
# from agentclientprotocol import AgentSideConnection, Message, ContentBlock
# from agentclientprotocol.types import TextContent, DiffContent, ToolCallReport

@register_controller(ControllerType.ACP_SERVER)
class AcpServerController(ControllerService):
    """
    ACP Server Controller that exposes workflows as agent capabilities
    for code editors supporting the Agent Client Protocol.
    """

    def __init__(
        self,
        config: AcpServerControllerConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        loggers: List[LoggerConfig],
        daemon: bool
    ):
        super().__init__(config, workflows, components, listeners, gateways, loggers, daemon)

        self.connection: Optional[Any] = None  # AgentSideConnection
        self.session_contexts: Dict[str, Dict[str, Any]] = {}

    async def _start(self) -> None:
        """Initialize ACP connection and register capabilities"""
        await super()._start()
        await self._initialize_acp_connection()
        await self._register_capabilities()

    async def _stop(self) -> None:
        """Cleanup ACP connection"""
        if self.connection:
            await self._shutdown_connection()
        await super()._stop()

    async def _initialize_acp_connection(self) -> None:
        """
        Initialize AgentSideConnection based on transport type
        """
        # TODO: Implement based on ACP Python SDK
        #
        # if self.config.transport == "stdio":
        #     self.connection = AgentSideConnection.stdio(
        #         agent_name=self.config.agent_name or self.config.name,
        #         version=self.config.agent_version,
        #         description=self.config.agent_description
        #     )
        # elif self.config.transport in ["http", "ws"]:
        #     self.connection = AgentSideConnection.remote(
        #         host=self.config.host,
        #         port=self.config.port,
        #         transport=self.config.transport
        #     )
        #
        # await self.connection.start()
        pass

    async def _register_capabilities(self) -> None:
        """
        Register workflow-based capabilities with ACP
        """
        for workflow_id, workflow_schema in self.workflow_schemas.items():
            await self._register_workflow_capability(workflow_id, workflow_schema)

    async def _register_workflow_capability(
        self,
        workflow_id: str,
        workflow: WorkflowSchema
    ) -> None:
        """
        Register a single workflow as an ACP capability

        Each workflow becomes a callable capability that the editor can invoke.
        """
        # TODO: Map workflow to ACP capability
        #
        # capability = {
        #     "id": workflow.name or workflow_id,
        #     "title": workflow.title,
        #     "description": workflow.description,
        #     "parameters": self._build_capability_parameters(workflow.input),
        #     "handler": lambda params: self._handle_capability_call(workflow_id, params)
        # }
        #
        # await self.connection.register_capability(capability)
        pass

    def _build_capability_parameters(self, input_vars: List[Any]) -> List[Dict[str, Any]]:
        """
        Convert workflow input variables to ACP parameter schema
        """
        parameters = []
        for var in input_vars:
            param = {
                "name": var.name or "input",
                "type": self._map_variable_type_to_acp(var.type),
                "description": var.get_annotation_value("description") or "",
                "required": var.default is None
            }
            parameters.append(param)
        return parameters

    def _map_variable_type_to_acp(self, var_type: WorkflowVariableType) -> str:
        """
        Map model-compose variable types to ACP types
        """
        mapping = {
            WorkflowVariableType.STRING: "string",
            WorkflowVariableType.NUMBER: "number",
            WorkflowVariableType.INTEGER: "integer",
            WorkflowVariableType.BOOLEAN: "boolean",
            WorkflowVariableType.OBJECT: "object",
            WorkflowVariableType.OBJECTS: "array",
            WorkflowVariableType.FILE: "string",  # file path
            WorkflowVariableType.IMAGE: "string",  # file path
        }
        return mapping.get(var_type, "string")

    async def _handle_capability_call(
        self,
        workflow_id: str,
        parameters: Dict[str, Any]
    ) -> List[Any]:  # List[ContentBlock]
        """
        Handle capability invocation from editor

        Executes the workflow and converts output to ACP content blocks
        """
        # Run workflow
        state = await self.run_workflow(workflow_id, parameters, wait_for_completion=True)

        # Convert output to ACP content blocks
        content_blocks = await self._convert_output_to_content(state, workflow_id)

        return content_blocks

    async def _convert_output_to_content(
        self,
        state: TaskState,
        workflow_id: str
    ) -> List[Any]:  # List[ContentBlock]
        """
        Convert workflow output to ACP content blocks

        Supports:
        - TextContent for regular output
        - DiffContent for code changes
        - ImageContent for image outputs
        - ToolCallReport for sub-workflow calls
        """
        workflow = self.workflow_schemas[workflow_id]
        content_blocks = []

        if not state.output:
            return content_blocks

        # Handle single output variable
        if len(workflow.output) == 1 and not workflow.output[0].name:
            var = workflow.output[0]
            block = await self._create_content_block(state.output, var)
            if block:
                content_blocks.append(block)
        else:
            # Handle multiple output variables
            for var in workflow.output:
                value = state.output.get(var.name) if isinstance(state.output, dict) else None
                block = await self._create_content_block(value, var)
                if block:
                    content_blocks.append(block)

        return content_blocks

    async def _create_content_block(self, value: Any, variable: Any) -> Optional[Any]:
        """
        Create appropriate ACP content block based on variable type
        """
        # TODO: Implement with ACP SDK types
        #
        # if variable.format == "diff":
        #     return DiffContent(
        #         type="diff",
        #         diff=str(value),
        #         language=variable.subtype or "python"
        #     )
        #
        # if variable.type in [WorkflowVariableType.IMAGE]:
        #     # Handle image content
        #     pass
        #
        # # Default to text content
        # if isinstance(value, (dict, list)):
        #     import json
        #     text = json.dumps(value, indent=2)
        # else:
        #     text = str(value)
        #
        # return TextContent(type="text", text=text)
        pass

    async def _shutdown_connection(self) -> None:
        """Gracefully shutdown ACP connection"""
        # TODO: Implement
        # await self.connection.stop()
        pass
```

### 3. Integration Points

#### 3.1 Controller Factory

**File**: `src/mindor/core/controller/__init__.py`

The existing factory pattern automatically handles the new controller type via the `@register_controller` decorator.

#### 3.2 CLI Integration

**File**: `src/mindor/cli/compose.py`

No changes needed - the CLI already supports any registered controller type.

### 4. Workflow Mapping Strategy

#### 4.1 Workflow to Capability Mapping

| Workflow Feature | ACP Capability |
|-----------------|----------------|
| Workflow ID | Capability ID |
| Workflow Title | Capability Title |
| Workflow Description | Capability Description |
| Input Variables | Parameters |
| Output Variables | Response Content Blocks |
| Job Chain | Internal execution (hidden from editor) |

#### 4.2 Special Output Formats

To support ACP-specific features, workflows can use format annotations:

```yaml
workflows:
  - id: refactor
    output:
      - name: changes
        type: string
        format: diff  # Creates DiffContent block
        subtype: python  # Language for syntax highlighting

  - id: analyze
    output:
      - name: report
        type: string
        format: markdown  # Creates TextContent with markdown

  - id: visualize
    output:
      - name: diagram
        type: image
        format: path  # Creates ImageContent from file path
```

### 5. Feature Support Matrix

| Feature | Phase 1 | Phase 2 | Phase 3 |
|---------|---------|---------|---------|
| STDIO transport | ✓ | ✓ | ✓ |
| HTTP transport | - | ✓ | ✓ |
| WebSocket transport | - | ✓ | ✓ |
| Basic workflow execution | ✓ | ✓ | ✓ |
| Text content blocks | ✓ | ✓ | ✓ |
| Diff content blocks | ✓ | ✓ | ✓ |
| Image content blocks | - | ✓ | ✓ |
| File operations (read/write) | - | ✓ | ✓ |
| Terminal execution | - | - | ✓ |
| Session management | - | ✓ | ✓ |
| Slash commands | - | - | ✓ |
| Mode switching | - | - | ✓ |

### 6. Dependencies

#### 6.1 Python ACP SDK

**Status**: To be verified - ACP documentation mentions Python SDK availability

**Required package**:
```toml
# pyproject.toml or setup.py
dependencies = [
    # ... existing dependencies
    "agentclientprotocol>=1.0.0",  # To be confirmed
]
```

**Fallback**: If no official Python SDK exists:
1. Use TypeScript SDK via subprocess (similar to how some tools wrap Node.js)
2. Implement minimal JSON-RPC protocol directly
3. Contribute Python SDK to ACP project

#### 6.2 Other Dependencies

No additional dependencies required - existing infrastructure sufficient.

### 7. Testing Strategy

#### 7.1 Unit Tests

```python
# tests/core/controller/test_acp_server.py

async def test_acp_server_initialization():
    """Test ACP server initialization with stdio transport"""

async def test_workflow_capability_registration():
    """Test workflow to capability conversion"""

async def test_capability_invocation():
    """Test calling a workflow through ACP"""

async def test_output_content_conversion():
    """Test converting workflow output to content blocks"""
```

#### 7.2 Integration Tests

```python
# tests/integration/test_acp_integration.py

async def test_end_to_end_workflow_execution():
    """Test complete workflow execution via ACP"""

async def test_multiple_transport_types():
    """Test stdio, HTTP, and WebSocket transports"""
```

#### 7.3 Manual Testing

Create example agent configurations for testing with actual editors (e.g., Zed).

### 8. Documentation

#### 8.1 User Documentation

**File**: `docs/controllers/acp-server.md`

- Overview of ACP support
- Configuration examples
- Workflow design patterns for coding agents
- Editor integration guide

#### 8.2 API Documentation

- ACP capability schema reference
- Supported content block types
- Transport configuration options

### 9. Migration and Compatibility

#### 9.1 Backward Compatibility

- Existing HTTP and MCP configurations unchanged
- No breaking changes to DSL schema
- Additive-only changes

#### 9.2 Multi-Controller Support

Allow running multiple controllers simultaneously:

```yaml
controllers:  # Note: plural
  - type: http-server
    port: 8080

  - type: mcp-server
    port: 8081

  - type: acp-server
    transport: stdio
```

**Note**: This requires refactoring from single `controller` to multiple `controllers` - considered for future enhancement.

### 10. Security Considerations

#### 10.1 File System Access

When `supports_file_operations: true`:
- Sandbox file operations to workspace directory
- Validate file paths to prevent directory traversal
- Implement read/write permissions

#### 10.2 Terminal Execution

When `supports_terminal: true`:
- Whitelist allowed commands
- Run in sandboxed environment
- Log all command executions
- Require explicit user confirmation in editor

#### 10.3 Authentication

For HTTP/WebSocket transports:
- Support API key authentication
- Optional mTLS for secure connections
- Rate limiting per client

### 11. Performance Considerations

#### 11.1 Async Execution

- All workflow executions are async
- Non-blocking I/O for STDIO communication
- Connection pooling for HTTP/WebSocket

#### 11.2 Resource Management

- Limit concurrent workflow executions (use existing `max_concurrent_count`)
- Stream large outputs when possible
- Timeout configuration for long-running workflows

### 12. Example Use Cases

#### 12.1 Code Review Agent

```yaml
controller:
  type: acp-server
  transport: stdio
  agent_name: "Smart Reviewer"

workflows:
  - id: review
    title: "Review Code"
    input:
      - name: code
        type: string
    jobs:
      - component: gpt-4-analyzer
    output:
      - type: string
        format: markdown
```

#### 12.2 Refactoring Agent

```yaml
workflows:
  - id: refactor
    title: "Suggest Refactoring"
    input:
      - name: file_path
        type: string
      - name: goal
        type: string
    output:
      - name: diff
        type: string
        format: diff
        subtype: python
```

#### 12.3 Documentation Generator

```yaml
workflows:
  - id: generate-docs
    title: "Generate Documentation"
    input:
      - name: function_signature
        type: string
    output:
      - name: docstring
        type: string
        format: markdown
```

### 13. Future Enhancements

1. **Multi-turn conversations**: Support back-and-forth dialogue with editor
2. **Proactive suggestions**: Agent-initiated prompts based on code changes
3. **Context awareness**: Access to full editor state (open files, cursor position)
4. **Custom content blocks**: Support for proprietary content types
5. **Agent marketplace**: Registry of pre-built ACP agents

### 14. Implementation Phases

#### Phase 1: MVP (4-6 weeks)
- Basic STDIO transport
- Workflow to capability mapping
- Text and diff content blocks
- Example configurations
- Core documentation

#### Phase 2: Enhanced Features (4-6 weeks)
- HTTP/WebSocket transports
- Image content blocks
- File operations support
- Session management
- Comprehensive testing

#### Phase 3: Advanced Capabilities (6-8 weeks)
- Terminal execution
- Slash commands
- Mode switching
- Security hardening
- Performance optimization

### 15. Open Questions

1. **Python SDK Availability**: Does ACP have an official Python SDK? If not, what's the best approach?
   - Answer: Need to verify with ACP project

2. **Transport Priority**: Which transport should be prioritized for MVP?
   - Recommendation: STDIO (simplest, most common for local agents)

3. **Multi-Controller Support**: Should we support running multiple controller types simultaneously?
   - Recommendation: Phase 2 feature, requires schema changes

4. **Streaming Support**: Should workflows support streaming responses?
   - Recommendation: Phase 2, leveraging existing streaming infrastructure

## Conclusion

This specification provides a complete roadmap for integrating ACP support into model-compose. The design:

- Maintains architectural consistency with existing controllers
- Leverages existing workflow and component infrastructure
- Provides clear extension points for future enhancements
- Follows established patterns in the codebase

By adding ACP support, model-compose becomes a powerful platform for building AI coding agents that work seamlessly with modern code editors.
