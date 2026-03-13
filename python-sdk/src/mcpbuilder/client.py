"""High-level chat client with callback-based event handling.

This module provides the MCPChatClient class which wraps the WebSocket connection
and provides a clean callback-based API for handling chat events.

Example:
    ```python
    import os
    from mcpbuilder import MCPChatClient
    
    # URL is loaded from MCP_CLIENT_URL env var, or pass explicitly for on-premise
    client = MCPChatClient(
        project_token=os.getenv("PROJECT_TOKEN"),
        deployment_name="my-deployment",
        # Optional: provide security params that override loaded credentials
        security_params={
            "X-API-KEY": os.getenv("MY_API_KEY"),
            "Authorization": f"Bearer {os.getenv('MY_ACCESS_TOKEN')}",
        }
    )
    
    # Register callbacks
    client \\
        .on_token(lambda text: print(text, end="", flush=True)) \\
        .on_final(lambda text, tool_calls: print(f"\\n\\nDone!")) \\
        .on_error(lambda msg: print(f"Error: {msg}"))
    
    # Connect and chat
    await client.connect()
    await client.send_message("What's the weather in London?")
    
    # When done
    await client.disconnect()
    ```
"""

import asyncio
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Self

from .websocket_client import WebSocketClient
from .types import ServerEvent, HistoryMessage

logger = logging.getLogger(__name__)

# Default cloud-hosted MCP Client Service URL
DEFAULT_MCP_CLIENT_URL = "https://mcp-client.p.apichap.com"

# Import MCPError for enhanced error handling
from .types import MCPError

# Type aliases for callback signatures
ConnectedCallback = Callable[[str], None]  # (session_id)
TokenCallback = Callable[[str], None]  # (text)
ToolStartCallback = Callable[[str, Dict[str, Any]], None]  # (name, input)
ToolEndCallback = Callable[[str, str, bool, Optional[str]], None]  # (name, output, success, error)
ToolConsentCallback = Callable[[str, str, Dict[str, Any], Optional[str]], None]  # (consent_id, tool, args, desc)
ConsentTimeoutCallback = Callable[[str], None]  # (consent_id)
ConsentPendingCallback = Callable[[str, str, str, float], None]  # (consent_id, tool, message, elapsed_seconds)
FinalCallback = Callable[[str, List[Dict[str, Any]]], None]  # (text, tool_calls)
ErrorCallback = Callable[[str], None]  # (message)
EnhancedErrorCallback = Callable[[MCPError], None]  # (error) - full error details
StatusCallback = Callable[[str], None]  # (message)
DisconnectedCallback = Callable[[Optional[str]], None]  # (reason)


class MCPChatClient:
    """
    High-level MCP chat client with callback-based event handling.
    
    Provides a fluent API for registering event callbacks and sending messages.
    All callbacks are optional - only register the ones you need.
    
    Attributes:
        session_id: The session ID after connecting (None before connect)
        is_connected: Whether currently connected to the service
    """
    
    def __init__(
        self,
        project_token: str,
        deployment_name: str,
        mcp_client_url: Optional[str] = None,
        security_params: Optional[Dict[str, str]] = None,
        system_message: Optional[str] = None,
        language: Optional[str] = None,
        message_history: Optional[List[HistoryMessage]] = None,
        cache_history: bool = False,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 5,
        reconnect_delay_ms: int = 2000,
    ):
        """
        Initialize the chat client.
        
        Args:
            project_token: Authentication token for the project
            deployment_name: Deployment identifier for this client
            mcp_client_url: Optional MCP Client Service WebSocket URL. Only required for 
                on-premise deployments. If not provided, uses MCP_CLIENT_URL environment 
                variable, falling back to the default cloud service (https://mcp-client.apichap.com).
            security_params: Optional dict of security parameters (key-value pairs) that
                will be merged with security headers loaded from chatbot settings. These
                take precedence over loaded values, allowing you to override or provide
                credentials that don't need to be fetched from the secret service.
            system_message: Optional system message/prompt for the LLM. Takes precedence
                over the system message configured in chatbot settings.
            language: Optional language for the assistant (e.g., "English", "German").
                Takes precedence over the language configured in chatbot settings.
            message_history: Optional initial message history to provide context.
                Messages are inserted after the system message but before new user messages.
                Useful for continuing conversations or providing example interactions.
            cache_history: Whether to cache conversation history on the server (default: False).
                If True, messages are automatically appended to history.
                If False, no history is stored server-side.
            auto_reconnect: Enable automatic reconnection on disconnect
            max_reconnect_attempts: Maximum number of reconnection attempts
            reconnect_delay_ms: Base delay between reconnection attempts (exponential backoff)
        """
        # Resolve MCP client URL: explicit param > env var > default cloud service
        resolved_url = mcp_client_url or os.getenv("MCP_CLIENT_URL", DEFAULT_MCP_CLIENT_URL)
        # Convert http/https to ws/wss for WebSocket connection
        resolved_url = resolved_url.rstrip("/")
        if resolved_url.startswith("https://"):
            resolved_url = "wss://" + resolved_url[8:]
        elif resolved_url.startswith("http://"):
            resolved_url = "ws://" + resolved_url[7:]
        self._mcp_client_url = resolved_url
        self._project_token = project_token
        self._deployment_name = deployment_name
        self._security_params = security_params or {}
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_delay_ms = reconnect_delay_ms
        self._system_message: Optional[str] = system_message
        self._language: Optional[str] = language
        self._message_history: Optional[List[HistoryMessage]] = message_history
        self._cache_history: bool = cache_history
        
        self._ws_client = WebSocketClient()
        self._ws_client.on_message(self._handle_event)
        
        self.session_id: Optional[str] = None
        
        # Callback storage
        self._on_connected: Optional[ConnectedCallback] = None
        self._on_token: Optional[TokenCallback] = None
        self._on_tool_start: Optional[ToolStartCallback] = None
        self._on_tool_end: Optional[ToolEndCallback] = None
        self._on_tool_consent_request: Optional[ToolConsentCallback] = None
        self._on_consent_timeout: Optional[ConsentTimeoutCallback] = None
        self._on_consent_pending: Optional[ConsentPendingCallback] = None
        self._on_final: Optional[FinalCallback] = None
        self._on_error: Optional[ErrorCallback] = None
        self._on_error_details: Optional[EnhancedErrorCallback] = None
        self._on_status: Optional[StatusCallback] = None
        self._on_disconnected: Optional[DisconnectedCallback] = None
    
    # =========================================================================
    # Callback Registration (Fluent API)
    # =========================================================================
    
    def on_connected(self, callback: ConnectedCallback) -> Self:
        """
        Register callback for connection established event.
        
        Args:
            callback: Function called with (session_id: str)
        
        Returns:
            Self for method chaining
        """
        self._on_connected = callback
        return self
    
    def on_token(self, callback: TokenCallback) -> Self:
        """
        Register callback for streaming text tokens.
        
        Args:
            callback: Function called with (text: str) for each token
        
        Returns:
            Self for method chaining
        """
        self._on_token = callback
        return self
    
    def on_tool_start(self, callback: ToolStartCallback) -> Self:
        """
        Register callback for tool execution starting.
        
        Args:
            callback: Function called with (name: str, input: dict)
        
        Returns:
            Self for method chaining
        """
        self._on_tool_start = callback
        return self
    
    def on_tool_end(self, callback: ToolEndCallback) -> Self:
        """
        Register callback for tool execution completed.
        
        Args:
            callback: Function called with (name: str, output: str, success: bool, error: Optional[str])
        
        Returns:
            Self for method chaining
        """
        self._on_tool_end = callback
        return self
    
    def on_tool_consent_request(self, callback: ToolConsentCallback) -> Self:
        """
        Register callback for tool consent requests.
        
        When called, you should call `respond_consent()` to allow/deny the tool.
        
        Args:
            callback: Function called with (consent_id: str, tool: str, arguments: dict, description: Optional[str])
        
        Returns:
            Self for method chaining
        """
        self._on_tool_consent_request = callback
        return self
    
    def on_consent_timeout(self, callback: ConsentTimeoutCallback) -> Self:
        """
        Register callback for consent request timeout.
        
        Args:
            callback: Function called with (consent_id: str)
        
        Returns:
            Self for method chaining
        """
        self._on_consent_timeout = callback
        return self
    
    def on_consent_pending(self, callback: ConsentPendingCallback) -> Self:
        """
        Register callback for consent pending warnings.
        
        Called when a consent request hasn't been responded to after ~30s.
        If not registered, a warning will be logged to stderr.
        
        Args:
            callback: Function called with (consent_id: str, tool: str, message: str, elapsed_seconds: float)
        
        Returns:
            Self for method chaining
        """
        self._on_consent_pending = callback
        return self
    
    def on_final(self, callback: FinalCallback) -> Self:
        """
        Register callback for final complete response with tool call details.
        
        Args:
            callback: Function called with (text: str, tool_calls: List[Dict])
                - text: The full response text
                - tool_calls: List of tool calls made during the task, each containing:
                    - name: Tool name
                    - input: Tool input parameters
                    - output: Tool output/result
                    - status: "success", "failure", "error", or "denied"
                    - start_time: ISO timestamp when tool started
                    - end_time: ISO timestamp when tool completed
        
        Returns:
            Self for method chaining
        """
        self._on_final = callback
        return self
    
    def on_error(self, callback: ErrorCallback) -> Self:
        """
        Register callback for errors.
        
        Args:
            callback: Function called with (message: str)
        
        Returns:
            Self for method chaining
        """
        self._on_error = callback
        return self
    
    def on_error_details(self, callback: EnhancedErrorCallback) -> Self:
        """
        Register callback for errors with full error details.
        
        This is an enhanced version of on_error that receives structured error
        information including error codes and additional details.
        
        Args:
            callback: Function called with MCPError object containing:
                - message: Human-readable error message
                - code: Error code for categorization (e.g., "MCP_CONNECTION_FAILED")
                - details: Additional error context
        
        Returns:
            Self for method chaining
        """
        self._on_error_details = callback
        return self
    
    def on_status(self, callback: StatusCallback) -> Self:
        """
        Register callback for status updates.
        
        Args:
            callback: Function called with (message: str)
        
        Returns:
            Self for method chaining
        """
        self._on_status = callback
        return self
    
    def on_disconnected(self, callback: DisconnectedCallback) -> Self:
        """
        Register callback for disconnection events.
        
        Args:
            callback: Function called with (reason: Optional[str])
        
        Returns:
            Self for method chaining
        """
        self._on_disconnected = callback
        return self
    
    # =========================================================================
    # Connection Methods
    # =========================================================================
    
    async def connect(
        self,
        timezone: Optional[str] = None,
    ) -> None:
        """
        Connect to the MCP chat service.
        
        All required parameters (project_token, deployment_name) are configured
        during client initialization.
        
        Args:
            timezone: Optional client timezone (e.g., "Europe/Berlin")
        """
        await self._ws_client.connect(
            url=self._mcp_client_url,
            deployment_name=self._deployment_name,
            project_token=self._project_token,
            auto_reconnect=self._auto_reconnect,
            max_reconnect_attempts=self._max_reconnect_attempts,
            reconnect_delay_ms=self._reconnect_delay_ms,
            timezone=timezone,
            system_message=self._system_message,
            language=self._language,
            security_params=self._security_params,
            message_history=self._message_history,
            cache_history=self._cache_history,
        )
    
    async def disconnect(self) -> None:
        """Disconnect from the service."""
        await self._ws_client.disconnect()
        self.session_id = None
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._ws_client.is_connected_status()
    
    # =========================================================================
    # Configuration Methods
    # =========================================================================
    
    def set_system_message(self, message: str) -> "MCPChatClient":
        """
        Set the system message/prompt for the LLM.
        
        Args:
            message: System message text
        
        Returns:
            Self for method chaining
        """
        self._system_message = message
        return self
    
    def set_language(self, language: str) -> "MCPChatClient":
        """
        Set the language for the assistant.
        
        Args:
            language: Language identifier (e.g., "English", "German", "French")
        
        Returns:
            Self for method chaining
        """
        self._language = language
        return self
    
    # =========================================================================
    # Message Methods
    # =========================================================================
    
    async def send_message(
        self,
        text: str,
        message_history: Optional[List[HistoryMessage]] = None,
    ) -> None:
        """
        Send a chat message.
        
        Args:
            text: Message text
            message_history: Optional message history override for this message only.
                If provided, it overrides any configured history for the current request.
        """
        await self._ws_client.send_message(text, message_history=message_history)
    
    async def stop(self) -> None:
        """Stop the current agent run."""
        await self._ws_client.send_stop()
    
    async def respond_consent(
        self,
        consent_id: str,
        allow: bool,
        allow_all: bool = False,
    ) -> None:
        """
        Respond to a tool consent request.
        
        Args:
            consent_id: The consent request ID from the callback
            allow: Whether to allow this tool execution
            allow_all: If True, auto-allow all future tool calls
        """
        await self._ws_client.send_tool_consent(consent_id, allow, allow_all)
    
    async def set_consent_all(self, enabled: bool = True) -> None:
        """
        Enable/disable auto-consent for all tools.
        
        Args:
            enabled: If True, all tool calls will be auto-approved
        """
        await self._ws_client.send_consent_set(allow_all=enabled)
    
    async def allow_tool(self, tool_name: str) -> None:
        """
        Auto-allow a specific tool.
        
        Args:
            tool_name: Name of the tool to auto-allow
        """
        await self._ws_client.send_consent_set(tool_name=tool_name)
    
    # =========================================================================
    # Event Handling
    # =========================================================================
    
    def _handle_event(self, event: ServerEvent) -> None:
        """Handle incoming server events and dispatch to callbacks."""
        try:
            event_type = event.type
            
            if event_type == "status":
                # Check for initialized status with session_id
                if event.message == "initialized" and event.session_id:
                    self.session_id = event.session_id
                    if self._on_connected:
                        self._on_connected(self.session_id)
                elif self._on_status:
                    self._on_status(event.message or event.status or "")
            
            elif event_type == "token":
                if self._on_token:
                    self._on_token(event.token or event.text or "")
            
            elif event_type == "tool_start":
                if self._on_tool_start:
                    self._on_tool_start(
                        event.name or event.tool_name or "",
                        event.input or event.tool_args or {},
                    )
            
            elif event_type == "tool_end_success":
                if self._on_tool_end:
                    output = event.output or event.tool_output or {}
                    output_str = output if isinstance(output, str) else str(output)
                    self._on_tool_end(
                        event.name or event.tool_name or "",
                        output_str,
                        True,
                        None,
                    )
            
            elif event_type == "tool_end_failure":
                if self._on_tool_end:
                    output = event.output or event.tool_output or {}
                    output_str = output if isinstance(output, str) else str(output)
                    self._on_tool_end(
                        event.name or event.tool_name or "",
                        output_str,
                        False,
                        event.message or event.error,
                    )
            
            elif event_type == "tool_denied":
                if self._on_tool_end:
                    self._on_tool_end(
                        event.name or event.tool_name or "",
                        "",
                        False,
                        event.reason or "User denied tool execution",
                    )
            
            elif event_type == "tool_error":
                if self._on_tool_end:
                    self._on_tool_end(
                        event.name or event.tool_name or "",
                        "",
                        False,
                        event.error or "Tool execution error",
                    )
            
            elif event_type == "tool_consent_request":
                if self._on_tool_consent_request:
                    self._on_tool_consent_request(
                        event.consent_id or "",
                        event.tool or event.name or "",
                        event.arguments or event.tool_args or {},
                        event.description,
                    )
            
            elif event_type == "consent_timeout":
                if self._on_consent_timeout:
                    self._on_consent_timeout(event.consent_id or "")
            
            elif event_type == "consent_pending":
                tool_name = event.tool or ""
                message = event.message or f"Consent pending for tool '{tool_name}'"
                elapsed = event.elapsed_seconds or 0.0
                if self._on_consent_pending:
                    self._on_consent_pending(
                        event.consent_id or "",
                        tool_name,
                        message,
                        elapsed,
                    )
                else:
                    # Log warning to stderr if no callback registered
                    import sys
                    print(
                        f"[MCPChatClient] WARNING: {message}\n"
                        f"Tip: Register on_tool_consent_request() callback and call respond_consent() to allow/deny tool execution.",
                        file=sys.stderr,
                    )
            
            elif event_type == "final":
                if self._on_final:
                    self._on_final(
                        event.text or "",
                        event.tool_calls or [],
                    )
            
            elif event_type == "error":
                error_message = event.error or event.message or "Unknown error"
                # Call simple callback for backward compatibility
                if self._on_error:
                    self._on_error(error_message)
                # Call enhanced callback with full error details
                if self._on_error_details:
                    self._on_error_details(MCPError(
                        message=error_message,
                        code=event.code,
                        details=event.details,
                    ))
            
            elif event_type in ("closing", "connection_closed"):
                if self._on_disconnected:
                    self._on_disconnected(event.reason)
        
        except Exception as e:
            error_message = f"Event handling error: {e}"
            logger.error(f"Error handling event {event.type}: {e}")
            if self._on_error:
                self._on_error(error_message)
            if self._on_error_details:
                self._on_error_details(MCPError(
                    message=error_message,
                    code="INTERNAL_ERROR",
                ))


__all__ = [
    "MCPChatClient",
    "MCPError",
    "ConnectedCallback",
    "TokenCallback",
    "ToolStartCallback",
    "ToolEndCallback",
    "ToolConsentCallback",
    "ConsentTimeoutCallback",
    "ConsentPendingCallback",
    "FinalCallback",
    "ErrorCallback",
    "EnhancedErrorCallback",
    "StatusCallback",
    "DisconnectedCallback",
]
