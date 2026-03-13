"""WebSocket client for connecting to MCP client service."""

import asyncio
import json
import logging
from typing import Callable, Optional, List
from urllib.parse import urlencode
import websockets
from websockets.client import WebSocketClientProtocol

from .types import ServerEvent, ClientMessage, HistoryMessage

logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client for MCP chat service communication."""
    
    def __init__(self):
        """Initialize the WebSocket client."""
        self.ws: Optional[WebSocketClientProtocol] = None
        self.is_connected = False
        self.was_ever_connected = False
        self.message_callbacks: list[Callable[[ServerEvent], None]] = []
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.auto_reconnect_enabled = False
        self.reconnect_delay_ms = 2000
        self.url = ""
        self.connection_params = {}
        self._reconnect_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._initialized_event: Optional[asyncio.Event] = None

    async def connect(
        self,
        url: str,
        deployment_name: str,
        project_token: str,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 3,
        reconnect_delay_ms: int = 2000,
        timezone: Optional[str] = None,
        system_message: Optional[str] = None,
        language: Optional[str] = None,
        security_params: Optional[dict] = None,
        message_history: Optional[List[HistoryMessage]] = None,
        cache_history: bool = False,
    ) -> None:
        """
        Connect to the MCP WebSocket service.
        
        Args:
            url: Base WebSocket URL (e.g., ws://localhost:8000)
            deployment_name: Deployment name for authentication
            project_token: Project authentication token
            auto_reconnect: Enable automatic reconnection
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_delay_ms: Base delay for reconnection
            timezone: Optional timezone for the session
            system_message: Optional system message/prompt for the LLM
            language: Optional language setting for the assistant
            security_params: Optional dict of security parameters to merge with
                loaded security headers (these take precedence)
            message_history: Optional initial message history to provide context
            cache_history: Whether to cache conversation history on the server (default: False)
        """
        if not deployment_name:
            raise ValueError("deployment_name is required")
        if not project_token:
            raise ValueError("project_token is required")
        
        self.url = url
        self.auto_reconnect_enabled = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay_ms = reconnect_delay_ms
        self.connection_params = {
            "deployment_name": deployment_name,
            "project_token": project_token,
        }

        if timezone:
            self.connection_params["timezone"] = timezone
        if system_message:
            self.connection_params["system_message"] = system_message
        if language:
            self.connection_params["language"] = language
        if security_params:
            # JSON-encode security params for URL transport
            # Filter out None and empty values to prevent server-side errors
            valid_params = {k: v for k, v in security_params.items() if v is not None and v != ""}
            if valid_params:
                self.connection_params["security_params"] = json.dumps(valid_params)
        if message_history:
            # JSON-encode message history for URL transport
            history_dicts = [msg.to_dict() for msg in message_history]
            self.connection_params["message_history"] = json.dumps(history_dicts)
        # Always include cache_history parameter
        self.connection_params["cache_history"] = str(cache_history).lower()
        
        await self._connect_internal()

    async def _connect_internal(self) -> None:
        """Internal connection logic."""
        try:
            ws_url = f"{self.url}/ws/chat?{urlencode(self.connection_params)}"
            logger.info(f"Connecting to {ws_url}")
            
            # Create an event to wait for the "initialized" status from server
            self._initialized_event = asyncio.Event()
            
            self.ws = await websockets.connect(ws_url)
            self.is_connected = True
            self.was_ever_connected = True
            self.reconnect_attempts = 0
            
            logger.info("Connected to MCP service")
            
            # Start message receiving loop as a background task (don't await it)
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Wait for the server to send "initialized" status (with timeout)
            try:
                await asyncio.wait_for(self._initialized_event.wait(), timeout=30.0)
                logger.info("Session initialized by server")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for server initialization, proceeding anyway")
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.is_connected = False
            
            if self.ws:
                await self.ws.close()
                self.ws = None
            
            # Try to reconnect
            if self.was_ever_connected and self.auto_reconnect_enabled:
                await self._handle_disconnect()
            else:
                self._broadcast_event(ServerEvent(
                    type="error",
                    error=f"Connection failed: {str(e)}"
                ))

    async def _receive_loop(self) -> None:
        """Receive messages from the server."""
        if not self.ws:
            return
        
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    
                    # Handle service-initiated closing
                    if data.get("type") == "closing":
                        logger.info(f"Service closing: {data.get('reason')}")
                        self._broadcast_event(ServerEvent(
                            type="closing",
                            reason=data.get("reason")
                        ))
                        break
                    
                    # Check for "initialized" status to signal connection is ready
                    if data.get("type") == "status" and data.get("message") == "initialized":
                        logger.info("Received initialized status from server")
                        if self._initialized_event:
                            self._initialized_event.set()
                    
                    # Convert to ServerEvent
                    event = ServerEvent.from_dict(data)
                    self._broadcast_event(event)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self.is_connected = False
            await self._handle_disconnect()

    async def _handle_disconnect(self) -> None:
        """Handle disconnection and attempt reconnection."""
        logger.info("Handling disconnect")
        self._broadcast_event(ServerEvent(
            type="status",
            status="Disconnected from chat service"
        ))
        
        if (
            self.was_ever_connected
            and self.auto_reconnect_enabled
            and self.reconnect_attempts < self.max_reconnect_attempts
        ):
            self.reconnect_attempts += 1
            delay = (self.reconnect_delay_ms * self.reconnect_attempts) / 1000.0
            logger.info(
                f"Reconnecting in {delay}s "
                f"({self.reconnect_attempts}/{self.max_reconnect_attempts})"
            )
            
            await asyncio.sleep(delay)
            await self._connect_internal()

    async def send_message(
        self,
        text: str,
        message_history: Optional[List[HistoryMessage]] = None,
    ) -> None:
        """
        Send a chat message to the service.
        
        Args:
            text: Message text to send
            message_history: Optional message history override for this message only
        """
        if not self.is_connected or not self.ws:
            logger.error("WebSocket not connected")
            self._broadcast_event(ServerEvent(
                type="error",
                error="Not connected to chat service"
            ))
            return
        
        try:
            history_dicts = None
            if message_history is not None:
                history_dicts = [msg.to_dict() for msg in message_history]

            message = ClientMessage(
                type="message",
                text=text,
                message_history=history_dicts,
            )
            await self.ws.send(json.dumps(message.to_dict()))
            logger.debug(f"Sent message: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self._broadcast_event(ServerEvent(
                type="error",
                error=f"Failed to send message: {str(e)}"
            ))

    async def send_stop(self) -> None:
        """Send a stop request to cancel the current operation."""
        if not self.is_connected or not self.ws:
            logger.error("WebSocket not connected")
            return
        
        try:
            message = ClientMessage(type="stop")
            await self.ws.send(json.dumps(message.to_dict()))
            logger.info("Sent stop request")
        except Exception as e:
            logger.error(f"Failed to send stop: {e}")

    async def send_tool_consent(
        self,
        consent_id: str,
        allow: bool,
        allow_all: bool = False,
    ) -> None:
        """
        Respond to a tool consent request.
        
        Args:
            consent_id: Consent request ID
            allow: Whether to allow the tool execution
            allow_all: Whether to always allow this tool in the future
        """
        if not self.is_connected or not self.ws:
            logger.error("WebSocket not connected")
            return
        
        try:
            message = ClientMessage(
                type="tool_consent_response",
                consent_id=consent_id,
                allow=allow,
                allow_all=allow_all if allow_all else None,
            )
            await self.ws.send(json.dumps(message.to_dict()))
            logger.info(
                f"Sent tool consent: {allow} "
                f"(allow_all={allow_all}) for {consent_id}"
            )
        except Exception as e:
            logger.error(f"Failed to send tool consent: {e}")

    async def send_consent_set(
        self,
        allow_all: bool = False,
        tool_name: Optional[str] = None,
    ) -> None:
        """
        Set consent preferences.
        
        Args:
            allow_all: If True, auto-allow all tool calls
            tool_name: If provided, auto-allow this specific tool
        """
        if not self.is_connected or not self.ws:
            logger.error("WebSocket not connected")
            return
        
        try:
            message = {"type": "tool_consent_set"}
            if allow_all:
                message["allow_all"] = True
            elif tool_name:
                message["tool_name"] = tool_name
            
            await self.ws.send(json.dumps(message))
            logger.info(f"Sent consent set: allow_all={allow_all}, tool_name={tool_name}")
        except Exception as e:
            logger.error(f"Failed to send consent set: {e}")

    def on_message(self, callback: Callable[[ServerEvent], None]) -> None:
        """
        Register a callback for server events.
        
        Args:
            callback: Function to call when events are received
        """
        self.message_callbacks.append(callback)

    def clear_callbacks(self) -> None:
        """Clear all registered callbacks."""
        self.message_callbacks.clear()

    def _broadcast_event(self, event: ServerEvent) -> None:
        """Broadcast event to all registered callbacks."""
        for callback in self.message_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in callback: {e}")

    async def disconnect(self) -> None:
        """Disconnect from the service."""
        self.is_connected = False
        self.was_ever_connected = False
        self.reconnect_attempts = 0
        self.clear_callbacks()
        
        # Cancel the receive task if running
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            finally:
                self.ws = None
        
        logger.info("WebSocket disconnected")

    def is_connected_status(self) -> bool:
        """Check if currently connected."""
        return self.is_connected and self.ws is not None
