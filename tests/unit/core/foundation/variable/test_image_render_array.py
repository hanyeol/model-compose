"""Semantic contract tests for ``ImageValueRenderer.render_array``.

The matrix:

* ``item_is_list=False`` → one batch element is one image.
  - flat ``[img, ...]`` → one ``ImageArrayValue`` (unit).
  - nested ``[[img, ...], ...]`` → ``List[ImageArrayValue]`` (explicit batch).
* ``item_is_list=True`` → one batch element is a group (list of images).
  Output is **always** a Python list (or ``StreamChunkIterator``) — the batch
  axis is explicit, and a non-batch input + lift collapses to a one-element
  list ``[ImageArrayValue]``. ``ArrayValue`` is never used as an outer
  wrapper (it always means "one unit" elsewhere in the codebase).
* ``as_stream`` picks the element content type (``PIL.Image`` vs.
  ``ImageStreamResource``). It does not affect the outer shape.
"""

from __future__ import annotations

from typing import Any, List

import pytest
from PIL import Image as PILImage

from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.variable.image import (
    ImageArrayValue,
    ImageValueRenderer,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

def make_image(color: str = "red", size: tuple = (2, 2)) -> PILImage.Image:
    return PILImage.new("RGB", size, color=color)


async def collect(value: Any) -> List[Any]:
    """Collect an ``ImageArrayValue`` / async iter to a list."""
    return [item async for item in value]


async def async_iter(items):
    for item in items:
        yield item


# ============================================================================
# item_is_list=False — element = one image, outer shape = batch of images
# ============================================================================


class TestFlatBatch:
    """``item_is_list=False``: ``render_array`` returns a single
    ``ImageArrayValue`` (the batch) or ``List[ImageArrayValue]`` only when the
    input is an *explicit* batch of image-arrays (nested list)."""

    @pytest.mark.anyio
    async def test_none_input_returns_none(self):
        result = await ImageValueRenderer().render_array(None)
        assert result is None

    @pytest.mark.anyio
    async def test_single_image_without_lift_returns_none(self):
        """Scalar image without ``single_as_array`` is not a batch."""
        result = await ImageValueRenderer().render_array(make_image())
        assert result is None

    @pytest.mark.anyio
    async def test_single_image_with_lift(self):
        """``single_as_array=True`` lifts a scalar image to a one-image batch."""
        img = make_image()
        result = await ImageValueRenderer().render_array(img, single_as_array=True)

        assert isinstance(result, ImageArrayValue)
        assert result.is_single is True
        assert await collect(result) == [img]

    @pytest.mark.anyio
    async def test_flat_list_is_one_batch(self):
        """Flat ``[img, img]`` is ONE batch of two images — not two batches."""
        a, b = make_image("red"), make_image("blue")
        result = await ImageValueRenderer().render_array([a, b])

        assert isinstance(result, ImageArrayValue)
        assert result.is_single is False
        assert await collect(result) == [a, b]

    @pytest.mark.anyio
    async def test_flat_list_with_lift_is_still_one_batch_not_single(self):
        """An explicit flat list is already batch-shaped; ``single_as_array``
        must not flip ``is_single`` to True."""
        a, b = make_image("red"), make_image("blue")
        result = await ImageValueRenderer().render_array([a, b], single_as_array=True)

        assert isinstance(result, ImageArrayValue)
        assert result.is_single is False
        assert await collect(result) == [a, b]

    @pytest.mark.anyio
    async def test_nested_list_is_batch_of_image_arrays(self):
        """Nested ``[[img, ...], [img, ...]]`` is an explicit batch — one
        ``ImageArrayValue`` per batch item."""
        a, b, c = make_image("red"), make_image("green"), make_image("blue")
        result = await ImageValueRenderer().render_array([[a, b], [c]])

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(x, ImageArrayValue) for x in result)
        assert await collect(result[0]) == [a, b]
        assert await collect(result[1]) == [c]

    @pytest.mark.anyio
    async def test_empty_list_is_empty_batch(self):
        """An empty list is still an explicit batch — of zero images."""
        result = await ImageValueRenderer().render_array([])

        assert isinstance(result, ImageArrayValue)
        assert result.is_single is False
        assert await collect(result) == []


# ============================================================================
# item_is_list=True — element = one image group, outer = batch of groups
# ============================================================================


class TestGroupedBatch:
    """``item_is_list=True``: each batch element is a group (list of refs).
    Output is **always** a Python ``List[ImageArrayValue]`` — a non-batch
    input + lift collapses to a one-element list.
    """

    @pytest.mark.anyio
    async def test_none_input_returns_none(self):
        result = await ImageValueRenderer().render_array(None, item_is_list=True)
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_without_lift_returns_none(self):
        result = await ImageValueRenderer().render_array(
            make_image(), item_is_list=True
        )
        assert result is None

    @pytest.mark.anyio
    async def test_scalar_with_lift_is_list_of_one_group(self):
        img = make_image()
        result = await ImageValueRenderer().render_array(
            img, item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ImageArrayValue)
        assert result[0].is_single is True
        assert await collect(result[0]) == [img]

    @pytest.mark.anyio
    async def test_flat_list_without_lift_returns_none(self):
        a, b = make_image("red"), make_image("blue")
        result = await ImageValueRenderer().render_array([a, b], item_is_list=True)
        assert result is None

    @pytest.mark.anyio
    async def test_flat_list_with_lift_is_list_of_one_group(self):
        """Flat ``[img, img]`` + lift → one-element list containing one group
        of both images."""
        a, b = make_image("red"), make_image("blue")
        result = await ImageValueRenderer().render_array(
            [a, b], item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ImageArrayValue)
        assert result[0].is_single is False
        assert await collect(result[0]) == [a, b]

    @pytest.mark.anyio
    async def test_nested_list_is_list_of_groups(self):
        """Nested ``[[img, ...], [img, ...]]`` → ``List[ImageArrayValue]``
        (explicit batch of groups)."""
        a, b, c = make_image("red"), make_image("green"), make_image("blue")
        result = await ImageValueRenderer().render_array(
            [[a, b], [c]], item_is_list=True
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(x, ImageArrayValue) for x in result)
        assert await collect(result[0]) == [a, b]
        assert await collect(result[1]) == [c]

    @pytest.mark.anyio
    async def test_nested_list_with_lift_stays_a_list(self):
        """Explicit batch is unaffected by ``single_as_array``."""
        a, b, c = make_image("red"), make_image("green"), make_image("blue")
        result = await ImageValueRenderer().render_array(
            [[a, b], [c]], item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 2


# ============================================================================
# Streaming inputs — outer axis is the batch
# ============================================================================


class TestNonFragmentedStream:
    """A non-fragmented ``StreamChunkIterator`` is a batch stream: each chunk
    is one batch item (one image for ``item_is_list=False``, one group for
    ``item_is_list=True``). The return is a ``StreamChunkIterator`` whose
    chunks are the per-batch-item renderings."""

    @pytest.mark.anyio
    async def test_flat_stream_yields_rendered_batch_items(self):
        """``item_is_list=False``: each chunk is a single image, which (per
        the matrix) is a scalar input to the per-chunk render — with
        ``single_as_array=False`` the per-chunk result is None, so this
        combination is not meaningful. The stream must still *preserve
        chunk count* and type."""
        a, b = make_image("red"), make_image("blue")
        source = StreamChunkIterator(async_iter([a, b]))

        result = await ImageValueRenderer().render_array(source)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2

    @pytest.mark.anyio
    async def test_flat_stream_with_lift_wraps_each_image_as_single_batch_item(self):
        """``item_is_list=False`` + ``single_as_array=True``: each image chunk
        becomes a 1-image ``ImageArrayValue`` with ``is_single=True``."""
        a, b = make_image("red"), make_image("blue")
        source = StreamChunkIterator(async_iter([a, b]))

        result = await ImageValueRenderer().render_array(source, single_as_array=True)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2
        assert all(isinstance(c, ImageArrayValue) for c in chunks)
        assert all(c.is_single is True for c in chunks)
        assert await collect(chunks[0]) == [a]
        assert await collect(chunks[1]) == [b]

    @pytest.mark.anyio
    async def test_grouped_stream_yields_rendered_groups(self):
        """``item_is_list=True``: each chunk is one group (= one batch item).
        Per-chunk output is an ``ImageArrayValue``; the stream itself is the
        batch axis."""
        a, b, c = make_image("red"), make_image("green"), make_image("blue")
        source = StreamChunkIterator(async_iter([[a, b], [c]]))

        result = await ImageValueRenderer().render_array(source, item_is_list=True)

        assert isinstance(result, StreamChunkIterator)
        chunks = await collect(result)
        assert len(chunks) == 2
        assert all(isinstance(c, ImageArrayValue) for c in chunks)
        assert await collect(chunks[0]) == [a, b]
        assert await collect(chunks[1]) == [c]


class TestFragmentedStream:
    """A fragmented ``StreamChunkIterator`` is a single logical image array
    delivered in pieces — the outer axis is NOT a batch here. Return is a
    single ``ImageArrayValue`` whose source is the fragmented stream."""

    @pytest.mark.anyio
    async def test_fragmented_stream_is_one_batch_item(self):
        a, b = make_image("red"), make_image("blue")
        source = StreamChunkIterator(async_iter([a, b]), is_fragmented=True)

        result = await ImageValueRenderer().render_array(source)

        assert isinstance(result, ImageArrayValue)
        assert result.is_single is False
        assert await collect(result) == [a, b]

    @pytest.mark.anyio
    async def test_fragmented_stream_item_is_list(self):
        """``item_is_list=True`` + fragmented: the whole stream is one group,
        returned as a one-element ``[ImageArrayValue]``."""
        a, b = make_image("red"), make_image("blue")
        source = StreamChunkIterator(async_iter([a, b]), is_fragmented=True)

        result = await ImageValueRenderer().render_array(
            source, item_is_list=True, single_as_array=True
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ImageArrayValue)
        assert await collect(result[0]) == [a, b]


# ============================================================================
# ImageArrayValue passthrough
# ============================================================================


class TestImageArrayValuePassthrough:
    """An existing ``ImageArrayValue`` input must be preserved (lazily
    re-coerced to the requested element contract) — not re-wrapped."""

    @pytest.mark.anyio
    async def test_passthrough_preserves_elements(self):
        a, b = make_image("red"), make_image("blue")
        source = ImageArrayValue([a, b])

        result = await ImageValueRenderer().render_array(source)

        assert isinstance(result, ImageArrayValue)
        assert await collect(result) == [a, b]

    @pytest.mark.anyio
    async def test_passthrough_preserves_is_single(self):
        a = make_image("red")
        source = ImageArrayValue([a], is_single=True)

        result = await ImageValueRenderer().render_array(source)

        assert isinstance(result, ImageArrayValue)
        assert result.is_single is True


# ============================================================================
# as_stream — element content type only
# ============================================================================


class TestAsStream:
    """``as_stream=True`` makes each image element an ``ImageStreamResource``.
    It must not change the outer shape or ``is_single``."""

    @pytest.mark.anyio
    async def test_flat_list_elements_are_streams(self):
        a, b = make_image("red"), make_image("blue")
        result = await ImageValueRenderer().render_array([a, b], as_stream=True)

        assert isinstance(result, ImageArrayValue)
        assert result.is_single is False

        elements = await collect(result)
        assert all(isinstance(e, ImageStreamResource) for e in elements)

    @pytest.mark.anyio
    async def test_lifted_scalar_element_is_stream(self):
        img = make_image()
        result = await ImageValueRenderer().render_array(
            img, single_as_array=True, as_stream=True
        )

        assert isinstance(result, ImageArrayValue)
        assert result.is_single is True

        elements = await collect(result)
        assert len(elements) == 1
        assert isinstance(elements[0], ImageStreamResource)
