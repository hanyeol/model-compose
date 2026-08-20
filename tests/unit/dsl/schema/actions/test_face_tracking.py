"""Unit tests for CommonFaceTrackingModelActionConfig validators."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.action.impl.model.tasks.face_tracking.impl.custom.impl.insightface import (
    InsightfaceFaceTrackingModelActionConfig,
)


class TestRequireAtLeastOneOutput:
    """The action must produce something — rejecting `return_tracks=false` and
    `return_frames=false` together turns a silent no-op into an early error."""

    def test_defaults_ok(self):
        cfg = InsightfaceFaceTrackingModelActionConfig(frames="x", frame_rate=2.0)

        assert cfg.return_tracks is True
        assert cfg.return_frames is False

    def test_frames_only_ok(self):
        cfg = InsightfaceFaceTrackingModelActionConfig(
            frames="x", frame_rate=2.0, return_tracks=False, return_frames=True,
        )

        assert cfg.return_tracks is False
        assert cfg.return_frames is True

    def test_both_false_rejected(self):
        with pytest.raises(ValidationError, match="'return_tracks' or 'return_frames' must be true"):
            InsightfaceFaceTrackingModelActionConfig(
                frames="x", frame_rate=2.0, return_tracks=False, return_frames=False,
            )

    def test_variable_reference_bypasses_literal_check(self):
        # `return_tracks` as a string is a variable reference to be resolved at
        # run time; the schema validator only enforces the literal-bool case.
        cfg = InsightfaceFaceTrackingModelActionConfig(
            frames="x",
            frame_rate=2.0,
            return_tracks="${input.want_tracks}",
            return_frames=False,
        )

        assert cfg.return_tracks == "${input.want_tracks}"
