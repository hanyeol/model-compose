"""End-to-end tests for downstream jobs whose dependencies land on a routing
branch that is never taken (e.g. the ``if_false`` side of an ``if`` job).

Without the skip-propagation fix, the runner raises
``RuntimeError: No runnable jobs but pending jobs remain.`` because the
unchosen branch stays in ``routing_jobs`` forever and the dependent job can
never become runnable.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import ComponentInstances
from mindor.core.workflow.interrupt import InterruptHandler
from mindor.core.workflow.workflow import Workflow
from mindor.dsl.schema.compose import ComposeConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_component_instances():
    ComponentInstances.clear()
    yield
    ComponentInstances.clear()


def _build_compose(workflow_def: Dict[str, Any], components_def: List[Dict[str, Any]]) -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": { "type": "http-server", "port": 8080 },
        "components": components_def,
        "workflows":  [ workflow_def ],
    })


async def _run_workflow(compose: ComposeConfig, workflow_id: str, input: Dict[str, Any]) -> Any:
    workflow_config = next(w for w in compose.workflows if w.id == workflow_id)
    global_configs = ComponentGlobalConfigs(
        components=compose.components,
        listeners=compose.listeners,
        gateways=compose.gateways,
        workflows=compose.workflows,
    )
    workflow = Workflow(workflow_id, workflow_config, global_configs)
    return await workflow.run(
        task_id="test-task",
        input=input,
        interrupt_handler=InterruptHandler(),
    )


ECHO_COMPONENT = {
    "id":   "echo",
    "type": "shell",
    "action": {
        "command": [ "echo", "${input.label}" ],
        "output":  "${result.stdout}",
    },
}


class TestConditionalBranchSkipE2E:
    @pytest.mark.anyio
    async def test_downstream_of_unchosen_if_branch_does_not_hang(self):
        workflow = {
            "id":   "wf",
            "jobs": [
                {
                    "id":    "cond",
                    "type":  "if",
                    "input": "${input.pick}",
                    "conditions": [ { "operator": "eq", "value": "a", "if_true": "branch_a" } ],
                    "otherwise":  "branch_b",
                },
                { "id": "branch_a", "component": "echo", "input": { "label": "A" } },
                { "id": "branch_b", "component": "echo", "input": { "label": "B" } },
                {
                    "id":         "final",
                    "component":  "echo",
                    "input":      { "label": "final" },
                    "depends_on": [ "branch_a" ],
                },
            ],
        }
        # Pick the otherwise branch; `branch_a` is never routed to, so `final`'s
        # dependency never completes. The fix should skip `final` and finish.
        result = await _run_workflow(
            _build_compose(workflow, [ ECHO_COMPONENT ]),
            "wf",
            { "pick": "b" },
        )
        assert result.strip() == "B"

    @pytest.mark.anyio
    async def test_chosen_if_branch_still_runs_downstream(self):
        workflow = {
            "id":   "wf",
            "jobs": [
                {
                    "id":    "cond",
                    "type":  "if",
                    "input": "${input.pick}",
                    "conditions": [ { "operator": "eq", "value": "a", "if_true": "branch_a" } ],
                    "otherwise":  "branch_b",
                },
                { "id": "branch_a", "component": "echo", "input": { "label": "A" } },
                { "id": "branch_b", "component": "echo", "input": { "label": "B" } },
                {
                    "id":         "final",
                    "component":  "echo",
                    "input":      { "label": "final" },
                    "depends_on": [ "branch_a" ],
                },
            ],
        }
        result = await _run_workflow(
            _build_compose(workflow, [ ECHO_COMPONENT ]),
            "wf",
            { "pick": "a" },
        )
        assert result.strip() == "final"
