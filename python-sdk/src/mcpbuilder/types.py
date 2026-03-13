"""Type definitions for the MCPBuilder SDK."""

from typing import Any, Literal, Optional, List
from dataclasses import dataclass, field


# =============================================================================
# Message History Types
# =============================================================================

MessageRole = Literal["user", "assistant"]


@dataclass
class HistoryMessage:
    """A message in the conversation history.
    
    Used to provide initial context when connecting.
    """
    
    role: MessageRole
    content: str
    
    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return {"role": self.role, "content": self.content}


# =============================================================================
# Server Event Types
# =============================================================================

ServerEventType = Literal[
    "status",
    "tools",
    "token",
    "tool_start",
    "tool_end_success",
    "tool_end_failure",
    "tool_denied",
    "tool_error",
    "final",
    "error",
    "connection_closed",
    "closing",
    "tool_reason",
    "credit_limit",
    "tool_consent_request",
    "consent_timeout",
    "consent_pending",
]


@dataclass
class ServerEvent:
    """Server-sent event from MCP chat service."""
    
    type: ServerEventType
    text: Optional[str] = None
    token: Optional[str] = None
    name: Optional[str] = None
    input: Optional[dict[str, Any]] = None
    output: Optional[dict[str, Any]] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None
    tool_output: Optional[dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None
    code: Optional[str] = None  # Error code for categorization (e.g., "MCP_CONNECTION_FAILED")
    details: Optional[dict[str, Any]] = None  # Additional error details
    status: Optional[str] = None
    session_id: Optional[str] = None
    tools: Optional[list[dict[str, Any]]] = None
    items: Optional[list[dict[str, Any]]] = None
    reason: Optional[str] = None
    consent_id: Optional[str] = None
    tool: Optional[str] = None
    arguments: Optional[dict[str, Any]] = None
    description: Optional[str] = None
    statuscode: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None  # List of tool calls made during task
    elapsed_seconds: Optional[float] = None  # Elapsed seconds for consent_pending
    timeout_seconds: Optional[float] = None  # Timeout seconds for consent_pending

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerEvent":
        """Create ServerEvent from dictionary."""
        # Map text field to token for token events
        if data.get("type") == "token" and "text" in data:
            data["token"] = data.get("text")
        
        # Map items to tools
        if "items" in data:
            data["tools"] = data.get("items")
        
        # Filter out unknown fields
        valid_fields = {f.name for f in ServerEvent.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)


@dataclass
class ClientMessage:
    """Client message to send to MCP chat service."""
    
    type: Literal["message", "stop", "tool_consent_response"]
    text: Optional[str] = None
    message_history: Optional[list[dict[str, str]]] = None
    consent_id: Optional[str] = None
    allow: Optional[bool] = None
    allow_all: Optional[bool] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {"type": self.type}
        
        if self.type == "message" and self.text is not None:
            data["text"] = self.text
            if self.message_history is not None:
                data["message_history"] = self.message_history
        elif self.type == "tool_consent_response":
            data["consent_id"] = self.consent_id
            data["allow"] = self.allow
            if self.allow_all is not None:
                data["allow_all"] = self.allow_all
        
        return data


@dataclass
class MCPError:
    """Structured error information from the server.
    
    Attributes:
        message: Human-readable error message
        code: Error code for categorization (e.g., "MCP_CONNECTION_FAILED")
        details: Additional error context
    """
    
    message: str
    code: Optional[str] = None
    details: Optional[dict[str, Any]] = None
