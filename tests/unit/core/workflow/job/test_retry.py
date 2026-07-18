"""Unit tests for the ``retry`` policy on the ``Job`` base class.

Verifies:
- No retry config → job fails on first exception.
- ``retry: N`` retries up to N total attempts.
- Success on a retry returns the successful output.
- Backoff modes compute the expected delay.
"""

from __future__ import annotations

from typing import Any, List, Optional

import pytest

from mindor.core.workflow.job.base import Job
from mindor.dsl.schema.job.impl.common import JobRetryBackoff, JobRetryConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeWorkflowContext:
    def __init__(self, task_id: str = "task-1"):
        self.task_id = task_id


class _FakeJobContext:
    def __init__(self, task_id: str = "task-1"):
        self.workflow = _FakeWorkflowContext(task_id=task_id)

    def register_source(self, scope, key, value):
        pass

    async def render_variable(self, scope, value, skip_decode=False):
        return value


class _FakeConfig:
    def __init__(self, retry: Optional[JobRetryConfig] = None):
        self.retry = retry
        self.on_error = None


class _ScriptedJob(Job):
    """Runs a scripted sequence of outputs/exceptions."""

    def __init__(self, script: List[Any], retry: Optional[JobRetryConfig] = None):
        self.id = "job"
        self.config = _FakeConfig(retry=retry)
        self.global_configs = None
        self._script = list(script)
        self.attempts = 0

    async def _run(self, context):
        self.attempts += 1
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.anyio
async def test_no_retry_config_fails_on_first_exception():
    job = _ScriptedJob([RuntimeError("boom")])
    with pytest.raises(RuntimeError, match="boom"):
        await job.run(_FakeJobContext())
    assert job.attempts == 1


@pytest.mark.anyio
async def test_retry_returns_success_after_transient_failure():
    retry = JobRetryConfig(max_attempt_count=3, delay=0.0)
    job = _ScriptedJob([RuntimeError("nope"), "ok"], retry=retry)

    result = await job.run(_FakeJobContext())

    assert result == "ok"
    assert job.attempts == 2


@pytest.mark.anyio
async def test_retry_raises_last_error_when_exhausted():
    retry = JobRetryConfig(max_attempt_count=3, delay=0.0)
    job = _ScriptedJob(
        [RuntimeError("first"), RuntimeError("second"), RuntimeError("third")],
        retry=retry,
    )

    with pytest.raises(RuntimeError, match="third"):
        await job.run(_FakeJobContext())
    assert job.attempts == 3


def _compute_delay(retry: JobRetryConfig, attempt: int) -> float:
    job = _ScriptedJob(["ok"], retry=retry)
    return job._resolve_retry_delay(attempt)


def test_backoff_fixed_returns_base_delay():
    retry = JobRetryConfig(max_attempt_count=5, delay=2.0, backoff=JobRetryBackoff.FIXED)
    assert _compute_delay(retry, 1) == 2.0
    assert _compute_delay(retry, 4) == 2.0


def test_backoff_exponential_doubles_each_attempt():
    retry = JobRetryConfig(max_attempt_count=5, delay=1.0, backoff=JobRetryBackoff.EXPONENTIAL)
    assert _compute_delay(retry, 1) == 1.0
    assert _compute_delay(retry, 3) == 4.0
    assert _compute_delay(retry, 5) == 16.0


def test_max_delay_caps_backoff():
    retry = JobRetryConfig(
        max_attempt_count=5, delay=1.0, backoff=JobRetryBackoff.EXPONENTIAL, max_delay=5.0
    )
    assert _compute_delay(retry, 5) == 5.0
