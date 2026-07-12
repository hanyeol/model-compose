"""Tests for the TextRerankingTaskAction's I/O matrix.

text_reranking has no `streaming` config (the model API is batch-only) and
also no chunk-level streaming inside a single reranking job — each tick emits
one completed ranked list. The output-shape rule mirrors the other atomic
model tasks:

    is_stream_input  = isinstance(query, list, StreamIterator, AsyncIterator)  # actually list is not-stream
    is_stream_input  = isinstance(query, (StreamIterator, AsyncIterator))
    is_single_input  = not isinstance(query, (list, StreamIterator, AsyncIterator))
    is_direct_output = output is empty or output == "${result}"

Stream mode (query is AsyncIterator) → AsyncIterator yielding one StreamChunkIterator per query.
Collect mode                          → single value (single query) or list (list of queries),
                                         each entry a StreamChunkIterator that resolves to the
                                         ranked-result list.

Tests cover:
- Query shapes: single str / List[str] / AsyncIterator[str]
- Documents: List[str] / List[Dict] with document_field
- Options: top_k / score_threshold / return_documents
- Rerank driver receives batched (queries, texts) with dict originals resolved to text
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Dict, List

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.text_reranking.common import TextRerankingTaskAction
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.dsl.schema.action import TextRerankingModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeRerankingAction(TextRerankingTaskAction):
    """Deterministic ``_rerank`` for testing.

    Each (query, text) pair scores as ``-abs(len(text) - len(query))`` so that
    documents whose length is closest to the query length rank highest. This
    makes the sort/top_k/threshold behavior predictable.
    """

    def __init__(self, config: TextRerankingModelActionConfig):
        super().__init__(config)
        self.batches_seen: List[Dict[str, Any]] = []

    async def _rerank(self, queries: List[str], documents: List[List[str]], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[List[float]]:
        self.batches_seen.append({ "queries": list(queries), "documents": [ list(d) for d in documents ], "params": params })
        return [
            [ -float(abs(len(text) - len(query))) for text in texts ]
            for query, texts in zip(queries, documents)
        ]


def _make_config(
    query_expr: Any,
    documents_expr: Any,
    output: Any = None,
    document_field: Any = None,
    top_k: Any = None,
    score_threshold: Any = None,
    return_documents: Any = True,
    batch_size: int = 2,
) -> TextRerankingModelActionConfig:
    raw: dict = {
        "query": query_expr,
        "documents": documents_expr,
        "batch_size": batch_size,
        "return_documents": return_documents,
    }
    if output is not None:
        raw["output"] = output
    if document_field is not None:
        raw["document_field"] = document_field
    if top_k is not None:
        raw["top_k"] = top_k
    if score_threshold is not None:
        raw["score_threshold"] = score_threshold
    return TextRerankingModelActionConfig.model_validate(raw)


async def _make_async_iter(items: List[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


async def _collect_stream(chunk: Any) -> List[Any]:
    """Drain a StreamChunkIterator/AsyncIterator to its list of yielded values."""
    if isinstance(chunk, (StreamIterator, AsyncIterator)):
        return [ item async for item in chunk ]
    return chunk


async def _drain_result(result: Any) -> Any:
    """Fully drain the run() return value into plain Python values.

    Collect-mode single query → StreamChunkIterator → drain once.
    Collect-mode list queries → list of StreamChunkIterator → drain each.
    Stream-mode                → AsyncIterator of StreamChunkIterator → drain outer, then each.
    """
    if isinstance(result, list):
        return [ await _collect_stream(item) for item in result ]
    if isinstance(result, (StreamIterator, AsyncIterator)):
        collected = []
        async for chunk in result:
            collected.append(await _collect_stream(chunk))
        return collected
    return await _collect_stream(result)


class TestSingleQuerySingleStringDocs:
    """Single query str + List[str] documents → single ranked list."""

    @pytest.mark.anyio
    async def test_no_output_returns_ranked_list(self):
        # query "hello" (len 5) vs docs with lengths [2, 11, 7, 5] → scores [-3, -6, -2, 0].
        # After sort desc: hey!! (0), goodbye (-2), hi (-3), hello world (-6).
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.docs}"))
        ctx    = ComponentActionContext("r-1", { "query": "hello", "docs": [ "hi", "hello world", "goodbye", "hey!!" ] })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)
        drained = await _drain_result(result)

        # Wrapped once by _stream_chunk_generator; drain yields [ranked_list].
        assert drained == [[
            { "index": 3, "score": -0.0, "document": "hey!!" },
            { "index": 2, "score": -2.0, "document": "goodbye" },
            { "index": 0, "score": -3.0, "document": "hi" },
            { "index": 1, "score": -6.0, "document": "hello world" },
        ]]

    @pytest.mark.anyio
    async def test_passthrough_output_returns_ranked_list(self):
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.docs}", output="${result}"))
        ctx    = ComponentActionContext("r-2", { "query": "hi", "docs": [ "a", "hi", "bcd" ] })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)
        drained = await _drain_result(result)

        assert isinstance(drained, list) and len(drained) == 1
        ranked = drained[0]
        assert ranked[0] == { "index": 1, "score": -0.0, "document": "hi" }


class TestSingleQueryDictDocs:
    """Object documents require document_field; originals preserved in output."""

    @pytest.mark.anyio
    async def test_dict_docs_with_document_field(self):
        docs = [
            { "id": 1, "text": "hi" },
            { "id": 2, "text": "hello world" },
            { "id": 3, "text": "goodbye" },
        ]
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.docs}", document_field="text"))
        ctx    = ComponentActionContext("r-3", { "query": "hello", "docs": docs })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)
        drained = await _drain_result(result)

        # Each result "document" field must be the original dict, not the extracted text.
        ranked = drained[0]
        for item in ranked:
            assert isinstance(item["document"], dict)
            assert "id" in item["document"] and "text" in item["document"]

        # Driver received only the extracted texts, not the dicts.
        seen = action.batches_seen[0]
        assert seen["queries"] == [ "hello" ]
        assert seen["documents"] == [[ "hi", "hello world", "goodbye" ]]

    @pytest.mark.anyio
    async def test_dict_docs_without_field_raises(self):
        docs = [ { "text": "hi" }, { "text": "hello" } ]
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.docs}"))
        ctx    = ComponentActionContext("r-4", { "query": "hi", "docs": docs })
        loop   = asyncio.get_running_loop()

        with pytest.raises(ValueError, match="document_field"):
            await action.run(ctx, loop)


class TestTopKAndThreshold:
    @pytest.mark.anyio
    async def test_top_k_trims_result(self):
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.docs}", top_k=2))
        ctx    = ComponentActionContext("r-5", { "query": "hello", "docs": [ "hi", "hello!", "x", "hello world", "hey!!" ] })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)
        drained = await _drain_result(result)

        assert len(drained[0]) == 2

    @pytest.mark.anyio
    async def test_score_threshold_filters(self):
        # Threshold -1.5 keeps score >= -1.5, drops -3.0 and -6.0.
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.docs}", score_threshold=-1.5))
        ctx    = ComponentActionContext("r-6", { "query": "hi", "docs": [ "a", "bc", "def", "wxyz", "verylong" ] })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)
        drained = await _drain_result(result)

        ranked = drained[0]
        for item in ranked:
            assert item["score"] >= -1.5

    @pytest.mark.anyio
    async def test_return_documents_false_omits_document(self):
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.docs}", return_documents=False))
        ctx    = ComponentActionContext("r-7", { "query": "hi", "docs": [ "a", "hi", "bc" ] })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)
        drained = await _drain_result(result)

        ranked = drained[0]
        for item in ranked:
            assert set(item.keys()) == { "index", "score" }


class TestListQueries:
    """List[str] queries with list-of-lists documents → one ranked list per query."""

    @pytest.mark.anyio
    async def test_list_queries_returns_list_of_ranked_lists(self):
        queries = [ "hi", "hello world" ]
        docs = [
            [ "a", "bc", "hi" ],
            [ "hello world!", "x", "yyy" ],
        ]
        action = _FakeRerankingAction(_make_config("${input.queries}", "${input.docs}"))
        ctx    = ComponentActionContext("r-8", { "queries": queries, "docs": docs })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)
        drained = await _drain_result(result)

        # drained is [[ranked_for_q1], [ranked_for_q2]]: each entry drained once by
        # _stream_chunk_generator wraps a single yield.
        assert len(drained) == 2
        ranked_q1 = drained[0][0]
        ranked_q2 = drained[1][0]
        # Best doc for "hi" (len 2) is "bc" or "hi" (both len 2), first result score = -0.0.
        assert ranked_q1[0]["score"] == -0.0
        # Best doc for "hello world" (len 11) is "hello world!" (len 12), score = -1.0.
        assert ranked_q2[0]["score"] == -1.0
        assert ranked_q2[0]["document"] == "hello world!"


class TestStreamQueries:
    """AsyncIterator queries → stream output; each chunk is a StreamChunkIterator."""

    @pytest.mark.anyio
    async def test_stream_queries_returns_async_iterator(self):
        async def _query_stream():
            for q in [ "hi", "hello" ]:
                yield q

        async def _docs_stream():
            for d in [ [ "a", "hi" ], [ "hello!", "world" ] ]:
                yield d

        action = _FakeRerankingAction(_make_config("${input.queries}", "${input.docs}"))
        ctx    = ComponentActionContext("r-9", { "queries": _query_stream(), "docs": _docs_stream() })
        loop   = asyncio.get_running_loop()
        result = await action.run(ctx, loop)

        assert isinstance(result, AsyncIterator)
        drained = await _drain_result(result)
        assert len(drained) == 2
        # drained[i] == [ranked_for_query_i]: each chunk drained once from a
        # single-yield _stream_chunk_generator.
        ranked_hi = drained[0][0]
        ranked_hello = drained[1][0]
        # Best "hi" (len 2) match: "hi" (len 2), score 0.
        assert ranked_hi[0]["document"] == "hi"
        # Best "hello" (len 5) match: "world" (len 5), score 0.
        assert ranked_hello[0]["document"] == "world"


class TestDriverBatching:
    """`_rerank` receives batches based on batch_size."""

    @pytest.mark.anyio
    async def test_batch_size_splits_calls(self):
        # 5 queries, batch_size=2 → 3 driver calls: [2, 2, 1]
        queries = [ "q1", "q2", "q3", "q4", "q5" ]
        docs = [ [ "a", "b" ], [ "c" ], [ "d", "e" ], [ "f" ], [ "g", "h" ] ]
        action = _FakeRerankingAction(_make_config("${input.queries}", "${input.docs}", batch_size=2))
        ctx    = ComponentActionContext("r-10", { "queries": queries, "docs": docs })
        loop   = asyncio.get_running_loop()
        await action.run(ctx, loop)

        # Three batches expected.
        assert len(action.batches_seen) == 3
        assert [ len(b["queries"]) for b in action.batches_seen ] == [ 2, 2, 1 ]
        # Total queries preserved across batches.
        flat_queries = [ q for b in action.batches_seen for q in b["queries"] ]
        assert flat_queries == queries


class TestParamsPropagation:
    """``_resolve_params`` builds the dict that the driver consumes via ``_rerank``."""

    @pytest.mark.anyio
    async def test_default_params_dict_keys(self):
        action = _FakeRerankingAction(_make_config("${input.query}", "${input.docs}"))
        ctx    = ComponentActionContext("r-11", { "query": "hi", "docs": [ "a", "hi" ] })
        loop   = asyncio.get_running_loop()
        await action.run(ctx, loop)

        assert len(action.batches_seen) == 1
        params = action.batches_seen[0]["params"]
        # Driver-agnostic params surfaced from the base resolver.
        assert set(params.keys()) >= { "normalize", "max_input_length" }
        assert params["normalize"] is True
        assert params["max_input_length"] == 512
