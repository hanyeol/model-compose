"""Tests for ImageTextScoringTaskAction's I/O and scoring-mode matrix.

Each scoring job is a pair (ImageArrayValue, TextArrayValue). The outer shape
rules match face_tracking / text_reranking:

    is_single_input  = isinstance(image, ImageArrayValue)
    is_stream_input  = isinstance(image, AsyncIterator)

Within a single job, three modes are resolved by ``_resolve_scoring_mode``:
- pairwise: len(image) == len(text) → per-pair scores (scalar when both are 1)
- texts_to_image: len(image) == 1, len(text) > 1 → list across text axis
- images_to_text: len(text) == 1, len(image) > 1 → list across image axis
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional

import pytest
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.image_text_scoring.common import (
    ImageTextScore,
    ImageTextScoringTaskAction,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.variable.text import TextArrayValue
from mindor.dsl.schema.action import ImageTextScoringModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _img(label: str) -> PILImage.Image:
    image = PILImage.new("RGB", (2, 2))
    image.filename = label
    return image


def _label(image: PILImage.Image) -> str:
    return getattr(image, "filename", "?")


class _FakeScoringAction(ImageTextScoringTaskAction):
    """Deterministic ``_score`` stub.

    Returns scalar cosine ``float(len(images) + len(texts))`` for pairwise len-1,
    list of ``[0.1, 1.1, ...]`` otherwise. Softmax is a simple normalized stub.
    """

    def __init__(self, config: ImageTextScoringModelActionConfig):
        super().__init__(config)
        self.calls: List[Dict[str, Any]] = []

    async def _score(
        self,
        images: List[PILImage.Image],
        texts: List[str],
        mode: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        self.calls.append({
            "image_labels": [ _label(i) for i in images ],
            "texts": list(texts),
            "mode": mode,
            "params": params,
        })

        length = max(len(images), len(texts))
        if mode == "pairwise" and length == 1:
            return { "cosine": 0.1 }

        cosines = [ float(i) + 0.1 for i in range(length) ]
        result: Dict[str, Any] = { "cosine": cosines }
        if mode != "pairwise" and params["return_softmax"]:
            total = sum(cosines) or 1.0
            result["softmax"] = [ c / total for c in cosines ]
        return result


def _make_config(output: Any = None, batch_size: int = 2, **params: Any) -> ImageTextScoringModelActionConfig:
    raw: Dict[str, Any] = { "image": "${input.image}", "text": "${input.text}", "batch_size": batch_size }
    if output is not None:
        raw["output"] = output
    if params:
        raw["params"] = params
    return ImageTextScoringModelActionConfig.model_validate(raw)


async def _make_async_iter(items: List[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


class TestPairwiseSingle:
    """One image + one text → single ImageTextScore with scalar cosine."""

    @pytest.mark.anyio
    async def test_returns_single_score(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-1", { "image": _img("a"), "text": "cat" })

        result = await action.run(ctx)

        assert isinstance(result, ImageTextScore)
        assert result["cosine"] == pytest.approx(0.1)
        assert len(action.calls) == 1
        assert action.calls[0]["mode"] == "pairwise"
        assert action.calls[0]["image_labels"] == [ "a" ]
        assert action.calls[0]["texts"] == [ "cat" ]


class TestPairwiseMultiWithinJob:
    """One job with N images + N texts (list on each side)."""

    @pytest.mark.anyio
    async def test_returns_single_score_with_list_cosine(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-2", { "image": [ _img("a"), _img("b"), _img("c") ], "text": [ "x", "y", "z" ] })

        result = await action.run(ctx)

        # A single scoring job → single ImageTextScore (not a list of them).
        assert isinstance(result, ImageTextScore)
        assert result["cosine"] == pytest.approx([ 0.1, 1.1, 2.1 ])
        assert action.calls[0]["mode"] == "pairwise"


class TestTextsToImage:
    """One image, many texts → list across the text axis + softmax."""

    @pytest.mark.anyio
    async def test_shape_and_softmax_present(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-3", { "image": _img("a"), "text": [ "x", "y", "z" ] })

        result = await action.run(ctx)

        assert isinstance(result, ImageTextScore)
        assert isinstance(result["cosine"], list)
        assert len(result["cosine"]) == 3
        assert "softmax" in result
        assert action.calls[0]["mode"] == "texts_to_image"


class TestImagesToText:
    """Many images, one text → list across the image axis + softmax."""

    @pytest.mark.anyio
    async def test_shape_and_softmax_present(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-4", { "image": [ _img("a"), _img("b") ], "text": "cat" })

        result = await action.run(ctx)

        assert isinstance(result, ImageTextScore)
        assert isinstance(result["cosine"], list)
        assert len(result["cosine"]) == 2
        assert "softmax" in result
        assert action.calls[0]["mode"] == "images_to_text"


class TestSoftmaxDisabled:
    @pytest.mark.anyio
    async def test_cross_scoring_without_softmax(self):
        action = _FakeScoringAction(_make_config(return_softmax=False))
        ctx = ComponentActionContext("r-5", { "image": _img("a"), "text": [ "x", "y" ] })

        result = await action.run(ctx)

        assert "softmax" not in result


class TestStreamInput:
    """AsyncIterator of per-job arrays → AsyncIterator output."""

    @pytest.mark.anyio
    async def test_stream_input_yields_stream_output(self):
        action = _FakeScoringAction(_make_config())
        image_stream = _make_async_iter([ ImageArrayValue([ _img("a") ]), ImageArrayValue([ _img("b"), _img("c") ]) ])
        text_stream  = _make_async_iter([ TextArrayValue([ "x" ]), TextArrayValue([ "y" ]) ])
        ctx = ComponentActionContext("r-7", { "image": image_stream, "text": text_stream })

        result = await action.run(ctx)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 2
        assert all(isinstance(r, ImageTextScore) for r in items)
        assert action.calls[0]["mode"] == "pairwise"
        assert action.calls[1]["mode"] == "images_to_text"


class TestIncompatibleLengths:
    @pytest.mark.anyio
    async def test_raises_on_mismatch(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-8", { "image": [ _img("a"), _img("b") ], "text": [ "x", "y", "z" ] })

        with pytest.raises(ValueError, match="Incompatible image/text lengths"):
            await action.run(ctx)
