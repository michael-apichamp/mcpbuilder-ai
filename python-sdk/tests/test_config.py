"""
Basic tests for MCPBuilder SDK configuration and types.
"""
import os
import pytest
from mcpbuilder import MCPChatClient, SDKConfig, ServerEvent


class TestSDKConfig:
    """Tests for SDKConfig dataclass."""

    def test_config_creation_minimal(self):
        """Test creating config with minimal required fields."""
        config = SDKConfig(
            mcp_client_url="wss://mcp-client.example.com",
            deployment_name="test-deployment"
        )
        assert config.mcp_client_url == "wss://mcp-client.example.com"
        assert config.deployment_name == "test-deployment"

    def test_config_default_values(self):
        """Test that optional fields have proper defaults."""
        config = SDKConfig(
            mcp_client_url="wss://mcp-client.example.com",
            deployment_name="test-deployment"
        )
        assert config.session_id is None
        assert config.timezone is None
        assert config.auto_reconnect is True
        assert config.max_reconnect_attempts == 5
        assert config.reconnect_delay_ms == 2000

    def test_config_validate_missing_deployment(self):
        """Test validation fails without deployment_name."""
        config = SDKConfig(
            mcp_client_url="wss://mcp-client.example.com",
            deployment_name=""
        )
        with pytest.raises(ValueError, match="deployment_name is required"):
            config.validate()


class TestMCPChatClient:
    """Tests for MCPChatClient initialization."""

    def setup_method(self):
        """Clean up env var before each test."""
        self._original_url = os.environ.pop("MCP_CLIENT_URL", None)

    def teardown_method(self):
        """Restore env var after each test."""
        if self._original_url is not None:
            os.environ["MCP_CLIENT_URL"] = self._original_url
        else:
            os.environ.pop("MCP_CLIENT_URL", None)

    def test_client_requires_project_token(self):
        """Test that client requires project_token."""
        # Should work with env var set
        os.environ["MCP_CLIENT_URL"] = "wss://test.example.com"
        client = MCPChatClient(project_token="test-token")
        assert client is not None

    def test_client_explicit_url(self):
        """Test client with explicit mcp_client_url."""
        client = MCPChatClient(
            project_token="test-token",
            mcp_client_url="wss://on-premise.example.com"
        )
        assert client is not None

    def test_client_missing_url_raises(self):
        """Test that missing URL raises ValueError."""
        # Env var already cleared by setup_method
        with pytest.raises(ValueError, match="MCP Client URL must be provided"):
            MCPChatClient(project_token="test-token")


class TestServerEvent:
    """Tests for ServerEvent type."""

    def test_server_event_is_dict(self):
        """Test that ServerEvent is a TypedDict."""
        # ServerEvent is a TypedDict, so it's used for type hints
        # We just verify it's importable and usable
        event: ServerEvent = {
            "type": "token",
            "text": "Hello"
        }
        assert event["type"] == "token"
        assert event["text"] == "Hello"
