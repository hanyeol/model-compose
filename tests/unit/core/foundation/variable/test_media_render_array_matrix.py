"""Semantic contract tests for the ``render_array`` matrix across
media-flavored renderers (text, audio, video, media, file, model_3d).

Each renderer is driven through the SAME matrix defined for images in
``test_image_render_array.py``. The matrix treats ``render_array``'s
outer axis as "batch of items" (``item_is_list=False``) or "batch of
groups" (``item_is_list=True``). Non-batch inputs collapse to one unit
wrapper; batch inputs become a Python list (or a ``StreamChunkIterator``).

Renderer-specific details — the wrapper class and a factory for one
"element" (bytes vs. str vs. StreamResource) — are injected per-renderer
through ``_MatrixSpec``. The matrix itself is renderer-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Type

import pytest

from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.variable.audio import (
    AudioArrayValue,
    AudioValueRenderer,
)
from mindor.core.foundation.variable.file import FileArrayValue, FileValueRenderer
from mindor.core.foundation.variable.media import (
    MediaArrayValue,
    MediaValueRenderer,
)
from mindor.core.foundation.variable.model_3d import (
    Model3DArrayValue,
    Model3DValueRenderer,
)
from mindor.core.foundation.variable.text import TextArrayValue, TextValueRenderer
from mindor.core.foundation.variable.video import (
    VideoArrayValue,
    VideoValueRenderer,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

async def collect(value: Any) -> List[Any]:
    return [item async for item in value]


async def async_iter(items):
    for item in items:
        yield item


# ---- Per-renderer spec ----


@dataclass
class _MatrixSpec:
    """Everything the matrix needs to drive one renderer type.

    - ``name``: pytest id.
    - ``make_renderer``: zero-arg factory for a fresh renderer.
    - ``array_cls``: the array-wrapper type (e.g. ``TextArrayValue``).
    - ``make_element``: zero-arg factory returning one renderer-specific
      input element (e.g. a ``str`` for text, ``bytes`` for audio).
    """

    name: str
    make_renderer: Callable[[], Any]
    array_cls: Type[Any]
    make_element: Callable[[], Any]


_SPECS = [
    _MatrixSpec(
        name="text",
        make_renderer=TextValueRenderer,
        array_cls=TextArrayValue,
        make_element=lambda: "hello",
    ),
    _MatrixSpec(
        name="audio",
        make_renderer=AudioValueRenderer,
        array_cls=AudioArrayValue,
        make_element=lambda: b"RIFF....WAVEfmt ",
    ),
    _MatrixSpec(
        name="video",
        make_renderer=VideoValueRenderer,
        array_cls=VideoArrayValue,
        make_element=lambda: b"\x00\x00\x00\x18ftypmp42",
    ),
    _MatrixSpec(
        name="media",
        make_renderer=MediaValueRenderer,
        array_cls=MediaArrayValue,
        make_element=lambda: b"\x00\x00\x00\x18ftypmp42",
    ),
    _MatrixSpec(
        name="model_3d",
        make_renderer=Model3DValueRenderer,
        array_cls=Model3DArrayValue,
        make_element=lambda: b"glTF\x02\x00\x00\x00",
    ),
    _MatrixSpec(
        name="file",
        make_renderer=FileValueRenderer,
        array_cls=FileArrayValue,
        # FileValueRenderer only accepts StreamResources — bytes would be dropped.
        make_element=lambda: BytesStreamResource(b"payload"),
    ),
]


_IDS = [spec.name for spec in _SPECS]


# ============================================================================
# item_is_list=False — element = one item, outer shape = batch of items
# ============================================================================


@pytest.mark.parametrize("spec", _SPECS, ids=_IDS)
class TestFlatBatch:
    """``item_is_list=False``: ``render_array`` returns a single
    ``XxxArrayValue`` (the batch) or ``List[XxxArrayValue]`` only when the
    input is an *explicit* batch of per-item arrays (nested list)."""

    @pytest.mark.anyio
    async def test_none_input_returns_none(self, spec: _MatrixSpec):
        result = await spec.make_renderer().render_array(None)
        assert result is None

    @pytest.mark.anyio
    async def test_single_element_without_lift_returns_none(self, spec: _MatrixSpec):
        result = await spec.make_renderer().render_array(spec.make_element())
        assert result is None

    @pytest.mark.anyio
    async def test_single_element_with_lift(self, spec: _MatrixSpec):
        element = spec.make_element()
        result = await spec.make_renderer().render_array(element, single_as_array=True)

        assert isinstance(result, spec.array_cls)
        assert result.is_single is True

        collected = await collect(result)
        assert len(collected) == 1

    @pytest.mark.anyio
    async def test_flat_list_is_one_batch(self, spec: _MatrixSpec):
        a, b = spec.make_element(), spec.make_element()
        result = await spec.make_renderer().render_array([a, b])

        assert isinstance(result, spec.array_cls)
        assert result.is_single is False

        collected = await collect(result)
        assert len(collected) == 2

    @pytest.mark.anyio
    async def test_flat_list_with_lift_is_still_one_batch_not_single(self, spec: _MatrixSpec):
        a, b = spec.make_element(), spec.make_element()
        result = await spec.make_renderer().render_array([a, b], single_as_array=True)

        assert isinstance(result, spec.array_cls)
        assert result.is_single is False

    @pytest.mark.anyio
    async def test_nested_list_is_batch_of_arrays(self, spec: _MatrixSpec):
        a, b, c = spec.make_element(), spec.make_element(), spec.make_element()
        result = await spec.make_renderer().render_array([[a, b], [c]])

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(x, spec.array_cls) for x in result)
        assert len(await collect(result[0])) == 2
        assert len(await collect(result[1])) == 1

    @pytest.mark.anyio
    async def test_empty_list_is_empty_batch(self, spec: _MatrixSpec):
        result = await spec.make_renderer().render_array([])

        assert isinstance(result, spec.array_cls)
        assert result.is_single is False
        assert await collect(result) == []


# ============================================================================
# item_is_list=True — element = one group, outer = batch of groups
# ============================================================================


@pytest.mark.parametrize("spec", _SPECS, ids=_IDS)
class TestGroupedBatch:
    """``item_is_list=True``: each batch element is a group (list of refs).
    Non-batch inputs collapse into one ``XxxArrayValue`` (unit); batch inputs
    produce a Python ``List[XxxArrayValue]``. No outer wrapper is added —
    ``ArrayValue`` is always a unit elsewhere in the codebase."""

    @pytest.mark.anyio
    async def test_none_input_returns_none(self, spec: _MatrixSpec):
        result = await spec.make_renderer().render_array(None, item_is_list=True)
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_without_lift_returns_none(self, spec: _MatrixSpec):
        result = await spec.make_renderer().render_array(
            spec.make_element(), item_is_list=True
        )
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_with_lift_is_list_of_one_group(self, spec: _MatrixSpec):
        element = spec.make_element()
        result = await spec.make_renderer().render_array(
            element, item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], spec.array_cls)
        assert result[0].is_single is True
        assert len(await collect(result[0])) == 1

    @pytest.mark.anyio
    async def test_flat_list_without_lift_returns_none(self, spec: _MatrixSpec):
        a, b = spec.make_element(), spec.make_element()
        result = await spec.make_renderer().render_array(
            [a, b], item_is_list=True
        )
        assert result is None

    @pytest.mark.anyio
    async def test_flat_list_with_lift_is_list_of_one_group(self, spec: _MatrixSpec):
        a, b = spec.make_element(), spec.make_element()
        result = await spec.make_renderer().render_array(
            [a, b], item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], spec.array_cls)
        assert result[0].is_single is False
        assert len(await collect(result[0])) == 2

    @pytest.mark.anyio
    async def test_nested_list_is_list_of_groups(self, spec: _MatrixSpec):
        a, b, c = spec.make_element(), spec.make_element(), spec.make_element()
        result = await spec.make_renderer().render_array(
            [[a, b], [c]], item_is_list=True
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(g, spec.array_cls) for g in result)
        assert len(await collect(result[0])) == 2
        assert len(await collect(result[1])) == 1

    @pytest.mark.anyio
    async def test_nested_list_with_lift_stays_a_list(self, spec: _MatrixSpec):
        a, b, c = spec.make_element(), spec.make_element(), spec.make_element()
        result = await spec.make_renderer().render_array(
            [[a, b], [c]], item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 2


# ============================================================================
# Streaming inputs
# ============================================================================


@pytest.mark.parametrize("spec", _SPECS, ids=_IDS)
class TestNonFragmentedStream:
    """A non-fragmented ``StreamChunkIterator`` is a batch stream: each chunk
    is one batch item. The return preserves the ``StreamChunkIterator`` type."""

    @pytest.mark.anyio
    async def test_flat_stream_preserves_chunk_count(self, spec: _MatrixSpec):
        a, b = spec.make_element(), spec.make_element()
        source = StreamChunkIterator(async_iter([a, b]))

        result = await spec.make_renderer().render_array(source)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2

    @pytest.mark.anyio
    async def test_flat_stream_with_lift_wraps_each_as_single_batch_item(self, spec: _MatrixSpec):
        a, b = spec.make_element(), spec.make_element()
        source = StreamChunkIterator(async_iter([a, b]))

        result = await spec.make_renderer().render_array(source, single_as_array=True)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2
        assert all(isinstance(c, spec.array_cls) for c in chunks)
        assert all(c.is_single is True for c in chunks)

    @pytest.mark.anyio
    async def test_grouped_stream_yields_rendered_groups(self, spec: _MatrixSpec):
        a, b, c = spec.make_element(), spec.make_element(), spec.make_element()
        source = StreamChunkIterator(async_iter([[a, b], [c]]))

        result = await spec.make_renderer().render_array(source, item_is_list=True)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2
        assert all(isinstance(ch, spec.array_cls) for ch in chunks)
        assert len(await collect(chunks[0])) == 2
        assert len(await collect(chunks[1])) == 1


@pytest.mark.parametrize("spec", _SPECS, ids=_IDS)
class TestFragmentedStream:
    """A fragmented ``StreamChunkIterator`` is one logical array delivered
    in pieces — one batch element only."""

    @pytest.mark.anyio
    async def test_fragmented_stream_is_one_batch_item(self, spec: _MatrixSpec):
        a, b = spec.make_element(), spec.make_element()
        source = StreamChunkIterator(async_iter([a, b]), is_fragmented=True)

        result = await spec.make_renderer().render_array(source)

        assert isinstance(result, spec.array_cls)
        assert result.is_single is False
        assert len(await collect(result)) == 2

    @pytest.mark.anyio
    async def test_fragmented_stream_item_is_list(self, spec: _MatrixSpec):
        """``item_is_list=True`` + fragmented stream: the whole stream is
        one group, returned as a one-element ``[XxxArrayValue]``."""
        a, b = spec.make_element(), spec.make_element()
        source = StreamChunkIterator(async_iter([a, b]), is_fragmented=True)

        result = await spec.make_renderer().render_array(
            source, item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], spec.array_cls)
        assert len(await collect(result[0])) == 2


# ============================================================================
# XxxArrayValue passthrough
# ============================================================================


@pytest.mark.parametrize("spec", _SPECS, ids=_IDS)
class TestArrayValuePassthrough:
    """An existing ``XxxArrayValue`` input must be preserved — not re-wrapped."""

    @pytest.mark.anyio
    async def test_passthrough_preserves_elements(self, spec: _MatrixSpec):
        a, b = spec.make_element(), spec.make_element()
        source = spec.array_cls([a, b])

        result = await spec.make_renderer().render_array(source)

        assert isinstance(result, spec.array_cls)
        assert len(await collect(result)) == 2

    @pytest.mark.anyio
    async def test_passthrough_preserves_is_single(self, spec: _MatrixSpec):
        a = spec.make_element()
        source = spec.array_cls([a], is_single=True)

        result = await spec.make_renderer().render_array(source)

        assert isinstance(result, spec.array_cls)
        assert result.is_single is True
