"""Unit tests for CommonPoseTrackingModelActionConfig validators."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.action.impl.model.tasks.pose_tracking.impl.custom.ultralytics import (
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


class TestImageFlagPairing:
    """Image-emitting flags must pair with the view they emit into:
    `return_track_image` only makes sense with `return_tracks`,
    `return_detection_image` and `return_frame_image` only make sense with
    `return_detections`. The pairing is split so the memory-heavy per-frame
    crops aren't silently enabled by the segment-image flag."""

    def test_track_image_without_tracks_rejected(self):
        with pytest.raises(ValidationError, match="'return_track_image' requires 'return_tracks' to be true"):
            YoloPoseTrackingModelActionConfig(
                frames="x", frame_rate=2.0,
                return_tracks=False, return_detections=True, return_track_image=True,
            )

    def test_detection_image_without_detections_rejected(self):
        with pytest.raises(ValidationError, match="'return_detection_image' requires 'return_detections' to be true"):
            YoloPoseTrackingModelActionConfig(
                frames="x", frame_rate=2.0,
                return_detections=False, return_detection_image=True,
            )

    def test_frame_image_without_detections_rejected(self):
        with pytest.raises(ValidationError, match="'return_frame_image' requires 'return_detections' to be true"):
            YoloPoseTrackingModelActionConfig(
                frames="x", frame_rate=2.0,
                return_detections=False, return_frame_image=True,
            )

    def test_track_and_detection_image_can_coexist(self):
        cfg = YoloPoseTrackingModelActionConfig(
            frames="x", frame_rate=2.0,
            return_tracks=True, return_detections=True,
            return_track_image=True, return_detection_image=True,
        )

        assert cfg.return_track_image is True
        assert cfg.return_detection_image is True

    def test_track_image_alone_with_tracks_ok(self):
        # The memory-saving configuration: segment crops only, no per-frame
        # crops. If this ever raises, long-video users lose their main escape
        # hatch from the OOM issue the flag split is here to fix.
        cfg = YoloPoseTrackingModelActionConfig(
            frames="x", frame_rate=2.0,
            return_tracks=True, return_detections=True,
            return_track_image=True, return_detection_image=False,
        )

        assert cfg.return_track_image is True
        assert cfg.return_detection_image is False
