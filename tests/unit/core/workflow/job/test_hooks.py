"""Unit tests for hook runtime helpers on the ``Job`` base class.

Hook contracts:
- before: ``async def hook(input, **kwargs)`` -> new input (None keeps original)
- after:  ``async def hook(input, output, **kwargs)`` -> new output (None keeps original)

``**kwargs`` receives HookPoint fields (task_id, job_id, run_id, phase).
"""

from __future__ import annotations

from typing import Any, Optional

import pytest

from mindor.core.workflow.job.base import Job, RoutingTarget
from mindor.dsl.schema.job.impl.common import JobHookConfig, JobHooksConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeWorkflowContext:
    def __init__(self, task_id: str = "task-1"):
        self.task_id = task_id


class _FakeJobContext:
    def __init__(self, task_id: str = "task-1"):
        self.workflow = _FakeWorkflowContext(task_id=task_id)


class _FakeConfig:
    def __init__(self, hook: Optional[JobHooksConfig] = None):
        self.hook = hook


class _FakeJob(Job):
    def __init__(self, hook_config: Optional[JobHooksConfig] = None, job_id: str = "job-1"):
        self.id = job_id
        self.config = _FakeConfig(hook=hook_config)
        self.global_configs = None

    async def run(self, context):  # unused for hook helper tests
        raise NotImplementedError


def make_hooks(before=None, after=None):
    payload = {}
    if before is not None:
        payload["before"] = before
    if after is not None:
        payload["after"] = after
    return JobHooksConfig(**payload)


@pytest.mark.anyio
async def test_before_hook_transforms_input():
    hooks = make_hooks(before={"script": (
        "async def hook(input, **kwargs):\n"
        "    input['prefix'] = 'hi'\n"
        "    return input\n"
    )})
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_before_hooks(_FakeJobContext(), "run-1", {"name": "world"})

    assert result == {"name": "world", "prefix": "hi"}


@pytest.mark.anyio
async def test_after_hook_transforms_output():
    hooks = make_hooks(after={"script": (
        "async def hook(input, output, **kwargs):\n"
        "    return {'wrapped': output}\n"
    )})
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_after_hooks(_FakeJobContext(), "run-1", {"in": True}, 42)

    assert result == {"wrapped": 42}


@pytest.mark.anyio
async def test_after_hook_can_read_input():
    hooks = make_hooks(after={"script": (
        "async def hook(input, output, **kwargs):\n"
        "    return {'in': input, 'out': output}\n"
    )})
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_after_hooks(_FakeJobContext(), "run-1", {"i": 1}, {"o": 2})

    assert result == {"in": {"i": 1}, "out": {"o": 2}}


@pytest.mark.anyio
async def test_after_hook_returning_none_replaces_output_with_none():
    # New contract: the hook's return value is always used verbatim, so
    # ``return None`` explicitly nulls the output.
    hooks = make_hooks(after={"script": (
        "async def hook(input, output, **kwargs):\n"
        "    return None\n"
    )})
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_after_hooks(_FakeJobContext(), "run-1", {"in": True}, {"was": True})

    assert result is None


@pytest.mark.anyio
async def test_before_hook_returning_none_replaces_input_with_none():
    hooks = make_hooks(before={"script": (
        "async def hook(input, **kwargs):\n"
        "    return None\n"
    )})
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_before_hooks(_FakeJobContext(), "run-1", {"was": True})

    assert result is None


@pytest.mark.anyio
async def test_before_hook_must_return_input_to_preserve():
    # To pass through unchanged, hooks must explicitly return the input.
    hooks = make_hooks(before={"script": (
        "async def hook(input, **kwargs):\n"
        "    return input\n"
    )})
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_before_hooks(_FakeJobContext(), "run-1", {"kept": True})

    assert result == {"kept": True}


@pytest.mark.anyio
async def test_multiple_after_hooks_run_in_order():
    hooks = make_hooks(after=[
        {"script": "async def hook(input, output, **kwargs):\n    output.append(1)\n    return output\n"},
        {"script": "async def hook(input, output, **kwargs):\n    output.append(2)\n    return output\n"},
        {"script": "async def hook(input, output, **kwargs):\n    output.append(3)\n    return output\n"},
    ])
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_after_hooks(_FakeJobContext(), "run-1", None, [])

    assert result == [1, 2, 3]


@pytest.mark.anyio
async def test_after_hooks_are_isolated_namespaces():
    hooks = make_hooks(after=[
        {"script": (
            "def helper(x): return x + 100\n"
            "async def hook(input, output, **kwargs):\n"
            "    return helper(output)\n"
        )},
        {"script": (
            "def helper(x): return x * 2\n"
            "async def hook(input, output, **kwargs):\n"
            "    return helper(output)\n"
        )},
    ])
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_after_hooks(_FakeJobContext(), "run-1", None, 1)

    # first hook: 1 + 100 = 101; second hook: 101 * 2 = 202
    assert result == 202


@pytest.mark.anyio
async def test_sync_hook_function_supported():
    hooks = make_hooks(before={"script": (
        "def hook(input, **kwargs):\n"
        "    return input + 1\n"
    )})
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_before_hooks(_FakeJobContext(), "run-1", 41)

    assert result == 42


@pytest.mark.anyio
async def test_hook_receives_hook_point_fields():
    hooks = make_hooks(after={"script": (
        "async def hook(input, output, **kwargs):\n"
        "    return {\n"
        "        'task_id': kwargs['task_id'],\n"
        "        'job_id': kwargs['job_id'],\n"
        "        'run_id': kwargs['run_id'],\n"
        "        'phase': kwargs['phase'],\n"
        "        'output': output,\n"
        "    }\n"
    )})
    job = _FakeJob(hook_config=hooks, job_id="my-job")

    result = await job._apply_after_hooks(_FakeJobContext(task_id="task-xyz"), "run-abc", None, 42)

    assert result == {
        "task_id": "task-xyz",
        "job_id": "my-job",
        "run_id": "run-abc",
        "phase": "after",
        "output": 42,
    }


@pytest.mark.anyio
async def test_hook_can_destructure_kwargs_explicitly():
    hooks = make_hooks(before={"script": (
        "async def hook(input, *, task_id, job_id, run_id, phase):\n"
        "    return {'input': input, 'meta': (task_id, job_id, run_id, phase)}\n"
    )})
    job = _FakeJob(hook_config=hooks, job_id="j1")

    result = await job._apply_before_hooks(_FakeJobContext(task_id="t1"), None, {"x": 1})

    assert result == {"input": {"x": 1}, "meta": ("t1", "j1", None, "before")}


@pytest.mark.anyio
async def test_missing_hook_function_raises():
    hooks = make_hooks(before={"script": "def not_hook(input, **kwargs): return input\n"})
    job = _FakeJob(hook_config=hooks)

    with pytest.raises(ValueError, match="must define a callable named 'hook'"):
        await job._apply_before_hooks(_FakeJobContext(), "run-1", {})


@pytest.mark.anyio
async def test_no_hook_config_is_passthrough():
    job = _FakeJob(hook_config=None)

    before_result = await job._apply_before_hooks(_FakeJobContext(), "run-1", {"data": 1})
    after_result = await job._apply_after_hooks(_FakeJobContext(), "run-1", {"in": True}, {"data": 2})

    assert before_result == {"data": 1}
    assert after_result == {"data": 2}


@pytest.mark.anyio
async def test_empty_phase_is_passthrough():
    hooks = make_hooks(before={"script": "async def hook(input, **kwargs): return input\n"})
    job = _FakeJob(hook_config=hooks)

    # after phase has no hooks -> should be passthrough (returns output unchanged)
    result = await job._apply_after_hooks(_FakeJobContext(), "run-1", {"in": 1}, {"data": 3})
    assert result == {"data": 3}


@pytest.mark.anyio
async def test_after_hook_observes_none_output_for_routing_jobs():
    hooks = make_hooks(after={"script": (
        "observed = []\n"
        "async def hook(input, output, **kwargs):\n"
        "    observed.append((input, output))\n"
        "    return 'ignored'\n"
    )})
    job = _FakeJob(hook_config=hooks)

    result = await job._apply_after_hooks(_FakeJobContext(), None, {"route": "on"}, None)

    assert result == "ignored"


@pytest.mark.anyio
async def test_after_hook_runs_before_output_render():
    # The after-hook is applied to the raw job output BEFORE the ``output``
    # template is rendered, so the template can reference values produced by
    # the hook. Here the filter job's raw output is a list; the after hook
    # converts it into ``{"summary": <len>}``; the output template then
    # projects that transformed dict through ``${output.summary}``.
    from pydantic import TypeAdapter
    from mindor.core.foundation.variable.renderer import VariableRenderer
    from mindor.core.workflow.job.impl.filter import FilterJob
    from mindor.dsl.schema.job import JobConfig

    class _Ctx:
        def __init__(self):
            self._sources = {"__global__": {"source": [10, 20, 30]}}
            self.renderer = VariableRenderer(self._resolve_source)
            self.workflow = _FakeWorkflowContext()

        def register_source(self, scope, key, value):
            self._sources.setdefault(scope or "__global__", {})[key] = value

        async def render_variable(self, scope, value, skip_decode=False):
            return await self.renderer.render(value, scope, skip_decode=skip_decode)

        async def _resolve_source(self, key, index, scope):
            sources = self._sources.get(scope or "__global__", {})
            if key in sources:
                v = sources[key]
                return v[index] if index is not None and isinstance(v, list) else v
            return None

    cfg = TypeAdapter(JobConfig).validate_python({
        "type": "filter",
        "input": "${source}",
        "output": {"result": "${output.summary}"},
        "hook": {
            "after": {
                "script": (
                    "async def hook(input, output, **kwargs):\n"
                    "    return {'summary': len(output)}\n"
                )
            }
        },
    })
    job = FilterJob.__new__(FilterJob)
    job.id = "j"
    job.config = cfg
    job.global_configs = None

    result = await job.run(_Ctx())

    # after hook transformed [10,20,30] -> {"summary": 3}
    # then output template rendered {"result": "${output.summary}"} -> {"result": 3}
    assert result == {"result": 3}


# ------------------------------------------------------------------ #
# Cross-job "after hook precedes output render" scenarios            #
# ------------------------------------------------------------------ #


class _FakeWorkflowForOutput:
    def __init__(self, task_id: str = "task-1"):
        self.task_id = task_id
        self.workflow_id = "wf-1"
        self.input = None
        self.run_ids = []

    def record_run_id(self, job_id, run_id):
        self.run_ids.append((job_id, run_id))


class _FakeCtx:
    """Reusable JobContext stand-in with a real VariableRenderer."""

    def __init__(self, workflow_input=None):
        from mindor.core.foundation.variable.renderer import VariableRenderer

        self._sources = {"__global__": {}}
        self.workflow = _FakeWorkflowForOutput()
        self.workflow.input = workflow_input
        self.is_terminal = False
        self.renderer = VariableRenderer(self._resolve_source)

    def register_source(self, scope, key, value):
        self._sources.setdefault(scope or "__global__", {})[key] = value

    async def render_variable(self, scope, value, skip_decode=False):
        return await self.renderer.render(value, scope, skip_decode=skip_decode)

    async def _resolve_source(self, key, index, scope):
        sources = self._sources.get(scope or "__global__", {})
        if key in sources:
            v = sources[key]
            return v[index] if index is not None and isinstance(v, list) else v
        return None


@pytest.mark.anyio
async def test_component_after_hook_runs_before_output_render():
    # ComponentJob._run should apply the after hook to the raw component
    # output BEFORE rendering the `output` template, so the template can
    # reference the transformed dict.
    from pydantic import TypeAdapter
    from mindor.core.workflow.job.impl.component import ComponentJob
    from mindor.dsl.schema.job import JobConfig

    class _FakeComponent:
        def __init__(self, result):
            self.id = "fake"
            self.started = True
            self._result = result

        async def start(self):
            self.started = True

        async def run(self, action, run_id, input, workflow, job_id):
            return self._result

    cfg = TypeAdapter(JobConfig).validate_python({
        "type": "component",
        "component": "c",
        "action": "a",
        "output": {"result": "${output.transformed.value}"},
        "hook": {
            "after": {
                "script": (
                    "async def hook(input, output, **kwargs):\n"
                    "    return {'transformed': {'value': output['n'] * 10}}\n"
                )
            }
        },
    })

    component = _FakeComponent(result={"n": 4})
    job = ComponentJob.__new__(ComponentJob)
    job.id = "cj"
    job.config = cfg
    job.global_configs = None
    job._create_component = lambda _id, _c: component  # type: ignore[assignment]

    result = await job.run(_FakeCtx(workflow_input={"q": "hi"}))

    # after hook wrapped {"n": 4} -> {"transformed": {"value": 40}}
    # output template rendered against it -> {"result": 40}
    assert result == {"result": 40}


@pytest.mark.anyio
async def test_for_each_after_hook_runs_before_output_render():
    # ForEachJob.run should apply the after hook to the aggregated batch
    # results BEFORE rendering the top-level `output` template.
    from pydantic import TypeAdapter
    from mindor.core.workflow.job.impl.for_each import ForEachJob
    from mindor.dsl.schema.job import JobConfig

    class _FakeComponent:
        def __init__(self):
            self.id = "fake"
            self.started = True

        async def start(self):
            self.started = True

        async def run(self, action, run_id, input, workflow, job_id):
            # Echo input times two.
            return input * 2

    cfg = TypeAdapter(JobConfig).validate_python({
        "type": "for-each",
        "input": [1, 2, 3],
        "do": {"component": "c", "action": "a"},
        "output": {"summary": "${output.total}", "count": "${output.count}"},
        "hook": {
            "after": {
                "script": (
                    "async def hook(input, output, **kwargs):\n"
                    "    return {'total': sum(output), 'count': len(output)}\n"
                )
            }
        },
    })

    component = _FakeComponent()
    job = ForEachJob.__new__(ForEachJob)
    job.id = "fej"
    job.config = cfg
    job.global_configs = None
    job._create_component = lambda _id, _c: component  # type: ignore[assignment]

    result = await job.run(_FakeCtx())

    # Component doubles each item -> [2, 4, 6]
    # after hook -> {"total": 12, "count": 3}
    # output template -> {"summary": 12, "count": 3}
    assert result == {"summary": 12, "count": 3}


@pytest.mark.anyio
async def test_delay_after_hook_runs_before_output_render():
    # DelayJob.run should apply the after hook to the raw delay output
    # (None) BEFORE rendering the `output` template. The hook replaces
    # None with a dict that the template then references.
    from pydantic import TypeAdapter
    from mindor.core.workflow.job.impl.delay import DelayJob
    from mindor.dsl.schema.job import JobConfig

    cfg = TypeAdapter(JobConfig).validate_python({
        "type": "delay",
        "mode": "time-interval",
        "duration": 0,
        "output": {"status": "${output.state}"},
        "hook": {
            "after": {
                "script": (
                    "async def hook(input, output, **kwargs):\n"
                    "    assert output is None\n"
                    "    return {'state': 'done'}\n"
                )
            }
        },
    })

    job = DelayJob.__new__(DelayJob)
    job.id = "dj"
    job.config = cfg
    job.global_configs = None

    result = await job.run(_FakeCtx())

    # after hook replaced None with {"state": "done"}
    # output template rendered against it -> {"status": "done"}
    assert result == {"status": "done"}
