from __future__ import annotations

from typing import List
from mindor.dsl.schema.component import ComponentConfig

def resolve_venv_label(component_config: ComponentConfig) -> str:
    """Default venv-sharing key derived from the component's declared
    identity axes — ``type[-task][-driver][-architecture|-family]``.

    Two components with the same label share one venv under
    ``<xdg_data_home>/mindor/venvs/<label>/``; a different axis value
    allocates a new one. ``architecture`` and ``family`` are mutually
    exclusive per driver (``huggingface`` exposes ``architecture``, ``custom``
    exposes ``family``), so only one of the two is appended."""
    parts: List[str] = [ component_config.type.value ]

    for attr in ("task", "driver"):
        value = getattr(component_config, attr, None)

        if value is not None:
            parts.append(value.value)

    variant = getattr(component_config, "architecture", None) or getattr(component_config, "family", None)

    if variant is not None:
        parts.append(variant.value)

    return "-".join(parts)
