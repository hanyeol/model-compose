"""Tests for the MediaPipe face-detection model task.

Verifies the I/O matrix for face detection (model-task pattern, matches video-converter):

    | input \\           | result shape                       |
    |--------------------|------------------------------------|
    | PILImage           | Dict (single detection result)     |
    | List[PILImage]     | List[Dict]                         |
    | AsyncIterator[...] | AsyncIterator[Dict]                |

Also verifies model resolution (default sentinel → auto-download, explicit path → as-is)
and an end-to-end check against a real human portrait that asserts at least one face is
detected with a plausible bounding box.
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
from mindor.dsl.schema.action import FaceDetectionModelActionConfig
from mindor.dsl.schema.component import ModelComponentConfig


pytest.importorskip("mediapipe")
pytest.importorskip("numpy")

from mindor.core.component.services.model.tasks.face_detection.custom.mediapipe import (
    BlazeFaceFaceDetectionTaskAction,
    BlazeFaceFaceDetectionTaskService,
)


_SAMPLE_FACE_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/lena.jpg"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_action_config(image: Any = "${input.image}", **kwargs: Any) -> FaceDetectionModelActionConfig:
    return TypeAdapter(FaceDetectionModelActionConfig).validate_python({ "image": image, **kwargs })


def _make_component_config(**kwargs: Any) -> ModelComponentConfig:
    raw: dict[str, Any] = {
        "type":   "model",
        "task":   "face-detection",
        "driver": "custom",
        "family": "blazeface",
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
    assert set(result.keys()) >= { "faces", "width", "height" }
    assert result["width"] == width
    assert result["height"] == height
    assert isinstance(result["faces"], list)


@pytest.fixture(scope="module")
def mediapipe_model_path() -> str:
    """Resolve (download if needed) the default BlazeFace .tflite model once per module."""
    service = BlazeFaceFaceDetectionTaskService(id="face-detection", config=_make_component_config(), daemon=False)
    try:
        return asyncio.run(service._resolve_model_path())
    except (URLError, TimeoutError, OSError) as e:
        pytest.skip(f"Unable to fetch MediaPipe face detection model: {e}")


@pytest.fixture
def make_action(mediapipe_model_path):
    def _factory(**kwargs: Any) -> BlazeFaceFaceDetectionTaskAction:
        return BlazeFaceFaceDetectionTaskAction(_make_action_config(**kwargs), mediapipe_model_path)
    return _factory


@pytest.fixture(scope="module")
def sample_face_image() -> PILImage.Image:
    request = Request(_SAMPLE_FACE_URL, headers={ "User-Agent": "model-compose-tests/1.0" })

    try:
        with urlopen(request, timeout=10) as response:
            data = response.read()
    except (URLError, TimeoutError, OSError) as e:
        pytest.skip(f"Unable to download sample face image: {e}")

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
    async def test_blank_image_yields_no_detections(self, make_action):
        action = make_action()
        context = ComponentActionContext("run-blank", { "image": _blank_image() })

        result = await action.run(context, asyncio.get_running_loop())

        assert result["faces"] == []

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
            assert entry["faces"] == []

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


# -----------------------------------------------------------------------------
# Model resolution
# -----------------------------------------------------------------------------

class TestModelResolution:
    """`model` lives on the component config; service resolves it to a local .tflite path."""

    def test_default_sentinel_resolves_to_local_file(self, mediapipe_model_path):
        assert mediapipe_model_path.endswith(".tflite")

    def test_custom_local_model_path_used_directly(self, mediapipe_model_path):
        service = BlazeFaceFaceDetectionTaskService(
            id="face-detection",
            config=_make_component_config(model=mediapipe_model_path),
            daemon=False,
        )
        assert asyncio.run(service._resolve_model_path()) == mediapipe_model_path

    def test_missing_local_model_path_raises(self):
        service = BlazeFaceFaceDetectionTaskService(
            id="face-detection",
            config=_make_component_config(model="/nonexistent/model.tflite"),
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
        action = make_action(output="${result.faces}")
        context = ComponentActionContext("run-extract", { "image": _blank_image() })

        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert result == []


# -----------------------------------------------------------------------------
# End-to-end with a real human face
# -----------------------------------------------------------------------------

class TestRealHumanFace:
    @pytest.mark.anyio
    async def test_detects_face_in_real_portrait(self, make_action, sample_face_image):
        width, height = sample_face_image.size

        action = make_action(min_confidence=0.5)
        context = ComponentActionContext("run-real", { "image": sample_face_image })

        result = await action.run(context, asyncio.get_running_loop())

        _assert_detection_result(result, width=width, height=height)
        assert len(result["faces"]) >= 1, "Expected at least one face in the sample portrait"

        for face in result["faces"]:
            assert set(face.keys()) >= { "bounding_box", "score" }
            x, y, w, h = face["bounding_box"]
            assert 0 <= x < width
            assert 0 <= y < height
            assert w > 0 and h > 0
            assert 0.0 <= face["score"] <= 1.0
            assert "landmarks" not in face

    @pytest.mark.anyio
    async def test_landmarks_included_when_requested(self, make_action, sample_face_image):
        action = make_action(return_landmarks=True)
        context = ComponentActionContext("run-real-landmarks", { "image": sample_face_image })

        result = await action.run(context, asyncio.get_running_loop())

        assert len(result["faces"]) >= 1

        width, height = sample_face_image.size
        for face in result["faces"]:
            assert "landmarks" in face
            assert isinstance(face["landmarks"], list)
            assert len(face["landmarks"]) > 0
            for kp in face["landmarks"]:
                assert 0 <= kp["x"] <= width
                assert 0 <= kp["y"] <= height

    @pytest.mark.anyio
    async def test_high_confidence_threshold_filters_results(self, make_action, sample_face_image):
        action = make_action(min_confidence=0.99)
        context = ComponentActionContext("run-real-strict", { "image": sample_face_image })

        result = await action.run(context, asyncio.get_running_loop())

        assert result["faces"] == []
