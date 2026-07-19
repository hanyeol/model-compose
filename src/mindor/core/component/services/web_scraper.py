from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import WebScraperComponentConfig
from mindor.dsl.schema.action import ActionConfig, WebScraperActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.rate_limit import RateLimiter
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.logger import logging
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
import aiohttp, asyncio
import sys, subprocess

class WebScraperAction:
    def __init__(
        self,
        config: WebScraperActionConfig,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        timeout: Optional[str]
    ):
        self.config: WebScraperActionConfig = config
        self.headers = headers
        self.cookies = cookies
        self.timeout = timeout

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        url        = await context.render_text(self.config.url)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(url, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(url, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_urls in BatchSourceIterator(url, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_urls, params, loop, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_urls in BatchSourceIterator(url, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_urls, params, loop, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        headers           = await context.render_variable(self.config.headers)
        cookies           = await context.render_variable(self.config.cookies)
        selector          = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath             = await context.render_variable(self.config.xpath) if self.config.xpath else None
        extract_mode      = await context.render_variable(self.config.extract_mode)
        attribute         = await context.render_variable(self.config.attribute) if self.config.attribute else None
        multiple          = await context.render_variable(self.config.multiple)
        enable_javascript = await context.render_variable(self.config.enable_javascript)
        wait_until        = await context.render_variable(self.config.wait_until)
        wait_for          = await context.render_variable(self.config.wait_for) if self.config.wait_for else None
        submit            = await context.render_variable(self.config.submit) if self.config.submit else None
        timeout           = (await context.render_variable(self.config.timeout) if self.config.timeout else self.timeout) or 60.0

        # Merge headers and cookies: component defaults + action overrides
        merged_headers = { **self.headers, **headers }
        merged_cookies = { **self.cookies, **cookies }

        return {
            "headers":           merged_headers,
            "cookies":           merged_cookies,
            "selector":          selector,
            "xpath":             xpath,
            "extract_mode":      extract_mode,
            "attribute":         attribute,
            "multiple":          multiple,
            "enable_javascript": enable_javascript,
            "wait_until":        wait_until,
            "wait_for":          wait_for,
            "submit":            submit,
            "timeout":           parse_duration(timeout),
        }

    async def _process_batch(
        self,
        urls: List[str],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Optional[Any]]:
        needs_browser = params["submit"] or params["enable_javascript"]
        if needs_browser and any(url is not None for url in urls):
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    return await asyncio.gather(*[
                        self._process(url, params, loop, browser, cancellation_token) for url in urls
                    ])
                finally:
                    await browser.close()

        return await asyncio.gather(*[
            self._process(url, params, loop, None, cancellation_token) for url in urls
        ])

    async def _process(
        self,
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        browser: Optional[Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> Optional[Any]:
        if url is None:
            logging.debug("Web scraper skipped because no URL was provided.")
            return None

        # Fetch HTML content (with optional form submission)
        if params["submit"] or params["enable_javascript"]:
            html_content = await self._fetch_html_with_javascript(
                browser,
                url,
                params["headers"],
                params["cookies"],
                params["timeout"],
                params["wait_until"],
                params["wait_for"],
                params["submit"],
                cancellation_token
            )
        else:
            html_content = await self._fetch_html(
                url,
                params["headers"],
                params["cookies"],
                params["timeout"],
                cancellation_token
            )

        # Parse and extract result
        if params["selector"]:
            return self._extract_with_selector(
                html_content,
                params["selector"],
                params["extract_mode"],
                params["attribute"],
                params["multiple"]
            )

        if params["xpath"]:
            return self._extract_with_xpath(
                html_content,
                params["xpath"],
                params["extract_mode"],
                params["attribute"],
                params["multiple"]
            )

        return self._extract_full_page(html_content, params["extract_mode"])

    async def _fetch_html_with_javascript(
        self,
        browser: Any,
        url: str,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        timeout: float,
        wait_until: str,
        wait_for: Optional[str],
        submit: Optional[Dict[str, Any]] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> str:
        """Fetch HTML content with JavaScript rendering using a shared playwright browser. Optionally submit form before extraction."""
        from urllib.parse import urlparse

        # Convert cookies dict to playwright cookie format
        parsed_url = urlparse(url)
        cookie_list = [
            {
                "name": name,
                "value": value,
                "domain": parsed_url.hostname,
                "path": "/"
            }
            for name, value in cookies.items()
        ]

        web_context = await browser.new_context(extra_http_headers=headers)

        # Add cookies to context
        if cookie_list:
            await web_context.add_cookies(cookie_list)

        page = await web_context.new_page()

        try:
            await page.goto(url, timeout=timeout * 1000, wait_until=wait_until)

            # If submit config is provided, fill and submit form first
            if submit:
                selector = submit.get("selector")
                xpath    = submit.get("xpath")
                form     = submit.get("form")
                wait_for = submit.get("wait_for")

                # Fill form inputs if form data is provided
                if form:
                    for input_selector, value in form.items():
                        await page.fill(input_selector, str(value))

                # Submit form
                if selector:
                    element = await page.query_selector(selector)
                    if element:
                        tag_name = await element.evaluate("el => el.tagName")
                        if tag_name.lower() == "form":
                            await element.evaluate("form => form.submit()")
                        else:
                            await element.click()
                elif xpath:
                    elements = await page.query_selector_all(f"xpath={xpath}")
                    if elements:
                        element = elements[0]
                        tag_name = await element.evaluate("el => el.tagName")
                        if tag_name.lower() == "form":
                            await element.evaluate("form => form.submit()")
                        else:
                            await element.click()
                else:
                    # No selector/xpath: find and submit the first form
                    element = await page.query_selector("form")
                    if element:
                        await element.evaluate("form => form.submit()")
                    else:
                        raise LookupError("No <form> element found on the page to submit")

                # Wait for navigation or specific element after submit
                if wait_for:
                    await page.wait_for_selector(wait_for, timeout=timeout * 1000)
                else:
                    await page.wait_for_load_state(wait_until if wait_until != "commit" else "load", timeout=timeout * 1000)

            # Wait for additional selector if specified (for non-submit cases)
            if wait_for and not submit:
                await page.wait_for_selector(wait_for, timeout=timeout * 1000)

            return await page.content()
        finally:
            await web_context.close()

    async def _fetch_html(
        self,
        url: str,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        timeout: float,
        cancellation_token: Optional[CancellationToken] = None
    ) -> str:
        """Fetch HTML content using aiohttp."""
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                response.raise_for_status()
                return await response.text()

    def _extract_with_selector(
        self,
        html: str,
        selector: Union[str, List[str], Dict[str, str]],
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> Any:
        """Extract content using CSS selector. Parses HTML once and reuses the parsed soup."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'lxml')

        def _extract(expr: str) -> Union[str, List[str], None]:
            if multiple:
                elements = soup.select(expr)
                if not elements:
                    return []
                return [ self._extract_from_element(element, extract_mode, attribute) for element in elements ]

            element = soup.select_one(expr)
            if not element:
                return None
            return self._extract_from_element(element, extract_mode, attribute)

        if isinstance(selector, dict):
            return { key: _extract(expr) for key, expr in selector.items() }
        if isinstance(selector, list):
            return [ _extract(expr) for expr in selector ]
        return _extract(selector)

    def _extract_with_xpath(
        self,
        html: str,
        xpath: Union[str, List[str], Dict[str, str]],
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> Any:
        """Extract content using XPath. Parses HTML once and reuses the parsed tree."""
        from lxml import etree

        tree = etree.HTML(html)

        def _extract(expr: str) -> Union[str, List[str], None]:
            elements = tree.xpath(expr)
            if not elements:
                return [] if multiple else None
            if multiple:
                return [ self._extract_from_xpath_element(element, extract_mode, attribute) for element in elements ]
            return self._extract_from_xpath_element(elements[0], extract_mode, attribute)

        if isinstance(xpath, dict):
            return { key: _extract(expr) for key, expr in xpath.items() }
        if isinstance(xpath, list):
            return [ _extract(expr) for expr in xpath ]
        return _extract(xpath)

    def _extract_from_element(self, element, extract_mode: str, attribute: Optional[str]) -> Optional[str]:
        """Extract content from a BeautifulSoup element."""
        if extract_mode == "text":
            return element.get_text(separator=" ", strip=True)

        if extract_mode == "html":
            return str(element)

        if extract_mode == "attribute":
            return element.get(attribute, "")

        return None

    def _extract_from_xpath_element(self, element, extract_mode: str, attribute: Optional[str]) -> str:
        """Extract content from an lxml element."""
        if extract_mode == "text":
            return element.text_content().strip() if hasattr(element, "text_content") else str(element).strip()
        
        if extract_mode == "html":
            from lxml import etree

            return etree.tostring(element, encoding="unicode", method="html") if hasattr(element, "tag") else str(element)
        
        if extract_mode == "attribute":
            return element.get(attribute, "") if hasattr(element, "get") else ""

        return ""

    def _extract_full_page(self, html: str, extract_mode: str) -> str:
        """Extract full page content without selector or xpath."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        if extract_mode == "text":
            return soup.get_text(separator=" ", strip=True)

        return str(soup)

@register_component(ComponentType.WEB_SCRAPER)
class WebScraperComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: WebScraperComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self._rate_limiter: Optional[RateLimiter] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "playwright", "beautifulsoup4", "lxml" ]

    async def _setup(self) -> None:
        subprocess.run(
            [ sys.executable, "-m", "playwright", "install", "chromium" ],
            check=True,
            capture_output=True
        )

    async def _start(self) -> None:
        if self.config.rate_limit:
            self._rate_limiter = RateLimiter(self.config.rate_limit)

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        self._rate_limiter = None

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        if self._rate_limiter:
            await self._rate_limiter.acquire()

        return await WebScraperAction(action, self.config.headers, self.config.cookies, self.config.timeout).run(context, asyncio.get_running_loop())
