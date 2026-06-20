"""Parity tests covering both ForEachJob and ComponentJob behaviors that should
be unchanged after the refactor. Each test asserts concrete output shape and
content so the same file can be run against the baseline implementation as
well.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
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


def _build_compose(workflow_def, components_def):
    return ComposeConfig.model_validate({
        "controller": {"type": "http-server", "port": 8080},
        "components": components_def,
        "workflows": [workflow_def],
    })


async def _run_workflow(compose, workflow_id, input):
    workflow_config = next(w for w in compose.workflows if w.id == workflow_id)
    gc = ComponentGlobalConfigs(
        components=compose.components,
        listeners=compose.listeners,
        gateways=compose.gateways,
        workflows=compose.workflows,
    )
    workflow = Workflow(workflow_id, workflow_config, gc)
    return await workflow.run(
        task_id="test-task",
        input=input,
        interrupt_handler=InterruptHandler(),
    )


ECHO = {
    "id": "echo",
    "type": "shell",
    "action": {
        "command": ["echo", "${input.label}"],
        "output": "${result.stdout}",
    },
}


# --- ForEachJob parity -----------------------------------------------------

@pytest.mark.anyio
async def test_for_each_list_returns_list_in_order():
    workflow = {
        "id": "wf",
        "jobs": [{
            "id": "loop",
            "type": "for-each",
            "input": [{"label": "a"}, {"label": "b"}, {"label": "c"}],
            "do": {"component": "echo", "input": {"label": "${item.label}"}},
        }],
    }
    result = await _run_workflow(_build_compose(workflow, [ECHO]), "wf", {})
    assert isinstance(result, list)
    assert [r.strip() for r in result] == ["a", "b", "c"]


@pytest.mark.anyio
async def test_for_each_single_value_unwraps_scalar():
    workflow = {
        "id": "wf",
        "jobs": [{
            "id": "loop",
            "type": "for-each",
            "input": {"label": "solo"},
            "do": {"component": "echo", "input": {"label": "${item.label}"}},
        }],
    }
    result = await _run_workflow(_build_compose(workflow, [ECHO]), "wf", {})
    assert not isinstance(result, list)
    assert result.strip() == "solo"


@pytest.mark.anyio
async def test_for_each_none_input_raises():
    """A None source has no items to iterate over — for-each should not silently
    no-op. The component invocation downstream of `${item.<field>}` is expected
    to raise."""
    workflow = {
        "id": "wf",
        "jobs": [{
            "id": "loop",
            "type": "for-each",
            "input": None,
            "do": {"component": "echo", "input": {"label": "${item.label}"}},
        }],
    }
    with pytest.raises(Exception):
        await _run_workflow(_build_compose(workflow, [ECHO]), "wf", {})


@pytest.mark.anyio
async def test_for_each_do_output_template_per_item():
    workflow = {
        "id": "wf",
        "jobs": [{
            "id": "loop",
            "type": "for-each",
            "input": [{"label": "x"}, {"label": "y"}],
            "do": {
                "component": "echo",
                "input": {"label": "${item.label}"},
                "output": "got=${output}",
            },
        }],
    }
    result = await _run_workflow(_build_compose(workflow, [ECHO]), "wf", {})
    assert isinstance(result, list)
    assert [r.strip() for r in result] == ["got=x", "got=y"]


# --- ComponentJob parity ---------------------------------------------------

@pytest.mark.anyio
async def test_component_job_no_repeat_returns_single_output():
    workflow = {
        "id": "wf",
        "input": {"label": "hi"},
        "jobs": [{
            "id": "do",
            "component": "echo",
            "input": {"label": "${input.label}"},
        }],
    }
    result = await _run_workflow(_build_compose(workflow, [ECHO]), "wf", {"label": "hi"})
    assert not isinstance(result, list)
    assert result.strip() == "hi"


@pytest.mark.anyio
async def test_component_job_repeat_count_returns_list():
    workflow = {
        "id": "wf",
        "input": {"label": "rep"},
        "jobs": [{
            "id": "do",
            "component": "echo",
            "input": {"label": "${input.label}"},
            "repeat_count": 3,
        }],
    }
    result = await _run_workflow(_build_compose(workflow, [ECHO]), "wf", {"label": "rep"})
    assert isinstance(result, list)
    assert len(result) == 3
    assert all(r.strip() == "rep" for r in result)


@pytest.mark.anyio
async def test_component_job_repeat_count_one_returns_scalar():
    workflow = {
        "id": "wf",
        "input": {"label": "one"},
        "jobs": [{
            "id": "do",
            "component": "echo",
            "input": {"label": "${input.label}"},
            "repeat_count": 1,
        }],
    }
    result = await _run_workflow(_build_compose(workflow, [ECHO]), "wf", {"label": "one"})
    assert not isinstance(result, list)
    assert result.strip() == "one"
