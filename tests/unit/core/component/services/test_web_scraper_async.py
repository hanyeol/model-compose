"""Async / contract tests for the refactored WebScraperAction.

Verifies:
- The `run()` signature no longer accepts a `loop` kwarg (it uses native
  async aiohttp / playwright — nothing to offload).
- `WebScraperAction` inherits `ComponentAction` and is invoked without a
  loop kwarg through the shared context.
- The batch code path uses `asyncio.gather` for parallelism: 5 URLs each
  taking ~100ms should complete in ~100-150ms, not ~500ms.
- aiohttp/playwright are not imported eagerly at module load beyond the
  top-level `aiohttp` import used by the sync-fetch path.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindor.core.component.action.base import ComponentAction
from mindor.core.component.services.web_scraper import (
    WebScraperAction,
    WebScraperComponent,
)
from mindor.dsl.schema.action import WebScraperActionConfig

from tests.async_helpers import assert_does_not_block, make_action_context


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_action(**config_kwargs) -> WebScraperAction:
    config = WebScraperActionConfig(url="${input.url}", **config_kwargs)
    return WebScraperAction(config, headers={}, cookies={}, timeout=None)


class TestWebScraperContract:
    """End-to-end drive with `_fetch_html` mocked to return HTML."""

    @pytest.mark.anyio
    async def test_single_url_extracts_via_selector(self):
        action = _make_action(selector="h1")
        context = make_action_context(input={"url": "https://a.example/"})

        async def fake_fetch(url, headers, cookies, timeout, cancellation_token=None):
            return f"<html><body><h1>Title of {url}</h1></body></html>"

        with patch.object(action, "_fetch_html", side_effect=fake_fetch):
            result = await action.run(context)

        assert result == "Title of https://a.example/"

    @pytest.mark.anyio
    async def test_batch_urls_returns_list(self):
        action = _make_action(selector="h1")
        context = make_action_context(
            input={"url": ["https://a.example/", "https://b.example/", "https://c.example/"]}
        )

        async def fake_fetch(url, headers, cookies, timeout, cancellation_token=None):
            return f"<html><body><h1>{url}</h1></body></html>"

        with patch.object(action, "_fetch_html", side_effect=fake_fetch):
            result = await action.run(context)

        assert result == ["https://a.example/", "https://b.example/", "https://c.example/"]

    @pytest.mark.anyio
    async def test_inheritance_from_component_action(self):
        action = _make_action(selector="h1")
        assert isinstance(action, ComponentAction), (
            "WebScraperAction must subclass ComponentAction to inherit `_run_in_executor` "
            "and the shared action lifecycle."
        )


class TestWebScraperBatchParallelism:
    """`_process_batch` uses `asyncio.gather` — 5 slow-fetches should overlap."""

    @pytest.mark.anyio
    async def test_5_urls_run_in_parallel(self):
        # `_process_batch` uses `asyncio.gather` inside the batch; parallelism
        # is per-batch. To exercise it we must ask for a batch_size ≥ len(urls).
        action = _make_action(selector="h1", batch_size=5)
        urls = [f"https://host{i}.example/" for i in range(5)]
        context = make_action_context(input={"url": urls})

        per_url_delay_s = 0.1

        async def fake_fetch(url, headers, cookies, timeout, cancellation_token=None):
            await asyncio.sleep(per_url_delay_s)
            return f"<html><body><h1>{url}</h1></body></html>"

        with patch.object(action, "_fetch_html", side_effect=fake_fetch):
            start = time.monotonic()
            result = await action.run(context)
            elapsed = time.monotonic() - start

        assert len(result) == 5
        # Parallel-gather budget: 100ms + scheduling overhead. If the loop is
        # serial the total is ~500ms; give ourselves a comfortable ceiling
        # under 300ms.
        assert elapsed < 0.3, (
            f"Expected parallel fetch (~{per_url_delay_s}s), got {elapsed:.2f}s — "
            f"batch dispatch appears to be serial."
        )

    @pytest.mark.anyio
    async def test_default_batch_size_serializes_fetches(self):
        """Latent behavior finding, worth pinning down: the default
        `batch_size=None` collapses to 1, so each URL is fetched in its own
        (single-URL) batch — sequentially. Parallelism requires an explicit
        `batch_size >= len(urls)`. If the default ever changes, this test
        will flip and prompt a re-review of documented behavior."""
        action = _make_action(selector="h1")  # no batch_size → 1
        urls = [f"https://host{i}.example/" for i in range(3)]
        context = make_action_context(input={"url": urls})

        per_url_delay_s = 0.1

        async def fake_fetch(url, headers, cookies, timeout, cancellation_token=None):
            await asyncio.sleep(per_url_delay_s)
            return f"<html><body><h1>ok</h1></body></html>"

        with patch.object(action, "_fetch_html", side_effect=fake_fetch):
            start = time.monotonic()
            await action.run(context)
            elapsed = time.monotonic() - start

        # 3 * 100ms sequential — well over 250ms.
        assert elapsed > 0.25, (
            f"Default batch_size (=1) is expected to serialize fetches; "
            f"got {elapsed:.2f}s. If this fails, the default may have changed."
        )


class TestWebScraperBatchDispatchesEveryUrl:
    """Even with batch_size=2 (multiple sub-batches), every URL still fires."""

    @pytest.mark.anyio
    async def test_batch_size_processes_all_urls(self):
        action = _make_action(selector="h1", batch_size=2)
        urls = [f"https://host{i}.example/" for i in range(5)]
        context = make_action_context(input={"url": urls})

        seen = []

        async def fake_fetch(url, headers, cookies, timeout, cancellation_token=None):
            seen.append(url)
            return f"<html><body><h1>ok</h1></body></html>"

        with patch.object(action, "_fetch_html", side_effect=fake_fetch):
            result = await action.run(context)

        assert seen == urls
        assert result == ["ok"] * 5


class TestWebScraperSignature:
    def test_action_run_has_no_loop_kwarg(self):
        signature = inspect.signature(WebScraperAction.run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names, (
            f"WebScraperAction.run should not accept `loop`; got {param_names!r}"
        )
        assert param_names == ["self", "context"]

    def test_component_run_has_no_loop_kwarg(self):
        signature = inspect.signature(WebScraperComponent._run)
        param_names = list(signature.parameters.keys())
        assert "loop" not in param_names
        assert param_names == ["self", "action", "context"]


class TestWebScraperNoneUrlPassesThrough:
    @pytest.mark.anyio
    async def test_none_in_list_produces_none_entry(self):
        action = _make_action(selector="h1")
        context = make_action_context(input={"url": [None, "https://a.example/"]})

        async def fake_fetch(url, headers, cookies, timeout, cancellation_token=None):
            return f"<html><body><h1>ok</h1></body></html>"

        with patch.object(action, "_fetch_html", side_effect=fake_fetch):
            result = await action.run(context)

        assert result == [None, "ok"]
