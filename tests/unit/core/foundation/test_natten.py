"""Pre-built wheel selection for natten on Linux x86_64 and aarch64.

The torch build each case targets is stubbed through `resolve_torch_build`, so
these tests pin down the wheel table and URL shapes without touching
nvidia-smi or the installed torch.
"""

from __future__ import annotations

import types
from typing import List, Optional, Tuple

import pytest

from mindor.core.foundation.package import natten as natten_module
from mindor.core.foundation.package.natten import natten_requirements

BASE = "https://github.com/SHI-Labs/NATTEN/releases/download"


def _url(version: str, local: str, py_minor: int, arch: str) -> str:
    return f"{BASE}/v{version}/natten-{version}%2B{local}-cp3{py_minor}-cp3{py_minor}-linux_{arch}.whl"


class _LogRecorder:
    def __init__(self) -> None:
        self.warnings: List[str] = []

    def info(self, message: str, *args, **kwargs) -> None:
        pass

    def warning(self, message: str, *args, **kwargs) -> None:
        self.warnings.append(message)


def _set_host(
    monkeypatch: pytest.MonkeyPatch,
    machine: str = "aarch64",
    py_minor: int = 12,
    torch_build: Tuple[Optional[str], Optional[str]] = ("2.9.1", "cu130"),
    cuda: bool = True,
    system: str = "linux",
) -> _LogRecorder:
    monkeypatch.setattr(natten_module, "sys", types.SimpleNamespace(platform=system, version_info=types.SimpleNamespace(minor=py_minor)))
    monkeypatch.setattr(natten_module, "platform", types.SimpleNamespace(machine=lambda: machine))
    monkeypatch.setattr(natten_module, "is_cuda_installed", lambda: cuda)
    monkeypatch.setattr(natten_module, "resolve_torch_build", lambda *specs: torch_build)
    recorder = _LogRecorder()
    monkeypatch.setattr(natten_module, "logging", recorder)
    return recorder


class TestX86_64:
    @pytest.mark.parametrize("channel", [ "cu128", "cu126" ])
    def test_pixal3d_pin_resolves_to_the_same_wheel_as_before(self, monkeypatch: pytest.MonkeyPatch, channel: str):
        _set_host(monkeypatch, machine="x86_64", torch_build=("2.7.1", channel))

        assert natten_requirements("torch==2.7.*", "natten==0.21.0") == [
            f"natten==0.21.0+torch270{channel}@{_url('0.21.0', f'torch270{channel}', 12, 'x86_64')}",
        ]

    def test_python_313_has_no_0_21_0_wheel(self, monkeypatch: pytest.MonkeyPatch):
        # The old table listed 3.13 for 0.21.0 and produced a URL that 404s.
        recorder = _set_host(monkeypatch, machine="x86_64", py_minor=13, torch_build=("2.7.1", "cu128"))

        assert natten_requirements("torch==2.7.*", "natten==0.21.0") == [ "natten==0.21.0" ]
        assert len(recorder.warnings) == 1

    def test_cuda11_torch_is_left_unresolved(self, monkeypatch: pytest.MonkeyPatch):
        recorder = _set_host(monkeypatch, machine="x86_64", torch_build=("2.7.1", "cu118"))

        assert natten_requirements("torch==2.7.*", "natten==0.21.0") == [ "natten==0.21.0" ]
        assert "libnatten" in recorder.warnings[0]

    def test_torch28_uses_0_21_1(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, machine="x86_64", torch_build=("2.8.0", "cu129"))

        assert natten_requirements("torch==2.8.*", "natten") == [
            f"natten==0.21.1+torch280cu129@{_url('0.21.1', 'torch280cu129', 12, 'x86_64')}",
        ]

    def test_pin_must_match_the_torch_minor(self, monkeypatch: pytest.MonkeyPatch):
        # natten 0.21.0 only ships torch 2.7 wheels; a torch 2.8 env must not get them.
        _set_host(monkeypatch, machine="x86_64", torch_build=("2.8.0", "cu128"))

        assert natten_requirements("torch==2.8.*", "natten==0.21.0") == [ "natten==0.21.0" ]


class TestAarch64:
    def test_0_21_0_pin_cannot_be_served(self, monkeypatch: pytest.MonkeyPatch):
        recorder = _set_host(monkeypatch, torch_build=("2.7.1", "cu128"))

        assert natten_requirements("torch==2.7.*", "natten==0.21.0") == [ "natten==0.21.0" ]
        assert len(recorder.warnings) == 1

    def test_exact_pin_on_torch29(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=("2.9.1", "cu130"))

        assert natten_requirements("torch==2.9.*", "natten==0.21.1") == [
            f"natten==0.21.1+torch290cu130@{_url('0.21.1', 'torch290cu130', 12, 'aarch64')}",
        ]

    def test_range_picks_the_newest_release_with_a_wheel(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=("2.9.1", "cu130"))

        assert natten_requirements("torch==2.9.*", "natten>=0.21.1") == [
            f"natten==0.21.5+torch290cu130@{_url('0.21.5', 'torch290cu130', 12, 'aarch64')}",
        ]

    def test_bare_spec_on_torch210_skips_releases_without_that_torch(self, monkeypatch: pytest.MonkeyPatch):
        # 0.21.7 has no torch 2.10 wheels, so 0.21.6 wins.
        _set_host(monkeypatch, py_minor=14, torch_build=("2.10.0", "cu128"))

        assert natten_requirements("torch==2.10.*", "natten") == [
            f"natten==0.21.6+torch2100cu128@{_url('0.21.6', 'torch2100cu128', 14, 'aarch64')}",
        ]

    @pytest.mark.parametrize("channel", [ "cu130", "cu132" ])
    def test_torch213_on_dgx_spark_channels(self, monkeypatch: pytest.MonkeyPatch, channel: str):
        _set_host(monkeypatch, torch_build=("2.13.0", channel))

        assert natten_requirements("torch>=2.13", "natten") == [
            f"natten==0.21.7+torch2130{channel}@{_url('0.21.7', f'torch2130{channel}', 12, 'aarch64')}",
        ]

    def test_torch28_has_no_aarch64_wheel(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=("2.8.0", "cu129"))

        assert natten_requirements("torch==2.8.*", "natten") == [ "natten" ]

    def test_channel_must_be_one_the_release_ships(self, monkeypatch: pytest.MonkeyPatch):
        # torch 2.12 wheels exist for cu126/cu130/cu132 only.
        _set_host(monkeypatch, torch_build=("2.12.0", "cu128"))

        assert natten_requirements("torch==2.12.*", "natten") == [ "natten" ]

    def test_fully_qualified_pin_only_accepts_that_build(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=("2.13.0", "cu132"))

        assert natten_requirements("torch==2.13.*", "natten==0.21.7+torch2130cu130") == [ "natten==0.21.7+torch2130cu130" ]


class TestSpecHandling:
    def test_non_natten_specs_and_direct_urls_pass_through(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch)
        direct = "natten@https://example.com/natten-0.21.5-cp312-cp312-linux_aarch64.whl"

        assert natten_requirements("torch==2.9.*", "einops", direct) == [ "einops", direct ]

    def test_marker_is_preserved(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch)

        [ resolved ] = natten_requirements("torch==2.9.*", "natten==0.21.5; python_version >= '3.10'")

        assert resolved.startswith("natten==0.21.5+torch290cu130; python_version >= \"3.10\"@https://")

    @pytest.mark.parametrize("system, machine", [ ("darwin", "arm64"), ("linux", "ppc64le"), ("win32", "AMD64") ])
    def test_unsupported_hosts_return_specs_unchanged(self, monkeypatch: pytest.MonkeyPatch, system: str, machine: str):
        _set_host(monkeypatch, system=system, machine=machine)

        assert natten_requirements("torch==2.9.*", "natten==0.21.5") == [ "natten==0.21.5" ]

    def test_hosts_without_nvidia_driver_return_specs_unchanged(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, cuda=False)

        assert natten_requirements("torch==2.9.*", "natten") == [ "natten" ]

    def test_cpu_torch_fallback_returns_specs_unchanged(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=(None, "cpu"))

        assert natten_requirements("torch==2.9.*", "natten") == [ "natten" ]

    def test_no_driver_channel_returns_specs_unchanged(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=("2.9.1", None))

        assert natten_requirements("torch==2.9.*", "natten") == [ "natten" ]
