"""Pre-built wheel selection for flash-attn on Linux x86_64 and aarch64.

The torch build each case targets is stubbed through `resolve_torch_build`, so
these tests pin down the wheel tables and URL shapes without touching
nvidia-smi or the installed torch.
"""

from __future__ import annotations

import types
from typing import List, Optional, Tuple

import pytest

from mindor.core.foundation.package import flash_attn as flash_attn_module
from mindor.core.foundation.package import torch as torch_module
from mindor.core.foundation.package.flash_attn import flash_attn_requirements, flash_attn_torch_spec
from mindor.core.foundation.package.torch import supported_torch_minors, resolve_torch_build, torch_requirements

UPSTREAM = "https://github.com/Dao-AILab/flash-attention/releases/download"
COMMUNITY = "https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download"


class _LogRecorder:
    def __init__(self) -> None:
        self.records: List[Tuple[str, str]] = []

    def info(self, message: str, *args, **kwargs) -> None:
        self.records.append(("info", message))

    def warning(self, message: str, *args, **kwargs) -> None:
        self.records.append(("warning", message))

    def messages(self, level: str) -> List[str]:
        return [ message for record_level, message in self.records if record_level == level ]


def _set_host(
    monkeypatch: pytest.MonkeyPatch,
    machine: str = "aarch64",
    py_minor: int = 12,
    torch_build: Tuple[Optional[str], Optional[str]] = ("2.9.1", "cu130"),
    cuda: bool = True,
    system: str = "linux",
) -> _LogRecorder:
    monkeypatch.setattr(flash_attn_module, "sys", types.SimpleNamespace(platform=system, version_info=types.SimpleNamespace(minor=py_minor)))
    monkeypatch.setattr(flash_attn_module, "platform", types.SimpleNamespace(machine=lambda: machine))
    monkeypatch.setattr(flash_attn_module, "is_cuda_installed", lambda: cuda)
    monkeypatch.setattr(flash_attn_module, "resolve_torch_build", lambda *specs: torch_build)
    recorder = _LogRecorder()
    monkeypatch.setattr(flash_attn_module, "logging", recorder)
    return recorder


class TestAarch64:
    def test_torch29_cu13_uses_upstream_post1_asset(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=("2.9.1", "cu130"))

        assert flash_attn_requirements("torch==2.9.*", "flash-attn==2.8.3.post1") == [
            f"flash-attn==2.8.3@{UPSTREAM}/v2.8.3.post1/flash_attn-2.8.3+cu13torch2.9cxx11abiTRUE-cp312-cp312-linux_aarch64.whl",
        ]

    def test_torch29_cu12_uses_upstream_v283_asset(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=("2.9.1", "cu128"))

        assert flash_attn_requirements("torch==2.9.*", "flash-attn") == [
            f"flash-attn@{UPSTREAM}/v2.8.3/flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_aarch64.whl",
        ]

    def test_torch210_cu13_uses_upstream_v283_asset(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=("2.10.0", "cu130"))

        assert flash_attn_requirements("torch==2.10.*", "flash-attn") == [
            f"flash-attn@{UPSTREAM}/v2.8.3/flash_attn-2.8.3+cu13torch2.10cxx11abiTRUE-cp312-cp312-linux_aarch64.whl",
        ]

    def test_torch27_falls_back_to_community_build(self, monkeypatch: pytest.MonkeyPatch):
        recorder = _set_host(monkeypatch, torch_build=("2.7.1", "cu128"))

        assert flash_attn_requirements("torch==2.7.*", "flash-attn==2.8.3.post1") == [
            f"flash-attn==2.8.3@{COMMUNITY}/v0.6.4/flash_attn-2.8.3+cu128torch2.7-cp312-cp312-linux_aarch64.whl",
        ]
        assert any("community-built" in message for message in recorder.messages("info"))
        assert recorder.messages("warning") == []

    def test_non_cp312_python_uses_community_build(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, py_minor=13, torch_build=("2.9.1", "cu130"))

        assert flash_attn_requirements("torch==2.9.*", "flash-attn") == [
            f"flash-attn@{COMMUNITY}/v0.7.16/flash_attn-2.8.3+cu130torch2.9-cp313-cp313-linux_aarch64.whl",
        ]

    @pytest.mark.parametrize("py_minor, tag", [ (12, "v0.9.48"), (13, "v0.9.49") ])
    def test_torch213_picks_the_tag_each_python_was_published_under(self, monkeypatch: pytest.MonkeyPatch, py_minor: int, tag: str):
        _set_host(monkeypatch, py_minor=py_minor, torch_build=("2.13.0", "cu130"))

        assert flash_attn_requirements("torch>=2.13", "flash-attn") == [
            f"flash-attn@{COMMUNITY}/{tag}/flash_attn-2.8.3+cu130torch2.13-cp3{py_minor}-cp3{py_minor}-linux_aarch64.whl",
        ]

    def test_torch28_has_no_wheel_and_warns(self, monkeypatch: pytest.MonkeyPatch):
        recorder = _set_host(monkeypatch, torch_build=("2.8.0", "cu129"))

        assert flash_attn_requirements("torch==2.8.*", "flash-attn==2.8.3.post1") == [ "flash-attn==2.8.3.post1" ]
        assert len(recorder.messages("warning")) == 1
        assert "no-build-isolation" in recorder.messages("warning")[0]

    def test_python_outside_community_matrix_is_left_unresolved(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, py_minor=13, torch_build=("2.7.1", "cu128"))

        assert flash_attn_requirements("torch==2.7.*", "flash-attn") == [ "flash-attn" ]

    def test_channel_must_match_exactly_for_community_builds(self, monkeypatch: pytest.MonkeyPatch):
        # torch 2.7 never ships cu130; a reused out-of-table build must not grab the cu128 wheel.
        _set_host(monkeypatch, torch_build=("2.7.1", "cu130"))

        assert flash_attn_requirements("torch==2.7.*", "flash-attn") == [ "flash-attn" ]


class TestX86_64:
    @pytest.mark.parametrize("torch_build, py_minor, expected_url", [
        (("2.8.0", "cu129"), 12, f"{UPSTREAM}/v2.8.3.post1/flash_attn-2.8.3.post1+cu12torch2.8cxx11abiFALSE-cp312-cp312-linux_x86_64.whl"),
        (("2.7.1", "cu128"), 13, f"{UPSTREAM}/v2.8.3.post1/flash_attn-2.8.3.post1+cu12torch2.7cxx11abiFALSE-cp313-cp313-linux_x86_64.whl"),
        (("2.5.1", "cu124"), 10, f"{UPSTREAM}/v2.8.3.post1/flash_attn-2.8.3.post1+cu12torch2.5cxx11abiFALSE-cp310-cp310-linux_x86_64.whl"),
    ])
    def test_existing_matrix_is_unchanged(self, monkeypatch: pytest.MonkeyPatch, torch_build, py_minor: int, expected_url: str):
        _set_host(monkeypatch, machine="x86_64", py_minor=py_minor, torch_build=torch_build)

        assert flash_attn_requirements("torch", "flash-attn==2.8.3.post1") == [ f"flash-attn==2.8.3.post1@{expected_url}" ]

    def test_torch29_cu13_keeps_post1_asset_and_aligns_pin(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, machine="x86_64", torch_build=("2.9.1", "cu130"))

        assert flash_attn_requirements("torch==2.9.*", "flash-attn==2.8.3.post1") == [
            f"flash-attn==2.8.3@{UPSTREAM}/v2.8.3.post1/flash_attn-2.8.3+cu13torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl",
        ]

    def test_torch29_on_cuda12_torch_picks_the_cu12_asset(self, monkeypatch: pytest.MonkeyPatch):
        # Previously torch 2.9 always mapped to the cu13 wheel, which cannot load against a cu128 torch.
        _set_host(monkeypatch, machine="x86_64", torch_build=("2.9.1", "cu128"))

        assert flash_attn_requirements("torch==2.9.*", "flash-attn") == [
            f"flash-attn@{UPSTREAM}/v2.8.3/flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl",
        ]

    def test_torch210_on_cuda12_torch_falls_back_to_community_build(self, monkeypatch: pytest.MonkeyPatch):
        # hanyeol/model-compose#50: upstream has no torch 2.10 + cu12 wheel.
        _set_host(monkeypatch, machine="x86_64", torch_build=("2.10.0", "cu128"))

        assert flash_attn_requirements("torch>=2.9,<2.11", "flash-attn==2.8.3.post1") == [
            f"flash-attn==2.8.3@{COMMUNITY}/v0.9.0/flash_attn-2.8.3+cu128torch2.10-cp312-cp312-linux_x86_64.whl",
        ]

    def test_non_cp312_python_uses_community_build(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, machine="x86_64", py_minor=11, torch_build=("2.9.1", "cu130"))

        assert flash_attn_requirements("torch==2.9.*", "flash-attn") == [
            f"flash-attn@{COMMUNITY}/v0.9.0/flash_attn-2.8.3+cu130torch2.9-cp311-cp311-linux_x86_64.whl",
        ]

    def test_cuda11_torch_is_left_unresolved(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, machine="x86_64", torch_build=("2.7.1", "cu118"))

        assert flash_attn_requirements("torch==2.7.*", "flash-attn") == [ "flash-attn" ]


class TestSpecHandling:
    def test_non_flash_specs_and_direct_urls_pass_through(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch)
        direct = "flash-attn@https://example.com/flash_attn-2.8.3-cp312-cp312-linux_aarch64.whl"

        assert flash_attn_requirements("torch==2.9.*", "einops", direct) == [ "einops", direct ]

    def test_incompatible_pin_is_left_unresolved(self, monkeypatch: pytest.MonkeyPatch):
        recorder = _set_host(monkeypatch)

        assert flash_attn_requirements("torch==2.9.*", "flash-attn==2.7.4") == [ "flash-attn==2.7.4" ]
        assert len(recorder.messages("warning")) == 1

    def test_post2_pin_is_not_downgraded_to_2_8_3(self, monkeypatch: pytest.MonkeyPatch):
        # 2.8.3.post2 carries real fixes, so it must not be swapped for the 2.8.3 assets.
        _set_host(monkeypatch)

        assert flash_attn_requirements("torch==2.9.*", "flash-attn==2.8.3.post2") == [ "flash-attn==2.8.3.post2" ]

    def test_underscore_name_and_extras_are_preserved_when_realigning(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch)

        [ resolved ] = flash_attn_requirements("torch==2.9.*", "flash_attn[test]==2.8.3.post1")

        assert resolved.startswith("flash_attn[test]==2.8.3@")

    @pytest.mark.parametrize("system, machine", [ ("darwin", "arm64"), ("linux", "ppc64le"), ("win32", "AMD64") ])
    def test_unsupported_hosts_return_specs_unchanged(self, monkeypatch: pytest.MonkeyPatch, system: str, machine: str):
        _set_host(monkeypatch, system=system, machine=machine)

        assert flash_attn_requirements("torch==2.9.*", "flash-attn==2.8.3.post1") == [ "flash-attn==2.8.3.post1" ]

    def test_hosts_without_nvidia_driver_return_specs_unchanged(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, cuda=False)

        assert flash_attn_requirements("torch==2.9.*", "flash-attn") == [ "flash-attn" ]

    def test_cpu_torch_fallback_returns_specs_unchanged(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, torch_build=(None, "cpu"))

        assert flash_attn_requirements("torch==2.9.*", "flash-attn") == [ "flash-attn" ]


class TestResolveTorchBuild:
    """`resolve_torch_build` must agree with what `torch_requirements` installs."""

    @pytest.fixture(autouse=True)
    def _no_installed_torch(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(torch_module, "_get_installed_torch_spec", lambda: None)

    @pytest.mark.parametrize("torch_spec, driver, expected", [
        ("torch==2.7.*",      (13, 0), ("2.7.1", "cu128")),
        ("torch==2.8.*",      (13, 0), ("2.8.0", "cu129")),
        ("torch==2.9.*",      (13, 0), ("2.9.1", "cu130")),
        ("torch==2.9.*",      (12, 8), ("2.9.1", "cu128")),
        ("torch>=2.4,<2.6",   (12, 4), ("2.5.1", "cu124")),
    ])
    def test_matches_torch_requirements(self, monkeypatch: pytest.MonkeyPatch, torch_spec: str, driver, expected):
        monkeypatch.setattr(torch_module, "get_cuda_driver_version", lambda: driver)

        version, channel = resolve_torch_build(torch_spec)
        [ torch_requirement ] = torch_requirements(torch_spec)

        assert (version, channel) == expected
        assert torch_requirement.endswith(f"@https://download.pytorch.org/whl/{channel}")

    def test_reuses_installed_torch_like_torch_requirements(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(torch_module, "get_cuda_driver_version", lambda: (13, 0))
        monkeypatch.setattr(torch_module, "_get_installed_torch_spec", lambda: ("2.9.0", "cu128"))

        assert resolve_torch_build("torch>=2.8") == ("2.9.0", "cu128")
        assert torch_requirements("torch>=2.8") == [ "torch>=2.8@https://download.pytorch.org/whl/cu128" ]

    def test_no_driver_has_no_channel(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(torch_module, "get_cuda_driver_version", lambda: None)

        assert resolve_torch_build("torch==2.7.*") == ("2.7.1", None)

    def test_no_cuda_channel_falls_back_to_cpu(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(torch_module, "get_cuda_driver_version", lambda: (11, 0))

        assert resolve_torch_build("torch==2.9.*") == (None, "cpu")


class TestFlashAttnTorchSpec:
    """`flash_attn_torch_spec` pins a torch range to a minor with a wheel (#50)."""

    @staticmethod
    def _host(monkeypatch: pytest.MonkeyPatch, builds, machine: str = "x86_64", py_minor: int = 12):
        _set_host(monkeypatch, machine=machine, py_minor=py_minor)

        def _resolve(spec: str):
            for minor, build in builds.items():
                if f"=={minor}.*" in spec:
                    return build
            return builds["default"]

        monkeypatch.setattr(flash_attn_module, "resolve_torch_build", _resolve)
        monkeypatch.setattr(flash_attn_module, "supported_torch_minors", lambda *specs: [ "2.10", "2.9" ])

    def test_cuda12_x86_pins_to_torch29_upstream(self, monkeypatch: pytest.MonkeyPatch):
        self._host(monkeypatch, { "default": ("2.10.0", "cu128"), "2.10": ("2.10.0", "cu128"), "2.9": ("2.9.1", "cu128") })

        spec = flash_attn_torch_spec("torch>=2.9,<2.11", "flash-attn==2.8.3.post1")

        assert spec == "torch<2.11,>=2.9,==2.9.*"
        assert flash_attn_requirements(spec, "flash-attn==2.8.3.post1") == [
            f"flash-attn==2.8.3@{UPSTREAM}/v2.8.3/flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl",
        ]

    def test_cuda13_keeps_the_range(self, monkeypatch: pytest.MonkeyPatch):
        self._host(monkeypatch, { "default": ("2.10.0", "cu130"), "2.10": ("2.10.0", "cu130"), "2.9": ("2.9.1", "cu130") })

        assert flash_attn_torch_spec("torch>=2.9,<2.11", "flash-attn==2.8.3.post1") == "torch>=2.9,<2.11"

    def test_community_only_keeps_the_range(self, monkeypatch: pytest.MonkeyPatch):
        # Python 3.11: upstream ships cp312 only, so no minor beats the original.
        self._host(monkeypatch, { "default": ("2.10.0", "cu128"), "2.10": ("2.10.0", "cu128"), "2.9": ("2.9.1", "cu128") }, py_minor=11)

        assert flash_attn_torch_spec("torch>=2.9,<2.11", "flash-attn==2.8.3.post1") == "torch>=2.9,<2.11"

    def test_unsupported_host_keeps_the_range(self, monkeypatch: pytest.MonkeyPatch):
        _set_host(monkeypatch, machine="ppc64le")

        assert flash_attn_torch_spec("torch>=2.9,<2.11", "flash-attn") == "torch>=2.9,<2.11"


class TestSupportedTorchMinors:
    def test_lists_minors_newest_first(self):
        assert supported_torch_minors("torch>=2.9,<2.11") == [ "2.10", "2.9" ]

    def test_bare_spec_lists_every_tabled_minor(self):
        minors = supported_torch_minors("torch")

        assert minors[0] == "2.13" and minors[-1] == "2.4" and len(minors) == len(set(minors))
