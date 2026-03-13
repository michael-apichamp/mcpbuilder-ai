"""MCPBuilder Python SDK for agent integration with MCP services.

The SDK loads the MCP Client URL from MCP_CLIENT_URL environment variable,
or accepts an explicit mcp_client_url parameter for on-premise deployments.

Example:
    import os
    from mcpbuilder import MCPChatClient
    
    client = MCPChatClient(project_token=os.getenv("PROJECT_TOKEN"))
    
    client.on_token(lambda t: print(t, end=""))
    
    await client.connect("my-deployment")
    await client.send_message("Hello!")
"""

__version__ = "0.1.0"

from .client import MCPChatClient
from .types import ServerEvent, ClientMessage, HistoryMessage, MessageRole
from .config import SDKConfig

__all__ = [
    # Primary API
    "MCPChatClient",
    "ServerEvent",
    "ClientMessage",
    # Message history types
    "HistoryMessage",
    "MessageRole",
    # Configuration helper (optional)
    "SDKConfig",
]
