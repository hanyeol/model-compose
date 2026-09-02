"""Unit tests for CommonPoseTrackingModelActionConfig validators."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.action.impl.model.tasks.pose_tracking.impl.custom.impl.yolo import (
    YoloPoseTrackingModelActionConfig,
)


class TestRequireAtLeastOneOutput:
    """The action must produce something — rejecting `return_tracks=false` and
    `return_detections=false` together turns a silent no-op into an early error."""

    def test_defaults_ok(self):
        cfg = YoloPoseTrackingModelActionConfig(frames="x", frame_rate=2.0)

        assert cfg.return_tracks is True
        assert cfg.return_detections is False

    def test_frames_only_ok(self):
        cfg = YoloPoseTrackingModelActionConfig(
            frames="x", frame_rate=2.0, return_tracks=False, return_detections=True,
        )

        assert cfg.return_tracks is False
        assert cfg.return_detections is True

    def test_both_false_rejected(self):
        with pytest.raises(ValidationError, match="'return_tracks' or 'return_detections' must be true"):
            YoloPoseTrackingModelActionConfig(
                frames="x", frame_rate=2.0, return_tracks=False, return_detections=False,
            )

    def test_variable_reference_bypasses_literal_check(self):
        # `return_tracks` as a string is a variable reference to be resolved at
        # run time; the schema validator only enforces the literal-bool case.
        cfg = YoloPoseTrackingModelActionConfig(
            frames="x",
            frame_rate=2.0,
            return_tracks="${input.want_tracks}",
            return_detections=False,
        )

        assert cfg.return_tracks == "${input.want_tracks}"
