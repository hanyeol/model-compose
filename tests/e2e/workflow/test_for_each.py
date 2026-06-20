"""Workflow-level integration tests for the `for-each` job type.

These tests build a real Workflow, run it through the workflow runner, and assert
the final output. They exercise:
- List input → list output: each item dispatched in parallel, results collected
- Stream input → stream output: items consumed lazily, results yielded as they come
- ${item} scope: caller renders item fields into do.input
- do.input fallback: passing item through when do.input is omitted
- do.output: per-iteration output transformation
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


def _build_compose(workflow_def: Dict[str, Any], components_def: List[Dict[str, Any]]) -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": { "type": "http-server", "port": 8080 },
        "components": components_def,
        "workflows": [ workflow_def ],
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


async def _collect(stream) -> list:
    """Collect a workflow result, tolerating either a list or an AsyncIterator."""
    if isinstance(stream, list):
        return stream
    return [ item async for item in stream ]


class TestForEachListInput:
    """List input → list output: each item dispatched, results collected."""

    @pytest.mark.anyio
    async def test_iterates_list_and_renders_item(self):
        """Each item in the list is passed to the shell command via ${item.label}."""
        components = [
            {
                "id": "echo",
                "type": "shell",
                "action": {
                    "command": [ "echo", "${input.label}" ],
                    "output": "${result.stdout}",
                },
            },
        ]
        workflow = {
            "id": "for-each-list",
            "jobs": [
                {
                    "id": "loop",
                    "type": "for-each",
                    "input": [
                        { "label": "alpha" },
                        { "label": "beta" },
                        { "label": "gamma" },
                    ],
                    "do": {
                        "component": "echo",
                        "input": { "label": "${item.label}" },
                    },
                },
            ],
        }

        compose = _build_compose(workflow, components)
        result = await _run_workflow(compose, "for-each-list", {})

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0].strip() == "alpha"
        assert result[1].strip() == "beta"
        assert result[2].strip() == "gamma"


class TestForEachDoInputFallback:
    """If do.input is omitted, the item itself is passed as the component input."""

    @pytest.mark.anyio
    async def test_item_passthrough_when_do_input_omitted(self):
        components = [
            {
                "id": "echo",
                "type": "shell",
                "action": {
                    "command": [ "echo", "${input.label}" ],
                    "output": "${result.stdout}",
                },
            },
        ]
        workflow = {
            "id": "for-each-passthrough",
            "jobs": [
                {
                    "id": "loop",
                    "type": "for-each",
                    "input": [
                        { "label": "x" },
                        { "label": "y" },
                    ],
                    "do": {
                        "component": "echo",
                        # no input: the item itself becomes the component input
                    },
                },
            ],
        }

        compose = _build_compose(workflow, components)
        result = await _run_workflow(compose, "for-each-passthrough", {})

        items = await _collect(result)
        assert len(items) == 2
        assert items[0].strip() == "x"
        assert items[1].strip() == "y"


class TestForEachDoOutput:
    """do.output transforms each iteration's component result."""

    @pytest.mark.anyio
    async def test_do_output_transforms_per_iteration(self):
        components = [
            {
                "id": "echo",
                "type": "shell",
                "action": {
                    "command": [ "echo", "${input.n}" ],
                    "output": { "raw": "${result.stdout}" },
                },
            },
        ]
        workflow = {
            "id": "for-each-do-output",
            "jobs": [
                {
                    "id": "loop",
                    "type": "for-each",
                    "input": [ { "n": "1" }, { "n": "2" } ],
                    "do": {
                        "component": "echo",
                        "input": { "n": "${item.n}" },
                        "output": "label=${output.raw}",
                    },
                },
            ],
        }

        compose = _build_compose(workflow, components)
        result = await _run_workflow(compose, "for-each-do-output", {})

        items = await _collect(result)
        assert len(items) == 2
        assert items[0].strip() == "label=1"
        assert items[1].strip() == "label=2"


class TestForEachUpstreamOutput:
    """for-each receives input from an upstream job's output (list of dicts)."""

    @pytest.mark.anyio
    async def test_consumes_upstream_job_output(self):
        """Upstream shell emits a JSON array; for-each iterates the parsed list."""
        components = [
            {
                "id": "make-items",
                "type": "shell",
                "action": {
                    "command": [ "echo", '[{"label":"one"},{"label":"two"},{"label":"three"}]' ],
                    "output": "${result.stdout as json}",
                },
            },
            {
                "id": "echo",
                "type": "shell",
                "action": {
                    "command": [ "echo", "got=${input.label}" ],
                    "output": "${result.stdout}",
                },
            },
        ]
        workflow = {
            "id": "for-each-upstream",
            "jobs": [
                {
                    "id": "produce",
                    "component": "make-items",
                },
                {
                    "id": "loop",
                    "type": "for-each",
                    "input": "${jobs.produce.output}",
                    "do": {
                        "component": "echo",
                        "input": { "label": "${item.label}" },
                    },
                    "depends_on": [ "produce" ],
                },
            ],
        }

        compose = _build_compose(workflow, components)
        result = await _run_workflow(compose, "for-each-upstream", {})

        items = await _collect(result)
        assert len(items) == 3
        assert items[0].strip() == "got=one"
        assert items[1].strip() == "got=two"
        assert items[2].strip() == "got=three"
