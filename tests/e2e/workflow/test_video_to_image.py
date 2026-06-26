"""Workflow-level integration tests for video_frame_extractor.

These tests build a real Workflow, run it through the workflow runner, and assert
the final output. They exercise:
- Stream mode end-to-end (extractor stream output → processor stream output)
- Collect mode passthrough (extractor dict propagated as workflow output)
- Single-frame mode (max_frame_count=1 → image_processor single image)

Pipeline cases that need array-pluck expression syntax (e.g. `frames[].image`) to
route extractor output into image_processor as a list are deferred until that syntax
is implemented — see `docs/specs/expression-array-pluck-spec.md`. Those cases are
already covered at the component layer in `test_video_frame_to_image_processor.py`.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from typing import Any, Dict, List

import pytest
from PIL import Image as PILImage

from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import ComponentInstances
from mindor.core.workflow.interrupt import InterruptHandler
from mindor.core.workflow.workflow import Workflow
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.dsl.schema.compose import ComposeConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_component_instances():
    """`create_component` caches instances in a module-level dict. Reset between tests
    so each workflow gets fresh components with its own config."""
    ComponentInstances.clear()
    yield
    ComponentInstances.clear()


@pytest.fixture(scope="module")
def sample_video():
    """Generate a small test video on disk."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        pytest.skip("opencv-python or numpy not installed")

    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    fps = 10
    total_frames = 6
    width, height = 32, 24

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))

    for i in range(total_frames):
        intensity = int((i / total_frames) * 255)
        frame = np.full((height, width, 3), intensity, dtype=np.uint8)
        writer.write(frame)

    writer.release()

    yield path

    if os.path.exists(path):
        os.unlink(path)


def _build_compose(workflow_def: Dict[str, Any], components_def: List[Dict[str, Any]]) -> ComposeConfig:
    """Validate a minimal ComposeConfig containing one workflow and the given components."""
    return ComposeConfig.model_validate({
        "controller": { "type": "http-server", "port": 8080 },
        "components": components_def,
        "workflows": [ workflow_def ],
    })


async def _run_workflow(compose: ComposeConfig, workflow_id: str, input: Dict[str, Any]) -> Any:
    workflow_config = next(w for w in compose.workflows if w.id == workflow_id)
    global_configs = ComponentGlobalConfigs(
        components=compose.components,
        listeners=compose.listeners,
        gateways=compose.gateways,
        workflows=compose.workflows,
    )
    workflow = Workflow(workflow_id, workflow_config, global_configs)
    return await workflow.run(
        task_id="test-task",
        input=input,
        interrupt_handler=InterruptHandler(),
    )


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


class TestWorkflowStreamMode:
    """End-to-end stream mode: extractor stream → processor stream."""

    @pytest.mark.skip(reason="Stream-to-stream pipelines need array-pluck expression (${result[].image}) routing; see docs/specs/expression-array-pluck-spec.md")
    @pytest.mark.anyio
    async def test_stream_to_stream(self, sample_video):
        """Extractor yields frames; processor consumes stream and yields grayscale stream."""
        components = [
            {
                "id": "extract",
                "type": "video-frame-extractor",
                "driver": "opencv",
                "action": {
                    "video": "${input.video}",
                    "output": "${result[].image}",
                },
            },
            {
                "id": "process",
                "type": "image-processor",
                "driver": "native",
                "action": {
                    "method": "grayscale",
                    "image": "${input.image}",
                    "output": "${result[]}",
                },
            },
        ]
        workflow = {
            "id": "stream-pipeline",
            "jobs": [
                {
                    "id": "extract-job",
                    "component": "extract",
                    "input": { "video": "${input.video}" },
                },
                {
                    "id": "process-job",
                    "component": "process",
                    "depends_on": [ "extract-job" ],
                    "input": { "image": "${jobs.extract-job.output}" },
                },
            ],
        }

        compose = _build_compose(workflow, components)
        result = await _run_workflow(compose, "stream-pipeline", { "video": FileStreamResource(sample_video, content_type="video/mp4") })

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 6
        assert all(isinstance(item, PILImage.Image) and item.mode == "L" for item in items)


class TestWorkflowCollectMode:
    """Extractor collect mode dict propagates through the workflow as-is."""

    @pytest.mark.anyio
    async def test_collect_mode_passthrough(self, sample_video):
        """Extractor collect mode returns a `List[{image, timestamp}]` that the workflow exposes unchanged.

        This validates the collect-mode contract at the workflow level: a single extractor job
        whose output is the raw frame list. Routing the list into a downstream image_processor
        would require array-pluck expression syntax (`frames[].image`), which is currently
        unsupported — see `docs/specs/expression-array-pluck-spec.md` for the planned syntax.
        """
        components = [
            {
                "id": "extract",
                "type": "video-frame-extractor",
                "driver": "opencv",
                "action": {
                    "video": "${input.video}",
                },
            },
        ]
        workflow = {
            "id": "collect-pipeline",
            "jobs": [
                {
                    "id": "extract-job",
                    "component": "extract",
                    "input": { "video": "${input.video}" },
                },
            ],
        }

        compose = _build_compose(workflow, components)
        result = await _run_workflow(compose, "collect-pipeline", { "video": FileStreamResource(sample_video, content_type="video/mp4") })

        assert isinstance(result, list)
        assert len(result) == 6
        assert all("image" in frame and "timestamp" in frame for frame in result)
        assert all(isinstance(frame["image"], PILImage.Image) for frame in result)


class TestWorkflowSingleFrame:
    """End-to-end single frame: extractor max_frame_count=1 → processor single."""

    @pytest.mark.anyio
    async def test_single_frame(self, sample_video):
        components = [
            {
                "id": "extract",
                "type": "video-frame-extractor",
                "driver": "opencv",
                "action": {
                    "video": "${input.video}",
                    "max_frame_count": 1,
                },
            },
            {
                "id": "process",
                "type": "image-processor",
                "driver": "native",
                "action": {
                    "method": "grayscale",
                    "image": "${input.image}",
                },
            },
        ]
        workflow = {
            "id": "single-pipeline",
            "jobs": [
                {
                    "id": "extract-job",
                    "component": "extract",
                    "input": { "video": "${input.video}" },
                },
                {
                    "id": "process-job",
                    "component": "process",
                    "depends_on": [ "extract-job" ],
                    "input": { "image": "${jobs.extract-job.output[0].image}" },
                },
            ],
        }

        compose = _build_compose(workflow, components)
        result = await _run_workflow(compose, "single-pipeline", { "video": FileStreamResource(sample_video, content_type="video/mp4") })

        assert isinstance(result, PILImage.Image)
        assert result.mode == "L"
