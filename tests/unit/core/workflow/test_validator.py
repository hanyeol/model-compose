"""Unit tests for ``mindor.core.workflow.validator``.

Covers ``WorkflowValidator`` (workflow-scoped: duplicate job ids,
component/action references) and ``JobGraphValidator`` (graph shape:
depends_on references, routing targets, entry job, cycles).
"""

from typing import Any, Dict, List

import pytest

from mindor.core.workflow.validator import WorkflowValidator, JobGraphValidator
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.compose import ComposeConfig


def _build_config(
    components: List[Dict[str, Any]] = None,
    workflows: List[Dict[str, Any]] = None,
) -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {"type": "http-server", "port": 8080},
        "components": components or [],
        "workflows": workflows or [],
        "listeners": [],
    })


def _shell_component(id: str, action_ids: List[str] = None, default_action: str = None, default: bool = False) -> Dict[str, Any]:
    action_ids = action_ids or ["__action__"]
    return {
        "id": id,
        "type": "shell",
        "default": default,
        "actions": [
            {
                "id": aid,
                "command": ["echo"],
                **({"default": True} if aid == default_action else {}),
            }
            for aid in action_ids
        ],
    }


def _job(id: str, component: str = "c1", action: str = None, depends_on: List[Any] = None, on_error_to: str = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"id": id, "component": component}
    if action is not None:
        out["action"] = action
    if depends_on:
        out["depends_on"] = depends_on
    if on_error_to is not None:
        out["on_error"] = {"to": on_error_to}
    return out


def _wf_and_components(jobs: List[Dict[str, Any]], components: List[Dict[str, Any]] = None):
    components = components or [_shell_component("c1")]
    config = _build_config(components=components, workflows=[{"id": "wf", "jobs": jobs}])
    return config.workflows[0], config.components


# --------------------------------------------------------------------------------------
# WorkflowValidator
# --------------------------------------------------------------------------------------


class TestWorkflowValidatorDuplicateJobIds:
    def test_duplicate_job_id_reports_error(self):
        workflow, components = _wf_and_components([_job("dup"), _job("dup")])
        errors = WorkflowValidator(workflow, components).validate()
        assert any("Duplicate job ID 'dup'" in e for e in errors)

    def test_placeholder_job_id_not_reported_as_duplicate(self):
        # Two anonymous jobs (default id "__job__") should not trigger dup error.
        workflow, components = _wf_and_components([
            {"component": "c1"},
            {"component": "c1"},
        ])
        errors = WorkflowValidator(workflow, components).validate()
        assert not any("Duplicate job ID" in e for e in errors)

    def test_unique_job_ids_ok(self):
        workflow, components = _wf_and_components([_job("j1"), _job("j2")])
        errors = WorkflowValidator(workflow, components).validate()
        assert not any("Duplicate" in e for e in errors)


class TestWorkflowValidatorComponentReferences:
    def test_missing_component_reference_reports_error(self):
        workflow, components = _wf_and_components([_job("j1", component="ghost")])
        errors = WorkflowValidator(workflow, components).validate()
        assert any("non-existent component 'ghost'" in e for e in errors)

    def test_default_component_with_single_component_ok(self):
        workflow, components = _wf_and_components([_job("j1", component="__default__")])
        errors = WorkflowValidator(workflow, components).validate()
        assert not any("default component" in e for e in errors)

    def test_default_component_with_explicit_default_flag_ok(self):
        workflow, components = _wf_and_components(
            [_job("j1", component="__default__")],
            components=[_shell_component("c1", default=True), _shell_component("c2")],
        )
        errors = WorkflowValidator(workflow, components).validate()
        assert not any("default component" in e for e in errors)

    def test_default_component_without_marker_when_multiple_reports_error(self):
        workflow, components = _wf_and_components(
            [_job("j1", component="__default__")],
            components=[_shell_component("c1"), _shell_component("c2")],
        )
        errors = WorkflowValidator(workflow, components).validate()
        assert any("default component but multiple components exist" in e for e in errors)


class TestWorkflowValidatorActionReferences:
    def test_missing_action_reference_reports_error(self):
        workflow, components = _wf_and_components(
            [_job("j1", component="c1", action="ghost")],
            components=[_shell_component("c1", action_ids=["a1", "a2"])],
        )
        errors = WorkflowValidator(workflow, components).validate()
        assert any(
            "non-existent action 'ghost'" in e and "component 'c1'" in e
            for e in errors
        )

    def test_default_action_with_single_action_ok(self):
        workflow, components = _wf_and_components(
            [_job("j1", component="c1", action="__default__")],
            components=[_shell_component("c1", action_ids=["only"])],
        )
        errors = WorkflowValidator(workflow, components).validate()
        assert not any("default action" in e for e in errors)

    def test_default_action_with_explicit_default_flag_ok(self):
        workflow, components = _wf_and_components(
            [_job("j1", component="c1", action="__default__")],
            components=[_shell_component("c1", action_ids=["a1", "a2"], default_action="a1")],
        )
        errors = WorkflowValidator(workflow, components).validate()
        assert not any("default action" in e for e in errors)

    def test_default_action_without_marker_when_multiple_reports_error(self):
        workflow, components = _wf_and_components(
            [_job("j1", component="c1", action="__default__")],
            components=[_shell_component("c1", action_ids=["a1", "a2"])],
        )
        errors = WorkflowValidator(workflow, components).validate()
        assert any("default action but component 'c1' has multiple actions" in e for e in errors)

    def test_unknown_component_skips_action_check(self):
        # When the component reference itself is missing, `_validate_action_references`
        # should skip silently so only the component-reference error is reported.
        workflow, components = _wf_and_components(
            [_job("j1", component="ghost", action="whatever")],
        )
        errors = WorkflowValidator(workflow, components).validate()
        assert not any("action 'whatever'" in e for e in errors)


class TestWorkflowValidatorNonComponentJobs:
    """Non-component jobs (`if`, `switch`, etc.) skip component/action checks."""

    def test_if_job_skips_component_and_action_checks(self):
        # An `if` job doesn't reference any component; validator should ignore it
        # instead of trying to resolve `component`/`action` fields.
        config = _build_config(
            components=[_shell_component("c1")],
            workflows=[{
                "id": "wf",
                "jobs": [
                    {
                        "id": "branch",
                        "type": "if",
                        "conditions": [{"operator": "eq", "value": 1, "if_true": "j2"}],
                    },
                    _job("j2"),
                ],
            }],
        )
        workflow = config.workflows[0]
        errors = WorkflowValidator(workflow, config.components).validate()
        assert not any("component" in e or "action" in e for e in errors)


class TestWorkflowValidatorInlineComponent:
    """Jobs may inline a full component object; validator must not treat it as a
    missing component id."""

    def test_inline_component_object_skips_component_reference_check(self):
        config = _build_config(
            components=[_shell_component("c1")],
            workflows=[{
                "id": "wf",
                "jobs": [{
                    "id": "j1",
                    "component": {
                        "id": "inline",
                        "type": "shell",
                        "actions": [{"id": "__action__", "command": ["echo"]}],
                    },
                }],
            }],
        )
        workflow = config.workflows[0]
        errors = WorkflowValidator(workflow, config.components).validate()
        assert not any("non-existent component" in e for e in errors)

    def test_inline_component_action_resolved_against_inline_component(self):
        # Inline component with action ids `a1`,`a2`; job references `a1`.
        config = _build_config(
            components=[_shell_component("c1")],
            workflows=[{
                "id": "wf",
                "jobs": [{
                    "id": "j1",
                    "component": {
                        "id": "inline",
                        "type": "shell",
                        "actions": [
                            {"id": "a1", "command": ["echo"]},
                            {"id": "a2", "command": ["echo"]},
                        ],
                    },
                    "action": "a1",
                }],
            }],
        )
        workflow = config.workflows[0]
        errors = WorkflowValidator(workflow, config.components).validate()
        assert not any("non-existent action" in e for e in errors)


class TestWorkflowValidatorEmptyJobs:
    def test_empty_jobs_returns_no_errors_and_skips_all_checks(self):
        config = _build_config(
            components=[_shell_component("c1")],
            workflows=[{"id": "wf", "jobs": []}],
        )
        workflow = config.workflows[0]
        assert WorkflowValidator(workflow, config.components).validate() == []


# --------------------------------------------------------------------------------------
# JobGraphValidator
# --------------------------------------------------------------------------------------


def _jobs_from(jobs_config: List[Dict[str, Any]]):
    """Build JobConfig objects via pydantic (they need a component for validation)."""
    config = _build_config(
        components=[_shell_component("c1")],
        workflows=[{"id": "wf", "jobs": jobs_config}],
    )
    return config.workflows[0].jobs


class TestJobGraphValidatorReferences:
    def test_self_dependency_reports_error(self):
        jobs = _jobs_from([_job("j1", depends_on=["j1"])])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert any("depends on itself" in e for e in errors)

    def test_missing_dependency_reports_error(self):
        jobs = _jobs_from([_job("j1", depends_on=["ghost"])])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert any("non-existent job 'ghost'" in e for e in errors)

    def test_routing_target_existence_ok(self):
        jobs = _jobs_from([_job("j1", on_error_to="j2"), _job("j2")])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert not any("Routing target" in e for e in errors)

    def test_missing_routing_target_reports_error(self):
        jobs = _jobs_from([_job("j1", on_error_to="ghost")])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert any(
            "Routing target 'ghost' does not exist" in e and "job 'j1'" in e
            for e in errors
        )


class TestJobGraphValidatorEntryJob:
    def test_at_least_one_entry_job_ok(self):
        jobs = _jobs_from([_job("j1"), _job("j2", depends_on=["j1"])])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert not any("no entry job" in e for e in errors)

    def test_no_entry_job_reports_error(self):
        # Circular deps also imply no entry — both errors should surface.
        jobs = _jobs_from([
            _job("a", depends_on=["b"]),
            _job("b", depends_on=["a"]),
        ])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert any("no entry job" in e for e in errors)


class TestJobGraphValidatorCycles:
    def test_no_cycles_ok(self):
        jobs = _jobs_from([
            _job("a"),
            _job("b", depends_on=["a"]),
            _job("c", depends_on=["b"]),
        ])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert not any("cycle" in e.lower() for e in errors)

    def test_two_node_cycle_reports_error(self):
        jobs = _jobs_from([
            _job("a", depends_on=["b"]),
            _job("b", depends_on=["a"]),
        ])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert any("Dependency cycle detected" in e for e in errors)

    def test_three_node_cycle_reports_error(self):
        jobs = _jobs_from([
            _job("a", depends_on=["c"]),
            _job("b", depends_on=["a"]),
            _job("c", depends_on=["b"]),
        ])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert any("Dependency cycle detected" in e for e in errors)

    def test_dependency_on_missing_job_does_not_infinite_loop(self):
        # `ghost` isn't in the map → the cycle DFS's "not in self.jobs" branch
        # returns early and processing completes.
        jobs = _jobs_from([_job("j1", depends_on=["ghost"])])
        errors = JobGraphValidator(jobs, "wf").validate()
        # Reference-missing error present, no cycle error.
        assert any("non-existent job 'ghost'" in e for e in errors)
        assert not any("cycle" in e.lower() for e in errors)


class TestJobGraphValidatorOrGroups:
    def test_or_group_with_valid_members_ok(self):
        jobs = _jobs_from([
            _job("root"),
            _job("left", depends_on=["root"]),
            _job("right", depends_on=["root"]),
            _job("merge", depends_on=[["left", "right"]]),
        ])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert errors == []

    def test_or_group_missing_member_reports_error(self):
        jobs = _jobs_from([_job("a"), _job("b", depends_on=[["a", "ghost"]])])
        errors = JobGraphValidator(jobs, "wf").validate()
        assert any("non-existent job 'ghost'" in e for e in errors)
