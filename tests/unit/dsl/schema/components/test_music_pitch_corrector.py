"""Schema-level validation tests for music-pitch-corrector.

Covers the invariants the DSL layer must enforce before anything reaches the
service layer: method discriminator, driver default, required-field rules per
target, and the role-separated input contract (plan=pitch, apply=audio+curve,
correct=audio+pitch).
"""

from pydantic import TypeAdapter, ValidationError
import pytest

from mindor.dsl.schema.component import (
    MusicPitchCorrectorComponentConfig,
    MusicPitchCorrectorDriverType,
    WorldMusicPitchCorrectorComponentConfig,
)
from mindor.dsl.schema.action import (
    WorldMusicPitchCorrectorPlanActionConfig,
    WorldMusicPitchCorrectorApplyActionConfig,
    WorldMusicPitchCorrectorCorrectActionConfig,
    MusicPitchCorrectorActionMethod,
)


COMPONENT_ADAPTER = TypeAdapter(MusicPitchCorrectorComponentConfig)

_PITCH_REF = "${jobs.pitch.output.frames}"


def _component(actions):
    return {
        "type": "music-pitch-corrector",
        "driver": "world",
        "runtime": "native",
        "actions": actions,
    }


class TestDriverDiscriminator:
    def test_world_driver_resolves(self):
        cfg = COMPONENT_ADAPTER.validate_python(_component([
            { "id": "p", "method": "plan", "pitch": _PITCH_REF, "key": "A" },
        ]))
        assert isinstance(cfg, WorldMusicPitchCorrectorComponentConfig)
        assert cfg.driver == MusicPitchCorrectorDriverType.WORLD

    def test_unknown_driver_rejected(self):
        bad = _component([{ "id": "p", "method": "plan", "pitch": _PITCH_REF, "key": "A" }])
        bad["driver"] = "psola"
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(bad)


class TestPlanValidation:
    def test_plan_requires_pitch(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_component([
                { "id": "p", "method": "plan", "key": "A" },
            ]))

    def test_plan_accepts_pitch(self):
        cfg = COMPONENT_ADAPTER.validate_python(_component([
            { "id": "p", "method": "plan", "pitch": _PITCH_REF, "key": "A" },
        ]))
        action = cfg.actions[0]
        assert isinstance(action, WorldMusicPitchCorrectorPlanActionConfig)
        assert action.method == MusicPitchCorrectorActionMethod.PLAN

    def test_variable_reference_target_is_allowed(self):
        """A `${...}` target is a runtime value; the schema layer can't tell
        whether it will be `scale` or `melody` and must not reject it.
        """
        cfg = COMPONENT_ADAPTER.validate_python(_component([
            { "id": "p", "method": "plan", "pitch": _PITCH_REF, "mode": "${input.mode}" },
        ]))
        assert cfg.actions[0].mode == "${input.mode}"


class TestApplyValidation:
    def test_apply_requires_curve(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_component([
                { "id": "a", "method": "apply", "audio": "x.wav" },
            ]))

    def test_apply_requires_audio(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_component([
                { "id": "a", "method": "apply", "curve": { "version": 1, "notes": [], "frames": {} } },
            ]))

    def test_apply_shape(self):
        cfg = COMPONENT_ADAPTER.validate_python(_component([
            {
                "id": "a",
                "method": "apply",
                "audio": "x.wav",
                "curve": { "version": 1, "notes": [], "frames": {} },
                "formant_shift": 0.5,
            },
        ]))
        action = cfg.actions[0]
        assert isinstance(action, WorldMusicPitchCorrectorApplyActionConfig)
        assert action.formant_shift == 0.5


class TestCorrectValidation:
    def test_correct_combines_fields(self):
        cfg = COMPONENT_ADAPTER.validate_python(_component([
            {
                "id": "c",
                "method": "correct",
                "audio": "x.wav",
                "pitch": _PITCH_REF,
                "key": "A",
                "scale": "minor",
                "formant_shift": 0.0,
                "return_curve": True,
            },
        ]))
        action = cfg.actions[0]
        assert isinstance(action, WorldMusicPitchCorrectorCorrectActionConfig)
        assert action.key == "A"
        assert action.return_curve is True

    def test_correct_requires_audio(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_component([
                { "id": "c", "method": "correct", "pitch": _PITCH_REF, "key": "A" },
            ]))

    def test_correct_requires_pitch(self):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(_component([
                { "id": "c", "method": "correct", "audio": "x.wav", "key": "A" },
            ]))
