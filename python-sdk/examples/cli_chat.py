#!/usr/bin/env python
"""
Interactive CLI chat client using the MCPBuilder Python SDK.

This example demonstrates a full-featured CLI chat with:
- Streaming responses
- Tool execution with consent handling
- Stop command support
- Error handling

Usage:
    1. Update DEPLOYMENT_NAME and MCP_CLIENT_URL at the top of this file
    2. Run: poetry run python examples/cli_chat.py
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
TIMEZONE = os.getenv("TIMEZONE", "Europe/Berlin")       # Client timezone

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


async def main():
    """Run interactive chat client."""
    
    # Create client - all configuration passed at initialization
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
    
    # Track when response is complete
    response_complete = asyncio.Event()
    
    # Register callbacks
    client \
        .on_connected(lambda sid: print(f"✅ Connected (session: {sid})")) \
        .on_token(lambda text: print(text, end="", flush=True)) \
        .on_tool_start(on_tool_start) \
        .on_tool_end(on_tool_end) \
        .on_tool_consent_request(lambda cid, tool, args, desc: handle_consent(client, cid, tool, args, desc)) \
        .on_final(lambda text, tool_calls: response_complete.set()) \
        .on_error(lambda msg: print(f"\n❌ Error: {msg}")) \
        .on_disconnected(lambda reason: print(f"\n🔌 Disconnected: {reason}"))
    
    print(f"🔗 Connecting to {MCP_CLIENT_URL} with deployment '{DEPLOYMENT_NAME}'...")
    
    try:
        # Connect - all configuration is set during initialization
        await client.connect(timezone=TIMEZONE)
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return
    
    print("💬 Type your messages (type 'quit' to exit, 'stop' to cancel):\n")
    
    try:
        while True:
            # Get user input
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("You: ")
                )
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Goodbye!")
                break
            
            user_input = user_input.strip()
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() in ["quit", "exit", "/quit", "/exit"]:
                print("👋 Goodbye!")
                break
            
            if user_input.lower() in ["stop", "/stop"]:
                print("⏹️  Stopping current request...")
                await client.stop()
                continue
            
            # Send message and stream response
            print("Agent: ", end="", flush=True)
            response_complete.clear()
            
            try:
                await client.send_message(user_input)
                
                # Wait for response to complete (with timeout)
                try:
                    await asyncio.wait_for(response_complete.wait(), timeout=120.0)
                except asyncio.TimeoutError:
                    print("\n⏱️  Response timeout")
                
                print()  # Newline after response
                
            except asyncio.CancelledError:
                print("\n⏹️  Cancelled")
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.exception("Chat error")
    
    finally:
        await client.disconnect()
        print("✅ Disconnected")


def on_tool_start(name: str, input_params: dict):
    """Handle tool start event."""
    print(f"\n🛠️  Using tool: {name}", flush=True)
    if input_params:
        input_str = str(input_params)
        if len(input_str) > 200:
            input_str = input_str[:200] + "..."
        print(f"   Input: {input_str}", flush=True)


def on_tool_end(name: str, output: str, success: bool, error: str | None):
    """Handle tool end event."""
    if success:
        print(f"✅ Tool {name} succeeded", flush=True)
        if output:
            output_str = str(output)
            if len(output_str) > 200:
                output_str = output_str[:200] + "..."
            print(f"   Output: {output_str}", flush=True)
    else:
        print(f"❌ Tool {name} failed", flush=True)
        if error:
            print(f"   Error: {error}", flush=True)


def handle_consent(client: MCPChatClient, consent_id: str, tool: str, args: dict, description: str | None):
    """Handle tool consent request - prompts user for approval."""
    print(f"\n\n⚠️  Tool consent request:", flush=True)
    print(f"   Tool: {tool}", flush=True)
    if description:
        print(f"   Description: {description}", flush=True)
    if args:
        args_str = str(args)
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."
        print(f"   Arguments: {args_str}", flush=True)
    
    try:
        response = input("\n   Allow this tool? (y/n/a=allow all): ").lower().strip()
        
        allow = response in ["y", "yes", "a", "always"]
        allow_all = response in ["a", "always"]
        
        asyncio.create_task(client.respond_consent(consent_id, allow, allow_all))
        
        if allow:
            print("   ✓ Approved", flush=True)
        else:
            print("   ✗ Denied", flush=True)
        
        print("Agent: ", end="", flush=True)
        
    except (EOFError, KeyboardInterrupt):
        asyncio.create_task(client.respond_consent(consent_id, False))
        print("   ✗ Cancelled", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
