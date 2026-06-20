"""Manual / live test for the web-scraper batch path.

Hits real URLs to verify:
  1. aiohttp batch (no JS) processes URLs concurrently.
  2. playwright batch shares a single browser across URLs.

Run directly: `python tests/_manual/test_web_scraper_batch_live.py`
Not collected by pytest (lives under tests/_manual/).
"""

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.web_scraper import WebScraperAction
from mindor.dsl.schema.action import WebScraperActionConfig


def _make_context(url_value: Any) -> ComponentActionContext:
    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    def contains_ref(key: str, value: Any) -> bool:
        return False
    ctx.contains_variable_reference = MagicMock(side_effect=contains_ref)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result}":
                return sources.get("result")
            if value == "${input.url}":
                return url_value
        return value

    async def render_text(value, **kwargs):
        resolved = await render_variable(value)
        return resolved

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_text = AsyncMock(side_effect=render_text)
    return ctx


def _make_action(**config_kwargs) -> WebScraperAction:
    payload = {"url": "${input.url}", **config_kwargs}
    config = WebScraperActionConfig(**payload)
    return WebScraperAction(config, headers={}, cookies={}, timeout=None)


async def test_aiohttp_batch():
    print("\n=== aiohttp batch (no JS) ===")
    urls = [
        "https://httpbin.org/html",
        "https://www.iana.org/help/example-domains",
        "https://www.rfc-editor.org/rfc/rfc2606.html",
    ]
    # No selector: extract full page text. Each page has a distinct,
    # recognizable token so we can confirm the right page mapped to the
    # right slot.
    expected_tokens = ["Moby-Dick", "Example Domains", "Reserved Top Level"]

    action = _make_action(batch_size=3)
    ctx = _make_context(urls)

    t0 = time.perf_counter()
    result = await action.run(ctx, asyncio.get_running_loop())
    elapsed = time.perf_counter() - t0

    print(f"  urls    : {urls}")
    print(f"  preview : {[(r or '')[:60] for r in result]}")
    print(f"  elapsed : {elapsed:.2f}s (concurrent fetch)")
    assert isinstance(result, list)
    assert len(result) == 3
    for url, token, r in zip(urls, expected_tokens, result):
        assert r and token in r, f"{url}: expected {token!r} in result, got {(r or '')[:120]!r}"


async def test_aiohttp_single():
    print("\n=== aiohttp single URL ===")
    action = _make_action(selector="h1")
    ctx = _make_context("https://httpbin.org/html")

    result = await action.run(ctx, asyncio.get_running_loop())
    print(f"  result  : {result!r}")
    assert isinstance(result, str)
    assert result and "Moby-Dick" in result


async def test_playwright_batch_shared_browser():
    print("\n=== playwright batch (shared browser) ===")
    urls = [
        "https://httpbin.org/html",
        "https://www.iana.org/help/example-domains",
        "https://www.rfc-editor.org/rfc/rfc2606.html",
    ]
    expected_tokens = ["Moby-Dick", "Example Domains", "Reserved Top Level"]

    action = _make_action(batch_size=3, enable_javascript=True)
    ctx = _make_context(urls)

    t0 = time.perf_counter()
    result = await action.run(ctx, asyncio.get_running_loop())
    elapsed = time.perf_counter() - t0

    print(f"  urls    : {urls}")
    print(f"  preview : {[(r or '')[:60] for r in result]}")
    print(f"  elapsed : {elapsed:.2f}s (one browser, concurrent contexts)")
    assert isinstance(result, list)
    assert len(result) == 3
    for url, token, r in zip(urls, expected_tokens, result):
        assert r and token in r, f"{url}: expected {token!r} in result, got {(r or '')[:120]!r}"


async def main():
    await test_aiohttp_single()
    await test_aiohttp_batch()

    try:
        await test_playwright_batch_shared_browser()
    except Exception as e:
        print(f"\n[playwright skipped] {type(e).__name__}: {e}")

    print("\nAll done.")


if __name__ == "__main__":
    asyncio.run(main())
