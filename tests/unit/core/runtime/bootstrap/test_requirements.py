"""Parity test between ``pyproject.toml`` ``[project] dependencies`` and
``src/mindor/core/runtime/bootstrap/requirements.txt``.

The requirements file is the single source consumed by both the Docker
runtime (copied into the build context as ``runtime-requirements.txt``)
and the upcoming virtualenv runtime. It must stay in lock-step with the
PyPI distribution metadata in ``pyproject.toml`` — otherwise a Docker /
virtualenv install will diverge from a ``pip install model-compose``.

PEP 508 environment markers (e.g. ``; python_version < '3.11'``) are
kept verbatim in both lists: pip honours them in ``requirements.txt``,
so a single file works across every Python version the project
supports.
"""

from __future__ import annotations

import sys
from importlib.resources import files
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def _project_root() -> Path:
    # tests/unit/core/runtime/bootstrap/test_requirements.py → repo root is 5 parents up.
    return Path(__file__).resolve().parents[5]


def _load_pyproject_dependencies() -> list[Requirement]:
    pyproject_path = _project_root() / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return [Requirement(line) for line in data["project"]["dependencies"]]


def _load_runtime_requirements() -> list[Requirement]:
    # Access via importlib.resources so the test exercises the same lookup
    # path the runtime code will use at install time.
    path = files("mindor.core.runtime.bootstrap").joinpath("requirements.txt")
    reqs: list[Requirement] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        reqs.append(Requirement(line))
    return reqs


def _key(req: Requirement) -> tuple[str, str, str]:
    # Name + version specifier + marker — every dimension that affects
    # what pip actually installs.
    return (
        canonicalize_name(req.name),
        str(req.specifier),
        str(req.marker) if req.marker is not None else "",
    )


class TestRuntimeRequirementsParity:
    def test_no_duplicates_in_runtime_requirements(self):
        reqs = _load_runtime_requirements()
        names = [canonicalize_name(r.name) for r in reqs]
        duplicates = {n for n in names if names.count(n) > 1}
        assert not duplicates, f"Duplicate packages in requirements.txt: {sorted(duplicates)}"

    def test_runtime_requirements_matches_pyproject(self):
        pyproject_keys = {_key(r) for r in _load_pyproject_dependencies()}
        runtime_keys = {_key(r) for r in _load_runtime_requirements()}

        missing_from_runtime = pyproject_keys - runtime_keys
        extra_in_runtime = runtime_keys - pyproject_keys

        assert not missing_from_runtime and not extra_in_runtime, (
            "core/runtime/bootstrap/requirements.txt is out of sync with "
            "pyproject.toml [project] dependencies.\n"
            f"  Missing from requirements.txt: {sorted(missing_from_runtime)}\n"
            f"  Extra in requirements.txt:     {sorted(extra_in_runtime)}\n"
            "Update one side so both lists match — package name, version "
            "specifier, and PEP 508 marker must all agree."
        )
