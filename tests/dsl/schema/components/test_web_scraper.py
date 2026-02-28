import pytest
from pydantic import ValidationError
from mindor.dsl.schema.action import WebScraperActionConfig, WebScraperSubmitConfig
from mindor.dsl.schema.component import WebScraperComponentConfig

class TestWebScraperActionConfig:
    """Test WebScraperActionConfig schema validation."""

    def test_minimal_valid_config(self):
        """Test minimal valid configuration."""
        config = WebScraperActionConfig(
            url="https://example.com"
        )
        assert config.url == "https://example.com"
        assert config.extract_mode == "text"
        assert config.multiple is False
        assert config.enable_javascript is False
        assert config.submit is None

    def test_full_config_with_selector(self):
        """Test full configuration with CSS selector."""
        config = WebScraperActionConfig(
            url="https://example.com",
            headers={"User-Agent": "test-agent"},
            selector=".article",
            extract_mode="html",
            multiple=True,
            timeout="60s"
        )
        assert config.url == "https://example.com"
        assert config.headers == {"User-Agent": "test-agent"}
        assert config.selector == ".article"
        assert config.extract_mode == "html"
        assert config.multiple is True
        assert config.timeout == "60s"

    def test_full_config_with_xpath(self):
        """Test full configuration with XPath."""
        config = WebScraperActionConfig(
            url="https://example.com",
            xpath="//div[@class='content']",
            extract_mode="text",
            multiple=False
        )
        assert config.xpath == "//div[@class='content']"
        assert config.selector is None

    def test_attribute_extraction(self):
        """Test attribute extraction configuration."""
        config = WebScraperActionConfig(
            url="https://example.com",
            selector="a.link",
            extract_mode="attribute",
            attribute="href"
        )
        assert config.extract_mode == "attribute"
        assert config.attribute == "href"

    def test_javascript_rendering(self):
        """Test JavaScript rendering configuration."""
        config = WebScraperActionConfig(
            url="https://example.com",
            enable_javascript=True,
            wait_for=".dynamic-content"
        )
        assert config.enable_javascript is True
        assert config.wait_for == ".dynamic-content"

    def test_invalid_selector_and_xpath_both(self):
        """Test that both selector and xpath cannot be specified."""
        with pytest.raises(ValidationError) as exc_info:
            WebScraperActionConfig(
                url="https://example.com",
                selector=".article",
                xpath="//div"
            )
        assert "Cannot specify both 'selector' and 'xpath'" in str(exc_info.value)

    def test_invalid_attribute_without_name(self):
        """Test that attribute name must be specified for attribute extraction."""
        with pytest.raises(ValidationError) as exc_info:
            WebScraperActionConfig(
                url="https://example.com",
                extract_mode="attribute"
            )
        assert "'attribute' must be specified when extract_mode='attribute'" in str(exc_info.value)

    def test_invalid_wait_for_without_javascript(self):
        """Test that wait_for requires javascript to be enabled."""
        with pytest.raises(ValidationError) as exc_info:
            WebScraperActionConfig(
                url="https://example.com",
                wait_for=".content"
            )
        assert "'wait_for' can only be used when enable_javascript=true" in str(exc_info.value)

    def test_missing_url(self):
        """Test that url is required."""
        with pytest.raises(ValidationError) as exc_info:
            WebScraperActionConfig()
        assert "url" in str(exc_info.value).lower()

    def test_form_submission_config(self):
        """Test form submission configuration."""
        config = WebScraperActionConfig(
            url="https://example.com/login",
            enable_javascript=True,
            submit=WebScraperSubmitConfig(
                selector="form#login",
                form={
                    "input[name='username']": "user@example.com",
                    "input[name='password']": "secret123"
                }
            )
        )
        assert config.enable_javascript is True
        assert config.submit is not None
        assert config.submit.selector == "form#login"
        assert config.submit.form["input[name='username']"] == "user@example.com"
        assert config.submit.form["input[name='password']"] == "secret123"

    def test_submit_requires_javascript(self):
        """Test that submit requires enable_javascript=true."""
        with pytest.raises(ValidationError) as exc_info:
            WebScraperActionConfig(
                url="https://example.com",
                enable_javascript=False,
                submit=WebScraperSubmitConfig(
                    form={"input": "value"}
                )
            )
        assert "'submit' requires enable_javascript=true" in str(exc_info.value)

    def test_submit_config_selector_and_xpath_both(self):
        """Test that submit config cannot have both selector and xpath."""
        with pytest.raises(ValidationError) as exc_info:
            WebScraperSubmitConfig(
                selector="form#login",
                xpath="//form[@id='login']",
                form={"input": "value"}
            )
        assert "Cannot specify both 'selector' and 'xpath' in submit config" in str(exc_info.value)

    def test_submit_config_without_form(self):
        """Test that submit config can be created without form data (just clicking submit button)."""
        config = WebScraperSubmitConfig(
            selector="button[type='submit']"
        )
        assert config.selector == "button[type='submit']"
        assert config.form is None

class TestWebScraperComponentConfig:
    """Test WebScraperComponentConfig schema validation."""

    def test_minimal_valid_config(self):
        """Test minimal valid component configuration."""
        config = WebScraperComponentConfig(
            id="scraper",
            type="web-scraper"
        )
        assert config.id == "scraper"
        assert config.type == "web-scraper"
        assert config.headers == {}
        assert config.timeout == "30s"
        assert config.actions == []

    def test_component_with_default_headers(self):
        """Test component with default headers."""
        config = WebScraperComponentConfig(
            id="scraper",
            type="web-scraper",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"},
            timeout="60s"
        )
        assert config.headers == {"User-Agent": "Mozilla/5.0", "Accept": "text/html"}
        assert config.timeout == "60s"

    def test_component_with_single_action(self):
        """Test component with a single action."""
        config = WebScraperComponentConfig(
            id="scraper",
            type="web-scraper",
            actions=[
                WebScraperActionConfig(
                    url="https://example.com",
                    selector=".article"
                )
            ]
        )
        assert len(config.actions) == 1
        assert config.actions[0].url == "https://example.com"
        assert config.actions[0].selector == ".article"

    def test_component_with_multiple_actions(self):
        """Test component with multiple actions."""
        config = WebScraperComponentConfig(
            id="scraper",
            type="web-scraper",
            actions=[
                WebScraperActionConfig(
                    id="action1",
                    url="https://example.com/page1",
                    selector=".content"
                ),
                WebScraperActionConfig(
                    id="action2",
                    url="https://example.com/page2",
                    xpath="//div[@class='article']"
                )
            ]
        )
        assert len(config.actions) == 2
        assert config.actions[0].id == "action1"
        assert config.actions[1].id == "action2"

    def test_inflate_single_action(self):
        """Test that single action properties are inflated into actions list."""
        config = WebScraperComponentConfig(
            id="scraper",
            type="web-scraper",
            action={
                "url": "https://example.com",
                "selector": ".article"
            }
        )
        assert len(config.actions) == 1
        assert config.actions[0].url == "https://example.com"
        assert config.actions[0].selector == ".article"

    def test_inflate_preserves_explicit_actions(self):
        """Test that explicit actions list is not overridden."""
        config = WebScraperComponentConfig(
            id="scraper",
            type="web-scraper",
            actions=[
                WebScraperActionConfig(
                    url="https://example.com",
                    selector=".content"
                )
            ]
        )
        assert len(config.actions) == 1
        assert config.actions[0].selector == ".content"

class TestWebScraperIntegration:
    """Test integration scenarios between component and action configs."""

    def test_action_headers_merge_concept(self):
        """Test that action can have its own headers (actual merging happens in service layer)."""
        component_config = WebScraperComponentConfig(
            id="scraper",
            type="web-scraper",
            headers={"User-Agent": "component-agent", "Accept": "text/html"}
        )

        action_config = WebScraperActionConfig(
            url="https://example.com",
            headers={"User-Agent": "action-agent", "Custom-Header": "value"}
        )

        # Component has default headers
        assert component_config.headers["User-Agent"] == "component-agent"

        # Action has its own headers
        assert action_config.headers["User-Agent"] == "action-agent"
        assert action_config.headers["Custom-Header"] == "value"

    def test_action_timeout_override_concept(self):
        """Test that action can override component timeout."""
        component_config = WebScraperComponentConfig(
            id="scraper",
            type="web-scraper",
            timeout="30s"
        )

        action_config = WebScraperActionConfig(
            url="https://example.com",
            timeout="120s"
        )

        assert component_config.timeout == "30s"
        assert action_config.timeout == "120s"

    def test_extract_modes(self):
        """Test all extraction modes."""
        # Text extraction
        text_config = WebScraperActionConfig(
            url="https://example.com",
            selector=".content",
            extract_mode="text"
        )
        assert text_config.extract_mode == "text"

        # HTML extraction
        html_config = WebScraperActionConfig(
            url="https://example.com",
            selector=".content",
            extract_mode="html"
        )
        assert html_config.extract_mode == "html"

        # Attribute extraction
        attr_config = WebScraperActionConfig(
            url="https://example.com",
            selector="a",
            extract_mode="attribute",
            attribute="href"
        )
        assert attr_config.extract_mode == "attribute"
        assert attr_config.attribute == "href"

    def test_form_submission_with_component(self):
        """Test form submission with component configuration."""
        component_config = WebScraperComponentConfig(
            id="scraper",
            type="web-scraper",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout="60s"
        )

        action_config = WebScraperActionConfig(
            url="https://example.com/login",
            enable_javascript=True,
            wait_for=".dashboard",
            submit=WebScraperSubmitConfig(
                selector="form#login",
                form={
                    "input[name='email']": "test@example.com",
                    "input[name='password']": "password123"
                }
            )
        )

        assert component_config.headers["User-Agent"] == "Mozilla/5.0"
        assert component_config.timeout == "60s"
        assert action_config.submit is not None
        assert action_config.submit.selector == "form#login"
        assert action_config.wait_for == ".dashboard"

    def test_form_submission_with_xpath(self):
        """Test form submission using XPath."""
        config = WebScraperActionConfig(
            url="https://example.com/contact",
            enable_javascript=True,
            submit=WebScraperSubmitConfig(
                xpath="//form[@id='contact-form']",
                form={
                    "//input[@name='name']": "John Doe",
                    "//input[@name='email']": "john@example.com",
                    "//textarea[@name='message']": "Hello!"
                }
            )
        )
        assert config.submit is not None
        assert config.submit.xpath == "//form[@id='contact-form']"
        assert len(config.submit.form) == 3
