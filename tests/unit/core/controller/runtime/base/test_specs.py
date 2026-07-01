"""Unit tests for ``ControllerRuntimeSpecs.generate_native_runtime_specs``.

This is the pure-data transform used to materialize a ``model-compose.yml`` for
a native runtime image (currently consumed by the Docker and Apple Container
launchers when building a context). Behavior under test:

* injects ``runtime: "native"`` into controller and every component (overriding
  whatever was on the source config)
* if ``webui.server_dir`` / ``webui.static_dir`` are set on the controller,
  rewrites them to the canonical in-context paths
* passes listeners / gateways / workflows / tracers / loggers through as
  ``model_dump()`` lists
* coerces enums to strings so the result is YAML-safe
"""

from __future__ import annotations

from pydantic import TypeAdapter

from mindor.core.controller.runtime.base.specs import ControllerRuntimeSpecs
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.workflow import WorkflowConfig


_component_adapter = TypeAdapter(ComponentConfig)


def _make_specs(controller_payload=None, component_payloads=None, workflow_payloads=None):
    controller = ControllerConfig.model_validate(controller_payload or {})
    components = [
        _component_adapter.validate_python(p) for p in (component_payloads or [])
    ]
    workflows = [
        WorkflowConfig.model_validate(p) for p in (workflow_payloads or [])
    ]
    return ControllerRuntimeSpecs(
        controller=controller,
        components=components,
        listeners=[],
        gateways=[],
        workflows=workflows,
        tracers=[],
        loggers=[],
    )


class TestControllerRuntimeOverride:
    """``runtime`` is forced to the literal string ``"native"`` regardless of
    the value on the source ``ControllerConfig``."""

    def test_default_controller_gets_native_runtime_string(self):
        specs = _make_specs()

        out = specs.generate_native_runtime_specs()

        assert out["controller"]["runtime"] == "native"

    def test_overrides_non_native_controller_runtime(self):
        specs = _make_specs(controller_payload={"runtime": {"type": "docker"}})

        out = specs.generate_native_runtime_specs()

        assert out["controller"]["runtime"] == "native"


class TestComponentRuntimeOverride:
    def test_components_get_native_runtime_string(self):
        specs = _make_specs(
            component_payloads=[
                {"id": "a", "type": "shell", "command": "echo a"},
                {"id": "b", "type": "shell", "command": "echo b"},
            ],
        )

        out = specs.generate_native_runtime_specs()

        assert len(out["components"]) == 2
        assert all(c["runtime"] == "native" for c in out["components"])

    def test_empty_components_yields_empty_list(self):
        specs = _make_specs()

        out = specs.generate_native_runtime_specs()

        assert out["components"] == []


class TestWebUIDirRewrite:
    """If ``webui.server_dir`` / ``webui.static_dir`` are present on the
    controller, the generated specs point them at the canonical in-context
    layout (``webui/server`` and ``webui/static``)."""

    def test_dynamic_webui_dirs_are_rewritten_to_in_context_paths(self):
        specs = _make_specs(controller_payload={
            "webui": {
                "driver": "dynamic",
                "command": "python app.py",
                "server_dir": "custom/server",
                "static_dir": "custom/static",
            },
        })

        out = specs.generate_native_runtime_specs()

        assert out["controller"]["webui"]["server_dir"] == "webui/server"
        assert out["controller"]["webui"]["static_dir"] == "webui/static"

    def test_missing_webui_is_left_alone(self):
        specs = _make_specs()

        out = specs.generate_native_runtime_specs()

        assert out["controller"].get("webui") is None


class TestEnumCoercion:
    """The final result must be YAML-safe — every enum value should already be
    a string by the time the caller dumps it."""

    def test_no_enum_objects_in_output(self):
        from enum import Enum

        specs = _make_specs(
            controller_payload={
                "webui": {
                    "driver": "dynamic",
                    "command": "python app.py",
                },
            },
            component_payloads=[
                {"id": "a", "type": "shell", "command": "echo a"},
            ],
        )

        out = specs.generate_native_runtime_specs()

        def _walk(value):
            if isinstance(value, dict):
                for v in value.values():
                    _walk(v)
            elif isinstance(value, list):
                for v in value:
                    _walk(v)
            else:
                assert not isinstance(value, Enum), f"unexpected Enum left in specs: {value!r}"

        _walk(out)


class TestPassThroughLists:
    """Listeners / gateways / workflows / tracers / loggers are emitted as
    ``model_dump()`` lists with no further transformation."""

    def test_workflows_dumped_to_dict_list(self):
        specs = _make_specs(workflow_payloads=[{"id": "wf1", "jobs": []}])

        out = specs.generate_native_runtime_specs()

        assert isinstance(out["workflows"], list)
        assert out["workflows"][0]["id"] == "wf1"

    def test_empty_pass_through_keys_are_present(self):
        specs = _make_specs()

        out = specs.generate_native_runtime_specs()

        for key in ("listeners", "gateways", "workflows", "tracers", "loggers"):
            assert out[key] == [], f"expected empty list for {key}"
