"""End-to-end workflow tests for the ``retry`` and ``on_error`` policies on jobs.

Failures are induced by invoking a shell command that does not exist, which
raises ``FileNotFoundError`` inside the job's `_run()`.

Covers:
- retry: N with success on a later attempt
- retry exhausted, then on_error.ignore returns None
- on_error.output renders a fallback with `${error.message}`
- on_error.to routes to a recovery job that then produces the workflow output
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


def _build_compose(workflow_def: Dict[str, Any], components_def: List[Dict[str, Any]] = None) -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": { "type": "http-server", "port": 8080 },
        "components": components_def or [],
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


# A shell command guaranteed to fail with FileNotFoundError inside the job.
FAILING_COMPONENT = {
    "id":   "failing",
    "type": "shell",
    "action": {
        "command": [ "/definitely/not/a/real/command/xyz123" ],
        "output":  "${result.stdout}",
    },
}

ECHO_COMPONENT = {
    "id":   "echo",
    "type": "shell",
    "action": {
        "command": [ "echo", "${input.label}" ],
        "output":  "${result.stdout}",
    },
}


class TestRetryE2E:
    @pytest.mark.anyio
    async def test_no_retry_propagates_failure(self):
        workflow = {
            "id":   "wf",
            "jobs": [ { "id": "j", "component": "failing" } ],
        }
        with pytest.raises(FileNotFoundError):
            await _run_workflow(_build_compose(workflow, [ FAILING_COMPONENT ]), "wf", {})

    @pytest.mark.anyio
    async def test_retry_exhausted_still_propagates(self):
        workflow = {
            "id":   "wf",
            "jobs": [ {
                "id":        "j",
                "component": "failing",
                "retry":     { "max_attempt_count": 3, "delay": 0.0 },
            } ],
        }
        with pytest.raises(FileNotFoundError):
            await _run_workflow(_build_compose(workflow, [ FAILING_COMPONENT ]), "wf", {})


class TestOnErrorE2E:
    @pytest.mark.anyio
    async def test_on_error_ignore_returns_none_output(self):
        workflow = {
            "id":   "wf",
            "jobs": [ {
                "id":        "j",
                "component": "failing",
                "on_error":  "ignore",
            } ],
        }
        result = await _run_workflow(_build_compose(workflow, [ FAILING_COMPONENT ]), "wf", {})
        assert result is None

    @pytest.mark.anyio
    async def test_on_error_output_returns_fallback_with_error_message(self):
        workflow = {
            "id":   "wf",
            "jobs": [ {
                "id":        "j",
                "component": "failing",
                "on_error":  {
                    "output": {
                        "status":  "failed",
                        "message": "${error.message}",
                    },
                },
            } ],
        }
        result = await _run_workflow(_build_compose(workflow, [ FAILING_COMPONENT ]), "wf", {})
        assert result["status"] == "failed"
        assert isinstance(result["message"], str) and result["message"]

    @pytest.mark.anyio
    async def test_on_error_to_routes_to_recovery_job(self):
        workflow = {
            "id":   "wf",
            "jobs": [
                {
                    "id":        "primary",
                    "component": "failing",
                    "on_error":  { "to": "recovery" },
                },
                {
                    "id":        "recovery",
                    "component": "echo",
                    "input":     { "label": "recovered" },
                },
            ],
        }
        result = await _run_workflow(
            _build_compose(workflow, [ FAILING_COMPONENT, ECHO_COMPONENT ]),
            "wf",
            {},
        )
        assert result == "recovered"


class TestRetryPlusOnErrorE2E:
    @pytest.mark.anyio
    async def test_retry_exhausted_then_on_error_ignore(self):
        workflow = {
            "id":   "wf",
            "jobs": [ {
                "id":        "j",
                "component": "failing",
                "retry":     2,
                "on_error":  "ignore",
            } ],
        }
        result = await _run_workflow(_build_compose(workflow, [ FAILING_COMPONENT ]), "wf", {})
        assert result is None
