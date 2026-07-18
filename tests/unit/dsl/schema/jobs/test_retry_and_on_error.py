"""Unit tests for ``retry`` / ``on_error`` normalisation and routing merge."""

import pytest
from pydantic import ValidationError, TypeAdapter

from mindor.dsl.schema.job import JobConfig
from mindor.dsl.schema.job.impl.common import (
    JobOnErrorConfig,
    JobRetryBackoff,
    JobRetryConfig,
)


def _build_job(**overrides):
    """Build a minimal delay job with the given retry/on_error fields."""
    payload = {
        "id":       "j",
        "type":     "delay",
        "mode":     "time-interval",
        "duration": "0s",
    }
    payload.update(overrides)
    return TypeAdapter(JobConfig).validate_python(payload)


class TestRetryNormalisation:
    def test_integer_shorthand_expands_to_max_attempt_count(self):
        job = _build_job(retry=3)
        assert isinstance(job.retry, JobRetryConfig)
        assert job.retry.max_attempt_count == 3
        assert job.retry.delay == 0.0
        assert job.retry.backoff == JobRetryBackoff.FIXED

    def test_object_form_preserves_all_fields(self):
        job = _build_job(retry={
            "max_attempt_count": 5,
            "delay":             "2s",
            "backoff":           "exponential",
            "max_delay":         "30s",
        })
        assert job.retry.max_attempt_count == 5
        assert job.retry.delay == "2s"
        assert job.retry.backoff == JobRetryBackoff.EXPONENTIAL
        assert job.retry.max_delay == "30s"

    def test_omitted_retry_is_none(self):
        job = _build_job()
        assert job.retry is None

    def test_max_attempt_count_must_be_positive(self):
        with pytest.raises(ValidationError):
            _build_job(retry={ "max_attempt_count": 0 })


class TestOnErrorNormalisation:
    def test_ignore_shorthand_expands_to_empty_config(self):
        job = _build_job(on_error="ignore")
        assert isinstance(job.on_error, JobOnErrorConfig)
        assert job.on_error.output is None
        assert job.on_error.to is None

    def test_ignore_shorthand_case_insensitive(self):
        job = _build_job(on_error="IGNORE")
        assert isinstance(job.on_error, JobOnErrorConfig)

    def test_unknown_string_shorthand_is_rejected(self):
        with pytest.raises(ValidationError):
            _build_job(on_error="fail")

    def test_output_object_form(self):
        job = _build_job(on_error={ "output": { "status": "failed" } })
        assert job.on_error.output == { "status": "failed" }
        assert job.on_error.to is None

    def test_to_object_form(self):
        job = _build_job(on_error={ "to": "cleanup" })
        assert job.on_error.to == "cleanup"

    def test_output_and_to_can_coexist(self):
        job = _build_job(on_error={ "output": { "x": 1 }, "to": "cleanup" })
        assert job.on_error.output == { "x": 1 }
        assert job.on_error.to == "cleanup"

    def test_omitted_on_error_is_none(self):
        job = _build_job()
        assert job.on_error is None


class TestGetRoutingJobsCommon:
    def test_returns_empty_set_by_default(self):
        job = _build_job()
        assert job.get_routing_jobs() == set()

    def test_includes_on_error_to(self):
        job = _build_job(on_error={ "to": "cleanup" })
        assert job.get_routing_jobs() == { "cleanup" }

    def test_ignores_on_error_without_to(self):
        job = _build_job(on_error={ "output": { "x": 1 } })
        assert job.get_routing_jobs() == set()


class TestGetRoutingJobsIfMerge:
    def test_if_merges_on_error_to_with_branch_targets(self):
        job = TypeAdapter(JobConfig).validate_python({
            "id":       "check",
            "type":     "if",
            "input":    "${x}",
            "value":    1,
            "if_true":  "yes",
            "if_false": "no",
            "on_error": { "to": "cleanup" },
        })
        assert job.get_routing_jobs() == { "yes", "no", "cleanup" }

    def test_if_with_otherwise_includes_otherwise_and_on_error(self):
        job = TypeAdapter(JobConfig).validate_python({
            "id":         "check",
            "type":       "if",
            "conditions": [ { "value": 1, "if_true": "yes" } ],
            "otherwise":  "fallback",
            "on_error":   { "to": "cleanup" },
        })
        assert job.get_routing_jobs() == { "yes", "fallback", "cleanup" }


class TestGetRoutingJobsSwitchMerge:
    def test_switch_merges_on_error_to_with_case_targets(self):
        job = TypeAdapter(JobConfig).validate_python({
            "id":        "route",
            "type":      "switch",
            "input":     "${x}",
            "cases":     [ { "value": "a", "then": "job-a" }, { "value": "b", "then": "job-b" } ],
            "otherwise": "job-default",
            "on_error":  { "to": "cleanup" },
        })
        assert job.get_routing_jobs() == { "job-a", "job-b", "job-default", "cleanup" }


class TestGetRoutingJobsRandomRouterMerge:
    def test_random_router_merges_on_error_to_with_routings(self):
        job = TypeAdapter(JobConfig).validate_python({
            "id":       "route",
            "type":     "random-router",
            "routings": [ { "to": "a" }, { "to": "b" } ],
            "on_error": { "to": "cleanup" },
        })
        assert job.get_routing_jobs() == { "a", "b", "cleanup" }
