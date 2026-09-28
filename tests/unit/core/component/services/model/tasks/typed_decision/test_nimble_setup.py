"""Installation of Bespoke's nimble package by the Nimble typed-decision driver.

The package is copied from GitHub next to `mindor` at a pinned revision. A copy
from before the release contract (nimble/scoring/release_contract.py) is replaced,
because install_package_from_github never replaces an installed package.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List

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


def _write_package(root: Path, *modules: str) -> None:
    scoring = root / "nimble" / "scoring"
    scoring.mkdir(parents=True)
    (root / "nimble" / "__init__.py").write_text("")
    for module in modules:
        (scoring / module).write_text("")


@pytest.fixture
def installs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    async def fake_install(module_name: str, repo_url: str, **kwargs: Any) -> None:
        calls.append({ "module_name": module_name, "repo_url": repo_url, **kwargs })
        _write_package(tmp_path, "parallel_schema.py", "release_contract.py")

    monkeypatch.setattr(nimble_driver, "get_mindor_install_root", lambda: tmp_path)
    monkeypatch.setattr(nimble_driver, "install_package_from_github", fake_install)
    monkeypatch.syspath_prepend(str(tmp_path))
    return calls


def test_installs_the_pinned_release(installs: List[Dict[str, Any]], tmp_path: Path):
    asyncio.run(_make_driver()._setup())

    assert [ call["revision"] for call in installs ] == [ "62076b4f2d36" ]
    assert (tmp_path / "nimble" / "scoring" / "release_contract.py").is_file()


def test_replaces_a_copy_from_before_the_release_contract(installs: List[Dict[str, Any]], tmp_path: Path):
    _write_package(tmp_path, "parallel_schema.py")

    asyncio.run(_make_driver()._setup())

    assert len(installs) == 1
    assert (tmp_path / "nimble" / "scoring" / "release_contract.py").is_file()


def test_keeps_a_copy_with_the_release_contract(installs: List[Dict[str, Any]], tmp_path: Path):
    _write_package(tmp_path, "parallel_schema.py", "release_contract.py")

    asyncio.run(_make_driver()._setup())

    assert installs == []
