"""E2E test: MCP server adapter serving a workflow, called by a real MCP client.

Boots a minimal ControllerService with an `mcp-server` adapter on an ephemeral
port, exposes a single `greet` workflow (implemented via `shell` echo), and
drives it end-to-end through a real MCP `streamable_http` client. Verifies:

1. The workflow is advertised by `list_tools()` with the expected schema.
2. `call_tool()` executes the workflow and returns the shell output.
"""

from __future__ import annotations

import asyncio
import socket
from contextlib import closing

import pytest

from mindor.core.component.component import ComponentInstances
from mindor.core.controller.controller import create_controller
from mindor.core.utils.transport.mcp_client import McpClient
from mindor.dsl.schema.compose import ComposeConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_component_instances():
    ComponentInstances.clear()
    yield
    ComponentInstances.clear()


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_compose(port: int) -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {
            "name": "test-mcp",
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [
                {
                    "type": "mcp-server",
                    "host": "127.0.0.1",
                    "port": port,
                    "base_path": "/mcp",
                }
            ],
        },
        "components": [
            {
                "id": "echo",
                "type": "shell",
                "action": {
                    "command": [ "python3", "-c", "import sys; print('Hello, ' + sys.argv[1] + '!')", "${input.name}" ],
                    "output": "${result.stdout}",
                },
            },
        ],
        "workflows": [
            {
                "id": "greet",
                "title": "Greet",
                "description": "Return a greeting message for the given name.",
                "job": {
                    "component": "echo",
                    "input": { "name": "${input.name}" },
                    "output": "${output}",
                },
            }
        ],
    })


async def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.05)
    raise TimeoutError(f"MCP server did not start on {host}:{port} within {timeout}s")


async def _run_scenario(port: int) -> None:
    compose = _build_compose(port)
    controller = create_controller(
        compose.controller,
        compose.workflows,
        compose.components,
        compose.systems,
        compose.listeners,
        compose.gateways,
        compose.tracers,
        compose.loggers,
        daemon=True,
    )
    await controller.start()
    try:
        await _wait_for_port("127.0.0.1", port)

        async with McpClient(f"http://127.0.0.1:{port}/mcp") as client:
            tools = await client.list_tools()
            tool_names = { t.name for t in tools }
            assert "greet" in tool_names, f"'greet' tool missing; got {tool_names}"

            greet = next(t for t in tools if t.name == "greet")
            assert greet.description and "greeting" in greet.description.lower()
            assert greet.inputSchema.get("properties", {}).get("name", {}).get("type") == "string"

            content = await client.call_tool("greet", { "name": "world" })
            assert content, "call_tool returned no content"
            text = getattr(content[0], "text", None)
            assert text is not None, f"Expected TextContent, got {type(content[0]).__name__}"
            assert "Hello, world!" in text
    finally:
        await controller.stop()


class TestMcpServerAdapter:
    def test_lists_and_calls_workflow_tool(self):
        # MCP SDK uses anyio task groups internally whose cancel scopes conflict
        # with pytest-anyio's runner, so drive the scenario in a fresh asyncio
        # event loop instead of relying on @pytest.mark.anyio.
        port = _free_port()
        asyncio.run(_run_scenario(port))
