"""Merged-checkpoint cache of the Nimble typed-decision driver.

The driver merges the LoRA adapter onto the base once and reuses the result. The
cache entry is named after the adapter weights, its release contract and the base,
carries the contract (schema_config.json) that Nimble's scorers read, and is
reused only once the merge finished (READY.json written last, then an atomic rename).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import types
from pathlib import Path

import pytest

from mindor.core.component.services.model.tasks.typed_decision.custom.nimble import NimbleTypedDecisionTaskDriver
from mindor.dsl.schema.component import NimbleTypedDecisionModelComponentConfig


class FakeMerge:
    """Stands in for transformers/peft/torch: 'merging' copies the adapter weights into the output."""

    def __init__(self):
        self.merges = 0
        self.fail_next_save = False

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self

        class Merged:
            def __init__(self, adapter_path: str):
                self.adapter_path = adapter_path

            def save_pretrained(self, path: str) -> None:
                os.makedirs(path, exist_ok=True)
                Path(path, "config.json").write_text("{}")
                if fake.fail_next_save:
                    fake.fail_next_save = False
                    raise OSError("No space left on device")
                weights = Path(self.adapter_path, "adapter_model.safetensors").read_bytes()
                Path(path, "model.safetensors").write_bytes(weights)

        class PeftModel:
            @staticmethod
            def from_pretrained(base_model, adapter_path: str):
                fake.merges += 1
                return types.SimpleNamespace(merge_and_unload=lambda safe_merge: Merged(adapter_path))

        class Tokenizer:
            def save_pretrained(self, path: str) -> None:
                Path(path, "tokenizer.json").write_text("{}")

        transformers = types.ModuleType("transformers")
        transformers.AutoTokenizer = types.SimpleNamespace(from_pretrained=lambda path: Tokenizer())
        transformers.Qwen3_5ForConditionalGeneration = types.SimpleNamespace(from_pretrained=lambda path, **kwargs: object())
        peft = types.ModuleType("peft")
        peft.PeftModel = PeftModel
        torch = types.ModuleType("torch")
        torch.bfloat16 = "bfloat16"
        monkeypatch.setitem(sys.modules, "transformers", transformers)
        monkeypatch.setitem(sys.modules, "peft", peft)
        monkeypatch.setitem(sys.modules, "torch", torch)


@pytest.fixture
def fake_merge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeMerge:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    fake = FakeMerge()
    fake.install(monkeypatch)
    return fake


def _make_driver() -> NimbleTypedDecisionTaskDriver:
    config = NimbleTypedDecisionModelComponentConfig(
        type="model",
        task="typed-decision",
        family="nimble",
        model="bespokelabs/Bespoke-Nimble-9B",
    )
    return NimbleTypedDecisionTaskDriver("nimble", config, daemon=False)


def _adapter(path: Path, weights: bytes, contract: str | None = None) -> str:
    path.mkdir(parents=True, exist_ok=True)
    (path / "adapter_model.safetensors").write_bytes(weights)
    if contract is not None:
        (path / "schema_config.json").write_text(contract)
    return str(path)


def _merge(adapter_path: str, base_path: Path) -> Path:
    base_path.mkdir(parents=True, exist_ok=True)
    return Path(asyncio.run(_make_driver()._merge_adapter(adapter_path, str(base_path))))


def test_merge_is_keyed_by_adapter_weights(fake_merge: FakeMerge, tmp_path: Path):
    base = tmp_path / "base"
    first = _merge(_adapter(tmp_path / "run1" / "adapter", b"first"), base)
    second = _merge(_adapter(tmp_path / "run2" / "adapter", b"second"), base)

    assert first != second
    assert (first / "model.safetensors").read_bytes() == b"first"
    assert (second / "model.safetensors").read_bytes() == b"second"
    assert json.loads((first / "READY.json").read_text())["adapter_sha256"] == hashlib.sha256(b"first").hexdigest()

    # The same weights in another folder reuse the finished merge.
    assert _merge(_adapter(tmp_path / "copy", b"first"), base) == first
    assert fake_merge.merges == 2


def test_adapter_trained_again_in_place_is_merged_again(fake_merge: FakeMerge, tmp_path: Path):
    adapter = tmp_path / "adapter"
    base = tmp_path / "base"
    before = _merge(_adapter(adapter, b"epoch-1"), base)
    after = _merge(_adapter(adapter, b"epoch-2"), base)

    assert before != after
    assert (after / "model.safetensors").read_bytes() == b"epoch-2"


def test_each_base_gets_its_own_merge(fake_merge: FakeMerge, tmp_path: Path):
    adapter = _adapter(tmp_path / "adapter", b"weights")

    assert _merge(adapter, tmp_path / "base-a") != _merge(adapter, tmp_path / "base-b")


def test_failed_merge_is_not_reused(fake_merge: FakeMerge, tmp_path: Path):
    adapter = _adapter(tmp_path / "adapter", b"weights")
    fake_merge.fail_next_save = True

    with pytest.raises(OSError, match="No space left"):
        _merge(adapter, tmp_path / "base")

    merged_root = tmp_path / "cache" / "models" / "nimble-merged"
    assert not [p for p in merged_root.iterdir() if (p / "READY.json").exists()]

    merged = _merge(adapter, tmp_path / "base")

    assert (merged / "model.safetensors").read_bytes() == b"weights"
    assert fake_merge.merges == 2
    assert sorted(p.name for p in merged_root.iterdir()) == [ merged.name ]


def test_merge_carries_the_release_contract(fake_merge: FakeMerge, tmp_path: Path):
    contract = json.dumps({ "task": "schema_candidate_classification_v2", "max_choices": 255 })
    merged = _merge(_adapter(tmp_path / "adapter", b"weights", contract), tmp_path / "base")

    assert (merged / "schema_config.json").read_text() == contract


def test_contract_change_is_merged_again(fake_merge: FakeMerge, tmp_path: Path):
    base = tmp_path / "base"
    old = _merge(_adapter(tmp_path / "old", b"weights", '{"max_choices": 26}'), base)
    new = _merge(_adapter(tmp_path / "new", b"weights", '{"max_choices": 255}'), base)

    assert old != new
    assert json.loads((new / "schema_config.json").read_text()) == { "max_choices": 255 }
