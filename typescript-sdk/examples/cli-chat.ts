/**
 * Interactive CLI chat client using the MCPBuilder TypeScript SDK.
 *
 * This example demonstrates a full-featured CLI chat with:
 * - Streaming responses
 * - Tool execution with consent handling
 * - Stop command support
 * - Error handling
 *
 * Usage:
 *   1. Set environment variables:
 *      export MCP_CLIENT_URL=wss://mcp-client.example.com
 *      export PROJECT_TOKEN=your-project-token
 *      export DEPLOYMENT_NAME=your-deployment
 *
 *   2. Run: npx ts-node examples/cli-chat.ts
 */

import * as readline from 'readline';
import { MCPChatClient } from '../src/index.js';

// Configuration from environment
const DEPLOYMENT_NAME = process.env.DEPLOYMENT_NAME || '';
const PROJECT_TOKEN = process.env.PROJECT_TOKEN || '';
const MCP_SERVICE_URL = process.env.MCP_CLIENT_URL || '';
const TIMEZONE = process.env.TIMEZONE || 'Europe/Berlin';

async function main(): Promise<void> {
  if (!DEPLOYMENT_NAME || !PROJECT_TOKEN || !MCP_SERVICE_URL) {
    console.error('❌ Missing required environment variables:');
    console.error('   - DEPLOYMENT_NAME');
    console.error('   - PROJECT_TOKEN');
    console.error('   - MCP_CLIENT_URL');
    process.exit(1);
  }

  // Create client
  const client = new MCPChatClient({
    projectToken: PROJECT_TOKEN,
    deploymentName: DEPLOYMENT_NAME,
    mcpClientUrl: MCP_SERVICE_URL,
    autoReconnect: true,
    maxReconnectAttempts: 5,
  });

  // Track when response is complete
  let responseResolve: (() => void) | null = null;

  // Helper to handle tool consent
  const handleConsent = async (
    consentId: string,
    tool: string,
    args: Record<string, unknown>,
    description?: string
  ): Promise<void> => {
    console.log(`\n⚠️  Tool consent requested: ${tool}`);
    if (description) {
      console.log(`   Description: ${description}`);
    }
    console.log(`   Arguments: ${JSON.stringify(args, null, 2)}`);

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    const answer = await new Promise<string>((resolve) => {
      rl.question('   Allow? (y/n/a=allow all): ', resolve);
    });
    rl.close();

    const normalizedAnswer = answer.toLowerCase().trim();
    const allow = normalizedAnswer === 'y' || normalizedAnswer === 'a';
    const allowAll = normalizedAnswer === 'a';

    await client.respondConsent(consentId, allow, allowAll);
  };

  // Register callbacks
  client
    .onConnected((sessionId) => console.log(`✅ Connected (session: ${sessionId})`))
    .onToken((text) => process.stdout.write(text))
    .onToolStart((name, input) => {
      console.log(`\n🔧 Calling: ${name}`);
      console.log(`   Input: ${JSON.stringify(input)}`);
    })
    .onToolEnd((name, _output, success, error) => {
      if (success) {
        console.log(`\n✓ ${name} completed`);
      } else {
        console.log(`\n✗ ${name} failed: ${error}`);
      }
    })
    .onToolConsentRequest(handleConsent)
    .onFinal((text, toolCalls) => {
      console.log('\n');
      responseResolve?.();
    })
    .onError((msg) => {
      console.error(`\n❌ Error: ${msg}`);
      responseResolve?.();
    })
    .onDisconnected((reason) => console.log(`\n🔌 Disconnected: ${reason}`));

  console.log(`🔗 Connecting to ${MCP_SERVICE_URL} with deployment '${DEPLOYMENT_NAME}'...`);

  try {
    await client.connect({ timezone: TIMEZONE });
  } catch (err) {
    console.error(`❌ Failed to connect: ${err}`);
    process.exit(1);
  }

  console.log("💬 Type your messages (type 'quit' to exit, 'stop' to cancel):\n");

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const prompt = (): void => {
    rl.question('You: ', async (input) => {
      const trimmedInput = input.trim();

      if (!trimmedInput) {
        prompt();
        return;
      }

      if (trimmedInput.toLowerCase() === 'quit') {
        console.log('👋 Goodbye!');
        await client.disconnect();
        rl.close();
        process.exit(0);
      }

      if (trimmedInput.toLowerCase() === 'stop') {
        console.log('⏹️  Stopping...');
        await client.stop();
        prompt();
        return;
      }

      process.stdout.write('\nAssistant: ');

      // Create promise to wait for response
      const responseComplete = new Promise<void>((resolve) => {
        responseResolve = resolve;
      });

      // Send message
      await client.sendMessage(trimmedInput);

      // Wait for response with timeout
      const timeout = new Promise<void>((resolve) => setTimeout(resolve, 120000));
      await Promise.race([responseComplete, timeout]);

      prompt();
    });
  };

  prompt();
}

main().catch(console.error);
