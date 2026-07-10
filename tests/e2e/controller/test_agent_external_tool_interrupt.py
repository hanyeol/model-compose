"""Controller-level E2E test for the agent component's external tool interrupt flow.

Boots a minimal ControllerService (no adapters, no daemon services) and runs a
workflow whose only job invokes an agent. The agent is wired to a shell-based
mock LLM: on the first call it emits a tool_call for an external tool declared
via ModelTool, and on the second call (after the tool result is injected) it
returns a plain content message.

The test asserts that:
1. The task transitions to `TaskStatus.INTERRUPTED` while the agent waits for
   external tool results.
2. `state.interrupt.metadata` carries the pending tool_calls in the shape
   `{ kind: "tool_calls", tool_calls: [{ id, name, arguments }, ...] }`.
3. Calling `controller.resume_workflow(...)` with a `{tool_call_id: result}`
   answer unblocks the agent, which then completes with the resulting messages.
"""

from __future__ import annotations

import pytest

from mindor.core.component.component import ComponentInstances
from mindor.core.controller.base import TaskStatus
from mindor.core.controller.controller import create_controller
from mindor.dsl.schema.compose import ComposeConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_component_instances():
    ComponentInstances.clear()
    yield
    ComponentInstances.clear()


# Mock LLM: parses the messages list from argv[1] (Python repr / literal form).
# If any prior message has role=tool, emit a final content message; otherwise
# emit a tool_call for `get_weather`.
MOCK_LLM_SCRIPT = (
    "import ast, json, sys\n"
    "messages = ast.literal_eval(sys.argv[1])\n"
    "tool_msg = next((m for m in messages if m.get('role') == 'tool'), None)\n"
    "if tool_msg is not None:\n"
    "    print(json.dumps({'content': 'weather=' + tool_msg['content']}))\n"
    "else:\n"
    "    print(json.dumps({\n"
    "        'tool_calls': [\n"
    "            { 'id': 'call_1', 'name': 'get_weather', 'arguments': { 'city': 'seoul' } }\n"
    "        ]\n"
    "    }))\n"
)


def _build_compose() -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [
            {
                "id": "mock_llm",
                "type": "shell",
                "action": {
                    "command": [ "python3", "-c", MOCK_LLM_SCRIPT, "${input.messages as string}" ],
                    "output": "${result.stdout as json}",
                },
            },
            {
                "id": "agent",
                "type": "agent",
                "model": {
                    "component": "mock_llm",
                    "input": { "messages": "${messages}" },
                },
                "tools": [
                    {
                        "name": "get_weather",
                        "description": "Get the current weather for a city.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": { "type": "string" }
                            },
                            "required": [ "city" ]
                        }
                    }
                ],
                "max_iteration_count": 3,
                "action": {
                    "prompt": "${input.prompt}",
                },
            },
        ],
        "workflows": [
            {
                "id": "chat",
                "jobs": [
                    {
                        "id": "run_agent",
                        "component": "agent",
                    }
                ],
            }
        ],
    })


class TestAgentExternalToolInterrupt:
    @pytest.mark.anyio
    async def test_interrupt_then_resume_completes_agent(self):
        compose = _build_compose()
        controller = create_controller(
            compose.controller,
            compose.workflows,
            compose.components,
            compose.systems,
            compose.listeners,
            compose.gateways,
            compose.tracers,
            compose.loggers,
            daemon=False,
        )
        await controller.start()
        try:
            interrupted = await controller.run_workflow(
                workflow_id="chat",
                input={ "prompt": "How's the weather in Seoul?" },
                wait_for_completion=True,
            )

            assert interrupted.status == TaskStatus.INTERRUPTED, f"Expected INTERRUPTED, got {interrupted.status}: {interrupted.error}"
            assert interrupted.interrupt is not None
            assert interrupted.interrupt.phase == "after"
            assert interrupted.interrupt.job_id == "run_agent"

            metadata = interrupted.interrupt.metadata or {}
            assert metadata.get("kind") == "tool_calls"
            calls = metadata.get("tool_calls") or []
            assert len(calls) == 1
            assert calls[0]["name"] == "get_weather"
            assert calls[0]["id"] == "call_1"
            assert calls[0]["arguments"] == { "city": "seoul" }

            await controller.resume_workflow(
                task_id=interrupted.task_id,
                job_id="run_agent",
                answer={ "call_1": { "temp": 21, "unit": "C" } },
            )
            final = await controller.wait_for_terminal_state(interrupted.task_id)

            assert final.status == TaskStatus.COMPLETED, f"Expected COMPLETED, got {final.status}: {final.error}"

            # The agent returns the full messages list by default. The last assistant
            # message should reflect the injected tool result.
            messages = final.output if isinstance(final.output, list) else []
            assistant_final = next(
                (m for m in reversed(messages) if m.get("role") == "assistant" and m.get("content")),
                None,
            )
            assert assistant_final is not None, f"No final assistant message in: {messages}"
            assert "weather=" in assistant_final["content"]
            assert "21" in assistant_final["content"]
        finally:
            await controller.stop()
