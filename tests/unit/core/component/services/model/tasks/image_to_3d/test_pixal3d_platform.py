"""Host-dependent torch / natten pins of the Pixal3D drivers."""

from __future__ import annotations

import pytest

from mindor.core.component.services.model.tasks.image_to_3d.custom.pixal3d import base as pixal3d_base
from mindor.core.component.services.model.tasks.image_to_3d.custom.pixal3d.base import Pixal3DImageTo3DTaskBaseDriver


def _set_platform(monkeypatch: pytest.MonkeyPatch, system: str, machine: str) -> None:
    monkeypatch.setattr(pixal3d_base.sys, "platform", system)
    monkeypatch.setattr(pixal3d_base.platform, "machine", lambda: machine)


def test_x86_64_keeps_the_validated_stack(monkeypatch: pytest.MonkeyPatch):
    _set_platform(monkeypatch, "linux", "x86_64")

    assert Pixal3DImageTo3DTaskBaseDriver._get_torch_and_natten_specs(None) == ("torch==2.7.*", "natten==0.21.0")


def test_linux_aarch64_moves_to_a_stack_with_aarch64_wheels(monkeypatch: pytest.MonkeyPatch):
    _set_platform(monkeypatch, "linux", "aarch64")

    assert Pixal3DImageTo3DTaskBaseDriver._get_torch_and_natten_specs(None) == ("torch==2.13.*", "natten==0.21.7")
