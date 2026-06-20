"""Unit tests for ``WorkflowConfig`` and ``WorkflowVariableConfig`` validators."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.workflow import (
    WorkflowConfig,
    WorkflowVariableConfig,
    WorkflowVariableType,
)
from mindor.dsl.schema.job.impl.types import JobType
from mindor.dsl.schema.job.impl.delay import DelayJobMode


class TestVariableNormalizeListMarker:
    def test_type_with_list_marker_split(self):
        cfg = WorkflowVariableConfig.model_validate({"type": "string[]"})
        assert cfg.type == WorkflowVariableType.STRING
        assert cfg.is_list is True

    def test_type_without_marker_stays_scalar(self):
        cfg = WorkflowVariableConfig.model_validate({"type": "string"})
        assert cfg.type == WorkflowVariableType.STRING
        assert cfg.is_list is False

    def test_image_list_marker(self):
        cfg = WorkflowVariableConfig.model_validate({"type": "image[]"})
        assert cfg.type == WorkflowVariableType.IMAGE
        assert cfg.is_list is True


class TestWorkflowValidateId:
    def test_default_id_rejected(self):
        with pytest.raises(ValidationError, match="Workflow id cannot be '__default__'"):
            WorkflowConfig.model_validate({"id": "__default__"})

    def test_custom_id_accepted(self):
        cfg = WorkflowConfig.model_validate({"id": "my-wf"})
        assert cfg.id == "my-wf"

    def test_omitted_id_uses_placeholder(self):
        cfg = WorkflowConfig.model_validate({})
        assert cfg.id == "__workflow__"


class TestWorkflowNormalizeJobs:
    def test_single_job_inflated_to_list(self):
        cfg = WorkflowConfig.model_validate({
            "id": "wf",
            "job": {"component": "c1"},
        })
        assert len(cfg.jobs) == 1

    def test_explicit_jobs_passes_through(self):
        cfg = WorkflowConfig.model_validate({
            "id": "wf",
            "jobs": [{"component": "c1"}, {"component": "c2"}],
        })
        assert len(cfg.jobs) == 2

    def test_missing_type_defaults_to_component(self):
        cfg = WorkflowConfig.model_validate({
            "id": "wf",
            "jobs": [{"component": "c1"}],
        })
        assert cfg.jobs[0].type == JobType.COMPONENT

    def test_delay_job_without_mode_gets_time_interval_default(self):
        cfg = WorkflowConfig.model_validate({
            "id": "wf",
            "jobs": [{"type": "delay", "duration": "5s"}],
        })
        assert cfg.jobs[0].mode == DelayJobMode.TIME_INTERVAL

    def test_non_delay_job_unaffected_by_mode_fill(self):
        cfg = WorkflowConfig.model_validate({
            "id": "wf",
            "jobs": [{"type": "component", "component": "c1"}],
        })
        assert cfg.jobs[0].type == JobType.COMPONENT
