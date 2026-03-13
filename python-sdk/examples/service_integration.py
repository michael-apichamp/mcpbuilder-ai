#!/usr/bin/env python
"""
Example: Using MCPBuilder SDK in a service/programmatic context.

This example demonstrates how to use the SDK programmatically in a service,
showing different patterns for handling events and responses.

Usage:
    1. Update DEPLOYMENT_NAME and MCP_CLIENT_URL at the top of this file
    2. Run: poetry run python examples/service_integration.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# ============================================================================
# EXAMPLE CONFIGURATION
# Update these values for your environment
# ============================================================================

DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME", "")      # Your deployment name
PROJECT_TOKEN = os.getenv("PROJECT_TOKEN", "")          # Your project token
MCP_CLIENT_URL = os.getenv("MCP_CLIENT_URL", "")        # MCP client service URL

# ============================================================================

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcpbuilder import MCPChatClient

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def example_simple_chat():
    """Example 1: Simple chat with callback handlers."""
    print("=" * 60)
    print("Example 1: Simple Chat with Callbacks")
    print("=" * 60)
    
    # Create client - all configuration passed at initialization
    # cache_history defaults to False - client manages history locally
    client = MCPChatClient(
        project_token=PROJECT_TOKEN,
        deployment_name=DEPLOYMENT_NAME,
        mcp_client_url=MCP_CLIENT_URL,
    )
    
    # Collect tokens for final response
    tokens = []
    response_done = asyncio.Event()
    
    # Register callbacks
    client \
        .on_connected(lambda sid: print(f"✅ Connected (session: {sid})")) \
        .on_token(lambda t: tokens.append(t)) \
        .on_final(lambda text, tool_calls: response_done.set()) \
        .on_error(lambda msg: print(f"❌ Error: {msg}"))
    
    try:
        print(f"Connecting to {MCP_CLIENT_URL}...")
        await client.connect()
        
        # Send message
        question = "What is 2 + 2?"
        print(f"\nSending: '{question}'")
        
        tokens.clear()
        response_done.clear()
        
        await client.send_message(question)
        
        # Wait for response
        await asyncio.wait_for(response_done.wait(), timeout=30.0)
        
        # Collect response
        response = "".join(tokens)
        print(f"\nResponse: {response}\n")
        
    except asyncio.TimeoutError:
        print("⏱️  Timeout waiting for response\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
    finally:
        await client.disconnect()


async def example_with_tool_handling():
    """Example 2: Chat with tool execution handling."""
    print("=" * 60)
    print("Example 2: Chat with Tool Handling")
    print("=" * 60)
    
    # Create client with explicit configuration
    client = MCPChatClient(
        project_token=PROJECT_TOKEN,
        deployment_name=DEPLOYMENT_NAME,
        mcp_client_url=MCP_CLIENT_URL,
    )
    
    # Track state
    tokens = []
    tools_called = []
    response_done = asyncio.Event()
    
    def on_tool_start(name: str, input_params: dict):
        print(f"  🔧 Tool starting: {name}")
        tools_called.append({"name": name, "input": input_params, "status": "started"})
    
    def on_tool_end(name: str, output: str, success: bool, error: str | None):
        status = "success" if success else f"failed: {error}"
        print(f"  {'✓' if success else '✗'} Tool {name}: {status}")
        for t in reversed(tools_called):
            if t["name"] == name and t["status"] == "started":
                t["status"] = "success" if success else "failed"
                t["output"] = output
                t["error"] = error
                break
    
    def on_consent(consent_id: str, tool: str, args: dict, desc: str | None):
        print(f"  🔐 Auto-approving tool: {tool}")
        asyncio.create_task(client.respond_consent(consent_id, allow=True))
    
    # Register callbacks
    client \
        .on_connected(lambda sid: print(f"✅ Connected (session: {sid})")) \
        .on_token(lambda t: tokens.append(t)) \
        .on_tool_start(on_tool_start) \
        .on_tool_end(on_tool_end) \
        .on_tool_consent_request(on_consent) \
        .on_final(lambda text, tool_calls: response_done.set()) \
        .on_error(lambda msg: print(f"❌ Error: {msg}"))
    
    try:
        print(f"Connecting to {MCP_CLIENT_URL}...")
        await client.connect()
        
        # Enable auto-consent for all tools
        await client.set_consent_all(enabled=True)
        print("✓ Auto-consent enabled for all tools\n")
        
        question = "What time is it right now?"
        print(f"Sending: '{question}'")
        print("Tool activity:")
        
        tokens.clear()
        response_done.clear()
        
        await client.send_message(question)
        
        await asyncio.wait_for(response_done.wait(), timeout=60.0)
        
        response = "".join(tokens)
        print(f"\nResponse: {response}")
        print(f"\nTools called: {len(tools_called)}")
        for t in tools_called:
            print(f"  - {t['name']}: {t['status']}")
        print()
        
    except asyncio.TimeoutError:
        print("⏱️  Timeout waiting for response\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
    finally:
        await client.disconnect()


async def example_error_handling():
    """Example 3: Error handling patterns."""
    print("=" * 60)
    print("Example 3: Error Handling")
    print("=" * 60)
    
    # Test with invalid URL - SDK configured directly, no .env loading
    client = MCPChatClient(
        project_token="test-token",
        deployment_name="test-deployment",
        mcp_client_url="ws://invalid-host:9999",  # Invalid host for testing
        auto_reconnect=False,
        max_reconnect_attempts=1,
    )
    
    client.on_error(lambda msg: print(f"  Error callback: {msg}"))
    
    try:
        print("Attempting connection to invalid URL (ws://invalid-host:9999)...")
        await asyncio.wait_for(
            client.connect(),
            timeout=5.0
        )
        print("✓ Connected (unexpected)")
    except asyncio.TimeoutError:
        print("⏱️  Connection timeout (expected)\n")
    except Exception as e:
        print(f"❌ Connection failed (expected): {type(e).__name__}\n")
    finally:
        await client.disconnect()


async def example_message_history():
    """Example 4: Using message_history for conversation continuity across sessions."""
    print("=" * 60)
    print("Example 4: Message History for Conversation Continuity")
    print("=" * 60)
    
    # Each connection gets a new server-generated session ID.
    # To carry context across sessions, capture the conversation and pass it
    # as message_history on the next send_message() call.
    
    from mcpbuilder import HistoryMessage
    
    response_done = asyncio.Event()
    tokens = []
    
    # --- First session: ask a question ---
    client1 = MCPChatClient(
        project_token=PROJECT_TOKEN,
        deployment_name=DEPLOYMENT_NAME,
        mcp_client_url=MCP_CLIENT_URL,
    )
    client1 \
        .on_connected(lambda sid: print(f"✅ Session 1: {sid}")) \
        .on_token(lambda t: tokens.append(t)) \
        .on_final(lambda text, tool_calls: response_done.set()) \
        .on_error(lambda msg: print(f"❌ Error: {msg}"))
    
    try:
        print(f"First connection to {MCP_CLIENT_URL}...")
        await client1.connect()
        
        question = "Remember the number 42"
        print(f"Sending: '{question}'")
        tokens.clear()
        response_done.clear()
        
        await client1.send_message(question)
        await asyncio.wait_for(response_done.wait(), timeout=30.0)
        
        first_response = "".join(tokens)
        print(f"Response: {first_response[:100]}...\n")
        
        await client1.disconnect()
        print("Disconnected from first session\n")
        
        # --- Second session: provide previous conversation as history ---
        # Build history from the first exchange
        history = [
            HistoryMessage(role="user", content=question),
            HistoryMessage(role="assistant", content=first_response),
        ]
        
        client2 = MCPChatClient(
            project_token=PROJECT_TOKEN,
            deployment_name=DEPLOYMENT_NAME,
            mcp_client_url=MCP_CLIENT_URL,
        )
        client2 \
            .on_connected(lambda sid: print(f"✅ Session 2: {sid}")) \
            .on_token(lambda t: tokens.append(t)) \
            .on_final(lambda text, tool_calls: response_done.set()) \
            .on_error(lambda msg: print(f"❌ Error: {msg}"))
        
        print("Second connection (new session, passing history)...")
        await client2.connect()
        
        follow_up = "What number did I ask you to remember?"
        print(f"Sending: '{follow_up}' (with history from session 1)")
        tokens.clear()
        response_done.clear()
        
        # Pass the previous conversation as message_history override
        await client2.send_message(follow_up, message_history=history)
        await asyncio.wait_for(response_done.wait(), timeout=30.0)
        
        print(f"Response: {''.join(tokens)}\n")
        
        await client2.disconnect()
        
    except asyncio.TimeoutError:
        print("⏱️  Timeout\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")


async def main():
    """Run examples."""
    print("\n" + "=" * 60)
    print("MCPBuilder Python SDK - Service Integration Examples")
    print("=" * 60 + "\n")
    
    print(f"Configuration:")
    print(f"  DEPLOYMENT_NAME: {DEPLOYMENT_NAME}")
    print(f"  MCP_CLIENT_URL: {MCP_CLIENT_URL}\n")
    
    # Run examples - uncomment the ones you want to run
    
    # await example_simple_chat()
    # await example_with_tool_handling()
    await example_error_handling()
    # await example_message_history()
    
    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
