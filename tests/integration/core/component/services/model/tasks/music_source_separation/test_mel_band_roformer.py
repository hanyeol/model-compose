"""Integration tests for the Mel-Band RoFormer music-source-separation driver.

The chunked-inference / stem post-processing pipeline is exercised by the
BS-RoFormer test module (see `test_bs_roformer.py`) since the two drivers
share `RoFormerMusicSourceSeparationTaskAction`. Here we verify the parts
that differ per driver — config parsing, driver dispatch, and that the
lazy model-class import points at `MelBandRoformer`.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest


pytest.importorskip("bs_roformer")

from pydantic import TypeAdapter

from mindor.core.component.services.model.tasks.music_source_separation.custom.custom import (
    CustomMusicSourceSeparationTaskDriver,
)
from mindor.core.component.services.model.tasks.music_source_separation.custom.roformer.mel_band_roformer import (
    MelBandRoFormerMusicSourceSeparationTaskDriver,
)
from mindor.dsl.schema.component import ModelComponentConfig


def _make_component_config(**overrides: Any) -> ModelComponentConfig:
    payload: Dict[str, Any] = {
        "type":   "model",
        "task":   "music-source-separation",
        "driver": "custom",
        "family": "mel-band-roformer",
        "model":  "ZFTurbo/Mel-Roformer-Vocals",
        "stems":  ["vocals"],
        "params": {
            "dim":         32,
            "depth":       1,
            "stereo":      True,
            "num_stems":   1,
            "num_bands":   4,
            "sample_rate": 44100,
        },
        "actions": [{ "audio": "${input.audio}" }],
    }
    payload.update(overrides)
    return TypeAdapter(ModelComponentConfig).validate_python(payload)


class TestConfigParsing:
    def test_family_and_stems(self):
        config = _make_component_config()

        assert type(config).__name__ == "MelBandRoFormerMusicSourceSeparationModelComponentConfig"
        assert config.family.value == "mel-band-roformer"
        assert config.stems == ["vocals"]
        assert config.params.num_bands == 4

    def test_action_type(self):
        config = _make_component_config()

        assert type(config.actions[0]).__name__ == "MelBandRoFormerMusicSourceSeparationModelActionConfig"


class TestDispatch:
    def test_custom_dispatcher_returns_mel_band_driver(self):
        config = _make_component_config()

        driver = CustomMusicSourceSeparationTaskDriver("c1", config, daemon=False)

        assert isinstance(driver, MelBandRoFormerMusicSourceSeparationTaskDriver)

    def test_setup_requirements_include_bs_roformer(self):
        config = _make_component_config()

        driver = CustomMusicSourceSeparationTaskDriver("c1", config, daemon=False)
        reqs = driver._get_setup_requirements()

        assert "bs-roformer" in reqs
        assert "safetensors" in reqs


class TestLazyModelClass:
    def test_get_model_class_returns_mel_band(self):
        from bs_roformer import MelBandRoformer

        config = _make_component_config()
        driver = CustomMusicSourceSeparationTaskDriver("c1", config, daemon=False)

        assert driver._get_model_class() is MelBandRoformer
