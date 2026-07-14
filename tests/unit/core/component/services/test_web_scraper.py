"""Tests for the WebScraperAction I/O matrix.

Network calls (`_fetch_html`) are stubbed so tests run offline. Playwright path is
not exercised here — that requires a browser and a real environment.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.web_scraper import WebScraperAction
from mindor.dsl.schema.action import WebScraperActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


_HTML_BY_URL = {
    "https://a.example/": "<html><body><h1>Alpha</h1><p>Page A</p></body></html>",
    "https://b.example/": "<html><body><h1>Beta</h1><p>Page B</p></body></html>",
    "https://c.example/": "<html><body><h1>Gamma</h1><p>Page C</p></body></html>",
}


def _make_context(url_value: Any) -> ComponentActionContext:
    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
            if value == "${input.url}":
                return url_value
        return value

    async def render_text(value, **kwargs):
        return await render_variable(value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_text = AsyncMock(side_effect=render_text)
    return ctx


def _make_action(output: Any = None, **config_kwargs) -> WebScraperAction:
    payload = {"url": "${input.url}", **config_kwargs}
    if output is not None:
        payload["output"] = output
    config = WebScraperActionConfig(**payload)
    return WebScraperAction(config, headers={}, cookies={}, timeout=None)


def _patch_fetch_html(action: WebScraperAction):
    async def fake_fetch(url, headers, cookies, timeout):
        return _HTML_BY_URL[url]
    return patch.object(action, "_fetch_html", side_effect=fake_fetch)


class TestSingleInput:
    @pytest.mark.anyio
    async def test_single_url_returns_extracted_text(self):
        action = _make_action(selector="h1")
        ctx = _make_context("https://a.example/")

        with _patch_fetch_html(action):
            result = await action.run(ctx, asyncio.get_running_loop())

        assert result == "Alpha"


class TestListInput:
    @pytest.mark.anyio
    async def test_list_returns_list_of_results(self):
        action = _make_action(selector="h1")
        ctx = _make_context(["https://a.example/", "https://b.example/", "https://c.example/"])

        with _patch_fetch_html(action):
            result = await action.run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert result == ["Alpha", "Beta", "Gamma"]


class TestStreamOutputTemplate:
    """Under the new model `${result[]}` no longer forces stream mode; web_scraper's
    unit result is a single value (str / dict / list), so the outer container is
    decided solely by the input shape — a list input keeps a list output."""

    @pytest.mark.anyio
    async def test_list_input_with_stream_output_template_returns_list(self):
        action = _make_action(selector="h1", output="${result[]}")
        ctx = _make_context(["https://a.example/", "https://b.example/"])

        with _patch_fetch_html(action):
            result = await action.run(ctx, asyncio.get_running_loop())

            assert not isinstance(result, AsyncIterator)


class TestBatchSize:
    @pytest.mark.anyio
    @pytest.mark.parametrize("batch_size", [1, 2, 3])
    async def test_list_with_batch_size(self, batch_size: int):
        action = _make_action(selector="h1", batch_size=batch_size)
        ctx = _make_context(["https://a.example/", "https://b.example/", "https://c.example/"])

        with _patch_fetch_html(action):
            result = await action.run(ctx, asyncio.get_running_loop())

        assert result == ["Alpha", "Beta", "Gamma"]


class TestExtractModes:
    @pytest.mark.anyio
    async def test_full_page_text(self):
        action = _make_action()  # no selector/xpath
        ctx = _make_context("https://a.example/")

        with _patch_fetch_html(action):
            result = await action.run(ctx, asyncio.get_running_loop())

        # Full page text extraction includes both h1 and p.
        assert "Alpha" in result
        assert "Page A" in result

    @pytest.mark.anyio
    async def test_html_extract_mode(self):
        action = _make_action(selector="h1", extract_mode="html")
        ctx = _make_context("https://a.example/")

        with _patch_fetch_html(action):
            result = await action.run(ctx, asyncio.get_running_loop())

        assert "<h1>" in result and "Alpha" in result


class TestNoneInput:
    @pytest.mark.anyio
    async def test_list_with_none_passes_through(self):
        action = _make_action(selector="h1")
        ctx = _make_context([None, "https://a.example/"])

        with _patch_fetch_html(action):
            result = await action.run(ctx, asyncio.get_running_loop())

        assert result == [None, "Alpha"]
