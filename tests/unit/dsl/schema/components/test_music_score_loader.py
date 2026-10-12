"""Schema-level validation tests for music-score-loader."""

from pydantic import TypeAdapter, ValidationError
import pytest

from mindor.dsl.schema.component import (
    MusicScoreLoaderComponentConfig,
    MusicScoreLoaderDriverType,
    LocalMusicScoreLoaderComponentConfig,
)
from mindor.dsl.schema.action import LocalMusicScoreLoaderActionConfig


COMPONENT_ADAPTER = TypeAdapter(MusicScoreLoaderComponentConfig)


def _component(actions):
    return {
        "type": "music-score-loader",
        "driver": "local",
        "runtime": "native",
        "actions": actions,
    }


class TestDriverDiscriminator:
    def test_local_driver_resolves(self):
        cfg = COMPONENT_ADAPTER.validate_python(_component([
            { "id": "load", "source": "song.mid" },
        ]))
        assert isinstance(cfg, LocalMusicScoreLoaderComponentConfig)
        assert cfg.driver == MusicScoreLoaderDriverType.LOCAL

    def test_unknown_driver_rejected(self):
        bad = _component([{ "id": "load", "source": "song.mid" }])
        bad["driver"] = "web"
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(bad)


class TestActionValidation:
    def test_source_required(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_component([{ "id": "load" }]))

    def test_format_optional(self):
        cfg = COMPONENT_ADAPTER.validate_python(_component([
            { "id": "load", "source": "song.mid" },
        ]))
        action = cfg.actions[0]
        assert isinstance(action, LocalMusicScoreLoaderActionConfig)
        assert action.format is None

    def test_format_accepts_known_values(self):
        for format in ("midi", "musicxml"):
            cfg = COMPONENT_ADAPTER.validate_python(_component([
                { "id": "load", "source": "song", "format": format },
            ]))
            assert cfg.actions[0].format == format

    def test_track_optional(self):
        cfg = COMPONENT_ADAPTER.validate_python(_component([
            { "id": "load", "source": "song.mid", "track": 1 },
        ]))
        assert cfg.actions[0].track == 1
