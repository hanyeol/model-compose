"""Tests for VideoTextScoringTaskAction's I/O and scoring-mode matrix.

A single call = a single scoring job carrying N videos × K texts. Within one
job the mode is resolved from the length pair:

- pairwise (N == K): one cosine per (video[i], text[i]) pair, scalar for len-1
- texts_to_video (N == 1, K > 1): list across the text axis + softmax
- videos_to_text (N > 1, K == 1): list across the video axis + softmax

Outer input shape:
- flat frames   → ImageArrayValue        → one video in this job
- nested frames → List[ImageArrayValue]  → N videos in this job
- stream        → async iterator         → one job per tick
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional

import pytest
from PIL import Image as PILImage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.video_text_scoring.common import (
    VideoTextScore,
    VideoTextScoringTaskAction,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.variable.text import TextArrayValue
from mindor.dsl.schema.action import VideoTextScoringModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _frame(label: str) -> PILImage.Image:
    image = PILImage.new("RGB", (2, 2))
    image.filename = label
    return image


def _label(frame: PILImage.Image) -> str:
    return getattr(frame, "filename", "?")


def _video(labels: List[str]) -> List[PILImage.Image]:
    return [ _frame(l) for l in labels ]


class _FakeScoringAction(VideoTextScoringTaskAction):
    """Deterministic ``_score`` stub.

    Returns scalar cosine ``0.1`` for single-pair pairwise, and lists keyed off
    the many-axis for every other mode. Softmax is a trivial normalized stub so
    tests can assert its presence and shape only.
    """

    def __init__(self, config: VideoTextScoringModelActionConfig):
        super().__init__(config)
        self.calls: List[Dict[str, Any]] = []

    async def _score(
        self,
        videos: List[List[PILImage.Image]],
        texts: List[str],
        mode: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        self.calls.append({
            "video_labels": [ [ _label(f) for f in video ] for video in videos ],
            "texts": list(texts),
            "mode": mode,
            "params": params,
        })

        if mode == "pairwise" and len(videos) == 1:
            return { "cosine": 0.1 }

        length = max(len(videos), len(texts))
        cosines = [ float(i) + 0.1 for i in range(length) ]
        result: Dict[str, Any] = { "cosine": cosines }
        if mode != "pairwise" and params["return_softmax"]:
            total = sum(cosines) or 1.0
            result["softmax"] = [ c / total for c in cosines ]
        return result


def _make_config(output: Any = None, batch_size: int = 1, **params: Any) -> VideoTextScoringModelActionConfig:
    raw: Dict[str, Any] = { "frames": "${input.frames}", "text": "${input.text}", "batch_size": batch_size }
    if output is not None:
        raw["output"] = output
    if params:
        raw["params"] = params
    return VideoTextScoringModelActionConfig.model_validate(raw)


async def _make_async_iter(items: List[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


class TestPairwiseSingleVideo:
    """One video + one caption → single VideoTextScore with scalar cosine."""

    @pytest.mark.anyio
    async def test_returns_single_score(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-1", { "frames": _video([ "f0", "f1", "f2" ]), "text": "cat" })

        result = await action.run(ctx)

        assert isinstance(result, VideoTextScore)
        assert result["cosine"] == pytest.approx(0.1)
        assert len(action.calls) == 1
        assert action.calls[0]["mode"] == "pairwise"
        assert action.calls[0]["video_labels"] == [ [ "f0", "f1", "f2" ] ]
        assert action.calls[0]["texts"] == [ "cat" ]


class TestTextsToVideo:
    """One video, many captions → list cosines + softmax."""

    @pytest.mark.anyio
    async def test_shape_and_softmax_present(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-2", { "frames": _video([ "f0", "f1" ]), "text": [ "x", "y", "z" ] })

        result = await action.run(ctx)

        assert isinstance(result, VideoTextScore)
        assert isinstance(result["cosine"], list)
        assert len(result["cosine"]) == 3
        assert "softmax" in result
        assert action.calls[0]["mode"] == "texts_to_video"


class TestVideosToText:
    """Many videos, one caption → list cosines + softmax across videos."""

    @pytest.mark.anyio
    async def test_shape_and_softmax_present(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-3", {
            "frames": [ _video([ "a0", "a1" ]), _video([ "b0", "b1" ]), _video([ "c0", "c1" ]) ],
            "text":   "cat",
        })

        result = await action.run(ctx)

        assert isinstance(result, VideoTextScore)
        assert isinstance(result["cosine"], list)
        assert len(result["cosine"]) == 3
        assert "softmax" in result
        assert action.calls[0]["mode"] == "videos_to_text"
        assert action.calls[0]["video_labels"] == [ [ "a0", "a1" ], [ "b0", "b1" ], [ "c0", "c1" ] ]


class TestPairwiseMultiVideo:
    """N videos + N captions (equal length) → pairwise list cosines."""

    @pytest.mark.anyio
    async def test_returns_list_cosine(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-4", {
            "frames": [ _video([ "a0" ]), _video([ "b0" ]) ],
            "text":   [ "cat", "dog" ],
        })

        result = await action.run(ctx)

        assert isinstance(result, VideoTextScore)
        assert result["cosine"] == pytest.approx([ 0.1, 1.1 ])
        assert action.calls[0]["mode"] == "pairwise"


class TestSoftmaxDisabled:
    @pytest.mark.anyio
    async def test_cross_scoring_without_softmax(self):
        action = _FakeScoringAction(_make_config(return_softmax=False))
        ctx = ComponentActionContext("r-5", { "frames": _video([ "f0" ]), "text": [ "x", "y" ] })

        result = await action.run(ctx)

        assert "softmax" not in result


class TestIncompatibleLengths:
    @pytest.mark.anyio
    async def test_raises_on_mismatch(self):
        action = _FakeScoringAction(_make_config())
        ctx = ComponentActionContext("r-6", {
            "frames": [ _video([ "a0" ]), _video([ "b0" ]) ],
            "text":   [ "x", "y", "z" ],
        })

        with pytest.raises(ValueError, match="Incompatible video/text lengths"):
            await action.run(ctx)


class TestStreamInput:
    """AsyncIterator of per-video frame arrays → AsyncIterator output, one job per tick."""

    @pytest.mark.anyio
    async def test_stream_input_yields_stream_output(self):
        action = _FakeScoringAction(_make_config())
        frames_stream = _make_async_iter([
            ImageArrayValue(_video([ "a0", "a1" ])),
            ImageArrayValue(_video([ "b0", "b1" ])),
        ])
        text_stream = _make_async_iter([ TextArrayValue([ "cat" ]), TextArrayValue([ "dog", "wolf" ]) ])
        ctx = ComponentActionContext("r-7", { "frames": frames_stream, "text": text_stream })

        result = await action.run(ctx)

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 2
        assert all(isinstance(r, VideoTextScore) for r in items)
        # Each tick scores exactly one video.
        assert action.calls[0]["mode"] == "pairwise"
        assert action.calls[1]["mode"] == "texts_to_video"
