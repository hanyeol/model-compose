"""Tests for the TextRerankingTaskAction's I/O matrix.

text_reranking has no `streaming` config (the model API is batch-only) and
also no chunk-level streaming inside a single reranking job — each tick emits
one completed ranked list. The output-shape rule mirrors the other atomic
model tasks:

    is_single_input  = not isinstance(query, (list, StreamIterator, AsyncIterator))
    is_direct_output = output is empty or output == "${result}"

Stream mode (query is AsyncIterator) -> AsyncIterator yielding one raw
ranked-list per query. Chunks are NOT wrapped in StreamChunkIterator.

Collect mode -> single ranked-list (single query) or list of ranked-lists
(list of queries). Each ranked-list is the raw `_build_ranked_result` return
value (a list of `{index, score}` dicts).

Tests cover:
- Query shapes: single str / List[str] / AsyncIterator[str]
- Options: top_k / score_threshold
- Driver receives one (query, texts) pair per `_rerank` call
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.text_reranking.common import TextRerankingTaskAction
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.variable.text import TextArrayValue
from mindor.dsl.schema.action import TextRerankingModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeRerankingAction(TextRerankingTaskAction):
    """Deterministic ``_rerank`` for testing.

    Each (query, text) pair scores as ``-abs(len(text) - len(query))`` so that
    texts whose length is closest to the query length rank highest. This makes
    the sort / top_k / threshold behavior predictable.
    """

    def __init__(self, config: TextRerankingModelActionConfig):
        super().__init__(config)
        self.calls: List[Dict[str, Any]] = []

    async def _rerank(
        self,
        query: str,
        texts: TextArrayValue,
        batch_size: int,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[float]:
        collected = await texts.collect()
        texts_list = [ str(text) for text in collected ]
        self.calls.append({
            "query": query,
            "texts": texts_list,
            "batch_size": batch_size,
            "params": params,
        })
        return [ -float(abs(len(text) - len(query))) for text in texts_list ]


def _make_config(
    query_expr: Any,
    texts_expr: Any,
    output: Any = None,
    top_k: Any = None,
    score_threshold: Any = None,
    batch_size: int = 32,
) -> TextRerankingModelActionConfig:
    raw: dict = {
        "query": query_expr,
        "texts": texts_expr,
        "batch_size": batch_size,
    }
    if output is not None:
        raw["output"] = output
    if top_k is not None:
        raw["top_k"] = top_k
    if score_threshold is not None:
        raw["score_threshold"] = score_threshold
    return TextRerankingModelActionConfig.model_validate(raw)


async def _make_async_iter(items: List[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


class TestSingleQueryStringTexts:
    """Single query str + List[str] texts -> single raw ranked list."""

    @pytest.mark.anyio
    async def test_single_query_returns_single_result(self):
        # query "hello" (len 5) vs texts with lengths [2, 11, 7, 5] -> scores [-3, -6, -2, 0].
        # After sort desc: hey!! (0), goodbye (-2), hi (-3), hello world (-6).
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.texts}"))
        ctx    = ComponentActionContext("r-1", { "query": "hello", "texts": [ "hi", "hello world", "goodbye", "hey!!" ] })
        result = await action.run(ctx)

        # Result is the raw ranked list (not wrapped in StreamChunkIterator, not
        # wrapped in an outer list).
        assert isinstance(result, list)
        assert not isinstance(result, StreamChunkIterator)
        assert result == [
            { "index": 3, "score": -0.0 },
            { "index": 2, "score": -2.0 },
            { "index": 0, "score": -3.0 },
            { "index": 1, "score": -6.0 },
        ]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_ranked_list(self):
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.texts}", output="${result}"))
        ctx    = ComponentActionContext("r-2", { "query": "hi", "texts": [ "a", "hi", "bcd" ] })
        result = await action.run(ctx)

        assert isinstance(result, list)
        assert result[0] == { "index": 1, "score": -0.0 }


class TestTopKAndThreshold:
    @pytest.mark.anyio
    async def test_top_k_trims_result(self):
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.texts}", top_k=2))
        ctx    = ComponentActionContext("r-3", { "query": "hello", "texts": [ "hi", "hello!", "x", "hello world", "hey!!" ] })
        result = await action.run(ctx)

        assert len(result) == 2

    @pytest.mark.anyio
    async def test_score_threshold_filters(self):
        # Threshold -1.5 keeps score >= -1.5, drops -3.0 and -6.0.
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.texts}", score_threshold=-1.5))
        ctx    = ComponentActionContext("r-4", { "query": "hi", "texts": [ "a", "bc", "def", "wxyz", "verylong" ] })
        result = await action.run(ctx)

        for item in result:
            assert item["score"] >= -1.5


class TestListQueries:
    """List[str] queries with list-of-lists texts -> one ranked list per query."""

    @pytest.mark.anyio
    async def test_non_streaming_returns_list_of_results(self):
        queries = [ "hi", "hello world" ]
        texts = [
            [ "a", "bc", "hi" ],
            [ "hello world!", "x", "yyy" ],
        ]
        action = _FakeRerankingAction(_make_config("${input.queries}", "${input.texts}"))
        ctx    = ComponentActionContext("r-5", { "queries": queries, "texts": texts })
        result = await action.run(ctx)

        # Non-streaming, list-of-queries branch: result is a plain list of ranked lists.
        assert isinstance(result, list)
        assert len(result) == 2
        # Each entry is the raw ranked list (list of dicts), not wrapped in
        # a StreamChunkIterator / StreamIterator / AsyncIterator.
        for ranked in result:
            assert isinstance(ranked, list)
            assert not isinstance(ranked, (StreamChunkIterator, StreamIterator))
            for item in ranked:
                assert isinstance(item, dict)
                assert set(item.keys()) == { "index", "score" }

        ranked_q1, ranked_q2 = result
        # Best text for "hi" (len 2) is "bc" or "hi" (both len 2), first result score = -0.0.
        assert ranked_q1[0]["score"] == -0.0
        # Best text for "hello world" (len 11) is "hello world!" (len 12), score = -1.0.
        assert ranked_q2[0]["score"] == -1.0
        assert ranked_q2[0]["index"] == 0


class TestStreamQueries:
    """AsyncIterator queries -> async-gen output; each chunk is a raw ranked list."""

    @pytest.mark.anyio
    async def test_streaming_input_yields_raw_results(self):
        async def _query_stream():
            for q in [ "hi", "hello" ]:
                yield q

        async def _texts_stream():
            for d in [ [ "a", "hi" ], [ "hello!", "world" ] ]:
                yield d

        action = _FakeRerankingAction(_make_config("${input.queries}", "${input.texts}"))
        ctx    = ComponentActionContext("r-6", { "queries": _query_stream(), "texts": _texts_stream() })
        result = await action.run(ctx)

        # Streaming branch returns an async generator (matches AsyncIterator ABC).
        assert isinstance(result, AsyncIterator)

        chunks = await _collect(result)
        assert len(chunks) == 2

        # Each yielded chunk is a raw ranked list (list of dicts) — no
        # StreamChunkIterator / StreamIterator wrapping.
        for chunk in chunks:
            assert isinstance(chunk, list)
            assert not isinstance(chunk, (StreamChunkIterator, StreamIterator))
            for item in chunk:
                assert isinstance(item, dict)
                assert set(item.keys()) == { "index", "score" }

        ranked_hi, ranked_hello = chunks
        # Best "hi" (len 2) match: "hi" (len 2), index 1.
        assert ranked_hi[0]["index"] == 1
        # Best "hello" (len 5) match: "world" (len 5), index 1.
        assert ranked_hello[0]["index"] == 1


class TestDriverCallShape:
    """`_rerank` is invoked once per (query, texts) pair."""

    @pytest.mark.anyio
    async def test_one_call_per_query(self):
        queries = [ "q1", "q2", "q3", "q4", "q5" ]
        texts = [ [ "a", "b" ], [ "c" ], [ "d", "e" ], [ "f" ], [ "g", "h" ] ]
        action = _FakeRerankingAction(_make_config("${input.queries}", "${input.texts}", batch_size=4))
        ctx    = ComponentActionContext("r-7", { "queries": queries, "texts": texts })
        await action.run(ctx)

        # One `_rerank` call per query — BatchSourceIterator packs each tick
        # into a length-1 batch and the base class unpacks before dispatching.
        assert len(action.calls) == len(queries)
        assert [ call["query"] for call in action.calls ] == queries
        # batch_size passes through from config.
        assert all(call["batch_size"] == 4 for call in action.calls)


class TestParamsPropagation:
    """``_resolve_params`` builds the dict that the driver consumes via ``_rerank``."""

    @pytest.mark.anyio
    async def test_default_params_dict_keys(self):
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.texts}"))
        ctx    = ComponentActionContext("r-8", { "query": "hi", "texts": [ "a", "hi" ] })
        await action.run(ctx)

        assert len(action.calls) == 1
        params = action.calls[0]["params"]
        # Driver-agnostic params surfaced from the base resolver.
        assert set(params.keys()) >= { "normalize", "max_input_length" }
        assert params["normalize"] is True
        assert params["max_input_length"] is None
