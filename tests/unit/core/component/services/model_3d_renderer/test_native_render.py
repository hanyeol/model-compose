"""Smoke tests for the native model-3d-renderer driver (moderngl backend)."""

from __future__ import annotations

import io
import os
import tempfile

import pytest

moderngl = pytest.importorskip("moderngl")
trimesh  = pytest.importorskip("trimesh")
PILImage = pytest.importorskip("PIL.Image")


DEFAULT_PARAMS = {
    "format": "png",
    "width": 128,
    "height": 128,
    "fit": "contain",
    "background": None,  # transparent
}

DEFAULT_CAMERA = {
    "yaw": 30.0,
    "pitch": 20.0,
    "roll": 0.0,
    "distance": None,
    "fov": 45.0,
    "up": "y",
}

DEFAULT_LIGHTING = {
    "preset": "studio",
    "ambient": 0.3,
    "directional": 1.0,
}


@pytest.fixture
def cube_glb_path():
    cube = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as handle:
        path = handle.name
    cube.export(path, file_type="glb")
    try:
        yield path
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def _render(path, params_overrides=None, camera_overrides=None, lighting_overrides=None):
    from mindor.core.component.services.model_3d_renderer.drivers.native import (
        NativeModel3DRendererAction,
    )

    params   = {**DEFAULT_PARAMS,   **(params_overrides   or {})}
    camera   = {**DEFAULT_CAMERA,   **(camera_overrides   or {})}
    lighting = {**DEFAULT_LIGHTING, **(lighting_overrides or {})}

    action = NativeModel3DRendererAction.__new__(NativeModel3DRendererAction)
    image = action._render_image(path, "glb", camera, lighting, params)

    buffer = io.BytesIO()
    image.save(buffer, "PNG" if params["format"] == "png" else "JPEG")
    return buffer.getvalue()


def test_renders_png_with_alpha(cube_glb_path):
    data = _render(cube_glb_path)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

    image = PILImage.open(io.BytesIO(data))
    image.load()
    assert image.size == (128, 128)
    assert image.mode == "RGBA"

    alphas = image.getchannel("A").getextrema()
    assert alphas[0] == 0, "transparent background should yield fully-transparent pixels"
    assert alphas[1] == 255, "cube pixels should be fully opaque"


def test_renders_jpeg_without_alpha(cube_glb_path):
    data = _render(cube_glb_path, params_overrides={"format": "jpeg", "background": (255, 255, 255, 255)})
    assert data[:3] == b"\xff\xd8\xff"

    image = PILImage.open(io.BytesIO(data))
    image.load()
    assert image.mode == "RGB"


def test_explicit_distance_is_respected(cube_glb_path):
    near = _render(cube_glb_path, camera_overrides={"distance": 1.5})
    far  = _render(cube_glb_path, camera_overrides={"distance": 10.0})

    def _opaque_pixel_count(data):
        image = PILImage.open(io.BytesIO(data))
        image.load()
        return sum(1 for a in image.getchannel("A").getdata() if a > 0)

    assert _opaque_pixel_count(near) > _opaque_pixel_count(far)
