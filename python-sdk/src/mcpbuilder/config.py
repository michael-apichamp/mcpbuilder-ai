"""SDK Configuration management."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SDKConfig:
    """
    Configuration for the MCPBuilder Python SDK.
    
    This is a simple dataclass for configuration. The consuming application
    is responsible for loading values from environment variables, config files,
    or any other source.
    
    Example:
        # Load from environment variables
        import os
        config = SDKConfig(
            mcp_client_url=os.getenv("MCP_CLIENT_URL"),
            deployment_name=os.getenv("DEPLOYMENT_NAME"),
        )
    """
    
    # Required: Deployment identifier
    deployment_name: str = ""
    
    # MCP Client Service URL - set via environment variable in deployment
    mcp_client_url: str = ""
    
    # Optional session ID (for resuming conversations)
    session_id: Optional[str] = None
    
    # Client timezone
    timezone: Optional[str] = None
    
    # Reconnection settings
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 5
    reconnect_delay_ms: int = 2000
    
    def validate(self) -> None:
        """
        Validate that required fields are set.
        
        Raises:
            ValueError: If deployment_name is not set
        """
        if not self.deployment_name:
            raise ValueError("deployment_name is required")
