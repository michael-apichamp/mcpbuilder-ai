"""High-level chat client for agent interaction."""

import asyncio
import logging
from typing import AsyncIterator, Callable, Optional
from uuid import uuid4

from .config import SDKConfig
from .types import ServerEvent
from .websocket_client import WebSocketClient

logger = logging.getLogger(__name__)


class ChatClient:
    """High-level chat client for interacting with MCP agents."""
    
    def __init__(self, config: SDKConfig):
        """
        Initialize the chat client.
        
        Args:
            config: SDK configuration
        """
        self.config = config
        self.ws_client = WebSocketClient()
        self.session_id = config.session_id or str(uuid4())
        self._message_queue: asyncio.Queue[ServerEvent] = asyncio.Queue()
        self._current_message_task: Optional[asyncio.Task] = None
        self._is_streaming = False

    async def connect(self) -> None:
        """
        Connect to the MCP chat service.
        
        Raises:
            ValueError: If required configuration is missing
        """
        self.config.validate_required()
        
        # Register callback to queue messages
        self.ws_client.on_message(self._on_server_event)
        
        # Build full WebSocket URL
        scheme = "wss" if self.config.mcp_client_url.startswith("https") else "ws"
        if self.config.mcp_client_url.startswith("http"):
            base_url = self.config.mcp_client_url.replace("http", scheme)
        else:
            base_url = self.config.mcp_client_url
        
        await self.ws_client.connect(
            url=base_url,
            project_id=self.config.project_id,
            access_token=self.config.access_token,
            session_id=self.session_id,
            auto_reconnect=self.config.auto_reconnect,
            max_reconnect_attempts=self.config.max_reconnect_attempts,
            reconnect_delay_ms=self.config.reconnect_delay_ms,
        )

    async def disconnect(self) -> None:
        """Disconnect from the service."""
        await self.ws_client.disconnect()
        
        # Clear queue
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def send_message(
        self,
        text: str,
        on_event: Optional[Callable[[ServerEvent], None]] = None,
    ) -> AsyncIterator[ServerEvent]:
        """
        Send a message and stream responses.
        
        Args:
            text: Message to send
            on_event: Optional callback for each event (called synchronously)
        
        Yields:
            ServerEvent objects as they arrive from the service
        """
        if not self.ws_client.is_connected_status():
            raise RuntimeError("Not connected to chat service")
        
        # Send the message
        await self.ws_client.send_message(text)
        self._is_streaming = True
        
        try:
            while self._is_streaming:
                try:
                    # Wait for message with timeout
                    event = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=self.config.message_timeout
                    )
                    
                    # Call optional callback
                    if on_event:
                        try:
                            on_event(event)
                        except Exception as e:
                            logger.error(f"Error in event callback: {e}")
                    
                    yield event
                    
                    # Stop streaming on final event
                    if event.type == "final":
                        self._is_streaming = False
                    
                except asyncio.TimeoutError:
                    logger.warning("Message timeout")
                    self._is_streaming = False
                    raise TimeoutError("Response timeout - no message received")
        
        except asyncio.CancelledError:
            logger.info("Message streaming cancelled")
            # Send stop to server
            try:
                await self.ws_client.send_stop()
            except Exception as e:
                logger.error(f"Error sending stop: {e}")
            raise

    async def send_message_buffered(self, text: str) -> list[ServerEvent]:
        """
        Send a message and collect all responses.
        
        Args:
            text: Message to send
        
        Returns:
            List of all ServerEvent responses
        """
        events = []
        async for event in self.send_message(text):
            events.append(event)
        return events

    async def request_tool_consent(
        self,
        consent_id: str,
        allow: bool,
        allow_all: bool = False,
    ) -> None:
        """
        Respond to a tool consent request.
        
        Args:
            consent_id: Consent request ID
            allow: Whether to allow the tool
            allow_all: Whether to always allow this tool
        """
        await self.ws_client.send_tool_consent(
            consent_id=consent_id,
            allow=allow,
            allow_all=allow_all,
        )

    async def stop(self) -> None:
        """Stop the current operation."""
        self._is_streaming = False
        await self.ws_client.send_stop()

    def _on_server_event(self, event: ServerEvent) -> None:
        """Handle incoming server events."""
        # Put non-blocking, drop if queue is full
        try:
            self._message_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Message queue full, dropping event")

    def is_connected(self) -> bool:
        """Check if connected to the service."""
        return self.ws_client.is_connected_status()

    @property
    def session(self) -> str:
        """Get the current session ID."""
        return self.session_id
