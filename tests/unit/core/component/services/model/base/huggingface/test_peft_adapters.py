"""Unit tests for PEFT adapter handling in ``HuggingfaceModelTaskDriver``.

Covers two layers:

1. Helper methods (``_resolve_model``, ``_get_model_params``,
   ``_get_model_options``) — pure logic, no external deps.
2. Integration of ``_load_peft_adapters`` / ``_apply_peft_adapters`` against a
   fake ``peft.PeftModel`` and fake ``BaseTunerLayer`` modules. Exercises
   adapter loading (all adapters start disabled) and forward-time blending
   via per-module ``set_adapter`` + ``set_scale`` calls.
"""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any, Dict, List, Tuple

import pytest
from pydantic import TypeAdapter

from mindor.core.component.services.model.base.huggingface.base import (
    HuggingfaceModelTaskDriver,
)
from mindor.dsl.schema.action import AppliedPeftAdapterConfig
from mindor.dsl.schema.component import (
    ModelComponentConfig,
    PeftAdapterConfig,
)

_ModelConfigAdapter = TypeAdapter(ModelComponentConfig)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _ConcreteService(HuggingfaceModelTaskDriver):
    """Concrete subclass: ``HuggingfaceModelTaskDriver`` and its parents declare
    abstract ``_load_model`` / ``_unload_model`` / ``_run`` / ``_get_model_class``
    — implement no-op stubs so the class is instantiable for unit tests.
    """

    async def _load_model(self) -> None:  # pragma: no cover - never called
        pass

    async def _unload_model(self) -> None:  # pragma: no cover - never called
        pass

    async def _run(self, action, context, loop):  # pragma: no cover - never called
        pass

    def _get_model_class(self):  # pragma: no cover - not exercised here
        raise NotImplementedError


class _FakeTunerLayer:
    """Stand-in for ``peft.tuners.tuners_utils.BaseTunerLayer``. Records
    ``set_adapter`` / ``set_scale`` calls per module.
    """

    def __init__(self) -> None:
        self.active_adapters: List[List[str]] = []
        self.scales: List[Tuple[str, float]] = []

    def set_adapter(self, names: List[str]) -> None:
        self.active_adapters.append(list(names))

    def set_scale(self, name: str, weight: float) -> None:
        self.scales.append((name, weight))


class _FakePeftModel:
    """Records adapter calls so tests can assert on the load/activation behavior."""

    instances: List["_FakePeftModel"] = []

    def __init__(self, base_model: Any, model_path: str, adapter_name: str, params: Dict[str, Any]):
        self.base_model = base_model
        self.loaded: List[Tuple[str, str, Dict[str, Any]]] = [(model_path, adapter_name, params)]
        self.adapter_layers_enabled: bool = True
        self.tuner_modules: List[_FakeTunerLayer] = [_FakeTunerLayer()]
        _FakePeftModel.instances.append(self)

    @classmethod
    def from_pretrained(cls, base_model: Any, model_path: str, adapter_name: str, **params: Any) -> "_FakePeftModel":
        return cls(base_model, model_path, adapter_name, params)

    def load_adapter(self, model_path: str, adapter_name: str, **params: Any) -> None:
        self.loaded.append((model_path, adapter_name, params))

    def disable_adapter_layers(self) -> None:
        self.adapter_layers_enabled = False

    def enable_adapter_layers(self) -> None:
        self.adapter_layers_enabled = True

    def modules(self):
        # Include a non-tuner sibling to verify the isinstance filter skips it.
        return [object(), *self.tuner_modules]


@pytest.fixture
def fake_peft_module(monkeypatch):
    """Inject fake ``peft`` + ``peft.tuners.tuners_utils`` modules for the test."""
    _FakePeftModel.instances.clear()

    peft_module = types.ModuleType("peft")
    peft_module.PeftModel = _FakePeftModel

    tuners_utils_module = types.ModuleType("peft.tuners.tuners_utils")
    tuners_utils_module.BaseTunerLayer = _FakeTunerLayer

    # Parent packages must exist so ``from peft.tuners.tuners_utils import ...`` resolves.
    tuners_pkg = types.ModuleType("peft.tuners")

    monkeypatch.setitem(sys.modules, "peft", peft_module)
    monkeypatch.setitem(sys.modules, "peft.tuners", tuners_pkg)
    monkeypatch.setitem(sys.modules, "peft.tuners.tuners_utils", tuners_utils_module)
    return peft_module


# ---------------------------------------------------------------------------
# Config factories
# ---------------------------------------------------------------------------


def _make_model_config(model: str = "org/base-model"):
    return _ModelConfigAdapter.validate_python({
        "id": "m1",
        "type": "model",
        "task": "text-generation",
        "driver": "huggingface",
        "model": model,
        "actions": [
            {"prompt": "${input.text}"},
        ],
    })


def _make_adapter_config(name: str = "adapter", **overrides: Any) -> PeftAdapterConfig:
    raw: Dict[str, Any] = {"type": "lora", "name": name, "model": "org/lora-adapter"}
    raw.update(overrides)
    return PeftAdapterConfig.model_validate(raw)


def _make_service(config=None) -> _ConcreteService:
    return _ConcreteService("m1", config or _make_model_config(), daemon=False)


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------


class TestResolveModel:
    def test_huggingface_returns_repository(self):
        service = _make_service()
        adapter = _make_adapter_config(model="org/lora-adapter")
        assert asyncio.run(service._provision_model(adapter.model)) == "org/lora-adapter"

    def test_local_returns_path(self, tmp_path):
        # Local paths that exist on disk are returned verbatim.
        local = tmp_path / "adapter.bin"
        local.write_bytes(b"")
        service = _make_service()
        adapter = _make_adapter_config(model=str(local))
        assert asyncio.run(service._provision_model(adapter.model)) == str(local)


class TestGetModelParamsForAdapter:
    """Adapter param building skips ``device_map`` (the base model owns device
    placement) and folds optional HF fields only when explicitly set.
    """

    def test_minimal_adapter_emits_no_params(self):
        service = _make_service()
        adapter = _make_adapter_config()
        assert service._get_model_params(adapter.model) == {}

    def test_passes_optional_huggingface_fields(self):
        service = _make_service()
        adapter = _make_adapter_config(model={
            "provider": "huggingface",
            "repository": "org/lora",
            "revision": "v2",
            "cache_dir": "/cache",
            "local_files_only": True,
            "token": "hf_xyz",
        })
        params = service._get_model_params(adapter.model)
        assert params == {
            "revision": "v2",
            "cache_dir": "/cache",
            "local_files_only": True,
            "token": "hf_xyz",
        }

    def test_low_cpu_mem_usage_included_when_truthy(self):
        service = _make_service()
        adapter = _make_adapter_config(low_cpu_mem_usage=True)
        # low_cpu_mem_usage lives in options (per-config), not model params.
        assert service._get_model_options(adapter) == {"low_cpu_mem_usage": True}

    def test_adapter_does_not_set_device_map(self):
        """Adapter loading must not inject ``device_map`` — the base model has
        already been placed on a device; passing ``device_map`` again to
        ``PeftModel.from_pretrained`` causes a re-dispatch.
        """
        service = _make_service()
        adapter = _make_adapter_config()
        assert "device_map" not in service._get_model_params(adapter.model)
        assert "device_map" not in service._get_model_options(adapter)


# ---------------------------------------------------------------------------
# _load_peft_adapters integration
# ---------------------------------------------------------------------------


class TestLoadPeftAdaptersSingle:
    def test_single_adapter_is_loaded_and_left_disabled(self, fake_peft_module):
        service = _make_service()
        adapter = _make_adapter_config(name="solo", model="org/lora-solo")
        sentinel_base = object()

        peft_model = asyncio.run(service._load_peft_adapters(sentinel_base, [adapter]))

        assert isinstance(peft_model, _FakePeftModel)
        assert peft_model.base_model is sentinel_base
        assert peft_model.loaded == [("org/lora-solo", "solo", {})]
        # Adapters are loaded but left off; actions turn them on per request.
        assert peft_model.adapter_layers_enabled is False


class TestLoadPeftAdaptersMultiple:
    def test_multiple_adapters_are_loaded_in_order(self, fake_peft_module):
        service = _make_service()
        adapters = [
            _make_adapter_config(name="style", model="org/style", weight=0.6),
            _make_adapter_config(name="domain", model="org/domain", weight=0.4),
            _make_adapter_config(name="tone", model="org/tone", weight=1.0),
        ]
        peft_model = asyncio.run(service._load_peft_adapters(object(), adapters))

        # First adapter loads via from_pretrained, remaining via load_adapter.
        assert peft_model.loaded == [
            ("org/style", "style", {}),
            ("org/domain", "domain", {}),
            ("org/tone", "tone", {}),
        ]
        assert peft_model.adapter_layers_enabled is False


class TestLoadPeftAdaptersForwardsParams:
    def test_per_adapter_params_are_forwarded(self, fake_peft_module):
        service = _make_service()
        adapters = [
            _make_adapter_config(
                name="style",
                model={
                    "provider": "huggingface",
                    "repository": "org/style",
                    "revision": "main",
                },
            ),
            _make_adapter_config(
                name="domain",
                model={
                    "provider": "huggingface",
                    "repository": "org/domain",
                    "cache_dir": "/cache",
                },
            ),
        ]
        peft_model = asyncio.run(service._load_peft_adapters(object(), adapters))

        assert peft_model.loaded[0] == ("org/style", "style", {"revision": "main"})
        assert peft_model.loaded[1] == ("org/domain", "domain", {"cache_dir": "/cache"})


# ---------------------------------------------------------------------------
# _apply_peft_adapters integration
# ---------------------------------------------------------------------------


class TestApplyPeftAdapters:
    """``_apply_peft_adapters`` activates named adapters on every tuner layer
    and sets per-adapter scales — no one-shot merge."""

    def test_single_adapter_sets_name_and_scale(self, fake_peft_module):
        service = _make_service()
        # Install a fake peft_model as if _load_peft_adapters had run.
        peft_model = _FakePeftModel(object(), "org/solo", "solo", {})
        peft_model.disable_adapter_layers()
        service.model = peft_model

        service._apply_peft_adapters([AppliedPeftAdapterConfig(name="solo", weight=0.5)])

        assert peft_model.adapter_layers_enabled is True
        tuner = peft_model.tuner_modules[0]
        assert tuner.active_adapters == [["solo"]]
        assert tuner.scales == [("solo", 0.5)]

    def test_multiple_adapters_set_all_names_and_each_scale(self, fake_peft_module):
        service = _make_service()
        peft_model = _FakePeftModel(object(), "org/style", "style", {})
        peft_model.disable_adapter_layers()
        service.model = peft_model

        service._apply_peft_adapters([
            AppliedPeftAdapterConfig(name="style", weight=0.6),
            AppliedPeftAdapterConfig(name="domain", weight=0.4),
            AppliedPeftAdapterConfig(name="tone", weight=1.0),
        ])

        assert peft_model.adapter_layers_enabled is True
        tuner = peft_model.tuner_modules[0]
        assert tuner.active_adapters == [["style", "domain", "tone"]]
        assert tuner.scales == [("style", 0.6), ("domain", 0.4), ("tone", 1.0)]

    def test_skips_non_tuner_modules(self, fake_peft_module):
        service = _make_service()
        peft_model = _FakePeftModel(object(), "org/solo", "solo", {})
        service.model = peft_model

        service._apply_peft_adapters([AppliedPeftAdapterConfig(name="solo", weight=1.0)])

        # Only the single real tuner layer received the calls; the plain
        # ``object()`` sibling in ``modules()`` was skipped.
        assert len(peft_model.tuner_modules[0].active_adapters) == 1


class TestDisablePeftAdapters:
    def test_disable_turns_off_adapter_layers(self, fake_peft_module):
        service = _make_service()
        peft_model = _FakePeftModel(object(), "org/solo", "solo", {})
        service.model = peft_model

        service._disable_peft_adapters()
        assert peft_model.adapter_layers_enabled is False
