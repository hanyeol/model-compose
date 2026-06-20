"""Unit tests for ``CloudflareHttpTunnelGatewayConfig.validate_named_tunnel_config``."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.gateway.impl.http_tunnel.impl.cloudflare import (
    CloudflareHttpTunnelGatewayConfig,
)


class TestNamedTunnelConfig:
    def test_token_only_ok(self):
        cfg = CloudflareHttpTunnelGatewayConfig(type="http-tunnel", driver="cloudflare", token="t")
        assert cfg.token == "t"

    def test_no_args_ok(self):
        # All optional — quick-tunnel mode.
        CloudflareHttpTunnelGatewayConfig(type="http-tunnel", driver="cloudflare")

    def test_tunnel_and_credentials_file_together_ok(self):
        cfg = CloudflareHttpTunnelGatewayConfig(
            type="http-tunnel", driver="cloudflare", tunnel="my-tunnel", credentials_file="/etc/cloudflared/creds.json",
        )
        assert cfg.tunnel == "my-tunnel"
        assert cfg.credentials_file == "/etc/cloudflared/creds.json"

    def test_tunnel_without_credentials_file_rejected(self):
        with pytest.raises(ValidationError, match="'credentials_file' is required when 'tunnel' is specified"):
            CloudflareHttpTunnelGatewayConfig(type="http-tunnel", driver="cloudflare", tunnel="my-tunnel")

    def test_credentials_file_without_tunnel_rejected(self):
        with pytest.raises(ValidationError, match="'tunnel' is required when 'credentials_file' is specified"):
            CloudflareHttpTunnelGatewayConfig(type="http-tunnel", driver="cloudflare", credentials_file="/etc/c.json")

    def test_token_and_tunnel_together_rejected(self):
        with pytest.raises(ValidationError, match="Cannot specify both 'token' and 'tunnel'"):
            CloudflareHttpTunnelGatewayConfig(
                type="http-tunnel",
                driver="cloudflare",
                token="t",
                tunnel="my-tunnel",
                credentials_file="/etc/c.json",
            )
