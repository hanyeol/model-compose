import pytest
from pydantic import ValidationError
from mindor.dsl.schema.action import (
    HttpClientActionConfig,
    HttpClientPollingCompletionConfig,
    HttpClientCallbackCompletionConfig,
    HttpClientCompletionType
)
from mindor.dsl.schema.component import HttpClientComponentConfig
from mindor.dsl.schema.transport.http import HttpStreamFormat

class TestHttpClientActionConfig:
    """Test HttpClientActionConfig schema validation."""

    def test_minimal_valid_config_with_endpoint(self):
        """Test minimal valid configuration with endpoint."""
        config = HttpClientActionConfig(
            endpoint="https://api.example.com/v1/chat"
        )
        assert config.endpoint == "https://api.example.com/v1/chat"
        assert config.path is None
        assert config.method == "POST"
        assert config.headers == {}
        assert config.body == {}
        assert config.params == {}

    def test_minimal_valid_config_with_path(self):
        """Test minimal valid configuration with path."""
        config = HttpClientActionConfig(
            path="/v1/chat"
        )
        assert config.path == "/v1/chat"
        assert config.endpoint is None
        assert config.method == "POST"

    def test_full_config_with_endpoint(self):
        """Test full configuration with endpoint."""
        config = HttpClientActionConfig(
            endpoint="https://api.example.com/v1/chat",
            method="POST",
            headers={"Authorization": "Bearer token123", "Content-Type": "application/json"},
            body={"prompt": "Hello", "max_tokens": 100},
            params={"version": "1.0"},
            stream_format=HttpStreamFormat.JSON
        )
        assert config.endpoint == "https://api.example.com/v1/chat"
        assert config.method == "POST"
        assert config.headers["Authorization"] == "Bearer token123"
        assert config.body["prompt"] == "Hello"
        assert config.params["version"] == "1.0"
        assert config.stream_format == HttpStreamFormat.JSON

    def test_different_http_methods(self):
        """Test different HTTP methods."""
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            config = HttpClientActionConfig(
                endpoint="https://api.example.com/resource",
                method=method
            )
            assert config.method == method

    def test_streaming_formats(self):
        """Test different streaming formats."""
        # JSON format
        json_config = HttpClientActionConfig(
            endpoint="https://api.example.com/stream",
            stream_format=HttpStreamFormat.JSON
        )
        assert json_config.stream_format == HttpStreamFormat.JSON

        # TEXT format
        text_config = HttpClientActionConfig(
            endpoint="https://api.example.com/stream",
            stream_format=HttpStreamFormat.TEXT
        )
        assert text_config.stream_format == HttpStreamFormat.TEXT

    def test_invalid_both_endpoint_and_path(self):
        """Test that both endpoint and path cannot be specified."""
        with pytest.raises(ValidationError) as exc_info:
            HttpClientActionConfig(
                endpoint="https://api.example.com/v1/chat",
                path="/v1/chat"
            )
        assert "Either 'endpoint' or 'path' must be set, but not both" in str(exc_info.value)

    def test_invalid_neither_endpoint_nor_path(self):
        """Test that either endpoint or path must be specified."""
        with pytest.raises(ValidationError) as exc_info:
            HttpClientActionConfig()
        assert "Either 'endpoint' or 'path' must be set, but not both" in str(exc_info.value)

class TestHttpClientPollingCompletionConfig:
    """Test HttpClientPollingCompletionConfig schema validation."""

    def test_minimal_polling_config_with_endpoint(self):
        """Test minimal polling configuration with endpoint."""
        config = HttpClientPollingCompletionConfig(
            type=HttpClientCompletionType.POLLING,
            endpoint="https://api.example.com/status/123"
        )
        assert config.type == HttpClientCompletionType.POLLING
        assert config.endpoint == "https://api.example.com/status/123"
        assert config.path is None
        assert config.method == "GET"

    def test_minimal_polling_config_with_path(self):
        """Test minimal polling configuration with path."""
        config = HttpClientPollingCompletionConfig(
            type=HttpClientCompletionType.POLLING,
            path="/status/123"
        )
        assert config.path == "/status/123"
        assert config.endpoint is None

    def test_full_polling_config(self):
        """Test full polling configuration."""
        config = HttpClientPollingCompletionConfig(
            type=HttpClientCompletionType.POLLING,
            endpoint="https://api.example.com/jobs/123",
            method="POST",
            headers={"Authorization": "Bearer token"},
            body={"check": True},
            params={"include": "details"},
            status="data.status",
            success_when=["completed", "success"],
            fail_when=["failed", "error"],
            interval="5s",
            timeout="60s",
            stream_format=HttpStreamFormat.JSON
        )
        assert config.endpoint == "https://api.example.com/jobs/123"
        assert config.method == "POST"
        assert config.status == "data.status"
        assert config.success_when == ["completed", "success"]
        assert config.fail_when == ["failed", "error"]
        assert config.interval == "5s"
        assert config.timeout == "60s"

    def test_polling_status_normalization_single_value(self):
        """Test that single status values are normalized to lists."""
        config = HttpClientPollingCompletionConfig(
            type=HttpClientCompletionType.POLLING,
            endpoint="https://api.example.com/status",
            success_when="completed",
            fail_when="failed"
        )
        assert config.success_when == ["completed"]
        assert config.fail_when == ["failed"]

    def test_polling_status_normalization_numeric(self):
        """Test that numeric status values are normalized."""
        config = HttpClientPollingCompletionConfig(
            type=HttpClientCompletionType.POLLING,
            endpoint="https://api.example.com/status",
            success_when=200,
            fail_when=500
        )
        assert config.success_when == [200]
        assert config.fail_when == [500]

    def test_invalid_polling_both_endpoint_and_path(self):
        """Test that polling cannot have both endpoint and path."""
        with pytest.raises(ValidationError) as exc_info:
            HttpClientPollingCompletionConfig(
                type=HttpClientCompletionType.POLLING,
                endpoint="https://api.example.com/status",
                path="/status"
            )
        assert "Either 'endpoint' or 'path' must be set, but not both" in str(exc_info.value)

    def test_invalid_polling_neither_endpoint_nor_path(self):
        """Test that polling must have either endpoint or path."""
        with pytest.raises(ValidationError) as exc_info:
            HttpClientPollingCompletionConfig(
                type=HttpClientCompletionType.POLLING
            )
        assert "Either 'endpoint' or 'path' must be set, but not both" in str(exc_info.value)


class TestHttpClientCallbackCompletionConfig:
    """Test HttpClientCallbackCompletionConfig schema validation."""

    def test_minimal_callback_config(self):
        """Test minimal callback configuration."""
        config = HttpClientCallbackCompletionConfig(
            type=HttpClientCompletionType.CALLBACK
        )
        assert config.type == HttpClientCompletionType.CALLBACK
        assert config.wait_for is None

    def test_callback_config_with_wait_for(self):
        """Test callback configuration with wait_for."""
        config = HttpClientCallbackCompletionConfig(
            type=HttpClientCompletionType.CALLBACK,
            wait_for="job_123"
        )
        assert config.wait_for == "job_123"

    def test_callback_config_with_stream_format(self):
        """Test callback configuration with stream format."""
        config = HttpClientCallbackCompletionConfig(
            type=HttpClientCompletionType.CALLBACK,
            wait_for="job_123",
            stream_format=HttpStreamFormat.JSON
        )
        assert config.stream_format == HttpStreamFormat.JSON

class TestHttpClientActionConfigWithCompletion:
    """Test HttpClientActionConfig with completion configurations."""

    def test_action_with_polling_completion(self):
        """Test action with polling completion."""
        config = HttpClientActionConfig(
            endpoint="https://api.example.com/jobs",
            method="POST",
            body={"task": "process"},
            completion=HttpClientPollingCompletionConfig(
                type=HttpClientCompletionType.POLLING,
                endpoint="https://api.example.com/jobs/123",
                status="status",
                success_when=["completed"]
            )
        )
        assert config.endpoint == "https://api.example.com/jobs"
        assert config.completion.type == HttpClientCompletionType.POLLING
        assert config.completion.endpoint == "https://api.example.com/jobs/123"

    def test_action_with_callback_completion(self):
        """Test action with callback completion."""
        config = HttpClientActionConfig(
            endpoint="https://api.example.com/async-task",
            method="POST",
            completion=HttpClientCallbackCompletionConfig(
                type=HttpClientCompletionType.CALLBACK,
                wait_for="task_123"
            )
        )
        assert config.completion.type == HttpClientCompletionType.CALLBACK
        assert config.completion.wait_for == "task_123"

    def test_action_with_polling_using_path(self):
        """Test action with polling completion using relative paths."""
        config = HttpClientActionConfig(
            path="/jobs",
            completion=HttpClientPollingCompletionConfig(
                type=HttpClientCompletionType.POLLING,
                path="/jobs/status",
                status="state",
                success_when=["done"]
            )
        )
        assert config.path == "/jobs"
        assert config.completion.path == "/jobs/status"

class TestHttpClientComponentConfig:
    """Test HttpClientComponentConfig schema validation."""

    def test_minimal_valid_config(self):
        """Test minimal valid component configuration."""
        config = HttpClientComponentConfig(
            id="client",
            type="http-client"
        )
        assert config.id == "client"
        assert config.type == "http-client"
        assert config.base_url is None
        assert config.headers == {}
        assert config.actions == []

    def test_component_with_base_url(self):
        """Test component with base URL."""
        config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            base_url="https://api.example.com"
        )
        assert config.base_url == "https://api.example.com"

    def test_component_with_default_headers(self):
        """Test component with default headers."""
        config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
                "User-Agent": "model-compose/1.0"
            }
        )
        assert config.headers["Authorization"] == "Bearer token"
        assert config.headers["Content-Type"] == "application/json"
        assert config.headers["User-Agent"] == "model-compose/1.0"

    def test_component_with_single_action(self):
        """Test component with a single action."""
        config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            base_url="https://api.example.com",
            actions=[
                HttpClientActionConfig(
                    path="/v1/chat",
                    method="POST"
                )
            ]
        )
        assert len(config.actions) == 1
        assert config.actions[0].path == "/v1/chat"

    def test_component_with_multiple_actions(self):
        """Test component with multiple actions."""
        config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            base_url="https://api.example.com",
            actions=[
                HttpClientActionConfig(
                    id="chat",
                    path="/v1/chat",
                    method="POST"
                ),
                HttpClientActionConfig(
                    id="completion",
                    path="/v1/completions",
                    method="POST"
                )
            ]
        )
        assert len(config.actions) == 2
        assert config.actions[0].id == "chat"
        assert config.actions[1].id == "completion"

    def test_inflate_single_action(self):
        """Test that single action properties are inflated into actions list."""
        config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            base_url="https://api.example.com",
            action={
                "path": "/v1/chat",
                "method": "POST",
                "body": {"model": "gpt-4"}
            }
        )
        assert len(config.actions) == 1
        assert config.actions[0].path == "/v1/chat"
        assert config.actions[0].method == "POST"
        assert config.actions[0].body["model"] == "gpt-4"

    def test_inflate_preserves_explicit_actions(self):
        """Test that explicit actions list is not overridden."""
        config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            base_url="https://api.example.com",
            actions=[
                HttpClientActionConfig(
                    path="/v1/chat"
                )
            ]
        )
        assert len(config.actions) == 1
        assert config.actions[0].path == "/v1/chat"

    def test_validation_path_requires_base_url(self):
        """Test that using path in action requires base_url in component."""
        with pytest.raises(ValidationError) as exc_info:
            HttpClientComponentConfig(
                id="client",
                type="http-client",
                actions=[
                    HttpClientActionConfig(
                        path="/v1/chat"
                    )
                ]
            )
        assert "uses 'path' but 'base_url' is not set" in str(exc_info.value)

    def test_validation_polling_path_requires_base_url(self):
        """Test that using path in polling completion requires base_url."""
        with pytest.raises(ValidationError) as exc_info:
            HttpClientComponentConfig(
                id="client",
                type="http-client",
                actions=[
                    HttpClientActionConfig(
                        endpoint="https://api.example.com/jobs",
                        completion=HttpClientPollingCompletionConfig(
                            type=HttpClientCompletionType.POLLING,
                            path="/status"
                        )
                    )
                ]
            )
        assert "uses 'path' but 'base_url' is not set" in str(exc_info.value)

    def test_endpoint_works_without_base_url(self):
        """Test that using endpoint works without base_url."""
        config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            actions=[
                HttpClientActionConfig(
                    endpoint="https://api.example.com/v1/chat"
                )
            ]
        )
        assert config.actions[0].endpoint == "https://api.example.com/v1/chat"

class TestHttpClientIntegration:
    """Test integration scenarios between component and action configs."""

    def test_api_with_polling_pattern(self):
        """Test typical async API pattern with polling."""
        component_config = HttpClientComponentConfig(
            id="async-api",
            type="http-client",
            base_url="https://api.example.com",
            headers={"Authorization": "Bearer secret-token"}
        )

        action_config = HttpClientActionConfig(
            path="/v1/jobs",
            method="POST",
            body={"type": "long-running-task", "params": {}},
            completion=HttpClientPollingCompletionConfig(
                type=HttpClientCompletionType.POLLING,
                path="/v1/jobs/${response.job_id}",
                method="GET",
                status="status",
                success_when=["completed", "success"],
                fail_when=["failed", "error", "cancelled"],
                interval="5s",
                timeout="300s"
            )
        )

        assert component_config.base_url == "https://api.example.com"
        assert action_config.path == "/v1/jobs"
        assert action_config.completion.path == "/v1/jobs/${response.job_id}"
        assert action_config.completion.interval == "5s"

    def test_streaming_api_pattern(self):
        """Test streaming API pattern."""
        config = HttpClientComponentConfig(
            id="streaming-api",
            type="http-client",
            base_url="https://api.openai.com",
            headers={"Authorization": "Bearer sk-..."},
            actions=[
                HttpClientActionConfig(
                    id="chat",
                    path="/v1/chat/completions",
                    method="POST",
                    body={
                        "model": "gpt-4",
                        "messages": [],
                        "stream": True
                    },
                    stream_format=HttpStreamFormat.JSON
                )
            ]
        )
        assert config.actions[0].stream_format == HttpStreamFormat.JSON

    def test_rest_api_crud_operations(self):
        """Test typical REST API CRUD operations."""
        config = HttpClientComponentConfig(
            id="rest-api",
            type="http-client",
            base_url="https://api.example.com/v1",
            headers={"Content-Type": "application/json"},
            actions=[
                HttpClientActionConfig(
                    id="create",
                    path="/resources",
                    method="POST"
                ),
                HttpClientActionConfig(
                    id="read",
                    path="/resources/${id}",
                    method="GET"
                ),
                HttpClientActionConfig(
                    id="update",
                    path="/resources/${id}",
                    method="PUT"
                ),
                HttpClientActionConfig(
                    id="delete",
                    path="/resources/${id}",
                    method="DELETE"
                ),
                HttpClientActionConfig(
                    id="list",
                    path="/resources",
                    method="GET"
                )
            ]
        )
        assert len(config.actions) == 5
        assert config.actions[0].id == "create"
        assert config.actions[0].method == "POST"
        assert config.actions[3].id == "delete"
        assert config.actions[3].method == "DELETE"

    def test_callback_based_webhook_pattern(self):
        """Test callback-based webhook pattern."""
        config = HttpClientComponentConfig(
            id="webhook-api",
            type="http-client",
            base_url="https://api.example.com",
            actions=[
                HttpClientActionConfig(
                    id="submit",
                    path="/v1/process",
                    method="POST",
                    body={
                        "data": "${input.data}",
                        "callback_url": "https://myapp.com/webhook"
                    },
                    completion=HttpClientCallbackCompletionConfig(
                        type=HttpClientCompletionType.CALLBACK,
                        wait_for="${response.callback_id}"
                    )
                )
            ]
        )
        assert config.actions[0].completion.type == HttpClientCompletionType.CALLBACK

    def test_mixed_endpoints_and_paths(self):
        """Test component with mix of absolute endpoints and relative paths."""
        config = HttpClientComponentConfig(
            id="mixed-client",
            type="http-client",
            base_url="https://api.example.com",
            actions=[
                # Action with relative path (uses base_url)
                HttpClientActionConfig(
                    id="internal",
                    path="/v1/internal",
                    method="GET"
                ),
                # Action with absolute endpoint (ignores base_url)
                HttpClientActionConfig(
                    id="external",
                    endpoint="https://external-api.com/v1/data",
                    method="GET"
                )
            ]
        )
        assert config.actions[0].path == "/v1/internal"
        assert config.actions[1].endpoint == "https://external-api.com/v1/data"

    def test_action_header_override(self):
        """Test action header override of component headers."""
        component_config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            headers={
                "Authorization": "Bearer component-token",
                "User-Agent": "model-compose/1.0"
            }
        )

        action_config = HttpClientActionConfig(
            endpoint="https://api.example.com/v1/data",
            headers={
                "Authorization": "Bearer action-token",
                "X-Custom-Header": "value"
            }
        )

        # Component has default headers
        assert component_config.headers["Authorization"] == "Bearer component-token"

        # Action has its own headers (merging happens at service layer)
        assert action_config.headers["Authorization"] == "Bearer action-token"
        assert action_config.headers["X-Custom-Header"] == "value"

    def test_action_header_inheritance(self):
        """Test action header inheritance from component.

        When component has default headers and action doesn't specify headers,
        the component headers should be used (merging happens at service layer).
        """
        component_config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            base_url="https://api.example.com",
            headers={
                "Authorization": "Bearer component-token",
                "User-Agent": "model-compose/1.0",
                "X-API-Version": "v1"
            },
            actions=[
                HttpClientActionConfig(
                    id="action-with-headers",
                    path="/with-headers",
                    headers={
                        "Authorization": "Bearer action-token",
                        "X-Request-ID": "12345"
                    }
                ),
                HttpClientActionConfig(
                    id="action-without-headers",
                    path="/without-headers"
                )
            ]
        )

        # Component has default headers
        assert component_config.headers["Authorization"] == "Bearer component-token"
        assert component_config.headers["User-Agent"] == "model-compose/1.0"
        assert component_config.headers["X-API-Version"] == "v1"

        # First action overrides some headers
        action_with_headers = component_config.actions[0]
        assert action_with_headers.headers["Authorization"] == "Bearer action-token"
        assert action_with_headers.headers["X-Request-ID"] == "12345"
        # Component headers will be merged at service layer

        # Second action has no headers (will inherit component headers at service layer)
        action_without_headers = component_config.actions[1]
        assert action_without_headers.headers == {}

    def test_action_header_partial_override(self):
        """Test action partial header override of component headers.

        When action specifies some headers, it should override only those specific
        headers while inheriting the rest from component (merging at service layer).
        """
        component_config = HttpClientComponentConfig(
            id="client",
            type="http-client",
            base_url="https://api.example.com",
            headers={
                "Authorization": "Bearer default-token",
                "Content-Type": "application/json",
                "User-Agent": "model-compose/1.0",
                "X-API-Version": "v1"
            }
        )

        action_config = HttpClientActionConfig(
            path="/api/resource",
            headers={
                "Authorization": "Bearer custom-token"
            }
        )

        # Component has multiple default headers
        assert len(component_config.headers) == 4
        assert component_config.headers["Authorization"] == "Bearer default-token"
        assert component_config.headers["Content-Type"] == "application/json"

        # Action only overrides Authorization
        assert len(action_config.headers) == 1
        assert action_config.headers["Authorization"] == "Bearer custom-token"
