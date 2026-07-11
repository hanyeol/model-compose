"""Tests for the YOLO pose-detection model task.

Verifies the I/O matrix for pose detection (mirrors test_mediapipe.py):

    | input \\           | result shape                       |
    |--------------------|------------------------------------|
    | PILImage           | Dict (single detection result)     |
    | List[PILImage]     | List[Dict]                         |
    | AsyncIterator[...] | AsyncIterator[Dict]                |

Also verifies model resolution (default sentinel → auto-download, explicit path → as-is),
YOLO-specific validator (rejects return_keypoints_3d / return_segmentation_mask), and an
end-to-end check against a real full-body image with plausible keypoint coordinates.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from io import BytesIO
from typing import Any, List
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest

from PIL import Image as PILImage
from pydantic import TypeAdapter, ValidationError

from mindor.core.component.context import ComponentActionContext
from mindor.dsl.schema.action import PoseDetectionModelActionConfig
from mindor.dsl.schema.component import ModelComponentConfig


pytest.importorskip("ultralytics")
pytest.importorskip("numpy")

from mindor.core.component.services.model.tasks.pose_detection.custom.yolo import (
    YoloPoseDetectionTaskAction,
    YoloPoseDetectionTaskService,
)
from mindor.dsl.schema.action.impl.model.tasks.pose_detection.impl.custom.impl.yolo import (
    YoloPoseDetectionModelActionConfig,
)


# Full-body subject from the OpenCV samples repository (consistent with mediapipe tests).
_SAMPLE_POSE_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/messi5.jpg"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_action_config(image: Any = "${input.image}", **kwargs: Any) -> PoseDetectionModelActionConfig:
    raw: dict[str, Any] = { "family": "yolo", "image": image, **kwargs }
    return TypeAdapter(PoseDetectionModelActionConfig).validate_python(raw)


def _make_component_config(**kwargs: Any) -> ModelComponentConfig:
    raw: dict[str, Any] = {
        "type":   "model",
        "task":   "pose-detection",
        "driver": "custom",
        "family": "yolo",
        **kwargs,
    }
    return TypeAdapter(ModelComponentConfig).validate_python(raw)


def _blank_image(size=(64, 48), color=(0, 0, 0)) -> PILImage.Image:
    return PILImage.new("RGB", size, color)


async def _make_async_iter(images: List[PILImage.Image]) -> AsyncIterator[PILImage.Image]:
    for image in images:
        yield image


async def _collect(stream: AsyncIterator[Any]) -> list:
    return [ item async for item in stream ]


def _assert_detection_result(result: Any, width: int, height: int) -> None:
    assert isinstance(result, dict)
    assert set(result.keys()) >= { "poses", "width", "height" }
    assert result["width"] == width
    assert result["height"] == height
    assert isinstance(result["poses"], list)


@pytest.fixture(scope="module")
def yolo_model_path() -> str:
    """Resolve (download if needed) the default YOLO pose weights once per module."""
    service = YoloPoseDetectionTaskService(id="pose-detection", config=_make_component_config(), daemon=False)
    try:
        return asyncio.run(service._resolve_model_path())
    except (URLError, TimeoutError, OSError) as e:
        pytest.skip(f"Unable to fetch YOLO pose detection model: {e}")


@pytest.fixture
def make_action(yolo_model_path):
    from ultralytics import YOLO

    model = YOLO(yolo_model_path)

    def _factory(**kwargs: Any) -> YoloPoseDetectionTaskAction:
        return YoloPoseDetectionTaskAction(_make_action_config(**kwargs), model)

    return _factory


@pytest.fixture(scope="module")
def sample_pose_image() -> PILImage.Image:
    request = Request(_SAMPLE_POSE_URL, headers={ "User-Agent": "model-compose-tests/1.0" })

    try:
        with urlopen(request, timeout=10) as response:
            data = response.read()
    except (URLError, TimeoutError, OSError) as e:
        pytest.skip(f"Unable to download sample pose image: {e}")

    image = PILImage.open(BytesIO(data)).convert("RGB")
    image.load()

    return image


# -----------------------------------------------------------------------------
# Single PIL image input
# -----------------------------------------------------------------------------

class TestSingleImageInput:
    @pytest.mark.anyio
    async def test_returns_single_dict_for_single_image(self, make_action):
        image = _blank_image(size=(64, 48))
        action = make_action()
        context = ComponentActionContext("run-single", { "image": image })

        result = await action.run(context, asyncio.get_running_loop())

        _assert_detection_result(result, width=64, height=48)

    @pytest.mark.anyio
    async def test_blank_image_yields_no_poses(self, make_action):
        action = make_action()
        context = ComponentActionContext("run-blank", { "image": _blank_image() })

        result = await action.run(context, asyncio.get_running_loop())

        assert result["poses"] == []

    @pytest.mark.anyio
    async def test_registers_result_source(self, make_action):
        action = make_action()
        context = ComponentActionContext("run-source", { "image": _blank_image() })

        await action.run(context, asyncio.get_running_loop())

        assert "result" in context.sources["__global__"]
        assert isinstance(context.sources["__global__"]["result"], dict)


# -----------------------------------------------------------------------------
# List[PILImage] input
# -----------------------------------------------------------------------------

class TestListImageInput:
    @pytest.mark.anyio
    async def test_returns_list_of_dicts_for_list_input(self, make_action):
        images = [ _blank_image(), _blank_image(), _blank_image() ]
        action = make_action(image="${input.images}")
        context = ComponentActionContext("run-list", { "images": images })

        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3
        for entry in result:
            _assert_detection_result(entry, width=64, height=48)
            assert entry["poses"] == []

    @pytest.mark.anyio
    async def test_empty_list_returns_empty_list(self, make_action):
        action = make_action(image="${input.images}")
        context = ComponentActionContext("run-empty", { "images": [] })

        result = await action.run(context, asyncio.get_running_loop())

        assert result == []


# -----------------------------------------------------------------------------
# AsyncIterator[PILImage] input
# -----------------------------------------------------------------------------

class TestAsyncIteratorInput:
    @pytest.mark.anyio
    async def test_returns_async_iterator_for_stream_input(self, make_action):
        images = [ _blank_image(), _blank_image() ]
        action = make_action(image="${input.stream}")
        context = ComponentActionContext("run-stream", { "stream": _make_async_iter(images) })

        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)

        collected = await _collect(result)
        assert len(collected) == 2
        for entry in collected:
            _assert_detection_result(entry, width=64, height=48)


# -----------------------------------------------------------------------------
# YOLO-specific validators
# -----------------------------------------------------------------------------

class TestYoloValidators:
    def test_return_keypoints_3d_rejected(self):
        with pytest.raises(ValidationError, match="return_keypoints_3d"):
            YoloPoseDetectionModelActionConfig(image="${input.image}", return_keypoints_3d=True)

    def test_return_segmentation_mask_rejected(self):
        with pytest.raises(ValidationError, match="return_segmentation_mask"):
            YoloPoseDetectionModelActionConfig(image="${input.image}", return_segmentation_mask=True)


# -----------------------------------------------------------------------------
# Detection options
# -----------------------------------------------------------------------------

class TestDetectionOptions:
    @pytest.mark.anyio
    async def test_invalid_min_confidence_raises(self, make_action):
        action = make_action(min_confidence=1.5)
        context = ComponentActionContext("run-bad-conf", { "image": _blank_image() })

        with pytest.raises(ValueError, match="min_confidence"):
            await action.run(context, asyncio.get_running_loop())

    @pytest.mark.anyio
    async def test_invalid_max_pose_count_raises(self, make_action):
        action = make_action(max_pose_count=0)
        context = ComponentActionContext("run-bad-num", { "image": _blank_image() })

        with pytest.raises(ValueError, match="max_pose_count"):
            await action.run(context, asyncio.get_running_loop())


# -----------------------------------------------------------------------------
# Model resolution
# -----------------------------------------------------------------------------

class TestModelResolution:
    def test_default_sentinel_resolves_to_local_file(self, yolo_model_path):
        assert yolo_model_path.endswith(".pt")

    def test_custom_local_model_path_used_directly(self, yolo_model_path):
        service = YoloPoseDetectionTaskService(
            id="pose-detection",
            config=_make_component_config(model=yolo_model_path),
            daemon=False,
        )
        assert asyncio.run(service._resolve_model_path()) == yolo_model_path

    def test_missing_local_model_path_raises(self):
        service = YoloPoseDetectionTaskService(
            id="pose-detection",
            config=_make_component_config(model="/nonexistent/pose_model.pt"),
            daemon=False,
        )
        with pytest.raises(FileNotFoundError):
            asyncio.run(service._resolve_model_path())


# -----------------------------------------------------------------------------
# End-to-end with a real full-body image
# -----------------------------------------------------------------------------

class TestRealHumanPose:
    @pytest.mark.anyio
    async def test_detects_pose_in_real_image(self, make_action, sample_pose_image):
        width, height = sample_pose_image.size

        action = make_action(min_confidence=0.5)
        context = ComponentActionContext("run-real", { "image": sample_pose_image })

        result = await action.run(context, asyncio.get_running_loop())

        _assert_detection_result(result, width=width, height=height)
        assert len(result["poses"]) >= 1, "Expected at least one pose in the sample image"

        for pose in result["poses"]:
            assert "bounding_box" in pose
            x, y, w, h = pose["bounding_box"]
            assert w > 0 and h > 0

            assert "score" in pose
            assert 0.0 <= pose["score"] <= 1.0

            assert "keypoints" in pose
            assert isinstance(pose["keypoints"], list)
            # YOLO / COCO topology returns 17 keypoints per detected pose.
            assert len(pose["keypoints"]) == 17

            for keypoint in pose["keypoints"]:
                assert set(keypoint.keys()) == { "x", "y", "visibility" }
                assert -width <= keypoint["x"] <= 2 * width
                assert -height <= keypoint["y"] <= 2 * height
                assert 0.0 <= keypoint["visibility"] <= 1.0

            assert "keypoints_3d" not in pose
            assert "segmentation_mask" not in pose


# -----------------------------------------------------------------------------
# OpenPose keypoints and skeleton image
# -----------------------------------------------------------------------------

class TestOpenposeAndSkeleton:
    @pytest.mark.anyio
    async def test_openpose_keypoints_returned_when_requested(self, make_action, sample_pose_image):
        action = make_action(return_openpose_keypoints=True)
        context = ComponentActionContext("run-op-kp", { "image": sample_pose_image })

        result = await action.run(context, asyncio.get_running_loop())

        assert len(result["poses"]) >= 1
        for pose in result["poses"]:
            assert "openpose_keypoints" in pose
            assert len(pose["openpose_keypoints"]) == 18
            for keypoint in pose["openpose_keypoints"]:
                assert set(keypoint.keys()) == { "x", "y", "visibility" }

    @pytest.mark.anyio
    async def test_skeleton_image_natural_layout(self, make_action, sample_pose_image):
        width, height = sample_pose_image.size
        action = make_action(return_skeleton_image=True)
        context = ComponentActionContext("run-skel-natural", { "image": sample_pose_image })

        result = await action.run(context, asyncio.get_running_loop())

        assert len(result["poses"]) >= 1
        for pose in result["poses"]:
            skeleton = pose["skeleton_image"]
            assert isinstance(skeleton, PILImage.Image)
            assert skeleton.size == (width, height)
            assert skeleton.getextrema() != ((0, 0), (0, 0), (0, 0))

    @pytest.mark.anyio
    async def test_skeleton_image_openpose_layout(self, make_action, sample_pose_image):
        width, height = sample_pose_image.size
        action = make_action(return_skeleton_image=True, skeleton_format="openpose")
        context = ComponentActionContext("run-skel-op", { "image": sample_pose_image })

        result = await action.run(context, asyncio.get_running_loop())

        assert len(result["poses"]) >= 1
        for pose in result["poses"]:
            assert isinstance(pose["skeleton_image"], PILImage.Image)
            assert pose["skeleton_image"].size == (width, height)

    @pytest.mark.anyio
    async def test_invalid_skeleton_format_raises(self, make_action):
        action = make_action(return_skeleton_image=True, skeleton_format="invalid")
        context = ComponentActionContext("run-skel-bad", { "image": _blank_image() })

        with pytest.raises(ValueError, match="skeleton_format"):
            await action.run(context, asyncio.get_running_loop())
