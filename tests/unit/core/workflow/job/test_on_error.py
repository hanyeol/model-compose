"""Unit tests for the ``on_error`` fallback on the ``Job`` base class.

Verifies:
- No on_error config → exception propagates.
- ``on_error: ignore`` returns None.
- ``on_error.output`` renders a fallback value and can reference ``${error.*}``.
- ``on_error.to`` returns a RoutingTarget so the runner routes to that job.
- ``on_error`` kicks in only after ``retry`` is exhausted.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from mindor.core.workflow.job.base import Job, RoutingTarget
from mindor.dsl.schema.job.impl.common import (
    JobOnErrorConfig,
    JobRetryConfig,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeWorkflowContext:
    def __init__(self, task_id: str = "task-1"):
        self.task_id = task_id


class _FakeJobContext:
    def __init__(self, task_id: str = "task-1"):
        self.workflow = _FakeWorkflowContext(task_id=task_id)
        self.sources: Dict[str, Any] = {}

    def register_source(self, scope, key, value):
        self.sources[key] = value

    async def render_variable(self, scope, value, skip_decode=False):
        # Minimal template substitution: replace `${error.message}` etc.
        if isinstance(value, str):
            return self._resolve_string(value)
        if isinstance(value, dict):
            return { k: await self.render_variable(scope, v) for k, v in value.items() }
        if isinstance(value, list):
            return [ await self.render_variable(scope, v) for v in value ]
        return value

    def _resolve_string(self, value: str) -> str:
        if not (value.startswith("${") and value.endswith("}")):
            return value
        path = value[2:-1]
        key, _, rest = path.partition(".")
        source = self.sources.get(key)
        if source is None:
            return None
        return source.get(rest) if rest else source


class _FakeConfig:
    def __init__(
        self,
        retry: Optional[JobRetryConfig] = None,
        on_error: Optional[JobOnErrorConfig] = None,
    ):
        self.retry = retry
        self.on_error = on_error


class _ScriptedJob(Job):
    def __init__(
        self,
        script: List[Any],
        retry: Optional[JobRetryConfig] = None,
        on_error: Optional[JobOnErrorConfig] = None,
    ):
        self.id = "job"
        self.config = _FakeConfig(retry=retry, on_error=on_error)
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
async def test_no_on_error_config_propagates_exception():
    job = _ScriptedJob([RuntimeError("boom")])
    with pytest.raises(RuntimeError, match="boom"):
        await job.run(_FakeJobContext())


@pytest.mark.anyio
async def test_on_error_empty_returns_none():
    on_error = JobOnErrorConfig()
    job = _ScriptedJob([RuntimeError("boom")], on_error=on_error)

    result = await job.run(_FakeJobContext())
    assert result is None


@pytest.mark.anyio
async def test_on_error_output_returns_rendered_fallback():
    on_error = JobOnErrorConfig(output={ "status": "failed", "reason": "${error.message}" })
    job = _ScriptedJob([ValueError("bad input")], on_error=on_error)

    result = await job.run(_FakeJobContext())
    assert result == { "status": "failed", "reason": "bad input" }


@pytest.mark.anyio
async def test_on_error_registers_error_source_with_message():
    on_error = JobOnErrorConfig(output={ "message": "${error.message}" })
    job = _ScriptedJob([ValueError("kaboom")], on_error=on_error)
    context = _FakeJobContext()

    result = await job.run(context)

    assert result == { "message": "kaboom" }
    assert context.sources["error"]["message"] == "kaboom"


@pytest.mark.anyio
async def test_on_error_to_returns_routing_target():
    on_error = JobOnErrorConfig(to="cleanup_job")
    job = _ScriptedJob([RuntimeError("boom")], on_error=on_error)

    result = await job.run(_FakeJobContext())
    assert isinstance(result, RoutingTarget)
    assert result.job_id == "cleanup_job"


@pytest.mark.anyio
async def test_on_error_applies_only_after_retries_exhausted():
    retry = JobRetryConfig(max_attempt_count=3, delay=0.0)
    on_error = JobOnErrorConfig()
    job = _ScriptedJob(
        [RuntimeError("a"), RuntimeError("b"), RuntimeError("c")],
        retry=retry,
        on_error=on_error,
    )

    result = await job.run(_FakeJobContext())
    assert result is None
    assert job.attempts == 3


@pytest.mark.anyio
async def test_on_error_not_applied_when_retry_succeeds():
    retry = JobRetryConfig(max_attempt_count=3, delay=0.0)
    on_error = JobOnErrorConfig(output={ "fallback": True })
    job = _ScriptedJob([RuntimeError("transient"), "ok"], retry=retry, on_error=on_error)

    result = await job.run(_FakeJobContext())
    assert result == "ok"
    assert job.attempts == 2
