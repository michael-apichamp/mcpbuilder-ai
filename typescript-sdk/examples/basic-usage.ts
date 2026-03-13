/**
 * Basic usage example for the MCPBuilder TypeScript SDK.
 *
 * This example demonstrates a simple chat interaction with:
 * - Client initialization
 * - Callback registration
 * - Sending a message
 *
 * Usage:
 *   1. Set environment variables:
 *      export MCP_CLIENT_URL=wss://mcp-client.example.com
 *      export PROJECT_TOKEN=your-project-token
 *      export DEPLOYMENT_NAME=your-deployment
 *
 *   2. Run: npx ts-node examples/basic-usage.ts
 */

import { MCPChatClient } from '../src/index.js';

async function main(): Promise<void> {
  // Create client - pass all configuration at initialization
  const client = new MCPChatClient({
    projectToken: process.env.PROJECT_TOKEN!,
    deploymentName: process.env.DEPLOYMENT_NAME!,
    // mcpClientUrl only needed for on-premise deployments
    // mcpClientUrl: 'wss://on-premise.example.com',
    // cacheHistory: false (default) - client manages history locally
    // Set to true to have server maintain conversation history
  });

  // Register callbacks to handle events
  client
    .onConnected((sessionId) => console.log(`✅ Connected (session: ${sessionId})`))
    .onToken((text) => process.stdout.write(text))
    .onFinal((text, toolCalls) => console.log('\n\n✓ Done'))
    .onError((msg) => console.error(`\n❌ Error: ${msg}`))
    .onDisconnected((reason) => console.log(`\n🔌 Disconnected: ${reason}`));

  console.log('🔗 Connecting to MCP service...');

  try {
    // Connect - all configuration already set
    await client.connect({ timezone: 'Europe/Berlin' });

    // Send a message
    await client.sendMessage('Hello! What can you help me with?');

    // Wait for response (in real app, use proper event handling)
    await new Promise((resolve) => setTimeout(resolve, 30000));

    // Disconnect when done
    await client.disconnect();
  } catch (err) {
    console.error('Failed to connect:', err);
    process.exit(1);
  }
}

main().catch(console.error);
