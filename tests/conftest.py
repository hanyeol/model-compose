"""Root conftest: applies tier markers to tests based on their directory.

- tests/unit/        → no marker (default tier)
- tests/integration/ → @pytest.mark.integration
- tests/e2e/         → @pytest.mark.e2e
- tests/live/        → @pytest.mark.live

`live` is excluded from the default run via pyproject.toml's `addopts`.
Individual tests may add @pytest.mark.live on top of any tier when they
require real cloud APIs or model downloads (e.g. integration tests that hit
a real Neo4j, e2e tests that need a real Redis).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_TESTS_ROOT = Path(__file__).resolve().parent

_TIER_MARKERS = {
    "integration": "integration",
    "e2e": "e2e",
    "live": "live",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        try:
            rel = Path(item.fspath).resolve().relative_to(_TESTS_ROOT)
        except ValueError:
            continue
        top = rel.parts[0] if rel.parts else ""
        marker = _TIER_MARKERS.get(top)
        if marker is not None:
            item.add_marker(getattr(pytest.mark, marker))
