"""Unit tests for ``mindor.core.compose.validator.ComposeValidator``.

Asserts the cross-reference and graph-shape errors that ``ComposeValidator``
emits. Each test builds a minimal valid ``ComposeConfig`` skeleton and mutates
the part under test.
"""

from typing import Any, Dict, List

import pytest

from mindor.core.compose.validator import ComposeValidator
from mindor.dsl.schema.compose import ComposeConfig


def _compose(
    components: List[Dict[str, Any]] = None,
    workflows: List[Dict[str, Any]] = None,
    listeners: List[Dict[str, Any]] = None,
) -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {"type": "http-server", "port": 8080},
        "components": components or [],
        "workflows": workflows or [],
        "listeners": listeners or [],
    })


def _shell_component(id: str, default: bool = False) -> Dict[str, Any]:
    return {
        "id": id,
        "type": "shell",
        "default": default,
        "actions": [{"id": "__action__", "command": ["echo"]}],
    }


def _job(id: str, component: str = "c1", depends_on: List[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"id": id, "component": component}
    if depends_on:
        out["depends_on"] = depends_on
    return out


class TestNoErrorsOnValidConfig:
    def test_single_component_single_workflow_no_errors(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": [_job("j1")]}],
        )
        assert ComposeValidator(config).validate() == []


class TestDuplicateIds:
    def test_duplicate_component_id(self):
        config = _compose(
            components=[_shell_component("c1"), _shell_component("c1")],
            workflows=[{"id": "wf", "jobs": [_job("j1", component="c1")]}],
        )
        errors = ComposeValidator(config).validate()
        assert any("Duplicate component ID 'c1'" in e for e in errors)

    def test_duplicate_workflow_id(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[
                {"id": "wf", "jobs": [_job("j1")]},
                {"id": "wf", "jobs": [_job("j2")]},
            ],
        )
        errors = ComposeValidator(config).validate()
        assert any("Duplicate workflow ID 'wf'" in e for e in errors)

    def test_duplicate_job_id_within_workflow(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": [_job("dup"), _job("dup")]}],
        )
        errors = ComposeValidator(config).validate()
        assert any("Duplicate job ID 'dup'" in e for e in errors)

    def test_same_job_id_in_different_workflows_ok(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[
                {"id": "wf1", "jobs": [_job("j1")]},
                {"id": "wf2", "jobs": [_job("j1")]},
            ],
        )
        assert ComposeValidator(config).validate() == []


class TestComponentReferences:
    def test_missing_component_reference(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": [_job("j1", component="ghost")]}],
        )
        errors = ComposeValidator(config).validate()
        assert any("non-existent component 'ghost'" in e for e in errors)

    def test_default_component_with_single_component_ok(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": [_job("j1", component="__default__")]}],
        )
        assert ComposeValidator(config).validate() == []

    def test_default_component_with_multiple_without_default_marker_errors(self):
        config = _compose(
            components=[_shell_component("c1"), _shell_component("c2")],
            workflows=[{"id": "wf", "jobs": [_job("j1", component="__default__")]}],
        )
        errors = ComposeValidator(config).validate()
        assert any("default component but multiple components exist" in e for e in errors)

    def test_default_component_with_explicit_default_flag_ok(self):
        config = _compose(
            components=[_shell_component("c1", default=True), _shell_component("c2")],
            workflows=[{"id": "wf", "jobs": [_job("j1", component="__default__")]}],
        )
        assert ComposeValidator(config).validate() == []


class TestJobGraphs:
    def test_self_dependency_detected(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": [_job("j1", depends_on=["j1"])]}],
        )
        errors = ComposeValidator(config).validate()
        assert any("depends on itself" in e for e in errors)

    def test_missing_dependency_reference(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": [_job("j1", depends_on=["ghost"])]}],
        )
        errors = ComposeValidator(config).validate()
        assert any("non-existent job 'ghost'" in e for e in errors)

    def test_two_node_cycle_detected(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{
                "id": "wf",
                "jobs": [
                    _job("a", depends_on=["b"]),
                    _job("b", depends_on=["a"]),
                ],
            }],
        )
        errors = ComposeValidator(config).validate()
        assert any("Dependency cycle detected" in e for e in errors)

    def test_no_entry_job_when_all_have_dependencies(self):
        # Every job depends on another → workflow has no entry. The validator also
        # reports the cycle that this implies.
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{
                "id": "wf",
                "jobs": [
                    _job("a", depends_on=["b"]),
                    _job("b", depends_on=["a"]),
                ],
            }],
        )
        errors = ComposeValidator(config).validate()
        assert any("has no entry job" in e for e in errors)

    def test_dag_with_diamond_shape_is_valid(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{
                "id": "wf",
                "jobs": [
                    _job("root"),
                    _job("left", depends_on=["root"]),
                    _job("right", depends_on=["root"]),
                    _job("merge", depends_on=["left", "right"]),
                ],
            }],
        )
        errors = ComposeValidator(config).validate()
        assert errors == []


class TestEmptyWorkflowSkipped:
    def test_empty_workflow_does_not_error(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": []}],
        )
        # Empty `jobs` is gracefully skipped — the validator just doesn't run
        # graph checks against it.
        assert ComposeValidator(config).validate() == []
