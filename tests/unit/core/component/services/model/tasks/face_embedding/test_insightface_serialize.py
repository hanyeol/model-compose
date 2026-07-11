"""Unit tests for InsightfaceFaceEmbeddingTaskAction._serialize().

Uses a fake Face stand-in so tests run without loading insightface / onnxruntime.
Validates that:
  - Output follows the { faces, width, height } contract shared with face-detection.
  - Each face dict includes embedding + bounding_box (xywh) + score.
  - Optional fields (landmarks, gender, age, pose) appear only when the underlying
    Face object exposes them AND the corresponding option is enabled.
  - normalize_embeddings picks `normed_embedding` when available, else falls back to `embedding`.
  - max_num_faces truncates the detected list.
  - Landmarks prefer the densest available set (2d_106 > 3d_68 > kps).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import numpy as np
import pytest

from mindor.core.component.services.model.tasks.face_embedding.custom.insightface import (
    InsightfaceFaceEmbeddingTaskAction,
)


def _fake_face(**attrs) -> SimpleNamespace:
    """SimpleNamespace approximates insightface's Face object well enough for
    _serialize's getattr-based access."""
    return SimpleNamespace(**attrs)


def _serialize(
    action_kwargs: Dict[str, Any] = None,
    faces: List[SimpleNamespace] = None,
    params: Dict[str, Any] = None,
    width: int = 100,
    height: int = 200,
) -> Dict[str, Any]:
    # Instantiate without going through __init__ (which needs a real model handle).
    action = InsightfaceFaceEmbeddingTaskAction.__new__(InsightfaceFaceEmbeddingTaskAction)
    return action._serialize(faces or [], width, height, params or {})


def _default_params(**overrides) -> Dict[str, Any]:
    base = {
        "face_detection":       True,
        "alignment":            True,
        "normalize_embeddings": True,
        "return_landmarks":     False,
        "return_gender_age":    False,
        "max_num_faces":        0,  # 0 = no limit
    }
    base.update(overrides)
    return base


class TestOutputContainer:

    def test_empty_face_list(self):
        result = _serialize(params=_default_params(), faces=[], width=640, height=480)
        assert result == {"faces": [], "width": 640, "height": 480}

    def test_single_face_minimal_fields(self):
        face = _fake_face(
            bbox=np.array([10.0, 20.0, 110.0, 220.0]),
            det_score=0.87,
            embedding=np.array([0.1, 0.2, 0.3]),
            normed_embedding=np.array([1.0, 0.0, 0.0]),
        )
        result = _serialize(params=_default_params(), faces=[face])
        assert set(result.keys()) == {"faces", "width", "height"}
        assert len(result["faces"]) == 1

        fd = result["faces"][0]
        # Only the always-present fields, no landmarks/age/gender/pose.
        assert set(fd.keys()) == {"embedding", "bounding_box", "score"}
        assert fd["embedding"] == [1.0, 0.0, 0.0]  # normed picked
        assert fd["bounding_box"] == [10, 20, 100, 200]  # xywh
        assert fd["score"] == pytest.approx(0.87)


class TestEmbeddingSelection:

    def test_normalize_true_picks_normed(self):
        face = _fake_face(
            bbox=np.array([0.0, 0.0, 1.0, 1.0]),
            det_score=1.0,
            embedding=np.array([9.9, 9.9]),
            normed_embedding=np.array([0.6, 0.8]),
        )
        result = _serialize(params=_default_params(normalize_embeddings=True), faces=[face])
        assert result["faces"][0]["embedding"] == [0.6, 0.8]

    def test_normalize_false_picks_raw(self):
        face = _fake_face(
            bbox=np.array([0.0, 0.0, 1.0, 1.0]),
            det_score=1.0,
            embedding=np.array([9.9, 9.9]),
            normed_embedding=np.array([0.6, 0.8]),
        )
        result = _serialize(params=_default_params(normalize_embeddings=False), faces=[face])
        assert result["faces"][0]["embedding"] == [9.9, 9.9]



class TestBoundingBox:

    def test_xywh_conversion(self):
        face = _fake_face(
            bbox=np.array([25.7, 40.3, 125.9, 240.1]),
            det_score=1.0,
            normed_embedding=np.array([0.0]),
        )
        result = _serialize(params=_default_params(), faces=[face])
        # x1=25, y1=40, x2=125, y2=240 -> [25, 40, 100, 200]
        assert result["faces"][0]["bounding_box"] == [25, 40, 100, 200]


class TestMaxNumFaces:

    def _make(self, n: int) -> List[SimpleNamespace]:
        return [
            _fake_face(
                bbox=np.array([float(i), 0.0, float(i + 10), 10.0]),
                det_score=1.0 - i * 0.1,
                normed_embedding=np.array([float(i)]),
            )
            for i in range(n)
        ]

    def test_limit_truncates(self):
        result = _serialize(params=_default_params(max_num_faces=2), faces=self._make(5))
        assert len(result["faces"]) == 2

    def test_zero_means_unlimited(self):
        result = _serialize(params=_default_params(max_num_faces=0), faces=self._make(4))
        assert len(result["faces"]) == 4

    def test_larger_than_detected(self):
        result = _serialize(params=_default_params(max_num_faces=10), faces=self._make(3))
        assert len(result["faces"]) == 3


class TestLandmarks:

    def _base_face(self, **extra):
        return _fake_face(
            bbox=np.array([0.0, 0.0, 10.0, 10.0]),
            det_score=1.0,
            normed_embedding=np.array([1.0]),
            **extra,
        )

    def test_no_return_landmarks_option_omits_field(self):
        face = self._base_face(kps=np.array([[1.0, 2.0], [3.0, 4.0]]))
        result = _serialize(params=_default_params(return_landmarks=False), faces=[face])
        assert "landmarks" not in result["faces"][0]

    def test_return_landmarks_but_no_data_omits_field(self):
        face = self._base_face()  # no kps / landmark_* attrs
        result = _serialize(params=_default_params(return_landmarks=True), faces=[face])
        assert "landmarks" not in result["faces"][0]

    def test_kps_when_only_kps_available(self):
        face = self._base_face(kps=np.array([[1.5, 2.5], [3.5, 4.5]]))
        result = _serialize(params=_default_params(return_landmarks=True), faces=[face])
        assert result["faces"][0]["landmarks"] == [{"x": 1, "y": 2}, {"x": 3, "y": 4}]

    def test_3d_68_preferred_over_kps(self):
        face = self._base_face(
            kps=np.array([[1.0, 2.0]]),
            landmark_3d_68=np.array([[10.0, 20.0], [30.0, 40.0]]),
        )
        result = _serialize(params=_default_params(return_landmarks=True), faces=[face])
        assert result["faces"][0]["landmarks"] == [{"x": 10, "y": 20}, {"x": 30, "y": 40}]

    def test_2d_106_preferred_over_all(self):
        face = self._base_face(
            kps=np.array([[1.0, 2.0]]),
            landmark_3d_68=np.array([[10.0, 20.0]]),
            landmark_2d_106=np.array([[100.0, 200.0], [110.0, 210.0]]),
        )
        result = _serialize(params=_default_params(return_landmarks=True), faces=[face])
        assert result["faces"][0]["landmarks"] == [{"x": 100, "y": 200}, {"x": 110, "y": 210}]


class TestGenderAge:

    def _base_face(self, **extra):
        return _fake_face(
            bbox=np.array([0.0, 0.0, 10.0, 10.0]),
            det_score=1.0,
            normed_embedding=np.array([1.0]),
            **extra,
        )

    def test_option_off_hides_fields(self):
        face = self._base_face(gender=1, age=30)
        result = _serialize(params=_default_params(return_gender_age=False), faces=[face])
        assert "gender" not in result["faces"][0]
        assert "age" not in result["faces"][0]

    def test_option_on_but_no_data_hides_fields(self):
        face = self._base_face()
        result = _serialize(params=_default_params(return_gender_age=True), faces=[face])
        assert "gender" not in result["faces"][0]
        assert "age" not in result["faces"][0]

    def test_male(self):
        face = self._base_face(gender=1, age=42)
        result = _serialize(params=_default_params(return_gender_age=True), faces=[face])
        assert result["faces"][0]["gender"] == "male"
        assert result["faces"][0]["age"] == 42

    def test_female(self):
        face = self._base_face(gender=0, age=25)
        result = _serialize(params=_default_params(return_gender_age=True), faces=[face])
        assert result["faces"][0]["gender"] == "female"
        assert result["faces"][0]["age"] == 25

    def test_only_gender_present(self):
        face = self._base_face(gender=1)
        result = _serialize(params=_default_params(return_gender_age=True), faces=[face])
        assert result["faces"][0]["gender"] == "male"
        assert "age" not in result["faces"][0]


class TestPose:
    """Pose is always emitted when present — no opt-in flag needed."""

    def _base_face(self, **extra):
        return _fake_face(
            bbox=np.array([0.0, 0.0, 10.0, 10.0]),
            det_score=1.0,
            normed_embedding=np.array([1.0]),
            **extra,
        )

    def test_pose_absent_by_default(self):
        result = _serialize(params=_default_params(), faces=[self._base_face()])
        assert "pose" not in result["faces"][0]

    def test_pose_serialized_when_present(self):
        # InsightFace stores pose as [pitch, yaw, roll] (landmark.py:111).
        face = self._base_face(pose=np.array([10.0, -5.0, 2.5]))
        result = _serialize(params=_default_params(), faces=[face])
        assert result["faces"][0]["pose"] == {"pitch": 10.0, "yaw": -5.0, "roll": 2.5}
