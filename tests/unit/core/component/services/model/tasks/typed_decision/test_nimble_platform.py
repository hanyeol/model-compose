"""Platform gating of the Nimble typed-decision driver.

The CUDA candidate scorer is plain PyTorch, so any Linux host with a CUDA GPU
(x86_64 or aarch64) gets the CUDA dependencies and scorer; Apple Silicon gets
MLX; everything else is rejected with a clear error.
"""

from __future__ import annotations

import sys
import types

import pytest

from mindor.core.component.services.model.tasks.typed_decision.custom import nimble as nimble_driver
from mindor.core.component.services.model.tasks.typed_decision.custom.nimble import NimbleTypedDecisionTaskDriver
from mindor.dsl.schema.component import NimbleTypedDecisionModelComponentConfig


def _make_driver() -> NimbleTypedDecisionTaskDriver:
    config = NimbleTypedDecisionModelComponentConfig(
        type="model",
        task="typed-decision",
        family="nimble",
        model="bespokelabs/Bespoke-Nimble-9B",
    )
    return NimbleTypedDecisionTaskDriver("nimble", config, daemon=False)


def _set_platform(monkeypatch: pytest.MonkeyPatch, system: str, machine: str) -> None:
    monkeypatch.setattr(nimble_driver.sys, "platform", system)
    monkeypatch.setattr(nimble_driver.platform, "machine", lambda: machine)
    # torch_requirements probes nvidia-smi; keep the specifier untouched.
    monkeypatch.setattr(nimble_driver, "torch_requirements", lambda *specs: list(specs))


@pytest.mark.parametrize("machine", [ "x86_64", "aarch64" ])
def test_linux_cuda_requirements(monkeypatch: pytest.MonkeyPatch, machine: str):
    _set_platform(monkeypatch, "linux", machine)

    requirements = _make_driver()._get_setup_requirements()

    assert "torch>=2.8,<3" in requirements
    assert "accelerate==1.15.0" in requirements
    assert not any(r.startswith("mlx") for r in requirements)


@pytest.mark.parametrize("machine", [ "x86_64", "aarch64" ])
def test_linux_loads_cuda_scorer(monkeypatch: pytest.MonkeyPatch, machine: str):
    _set_platform(monkeypatch, "linux", machine)

    class FakeCudaCandidateScorer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    cuda_scorer = types.ModuleType("nimble.scoring.cuda_scorer")
    cuda_scorer.CudaCandidateScorer = FakeCudaCandidateScorer
    monkeypatch.setitem(sys.modules, "nimble", types.ModuleType("nimble"))
    monkeypatch.setitem(sys.modules, "nimble.scoring", types.ModuleType("nimble.scoring"))
    monkeypatch.setitem(sys.modules, "nimble.scoring.cuda_scorer", cuda_scorer)

    scorer = _make_driver()._load_scorer("/tmp/merged")

    assert isinstance(scorer, FakeCudaCandidateScorer)
    assert scorer.kwargs["model_path"] == "/tmp/merged"


def test_unsupported_platform_raises(monkeypatch: pytest.MonkeyPatch):
    _set_platform(monkeypatch, "darwin", "x86_64")

    with pytest.raises(RuntimeError, match="Nimble supports only"):
        _make_driver()._load_scorer("/tmp/merged")
