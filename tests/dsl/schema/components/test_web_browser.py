"""Tests for web-browser component and action schemas (Chrome and Playwright)."""

import pytest
from pydantic import ValidationError, TypeAdapter

from mindor.dsl.schema.action import (
    WebBrowserActionConfig,
    WebBrowserNavigateActionConfig,
    WebBrowserClickActionConfig,
    WebBrowserInputTextActionConfig,
    WebBrowserScreenshotActionConfig,
    WebBrowserEvaluateActionConfig,
    WebBrowserWaitForActionConfig,
    WebBrowserExtractActionConfig,
    WebBrowserGetCookiesActionConfig,
    WebBrowserSetCookiesActionConfig,
    WebBrowserScrollActionConfig,
    WebBrowserActionMethod,
)
from mindor.dsl.schema.component import (
    WebBrowserComponentConfig,
    ChromeWebBrowserComponentConfig,
    PlaywrightWebBrowserComponentConfig,
    WebBrowserDriver,
)


ActionAdapter = TypeAdapter(WebBrowserActionConfig)
ComponentAdapter = TypeAdapter(WebBrowserComponentConfig)


class TestWebBrowserNavigateActionConfig:
    """Test navigate action schema validation."""

    def test_minimal_config(self):
        """Test minimal navigate configuration with defaults."""
        config = WebBrowserNavigateActionConfig(
            method="navigate",
            url="https://example.com"
        )
        assert config.url == "https://example.com"
        assert config.wait_until == "load"

    def test_full_config(self):
        """Test full navigate configuration with all options."""
        config = WebBrowserNavigateActionConfig(
            method="navigate",
            url="https://example.com",
            wait_until="networkidle",
            timeout="10s"
        )
        assert config.wait_until == "networkidle"
        assert config.timeout == "10s"

    def test_missing_url(self):
        """Test that missing url raises validation error."""
        with pytest.raises(ValidationError):
            WebBrowserNavigateActionConfig(method="navigate")


class TestWebBrowserClickActionConfig:
    """Test click action schema validation."""

    def test_click_by_selector(self):
        """Test click action targeting an element by CSS selector."""
        config = WebBrowserClickActionConfig(
            method="click",
            selector="button#submit"
        )
        assert config.selector == "button#submit"
        assert config.xpath is None
        assert config.x is None
        assert config.y is None

    def test_click_by_xpath(self):
        """Test click action targeting an element by XPath."""
        config = WebBrowserClickActionConfig(
            method="click",
            xpath="//button[@id='submit']"
        )
        assert config.xpath == "//button[@id='submit']"
        assert config.selector is None

    def test_click_by_coordinates(self):
        """Test click action targeting a point by x/y coordinates."""
        config = WebBrowserClickActionConfig(
            method="click",
            x=100,
            y=200
        )
        assert config.x == 100
        assert config.y == 200

    def test_invalid_no_target(self):
        """Test that click without any target raises validation error."""
        with pytest.raises(ValidationError, match="Exactly one"):
            WebBrowserClickActionConfig(method="click")

    def test_invalid_multiple_targets(self):
        """Test that click with both selector and xpath raises validation error."""
        with pytest.raises(ValidationError, match="Exactly one"):
            WebBrowserClickActionConfig(
                method="click",
                selector="button",
                xpath="//button"
            )

    def test_invalid_partial_coordinates(self):
        """Test that click with only x coordinate raises validation error."""
        with pytest.raises(ValidationError, match="Exactly one"):
            WebBrowserClickActionConfig(method="click", x=100)


class TestWebBrowserInputTextActionConfig:
    """Test input-text action schema validation."""

    def test_input_with_selector(self):
        """Test input-text action with CSS selector."""
        config = WebBrowserInputTextActionConfig(
            method="input-text",
            selector="input[name='q']",
            text="hello"
        )
        assert config.text == "hello"
        assert config.clear_first is True

    def test_input_with_xpath(self):
        """Test input-text action with XPath and clear_first disabled."""
        config = WebBrowserInputTextActionConfig(
            method="input-text",
            xpath="//input[@name='q']",
            text="hello",
            clear_first=False
        )
        assert config.clear_first is False

    def test_invalid_no_target(self):
        """Test that input-text without target raises validation error."""
        with pytest.raises(ValidationError, match="Either 'selector' or 'xpath'"):
            WebBrowserInputTextActionConfig(method="input-text", text="hello")

    def test_invalid_both_targets(self):
        """Test that input-text with both selector and xpath raises validation error."""
        with pytest.raises(ValidationError, match="Only one"):
            WebBrowserInputTextActionConfig(
                method="input-text",
                selector="input",
                xpath="//input",
                text="hello"
            )

    def test_missing_text(self):
        """Test that input-text without text raises validation error."""
        with pytest.raises(ValidationError):
            WebBrowserInputTextActionConfig(method="input-text", selector="input")


class TestWebBrowserScreenshotActionConfig:
    """Test screenshot action schema validation."""

    def test_defaults(self):
        """Test screenshot action with default values."""
        config = WebBrowserScreenshotActionConfig(method="screenshot")
        assert config.full_page is False
        assert config.selector is None
        assert config.format == "png"
        assert config.quality is None

    def test_full_page_jpeg(self):
        """Test screenshot action with full page JPEG configuration."""
        config = WebBrowserScreenshotActionConfig(
            method="screenshot",
            full_page=True,
            format="jpeg",
            quality=80
        )
        assert config.full_page is True
        assert config.format == "jpeg"
        assert config.quality == 80

    def test_element_screenshot(self):
        """Test screenshot action targeting a specific element."""
        config = WebBrowserScreenshotActionConfig(
            method="screenshot",
            selector=".hero-image"
        )
        assert config.selector == ".hero-image"


class TestWebBrowserEvaluateActionConfig:
    """Test evaluate action schema validation."""

    def test_basic(self):
        """Test basic evaluate action with expression."""
        config = WebBrowserEvaluateActionConfig(
            method="evaluate",
            expression="document.title"
        )
        assert config.expression == "document.title"

    def test_missing_expression(self):
        """Test that evaluate without expression raises validation error."""
        with pytest.raises(ValidationError):
            WebBrowserEvaluateActionConfig(method="evaluate")


class TestWebBrowserWaitForActionConfig:
    """Test wait-for action schema validation."""

    def test_wait_by_selector(self):
        """Test wait-for action with CSS selector and default condition."""
        config = WebBrowserWaitForActionConfig(
            method="wait-for",
            selector=".loaded"
        )
        assert config.condition == "present"

    def test_wait_visible(self):
        """Test wait-for action with XPath and visible condition."""
        config = WebBrowserWaitForActionConfig(
            method="wait-for",
            xpath="//div[@class='content']",
            condition="visible"
        )
        assert config.condition == "visible"

    def test_invalid_no_target(self):
        """Test that wait-for without target raises validation error."""
        with pytest.raises(ValidationError, match="Either 'selector' or 'xpath'"):
            WebBrowserWaitForActionConfig(method="wait-for")

    def test_invalid_both_targets(self):
        """Test that wait-for with both selector and xpath raises validation error."""
        with pytest.raises(ValidationError, match="Only one"):
            WebBrowserWaitForActionConfig(
                method="wait-for",
                selector=".a",
                xpath="//a"
            )


class TestWebBrowserExtractActionConfig:
    """Test extract action schema validation."""

    def test_text_extraction(self):
        """Test text extraction with CSS selector."""
        config = WebBrowserExtractActionConfig(
            method="extract",
            selector=".content",
            extract_mode="text"
        )
        assert config.extract_mode == "text"
        assert config.multiple is False

    def test_html_extraction_multiple(self):
        """Test HTML extraction of multiple elements."""
        config = WebBrowserExtractActionConfig(
            method="extract",
            selector=".item",
            extract_mode="html",
            multiple=True
        )
        assert config.extract_mode == "html"
        assert config.multiple is True

    def test_attribute_extraction(self):
        """Test attribute extraction with specified attribute name."""
        config = WebBrowserExtractActionConfig(
            method="extract",
            selector="a",
            extract_mode="attribute",
            attribute="href"
        )
        assert config.attribute == "href"

    def test_invalid_attribute_without_name(self):
        """Test that attribute extraction without attribute name raises error."""
        with pytest.raises(ValidationError, match="'attribute' is required"):
            WebBrowserExtractActionConfig(
                method="extract",
                selector="a",
                extract_mode="attribute"
            )

    def test_invalid_no_target(self):
        """Test that extract without target raises validation error."""
        with pytest.raises(ValidationError, match="Either 'selector' or 'xpath'"):
            WebBrowserExtractActionConfig(method="extract")


class TestWebBrowserCookieActionConfig:
    """Test cookie action schema validation."""

    def test_get_cookies_default(self):
        """Test get-cookies action with default values."""
        config = WebBrowserGetCookiesActionConfig(method="get-cookies")
        assert config.urls is None

    def test_get_cookies_with_urls(self):
        """Test get-cookies action with specific URLs."""
        config = WebBrowserGetCookiesActionConfig(
            method="get-cookies",
            urls=["https://example.com"]
        )
        assert config.urls == ["https://example.com"]

    def test_set_cookies(self):
        """Test set-cookies action with cookie data."""
        config = WebBrowserSetCookiesActionConfig(
            method="set-cookies",
            cookies=[{"name": "session", "value": "abc", "domain": "example.com"}]
        )
        assert len(config.cookies) == 1

    def test_set_cookies_missing(self):
        """Test that set-cookies without cookies raises validation error."""
        with pytest.raises(ValidationError):
            WebBrowserSetCookiesActionConfig(method="set-cookies")


class TestWebBrowserScrollActionConfig:
    """Test scroll action schema validation."""

    def test_defaults(self):
        """Test scroll action with default values."""
        config = WebBrowserScrollActionConfig(method="scroll")
        assert config.x == 0
        assert config.y == 0
        assert config.selector is None

    def test_scroll_down(self):
        """Test scroll action with vertical offset."""
        config = WebBrowserScrollActionConfig(
            method="scroll",
            y=500
        )
        assert config.y == 500

    def test_scroll_element(self):
        """Test scroll action targeting a specific element."""
        config = WebBrowserScrollActionConfig(
            method="scroll",
            selector=".scrollable",
            y=100
        )
        assert config.selector == ".scrollable"


class TestWebBrowserActionConfigDiscriminator:
    """Test discriminated union resolution by method field."""

    def test_discriminator_navigate(self):
        """Test that navigate method resolves to WebBrowserNavigateActionConfig."""
        config = ActionAdapter.validate_python({"method": "navigate", "url": "https://example.com"})
        assert isinstance(config, WebBrowserNavigateActionConfig)

    def test_discriminator_click(self):
        """Test that click method resolves to WebBrowserClickActionConfig."""
        config = ActionAdapter.validate_python({"method": "click", "selector": "button"})
        assert isinstance(config, WebBrowserClickActionConfig)

    def test_discriminator_input_text(self):
        """Test that input-text method resolves to WebBrowserInputTextActionConfig."""
        config = ActionAdapter.validate_python({"method": "input-text", "selector": "input", "text": "hi"})
        assert isinstance(config, WebBrowserInputTextActionConfig)

    def test_discriminator_screenshot(self):
        """Test that screenshot method resolves to WebBrowserScreenshotActionConfig."""
        config = ActionAdapter.validate_python({"method": "screenshot"})
        assert isinstance(config, WebBrowserScreenshotActionConfig)

    def test_discriminator_evaluate(self):
        """Test that evaluate method resolves to WebBrowserEvaluateActionConfig."""
        config = ActionAdapter.validate_python({"method": "evaluate", "expression": "1+1"})
        assert isinstance(config, WebBrowserEvaluateActionConfig)

    def test_discriminator_wait_for(self):
        """Test that wait-for method resolves to WebBrowserWaitForActionConfig."""
        config = ActionAdapter.validate_python({"method": "wait-for", "selector": ".x"})
        assert isinstance(config, WebBrowserWaitForActionConfig)

    def test_discriminator_extract(self):
        """Test that extract method resolves to WebBrowserExtractActionConfig."""
        config = ActionAdapter.validate_python({"method": "extract", "selector": ".x"})
        assert isinstance(config, WebBrowserExtractActionConfig)

    def test_discriminator_get_cookies(self):
        """Test that get-cookies method resolves to WebBrowserGetCookiesActionConfig."""
        config = ActionAdapter.validate_python({"method": "get-cookies"})
        assert isinstance(config, WebBrowserGetCookiesActionConfig)

    def test_discriminator_set_cookies(self):
        """Test that set-cookies method resolves to WebBrowserSetCookiesActionConfig."""
        config = ActionAdapter.validate_python({"method": "set-cookies", "cookies": [{"name": "a", "value": "b"}]})
        assert isinstance(config, WebBrowserSetCookiesActionConfig)

    def test_discriminator_scroll(self):
        """Test that scroll method resolves to WebBrowserScrollActionConfig."""
        config = ActionAdapter.validate_python({"method": "scroll"})
        assert isinstance(config, WebBrowserScrollActionConfig)


class TestChromeWebBrowserComponentConfig:
    """Test Chrome driver component schema validation."""

    def test_minimal_config(self):
        """Test minimal Chrome configuration with defaults."""
        config = ChromeWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            driver="chrome"
        )
        assert config.driver == WebBrowserDriver.CHROME
        assert config.debugger.host == "localhost"
        assert config.debugger.port == 9222
        assert config.debugger.protocol == "http"
        assert config.debugger.url is None
        assert config.timeout == "30s"
        assert config.actions == []

    def test_driver_default(self):
        """Test that driver defaults to chrome."""
        config = ChromeWebBrowserComponentConfig(
            id="browser",
            type="web-browser"
        )
        assert config.driver == WebBrowserDriver.CHROME

    def test_custom_host_port(self):
        """Test Chrome configuration with custom debugger host and port."""
        config = ChromeWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            debugger={"host": "remote-host", "port": 9333}
        )
        assert config.debugger.host == "remote-host"
        assert config.debugger.port == 9333

    def test_url(self):
        """Test Chrome configuration with debugger URL."""
        config = ChromeWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            debugger={"url": "http://remote-host:9222"}
        )
        assert config.debugger.url == "http://remote-host:9222"

    def test_url_and_host_exclusive(self):
        """Test that debugger url and host cannot both be specified."""
        with pytest.raises(ValueError):
            ChromeWebBrowserComponentConfig(
                id="browser",
                type="web-browser",
                debugger={"url": "http://remote-host:9222", "host": "remote-host"}
            )

    def test_with_actions(self):
        """Test Chrome configuration with multiple actions."""
        config = ChromeWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            actions=[
                WebBrowserNavigateActionConfig(method="navigate", url="https://example.com"),
                WebBrowserScreenshotActionConfig(method="screenshot"),
            ]
        )
        assert len(config.actions) == 2

    def test_with_timeout(self):
        """Test Chrome configuration with custom timeout."""
        config = ChromeWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            timeout="60s"
        )
        assert config.timeout == "60s"


class TestPlaywrightWebBrowserComponentConfig:
    """Test Playwright driver component schema validation."""

    def test_minimal_config(self):
        """Test minimal Playwright configuration with defaults."""
        config = PlaywrightWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            driver="playwright"
        )
        assert config.driver == WebBrowserDriver.PLAYWRIGHT
        assert config.browser == "chromium"
        assert config.headless is True
        assert config.args == []
        assert config.timeout == "30s"
        assert config.actions == []

    def test_firefox(self):
        """Test Playwright configuration with Firefox browser."""
        config = PlaywrightWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            driver="playwright",
            browser="firefox"
        )
        assert config.browser == "firefox"

    def test_webkit_headed(self):
        """Test Playwright configuration with WebKit in headed mode."""
        config = PlaywrightWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            driver="playwright",
            browser="webkit",
            headless=False
        )
        assert config.browser == "webkit"
        assert config.headless is False

    def test_with_args(self):
        """Test Playwright configuration with browser launch arguments."""
        config = PlaywrightWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            driver="playwright",
            args=["--no-sandbox", "--disable-gpu"]
        )
        assert config.args == ["--no-sandbox", "--disable-gpu"]

    def test_with_actions(self):
        """Test Playwright configuration with actions."""
        config = PlaywrightWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            driver="playwright",
            actions=[
                WebBrowserNavigateActionConfig(method="navigate", url="https://example.com"),
            ]
        )
        assert len(config.actions) == 1


class TestWebBrowserComponentConfigDiscriminator:
    """Test discriminated union resolution by driver field."""

    def test_chrome_discriminator(self):
        """Test that chrome driver resolves to ChromeWebBrowserComponentConfig."""
        config = ComponentAdapter.validate_python({
            "id": "browser", "type": "web-browser", "driver": "chrome",
            "debugger": {"host": "remote", "port": 9333}
        })
        assert isinstance(config, ChromeWebBrowserComponentConfig)
        assert config.debugger.host == "remote"

    def test_playwright_discriminator(self):
        """Test that playwright driver resolves to PlaywrightWebBrowserComponentConfig."""
        config = ComponentAdapter.validate_python({
            "id": "browser", "type": "web-browser", "driver": "playwright",
            "browser": "firefox"
        })
        assert isinstance(config, PlaywrightWebBrowserComponentConfig)
        assert config.browser == "firefox"

    def test_default_driver_is_chrome(self):
        """Test that driver defaults to chrome when constructing directly."""
        config = ChromeWebBrowserComponentConfig(
            id="browser", type="web-browser"
        )
        assert config.driver == WebBrowserDriver.CHROME


class TestWebBrowserIntegration:
    """Test integration scenarios."""

    def test_chrome_full_workflow(self):
        """Test Chrome component with multiple action types."""
        config = ChromeWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            debugger={"host": "localhost", "port": 9222},
            timeout="30s",
            actions=[
                WebBrowserNavigateActionConfig(
                    id="navigate",
                    method="navigate",
                    url="${input.url}",
                    wait_until="networkidle"
                ),
                WebBrowserInputTextActionConfig(
                    id="type",
                    method="input-text",
                    selector="input[name='q']",
                    text="${input.query}"
                ),
                WebBrowserClickActionConfig(
                    id="submit",
                    method="click",
                    selector="button[type='submit']"
                ),
                WebBrowserScreenshotActionConfig(
                    id="capture",
                    method="screenshot",
                    full_page=True,
                    format="png"
                ),
                WebBrowserExtractActionConfig(
                    id="results",
                    method="extract",
                    selector=".result",
                    extract_mode="text",
                    multiple=True
                ),
            ]
        )
        assert len(config.actions) == 5
        assert config.actions[0].id == "navigate"
        assert config.actions[1].id == "type"
        assert config.actions[4].multiple is True

    def test_playwright_headless_scrape(self):
        """Test Playwright component for headless scraping."""
        config = PlaywrightWebBrowserComponentConfig(
            id="scraper",
            type="web-browser",
            driver="playwright",
            browser="chromium",
            headless=True,
            timeout="60s",
            actions=[
                WebBrowserNavigateActionConfig(
                    id="go",
                    method="navigate",
                    url="https://example.com",
                    wait_until="load"
                ),
                WebBrowserEvaluateActionConfig(
                    id="title",
                    method="evaluate",
                    expression="document.title"
                ),
            ]
        )
        assert config.browser == "chromium"
        assert config.headless is True
        assert len(config.actions) == 2

    def test_action_timeout_override(self):
        """Test that action can override component timeout."""
        config = ChromeWebBrowserComponentConfig(
            id="browser",
            type="web-browser",
            timeout="30s",
            actions=[
                WebBrowserNavigateActionConfig(
                    method="navigate",
                    url="https://slow-site.com",
                    timeout="120s"
                ),
                WebBrowserEvaluateActionConfig(
                    method="evaluate",
                    expression="document.readyState",
                    timeout="5s"
                ),
            ]
        )
        assert config.timeout == "30s"
        assert config.actions[0].timeout == "120s"
        assert config.actions[1].timeout == "5s"
