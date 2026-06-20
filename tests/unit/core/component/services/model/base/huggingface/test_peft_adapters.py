"""Unit tests for PEFT adapter handling in ``HuggingfaceModelTaskService``.

Covers two layers:

1. Helper methods (``_build_peft_adapter_lists``, ``_get_model_path``,
   ``_get_model_params``) — pure logic, no external deps.
2. Integration of ``_load_peft_adapters`` against a fake ``peft.PeftModel`` that
   records ``from_pretrained`` / ``load_adapter`` / ``add_weighted_adapter`` /
   ``set_adapter`` calls. Exercises the single-adapter, multi-adapter, and
   non-unit-weight branches.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Dict, List, Tuple

import pytest
from pydantic import TypeAdapter

from mindor.core.component.services.model.base.huggingface.base import (
    HuggingfaceModelTaskService,
)
from mindor.dsl.schema.component import (
    ModelComponentConfig,
    PeftAdapterConfig,
)

_ModelConfigAdapter = TypeAdapter(ModelComponentConfig)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _ConcreteService(HuggingfaceModelTaskService):
    """Concrete subclass: ``HuggingfaceModelTaskService`` and its parents declare
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


class _FakePeftModel:
    """Records adapter calls so tests can assert on the merge/set behavior."""

    instances: List["_FakePeftModel"] = []

    def __init__(self, base_model: Any, model_path: str, adapter_name: str, params: Dict[str, Any]):
        self.base_model = base_model
        self.loaded: List[Tuple[str, str, Dict[str, Any]]] = [(model_path, adapter_name, params)]
        self.weighted_adapters: List[Tuple[List[str], List[float], str]] = []
        self.active_adapter: str | None = None
        _FakePeftModel.instances.append(self)

    @classmethod
    def from_pretrained(cls, base_model: Any, model_path: str, adapter_name: str, **params: Any) -> "_FakePeftModel":
        return cls(base_model, model_path, adapter_name, params)

    def load_adapter(self, model_path: str, adapter_name: str, **params: Any) -> None:
        self.loaded.append((model_path, adapter_name, params))

    def add_weighted_adapter(self, names: List[str], weights: List[float], adapter_name: str) -> None:
        self.weighted_adapters.append((list(names), list(weights), adapter_name))

    def set_adapter(self, name: str) -> None:
        self.active_adapter = name


@pytest.fixture
def fake_peft_module(monkeypatch):
    """Inject a fake ``peft`` module exposing ``PeftModel`` for the duration of a test."""
    _FakePeftModel.instances.clear()
    module = types.ModuleType("peft")
    module.PeftModel = _FakePeftModel
    monkeypatch.setitem(sys.modules, "peft", module)
    return module


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
            {"text": "${input.text}"},
        ],
    })


def _make_adapter_config(**overrides: Any) -> PeftAdapterConfig:
    raw: Dict[str, Any] = {"type": "lora", "model": "org/lora-adapter"}
    raw.update(overrides)
    return PeftAdapterConfig.model_validate(raw)


def _make_service(config=None) -> _ConcreteService:
    return _ConcreteService("m1", config or _make_model_config(), daemon=False)


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------


class TestBuildPeftAdapterLists:
    def test_uses_explicit_names_and_weights(self):
        service = _make_service()
        adapters = [
            _make_adapter_config(name="style", weight=0.7),
            _make_adapter_config(name="domain", weight=0.3),
        ]
        names, weights = service._build_peft_adapter_lists(adapters)
        assert names == ["style", "domain"]
        assert weights == [0.7, 0.3]

    def test_synthesizes_default_name_per_index(self):
        service = _make_service()
        adapters = [
            _make_adapter_config(),
            _make_adapter_config(name="explicit"),
            _make_adapter_config(),
        ]
        names, weights = service._build_peft_adapter_lists(adapters)
        assert names == ["peft_adapter_0", "explicit", "peft_adapter_2"]
        assert weights == [1.0, 1.0, 1.0]


class TestGetModelPath:
    def test_huggingface_returns_repository(self):
        service = _make_service()
        adapter = _make_adapter_config(model="org/lora-adapter")
        assert service._get_model_path(adapter) == "org/lora-adapter"

    def test_local_returns_path(self):
        service = _make_service()
        adapter = _make_adapter_config(model="./local-adapter")
        assert service._get_model_path(adapter) == "./local-adapter"


class TestGetModelParamsForAdapter:
    """Adapter param building skips ``device_map`` (the base model owns device
    placement) and folds optional HF fields only when explicitly set.
    """

    def test_minimal_adapter_emits_no_params(self):
        service = _make_service()
        adapter = _make_adapter_config()
        assert service._get_model_params(adapter) == {}

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
        params = service._get_model_params(adapter)
        assert params == {
            "revision": "v2",
            "cache_dir": "/cache",
            "local_files_only": True,
            "token": "hf_xyz",
        }

    def test_low_cpu_mem_usage_included_when_truthy(self):
        service = _make_service()
        adapter = _make_adapter_config(low_cpu_mem_usage=True)
        assert service._get_model_params(adapter) == {"low_cpu_mem_usage": True}

    def test_adapter_does_not_set_device_map(self):
        """Adapter loading must not inject ``device_map`` — the base model has
        already been placed on a device; passing ``device_map`` again to
        ``PeftModel.from_pretrained`` causes a re-dispatch.
        """
        service = _make_service()
        adapter = _make_adapter_config()
        assert "device_map" not in service._get_model_params(adapter)


# ---------------------------------------------------------------------------
# _load_peft_adapters integration
# ---------------------------------------------------------------------------


class TestLoadPeftAdaptersSingle:
    def test_single_unit_weight_skips_weighted_merge(self, fake_peft_module):
        service = _make_service()
        adapter = _make_adapter_config(name="solo", model="org/lora-solo")
        sentinel_base = object()

        peft_model = service._load_peft_adapters(sentinel_base, [adapter])

        assert isinstance(peft_model, _FakePeftModel)
        assert peft_model.base_model is sentinel_base
        assert peft_model.loaded == [("org/lora-solo", "solo", {})]
        assert peft_model.weighted_adapters == []
        assert peft_model.active_adapter == "solo"

    def test_single_non_unit_weight_triggers_weighted_merge(self, fake_peft_module):
        service = _make_service()
        adapter = _make_adapter_config(name="solo", weight=0.5)
        peft_model = service._load_peft_adapters(object(), [adapter])

        assert peft_model.weighted_adapters == [(["solo"], [0.5], "blended_adapter")]
        assert peft_model.active_adapter == "blended_adapter"


class TestLoadPeftAdaptersMultiple:
    def test_multiple_adapters_are_merged_under_blended_name(self, fake_peft_module):
        service = _make_service()
        adapters = [
            _make_adapter_config(name="style", model="org/style", weight=0.6),
            _make_adapter_config(name="domain", model="org/domain", weight=0.4),
            _make_adapter_config(name="tone", model="org/tone", weight=1.0),
        ]
        peft_model = service._load_peft_adapters(object(), adapters)

        # First adapter loads via from_pretrained, remaining via load_adapter.
        assert peft_model.loaded == [
            ("org/style", "style", {}),
            ("org/domain", "domain", {}),
            ("org/tone", "tone", {}),
        ]
        assert peft_model.weighted_adapters == [
            (["style", "domain", "tone"], [0.6, 0.4, 1.0], "blended_adapter")
        ]
        assert peft_model.active_adapter == "blended_adapter"

    def test_default_names_are_synthesized_for_multi_adapter(self, fake_peft_module):
        service = _make_service()
        adapters = [_make_adapter_config(model="org/a"), _make_adapter_config(model="org/b")]
        peft_model = service._load_peft_adapters(object(), adapters)

        names = [entry[1] for entry in peft_model.loaded]
        assert names == ["peft_adapter_0", "peft_adapter_1"]
        assert peft_model.weighted_adapters[0][0] == ["peft_adapter_0", "peft_adapter_1"]


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
        peft_model = service._load_peft_adapters(object(), adapters)

        assert peft_model.loaded[0] == ("org/style", "style", {"revision": "main"})
        assert peft_model.loaded[1] == ("org/domain", "domain", {"cache_dir": "/cache"})
