"""Unit tests for `core/workflow/schema.py`.

Regression coverage for `WorkflowOutputVariableResolver` output-schema
resolution across for-each jobs and sub-workflow inlining.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from mindor.core.workflow.schema import (
    WorkflowOutputVariableResolver,
    WorkflowVariableGroup,
    create_workflow_schemas,
)
from mindor.dsl.schema.compose import ComposeConfig
from mindor.dsl.schema.workflow import WorkflowVariableGroupConfig


def _load_compose(spec: Dict[str, Any]) -> ComposeConfig:
    spec.setdefault("controller", {"type": "http-server", "port": 8080})
    return ComposeConfig.model_validate(spec)


def test_for_each_over_subworkflow_ending_in_for_each_flattens_groups():
    """Parent for-each that invokes a sub-workflow whose terminal job is
    itself a for-each must not surface a nested `WorkflowVariableGroup`.

    Before the fix, this raised `TypeError: unhashable type: 'WorkflowVariableGroup'`
    from `_to_variable_config_list` because the inner group leaked into the
    outer group's `variables` list, which is typed as leaf variables only.
    """
    compose = _load_compose({
        "components": [
            {
                "id": "runner",
                "type": "workflow",
                "action": {"workflow": "inner", "input": "${input}"},
            },
            {
                "id": "storage",
                "type": "file-store",
                "driver": "local",
                "base_path": "./out",
                "action": {
                    "method": "put",
                    "path": "${input.path}",
                    "source": "${input.source}",
                },
                "output": "${result.path}",
            },
            {
                "id": "extractor",
                "type": "video-frame-extractor",
                "driver": "ffmpeg",
                "action": {
                    "video": "${input.video}",
                    "streaming": True,
                },
            },
        ],
        "workflows": [
            {
                "id": "outer",
                "jobs": [
                    {
                        "id": "fan-out",
                        "type": "for-each",
                        "input": "${input.items}",
                        "do": {
                            "component": "runner",
                            "input": {"video": "${item}"},
                        },
                    },
                ],
            },
            {
                "id": "inner",
                "jobs": [
                    {
                        "id": "extract",
                        "component": "extractor",
                        "input": {"video": "${input.video as video;url}"},
                    },
                    {
                        "id": "save",
                        "type": "for-each",
                        "input": "${jobs.extract.output}",
                        "do": {
                            "component": "storage",
                            "input": {
                                "path": "frame-${item.timestamp}.png",
                                "source": "${item.image as image/png}",
                            },
                        },
                        "depends_on": ["extract"],
                    },
                ],
            },
        ],
    })

    # Would previously raise TypeError; must now build a valid schema map.
    schemas = create_workflow_schemas(compose.workflows, compose.components)

    outer_output = schemas["outer"].output
    assert len(outer_output) == 1
    assert isinstance(outer_output[0], WorkflowVariableGroupConfig)
    # After flattening, the outer group's variables are leaf configs only —
    # never further groups.
    for variable in outer_output[0].variables:
        assert not isinstance(variable, WorkflowVariableGroupConfig)


def test_to_variable_config_list_flattens_arbitrarily_nested_groups():
    """`_to_variable_config_list` must strip nested groups from a group's
    `variables` list at any depth — the outer group's `repeat_count` is the
    only iteration marker the consumer knows how to interpret."""
    resolver = WorkflowOutputVariableResolver()

    leaf_a = resolver._any_variable()
    leaf_b = resolver._any_variable()
    leaf_c = resolver._any_variable()

    outer = WorkflowVariableGroup(
        name="outer",
        variables=[
            leaf_a,
            WorkflowVariableGroup(
                name="inner",
                variables=[
                    leaf_b,
                    WorkflowVariableGroup(name="deeper", variables=[leaf_c], repeat_count=0),
                ],
                repeat_count=0,
            ),
        ],
        repeat_count=0,
    )

    configs = resolver._to_variable_config_list([outer])

    assert len(configs) == 1
    assert isinstance(configs[0], WorkflowVariableGroupConfig)
    # All entries under the group must be leaf configs, never nested groups.
    for variable in configs[0].variables:
        assert not isinstance(variable, WorkflowVariableGroupConfig)


def test_for_each_terminal_job_still_wraps_output_in_group():
    """A workflow whose terminal job is a for-each should still expose its
    output as a single `WorkflowVariableGroupConfig` (unchanged behavior)."""
    compose = _load_compose({
        "components": [
            {
                "id": "storage",
                "type": "file-store",
                "driver": "local",
                "base_path": "./out",
                "action": {
                    "method": "put",
                    "path": "${input.path}",
                    "source": "${input.source}",
                },
                "output": "${result.path}",
            },
        ],
        "workflows": [
            {
                "id": "solo",
                "jobs": [
                    {
                        "id": "save",
                        "type": "for-each",
                        "input": "${input.items}",
                        "do": {
                            "component": "storage",
                            "input": {
                                "path": "${item.path}",
                                "source": "${item.source}",
                            },
                        },
                    },
                ],
            },
        ],
    })

    schemas = create_workflow_schemas(compose.workflows, compose.components)
    output = schemas["solo"].output

    assert len(output) == 1
    assert isinstance(output[0], WorkflowVariableGroupConfig)
