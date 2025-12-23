from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import WebScraperComponentConfig
from mindor.dsl.schema.action import ActionConfig, WebScraperActionConfig
from mindor.core.utils.time import parse_duration
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
from bs4 import BeautifulSoup
from lxml import etree
import aiohttp

class WebScraperAction:
    def __init__(self, config: WebScraperActionConfig, headers: Dict[str, str], cookies: Dict[str, str], timeout: Optional[str]):
        self.config: WebScraperActionConfig = config
        self.headers = headers
        self.cookies = cookies
        self.timeout = timeout

    async def run(self, context: ComponentActionContext) -> Any:
        url               = await context.render_variable(self.config.url)
        headers           = await context.render_variable(self.config.headers)
        cookies           = await context.render_variable(self.config.cookies)
        selector          = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath             = await context.render_variable(self.config.xpath) if self.config.xpath else None
        extract_mode      = await context.render_variable(self.config.extract_mode)
        attribute         = await context.render_variable(self.config.attribute) if self.config.attribute else None
        multiple          = await context.render_variable(self.config.multiple)
        enable_javascript = await context.render_variable(self.config.enable_javascript)
        wait_for          = await context.render_variable(self.config.wait_for) if self.config.wait_for else None
        submit            = await context.render_variable(self.config.submit) if self.config.submit else None

        # Merge headers and cookies: component defaults + action overrides
        merged_headers = { **self.headers, **headers }
        merged_cookies = { **self.cookies, **cookies }
        timeout = parse_duration((await context.render_variable(self.config.timeout) if self.config.timeout else self.timeout) or 60.0).total_seconds()

        # Fetch HTML content (with optional form submission)
        if submit or enable_javascript:
            html_content = await self._fetch_html_with_javascript(url, merged_headers, merged_cookies, timeout, wait_for, submit)
        else:
            html_content = await self._fetch_html(url, merged_headers, merged_cookies, timeout)

        # Parse and extract
        if selector:
            result = self._extract_with_selector(html_content, selector, extract_mode, attribute, multiple)
        elif xpath:
            result = self._extract_with_xpath(html_content, xpath, extract_mode, attribute, multiple)
        else:
            result = self._extract_full_page(html_content, extract_mode)

        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _fetch_html_with_javascript(
        self,
        url: str,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        timeout: float,
        wait_for: Optional[str],
        submit: Optional[Dict[str, Any]] = None
    ) -> str:
        """Fetch HTML content with JavaScript rendering using playwright. Optionally submit form before extraction."""
        from playwright.async_api import async_playwright
        from urllib.parse import urlparse

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # Convert cookies dict to playwright cookie format
            parsed_url = urlparse(url)
            cookie_list = [
                {
                    "name": name,
                    "value": value,
                    "domain": parsed_url.netloc,
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
                await page.goto(url, timeout=timeout * 1000, wait_until="networkidle")

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
                        await page.evaluate("document.querySelector('form').submit()")

                    # Wait for navigation or specific element after submit
                    if wait_for:
                        await page.wait_for_selector(wait_for, timeout=timeout * 1000)
                    else:
                        await page.wait_for_load_state("networkidle", timeout=timeout * 1000)

                # Wait for additional selector if specified (for non-submit cases)
                if wait_for and not submit:
                    await page.wait_for_selector(wait_for, timeout=timeout * 1000)

                return await page.content()
            finally:
                await browser.close()

    async def _fetch_html(self, url: str, headers: Dict[str, str], cookies: Dict[str, str], timeout: float) -> str:
        """Fetch HTML content using aiohttp."""
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                response.raise_for_status()
                return await response.text()

    def _extract_with_selector(
        self,
        html: str,
        selector: str,
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> Union[str, List[str], None]:
        """Extract content using CSS selector."""
        soup = BeautifulSoup(html, 'lxml')

        if multiple:
            elements = soup.select(selector)

            if not elements:
                return []

            return [ self._extract_from_element(element, extract_mode, attribute) for element in elements ]
        else:
            element = soup.select_one(selector)

            if not element:
                return None

            return self._extract_from_element(element, extract_mode, attribute)

    def _extract_with_xpath(
        self,
        html: str,
        xpath: str,
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> Union[str, List[str], None]:
        """Extract content using XPath."""
        tree = etree.HTML(html)
        elements = tree.xpath(xpath)

        if not elements:
            return [] if multiple else None

        if multiple:
            return [ self._extract_from_xpath_element(elem, extract_mode, attribute) for elem in elements ]

        return self._extract_from_xpath_element(elements[0], extract_mode, attribute)

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
            return etree.tostring(element, encoding="unicode", method="html") if hasattr(element, "tag") else str(element)
        
        if extract_mode == "attribute":
            return element.get(attribute, "") if hasattr(element, "get") else ""

        return ""

    def _extract_full_page(self, html: str, extract_mode: str) -> str:
        """Extract full page content without selector or xpath."""
        soup = BeautifulSoup(html, "lxml")

        if extract_mode == "text":
            return soup.get_text(separator=" ", strip=True)

        return str(soup)

@register_component(ComponentType.WEB_SCRAPER)
class WebScraperComponent(ComponentService):
    def __init__(self, id: str, config: WebScraperComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "playwright", "bs4", "lxml" ]

    async def _setup(self) -> None:
        """Install playwright browsers after package installation."""
        import subprocess
        import sys

        # Install playwright browsers (chromium, firefox, webkit)
        subprocess.run(
            [ sys.executable, "-m", "playwright", "install", "chromium" ],
            check=True,
            capture_output=True
        )

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WebScraperAction(action, self.config.headers, self.config.cookies, self.config.timeout).run(context)
