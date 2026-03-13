#!/usr/bin/env python3
"""Example: Simple chat using MCPChatClient with callback-based events.

This example shows how to use the high-level MCPChatClient with the
callback registration pattern.

Usage:
    1. Update DEPLOYMENT_NAME and MCP_CLIENT_URL at the top of this file
    2. Run: poetry run python examples/callback_chat.py
"""

import asyncio
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
TIMEZONE = os.getenv("TIMEZONE", "Europe/Berlin")       # Client timezone

# ============================================================================

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcpbuilder import MCPChatClient


async def main():
    """Run a simple chat session with callbacks."""
    
    # Create client - all configuration is passed at initialization
    client = MCPChatClient(
        project_token=PROJECT_TOKEN,
        deployment_name=DEPLOYMENT_NAME,
        mcp_client_url=MCP_CLIENT_URL,
        auto_reconnect=True,
        max_reconnect_attempts=5,
        # cache_history: Server-side history caching (default: False)
        # - False: Client manages history locally (recommended for most cases)
        # - True: Server maintains conversation history across reconnections
    )
    
    # Track state
    response_complete = asyncio.Event()
    
    # Register callbacks using fluent API
    client \
        .on_connected(lambda sid: print(f"✓ Connected (session: {sid})")) \
        .on_token(lambda text: print(text, end="", flush=True)) \
        .on_tool_start(lambda name, input: print(f"\n🔧 Tool: {name}")) \
        .on_tool_end(lambda name, output, success, error: print(
            f"\n{'✓' if success else '✗'} Tool {name} {'succeeded' if success else f'failed: {error}'}"
        )) \
        .on_tool_consent_request(lambda cid, tool, args, desc: handle_consent(client, cid, tool, args)) \
        .on_final(lambda text, tool_calls: response_complete.set()) \
        .on_error(lambda msg: print(f"\n❌ Error: {msg}")) \
        .on_disconnected(lambda reason: print(f"\n🔌 Disconnected: {reason}"))
    
    print(f"Connecting to {MCP_CLIENT_URL} with deployment '{DEPLOYMENT_NAME}'...")
    
    try:
        # Connect - all configuration is set during initialization
        await client.connect(timezone=TIMEZONE)
        
        # Interactive chat loop
        print("\nType your message (or 'quit' to exit, 'stop' to cancel):\n")
        
        while True:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("You: ")
                )
                
                if user_input.lower() == "quit":
                    break
                
                if user_input.lower() == "stop":
                    await client.stop()
                    print("Stopped current run")
                    continue
                
                if not user_input.strip():
                    continue
                
                # Reset completion event
                response_complete.clear()
                
                # Send message
                print("\nAssistant: ", end="", flush=True)
                await client.send_message(user_input)
                
                # Wait for response to complete (with timeout)
                try:
                    await asyncio.wait_for(response_complete.wait(), timeout=120.0)
                except asyncio.TimeoutError:
                    print("\n⏰ Response timeout")
                
                print()  # Newline after response
                
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n\nInterrupted by user")
                break
    
    finally:
        await client.disconnect()
        print("Goodbye!")


def handle_consent(client: MCPChatClient, consent_id: str, tool: str, args: dict):
    """Handle tool consent requests - auto-approve for this example."""
    print(f"\n🔐 Consent requested for {tool}")
    print(f"   Args: {args}")
    print("   Auto-approving...")
    
    # In a real app, you might prompt the user or check a whitelist
    asyncio.create_task(client.respond_consent(consent_id, allow=True))


if __name__ == "__main__":
    asyncio.run(main())
