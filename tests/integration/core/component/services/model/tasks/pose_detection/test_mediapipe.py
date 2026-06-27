"""Tests for the MediaPipe pose-detection model task.

Verifies the I/O matrix for pose detection (model-task pattern, matches face-detection):

    | input \\           | result shape                       |
    |--------------------|------------------------------------|
    | PILImage           | Dict (single detection result)     |
    | List[PILImage]     | List[Dict]                         |
    | AsyncIterator[...] | AsyncIterator[Dict]                |

Also verifies model resolution (default sentinel → auto-download, explicit path → as-is)
and an end-to-end check against a real full-body image that asserts at least one pose is
detected with plausible keypoint coordinates.
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
from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.dsl.schema.action import PoseDetectionModelActionConfig
from mindor.dsl.schema.component import ModelComponentConfig


pytest.importorskip("mediapipe")
pytest.importorskip("numpy")

from mindor.core.component.services.model.tasks.pose_detection.custom.mediapipe import (
    BlazePosePoseDetectionTaskAction,
    BlazePosePoseDetectionTaskService,
)


# Full-body subject from the OpenCV samples repository (consistent with face-detection tests).
_SAMPLE_POSE_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/messi5.jpg"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_action_config(image: Any = "${input.image}", **kwargs: Any) -> PoseDetectionModelActionConfig:
    return TypeAdapter(PoseDetectionModelActionConfig).validate_python({ "image": image, **kwargs })


def _make_component_config(**kwargs: Any) -> ModelComponentConfig:
    raw: dict[str, Any] = {
        "type":   "model",
        "task":   "pose-detection",
        "driver": "custom",
        "family": "blazepose",
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
def mediapipe_model_path() -> str:
    """Resolve (download if needed) the default BlazePose .task model once per module."""
    service = BlazePosePoseDetectionTaskService(id="pose-detection", config=_make_component_config(), daemon=False)
    try:
        return asyncio.run(service._resolve_model_path())
    except (URLError, TimeoutError, OSError) as e:
        pytest.skip(f"Unable to fetch MediaPipe pose detection model: {e}")


@pytest.fixture
def make_action(mediapipe_model_path):
    def _factory(**kwargs: Any) -> BlazePosePoseDetectionTaskAction:
        return BlazePosePoseDetectionTaskAction(_make_action_config(**kwargs), mediapipe_model_path)
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

    @pytest.mark.anyio
    async def test_registers_list_result_source(self, make_action):
        images = [ _blank_image(), _blank_image() ]
        action = make_action(image="${input.images}")
        context = ComponentActionContext("run-list-source", { "images": images })

        await action.run(context, asyncio.get_running_loop())

        registered = context.sources["__global__"]["result"]
        assert isinstance(registered, list)
        assert len(registered) == 2


# -----------------------------------------------------------------------------
# AsyncIterator[PILImage] input
# -----------------------------------------------------------------------------

class TestAsyncIteratorInput:
    @pytest.mark.anyio
    async def test_returns_async_iterator_for_stream_input(self, make_action):
        images = [ _blank_image(), _blank_image(), _blank_image() ]
        action = make_action(image="${input.stream}")
        context = ComponentActionContext("run-stream", { "stream": _make_async_iter(images) })

        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)

        collected = await _collect(result)
        assert len(collected) == 3
        for entry in collected:
            _assert_detection_result(entry, width=64, height=48)


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
    async def test_invalid_num_poses_raises(self, make_action):
        action = make_action(num_poses=0)
        context = ComponentActionContext("run-bad-num", { "image": _blank_image() })

        with pytest.raises(ValueError, match="num_poses"):
            await action.run(context, asyncio.get_running_loop())


# -----------------------------------------------------------------------------
# Model resolution
# -----------------------------------------------------------------------------

class TestModelResolution:
    """`model` lives on the component config; service resolves it to a local .task path."""

    def test_default_sentinel_resolves_to_local_file(self, mediapipe_model_path):
        assert mediapipe_model_path.endswith(".task")

    def test_custom_local_model_path_used_directly(self, mediapipe_model_path):
        service = BlazePosePoseDetectionTaskService(
            id="pose-detection",
            config=_make_component_config(model=mediapipe_model_path),
            daemon=False,
        )
        assert asyncio.run(service._resolve_model_path()) == mediapipe_model_path

    def test_missing_local_model_path_raises(self):
        service = BlazePosePoseDetectionTaskService(
            id="pose-detection",
            config=_make_component_config(model="/nonexistent/pose_model.task"),
            daemon=False,
        )
        with pytest.raises(FileNotFoundError):
            asyncio.run(service._resolve_model_path())


# -----------------------------------------------------------------------------
# Output expression rendering
# -----------------------------------------------------------------------------

class TestOutputExpressionRendering:
    @pytest.mark.anyio
    async def test_passthrough_output_returns_raw_result(self, make_action):
        action = make_action(output="${result}")
        context = ComponentActionContext("run-passthrough", { "image": _blank_image() })

        result = await action.run(context, asyncio.get_running_loop())

        _assert_detection_result(result, width=64, height=48)

    @pytest.mark.anyio
    async def test_custom_output_extracts_field(self, make_action):
        action = make_action(output="${result.poses}")
        context = ComponentActionContext("run-extract", { "image": _blank_image() })

        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert result == []


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
            assert "keypoints" in pose
            assert isinstance(pose["keypoints"], list)
            # MediaPipe Pose returns 33 landmarks per detected pose.
            assert len(pose["keypoints"]) == 33

            for keypoint in pose["keypoints"]:
                assert set(keypoint.keys()) >= { "x", "y", "z", "visibility", "presence" }
                # 2D coordinates may slightly exceed the frame for out-of-frame body parts;
                # MediaPipe still returns predictions. Loosely bound around the image size.
                assert -width <= keypoint["x"] <= 2 * width
                assert -height <= keypoint["y"] <= 2 * height
                assert 0.0 <= keypoint["visibility"] <= 1.0
                assert 0.0 <= keypoint["presence"] <= 1.0

            assert "keypoints_3d" not in pose
            assert "segmentation_mask" not in pose

    @pytest.mark.anyio
    async def test_keypoints_3d_included_when_requested(self, make_action, sample_pose_image):
        action = make_action(include_keypoints_3d=True)
        context = ComponentActionContext("run-real-3d", { "image": sample_pose_image })

        result = await action.run(context, asyncio.get_running_loop())

        assert len(result["poses"]) >= 1
        for pose in result["poses"]:
            assert "keypoints_3d" in pose
            assert isinstance(pose["keypoints_3d"], list)
            assert len(pose["keypoints_3d"]) == 33
            for keypoint in pose["keypoints_3d"]:
                # World landmarks are in meters relative to the hip center.
                # Plausible human extent is well within ±2 m on each axis.
                assert -2.0 <= keypoint["x"] <= 2.0
                assert -2.0 <= keypoint["y"] <= 2.0
                assert -2.0 <= keypoint["z"] <= 2.0

    @pytest.mark.anyio
    async def test_segmentation_mask_included_when_requested(self, make_action, sample_pose_image):
        action = make_action(include_segmentation_mask=True)
        context = ComponentActionContext("run-real-mask", { "image": sample_pose_image })

        result = await action.run(context, asyncio.get_running_loop())

        assert len(result["poses"]) >= 1
        for pose in result["poses"]:
            assert "segmentation_mask" in pose
            mask_bytes = pose["segmentation_mask"]
            assert isinstance(mask_bytes, bytes)
            assert mask_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "Mask should be PNG-encoded"

    @pytest.mark.anyio
    async def test_keypoints_excluded_when_disabled(self, make_action, sample_pose_image):
        action = make_action(include_keypoints=False)
        context = ComponentActionContext("run-real-nokp", { "image": sample_pose_image })

        result = await action.run(context, asyncio.get_running_loop())

        assert len(result["poses"]) >= 1
        for pose in result["poses"]:
            assert "keypoints" not in pose

    @pytest.mark.anyio
    async def test_high_confidence_threshold_filters_results(self, make_action, sample_pose_image):
        action = make_action(min_confidence=0.99, min_presence_confidence=0.99)
        context = ComponentActionContext("run-real-strict", { "image": sample_pose_image })

        result = await action.run(context, asyncio.get_running_loop())

        # Extremely strict thresholds should drop detections on most images.
        assert result["poses"] == []
