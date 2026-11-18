"""Tests for ImageTextScoringTaskAction's I/O and scoring-mode matrix.

Each scoring job is a pair (ImageArrayValue, TextArrayValue). The outer shape
rules match face_tracking / text_reranking:

    is_single_input  = isinstance(image, ImageArrayValue)
    is_stream_input  = isinstance(image, AsyncIterator)

Within a single job, three modes are resolved by the driver:
- pairwise: len(image) == len(text) -> per-pair scores (scalar when both are 1)
- texts_to_image: len(image) == 1, len(text) > 1 -> list across text axis
- images_to_text: len(text) == 1, len(image) > 1 -> list across image axis

The core base class delegates to ``_score_batch`` and leaves mode resolution to
each concrete driver, so the fake action below replicates the driver-side
mode-resolution + per-pair scoring contract.
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


def _resolve_mode(num_images: int, num_texts: int) -> str:
    if num_images == 0 or num_texts == 0:
        raise ValueError(f"Image-text scoring input cannot be empty: images={num_images}, texts={num_texts}")
    if num_images == num_texts:
        return "pairwise"
    if num_images == 1:
        return "texts_to_image"
    if num_texts == 1:
        return "images_to_text"
    raise ValueError(
        f"Incompatible image/text lengths for scoring: images={num_images}, texts={num_texts}. "
        "Lengths must match, or one side must have length 1."
    )


class _FakeScoringAction(ImageTextScoringTaskAction):
    """Deterministic ``_score_batch`` stub.

    Replicates the driver-side mode resolution and per-job scoring so tests can
    assert over the resolved mode and output shape. Scalar cosine ``0.1`` for
    single-pair pairwise, and a list of ``[0.1, 1.1, ...]`` otherwise; softmax
    is a trivial normalized stub so tests can assert its presence and shape.
    """

    def __init__(self, config: ImageTextScoringModelActionConfig):
        super().__init__(config)
        self.calls: List[Dict[str, Any]] = []

    async def _score_batch(
        self,
        images: List[ImageArrayValue],
        texts: List[TextArrayValue],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[ImageTextScore]:
        # Mirror the Huggingface driver: collect each per-job ArrayValue down to
        # the underlying Python list before scoring.
        images_per_job = [ await array.collect() for array in images ]
        texts_per_job  = [ await array.collect() for array in texts  ]

        results: List[ImageTextScore] = []
        for job_images, job_texts in zip(images_per_job, texts_per_job):
            mode = _resolve_mode(len(job_images), len(job_texts))
            self.calls.append({
                "image_labels": [ _label(i) for i in job_images ],
                "texts": list(job_texts),
                "mode": mode,
                "params": params,
            })

            length = max(len(job_images), len(job_texts))
            if mode == "pairwise" and length == 1:
                results.append(ImageTextScore({ "cosine": 0.1 }))
                continue

            cosines = [ float(i) + 0.1 for i in range(length) ]
            score: Dict[str, Any] = { "cosine": cosines }
            if mode != "pairwise" and params["return_softmax"]:
                total = sum(cosines) or 1.0
                score["softmax"] = [ c / total for c in cosines ]
            results.append(ImageTextScore(score))

        return results


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
