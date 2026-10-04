"""Broadcasting matrix for model_3d x camera x lighting.

The core zip logic is driver-agnostic — these tests stub out `_render_batch`
and verify that per-item (model, camera, lighting) triples arrive in the
expected combinations: N=N=N, 1xN, Nx1, and streaming inputs.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model_3d_renderer.drivers.common import (
    Model3DRendererAction,
)
from mindor.dsl.schema.action.impl.model_3d_renderer import (
    Model3DRendererActionConfig,
    Model3DRendererCameraConfig,
    Model3DRendererLightingConfig,
)


class _RecordingAction(Model3DRendererAction):
    def __init__(self, config):
        super().__init__(config)
        self.triples: List[tuple] = []

    async def _render_batch(self, models, cameras, lightings, params, cancellation_token=None):
        for model, camera, lighting in zip(models, cameras, lightings):
            self.triples.append((model, camera, lighting))
        return [ f"img({model})" for model in models ]


def _make_context(models):
    context = MagicMock(spec=ComponentActionContext)
    context.cancellation_token = None

    async def render_variable(value, scope=None, skip_decode=False):
        # Mimic VariableRenderer: Pydantic models serialize to dicts, lists
        # recurse. The real renderer walks AST then normalizes model instances.
        return _normalize(value)

    async def render_scalar(value, cast, default=None):
        if value is None:
            return default
        if isinstance(cast, str):
            return value
        return cast(value)

    async def render_model_3d(value):
        return models

    async def render_array(value, single_as_array=False):
        from mindor.core.foundation.variable.array import ArrayValue
        if isinstance(value, list):
            return ArrayValue([ _dump(entry) for entry in value ])
        return ArrayValue([ _dump(value) ])

    context.render_variable = AsyncMock(side_effect=render_variable)
    context.render_scalar = AsyncMock(side_effect=render_scalar)
    context.render_model_3d = AsyncMock(side_effect=render_model_3d)
    context.render_array = AsyncMock(side_effect=render_array)
    context.register_source = MagicMock()
    return context


def _dump(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _normalize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [ _normalize(entry) for entry in value ]
    return value


def _config(**overrides) -> Model3DRendererActionConfig:
    data = {"model_3d": "placeholder"}
    data.update(overrides)
    return Model3DRendererActionConfig(**data)


@pytest.mark.anyio
async def test_single_model_single_camera_returns_scalar():
    context = _make_context("m0")
    config = _config(camera=Model3DRendererCameraConfig(yaw=10))
    action = _RecordingAction(config)

    result = await action.run(context)

    assert result == "img(m0)"
    assert action.triples == [("m0", {"yaw": 10.0, "pitch": 20.0, "roll": 0.0, "distance": None, "fov": 45.0, "up": "y"}, None)]


@pytest.mark.anyio
async def test_one_model_many_cameras_broadcasts_model():
    context = _make_context("m0")
    cameras = [
        Model3DRendererCameraConfig(yaw=0),
        Model3DRendererCameraConfig(yaw=45),
        Model3DRendererCameraConfig(yaw=90),
    ]
    action = _RecordingAction(_config(camera=cameras))

    result = await action.run(context)

    assert isinstance(result, list) and len(result) == 3
    assert [ triple[0] for triple in action.triples ] == ["m0", "m0", "m0"]
    assert [ triple[1]["yaw"] for triple in action.triples ] == [0.0, 45.0, 90.0]


@pytest.mark.anyio
async def test_many_models_one_camera_broadcasts_camera():
    context = _make_context(["m0", "m1", "m2"])
    camera = Model3DRendererCameraConfig(yaw=35)
    action = _RecordingAction(_config(model_3d=["a", "b", "c"], camera=camera))

    result = await action.run(context)

    assert isinstance(result, list) and len(result) == 3
    assert [ triple[0] for triple in action.triples ] == ["m0", "m1", "m2"]
    assert all(triple[1]["yaw"] == 35.0 for triple in action.triples)


@pytest.mark.anyio
async def test_equal_length_zips_models_and_cameras():
    context = _make_context(["m0", "m1", "m2"])
    cameras = [
        Model3DRendererCameraConfig(yaw=0),
        Model3DRendererCameraConfig(yaw=45),
        Model3DRendererCameraConfig(yaw=90),
    ]
    action = _RecordingAction(_config(model_3d=["a", "b", "c"], camera=cameras))

    await action.run(context)

    yaws = [ triple[1]["yaw"] for triple in action.triples ]
    assert yaws == [0.0, 45.0, 90.0]
    assert [ triple[0] for triple in action.triples ] == ["m0", "m1", "m2"]


@pytest.mark.anyio
async def test_mismatched_lengths_raise():
    context = _make_context(["m0", "m1"])
    cameras = [
        Model3DRendererCameraConfig(yaw=0),
        Model3DRendererCameraConfig(yaw=45),
        Model3DRendererCameraConfig(yaw=90),
    ]
    action = _RecordingAction(_config(model_3d=["a", "b"], camera=cameras))

    with pytest.raises(ValueError, match="different lengths"):
        await action.run(context)


@pytest.mark.anyio
async def test_lighting_axis_also_broadcasts():
    context = _make_context("m0")
    cameras = [Model3DRendererCameraConfig(yaw=y) for y in (0, 45)]
    lighting = Model3DRendererLightingConfig(preset="flat", ambient=0.5)
    action = _RecordingAction(_config(camera=cameras, lighting=lighting))

    await action.run(context)

    assert [ triple[2]["preset"] for triple in action.triples ] == ["flat", "flat"]


@pytest.mark.anyio
async def test_three_way_zip():
    context = _make_context(["m0", "m1"])
    cameras = [Model3DRendererCameraConfig(yaw=0), Model3DRendererCameraConfig(yaw=90)]
    lightings = [Model3DRendererLightingConfig(preset="flat"), Model3DRendererLightingConfig(preset="outdoor")]
    action = _RecordingAction(_config(model_3d=["a", "b"], camera=cameras, lighting=lightings))

    await action.run(context)

    assert [ triple[1]["yaw"] for triple in action.triples ] == [0.0, 90.0]
    assert [ triple[2]["preset"] for triple in action.triples ] == ["flat", "outdoor"]


@pytest.mark.anyio
async def test_streaming_model_input_yields_stream_output():
    async def _model_stream():
        for name in ("m0", "m1", "m2"):
            yield name

    context = _make_context(None)

    async def _render_model_3d(value):
        return _model_stream()

    context.render_model_3d = AsyncMock(side_effect=_render_model_3d)

    cameras = [Model3DRendererCameraConfig(yaw=y) for y in (0, 45, 90)]
    action = _RecordingAction(_config(camera=cameras))

    result = await action.run(context)

    collected = []
    async for item in result:
        collected.append(item)

    assert collected == ["img(m0)", "img(m1)", "img(m2)"]
    assert [ triple[1]["yaw"] for triple in action.triples ] == [0.0, 45.0, 90.0]
