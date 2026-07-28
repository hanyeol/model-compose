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


def _job(id: str, component: str = "c1", action: str = None, depends_on: List[Any] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"id": id, "component": component}
    if action is not None:
        out["action"] = action
    if depends_on:
        out["depends_on"] = depends_on
    return out


def _shell_component_with_actions(id: str, action_ids: List[str], default_action: str = None) -> Dict[str, Any]:
    return {
        "id": id,
        "type": "shell",
        "actions": [
            {"id": aid, "command": ["echo"], **({"default": True} if aid == default_action else {})}
            for aid in action_ids
        ],
    }


def _workflow_component(id: str, action_workflows: List[str]) -> Dict[str, Any]:
    return {
        "id": id,
        "type": "workflow",
        "actions": [{"id": f"a{i}", "workflow": wf} for i, wf in enumerate(action_workflows)],
    }


def _http_trigger_listener(triggers: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"type": "http-trigger", "triggers": triggers}


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

    def test_or_group_dependencies_are_valid(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{
                "id": "wf",
                "jobs": [
                    _job("root"),
                    _job("left", depends_on=["root"]),
                    _job("right", depends_on=["root"]),
                    _job("merge", depends_on=[["left", "right"]]),
                ],
            }],
        )
        errors = ComposeValidator(config).validate()
        assert errors == []

    def test_missing_dependency_reference_inside_or_group(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{
                "id": "wf",
                "jobs": [
                    _job("a"),
                    _job("b", depends_on=[["a", "ghost"]]),
                ],
            }],
        )
        errors = ComposeValidator(config).validate()
        assert any("non-existent job 'ghost'" in e for e in errors)

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


class TestPlaceholderIdsSkippedForDuplicates:
    """Placeholder ids (`__component__`, `__workflow__`) are skipped by the
    duplicate detectors so single anonymous entries don't raise false positives."""

    def test_placeholder_component_id_not_reported_as_duplicate(self):
        config = _compose(
            components=[
                {"id": "__component__", "type": "shell", "actions": [{"id": "__action__", "command": ["echo"]}]},
                {"id": "__component__", "type": "shell", "actions": [{"id": "__action__", "command": ["echo"]}]},
            ],
            workflows=[{"id": "wf", "jobs": [_job("j1", component="__default__")]}],
        )
        errors = ComposeValidator(config).validate()
        assert not any("Duplicate component ID" in e for e in errors)

    def test_placeholder_workflow_id_not_reported_as_duplicate(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[
                {"id": "__workflow__", "jobs": [_job("j1")]},
                {"id": "__workflow__", "jobs": [_job("j2")]},
            ],
        )
        errors = ComposeValidator(config).validate()
        assert not any("Duplicate workflow ID" in e for e in errors)


class TestWorkflowReferencesInComponents:
    """`_validate_workflow_references` — workflow-typed components pointing at workflow ids."""

    def test_workflow_component_references_missing_workflow_reports_error(self):
        config = _compose(
            components=[_workflow_component("wc", action_workflows=["ghost"])],
            workflows=[{"id": "wf", "jobs": [_job("j1", component="wc")]}],
        )
        errors = ComposeValidator(config).validate()
        assert any(
            "non-existent workflow 'ghost'" in e and "component 'wc'" in e
            for e in errors
        )

    def test_workflow_component_references_existing_workflow_ok(self):
        # Two workflows so `has_default_workflow = False`. The component action
        # explicitly names the target workflow, so no error.
        config = _compose(
            components=[_workflow_component("wc", action_workflows=["wf1"])],
            workflows=[
                {"id": "wf1", "jobs": [_job("j1", component="__default__")]},
                {"id": "wf2", "jobs": [_job("j1", component="__default__")]},
            ],
        )
        errors = ComposeValidator(config).validate()
        assert not any("workflow" in e and "non-existent" in e for e in errors)

    def test_workflow_component_default_workflow_with_single_workflow_ok(self):
        # Single workflow → `__default__` resolves. No error expected.
        config = _compose(
            components=[_workflow_component("wc", action_workflows=["__default__"])],
            workflows=[{"id": "only", "jobs": [_job("j1", component="wc")]}],
        )
        errors = ComposeValidator(config).validate()
        assert not any("default workflow" in e for e in errors)

    def test_workflow_component_default_without_marker_when_multiple_reports_error(self):
        config = _compose(
            components=[_workflow_component("wc", action_workflows=["__default__"])],
            workflows=[
                {"id": "wf1", "jobs": [_job("j1", component="wc")]},
                {"id": "wf2", "jobs": [_job("j1", component="wc")]},
            ],
        )
        errors = ComposeValidator(config).validate()
        assert any("default workflow but multiple workflows exist" in e for e in errors)


class TestWorkflowReferencesInListeners:
    """`_validate_workflow_references` — HTTP trigger listeners pointing at workflow ids."""

    def test_http_trigger_references_missing_workflow_reports_error(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": [_job("j1")]}],
            listeners=[_http_trigger_listener([
                {"path": "/x", "workflow": "ghost"},
            ])],
        )
        errors = ComposeValidator(config).validate()
        assert any(
            "non-existent workflow 'ghost'" in e and "listeners[0].triggers[0]" in e
            for e in errors
        )

    def test_http_trigger_references_existing_workflow_ok(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": [_job("j1")]}],
            listeners=[_http_trigger_listener([
                {"path": "/x", "workflow": "wf"},
            ])],
        )
        assert ComposeValidator(config).validate() == []

    def test_http_trigger_default_workflow_with_single_workflow_ok(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[{"id": "only", "jobs": [_job("j1")]}],
            listeners=[_http_trigger_listener([
                {"path": "/x", "workflow": "__default__"},
            ])],
        )
        errors = ComposeValidator(config).validate()
        assert not any("default workflow" in e for e in errors)

    def test_http_trigger_default_without_marker_when_multiple_reports_error(self):
        config = _compose(
            components=[_shell_component("c1")],
            workflows=[
                {"id": "wf1", "jobs": [_job("j1")]},
                {"id": "wf2", "jobs": [_job("j1")]},
            ],
            listeners=[_http_trigger_listener([
                {"path": "/x", "workflow": "__default__"},
            ])],
        )
        errors = ComposeValidator(config).validate()
        assert any(
            "default workflow but multiple workflows exist" in e and "listeners[0].triggers[0]" in e
            for e in errors
        )
