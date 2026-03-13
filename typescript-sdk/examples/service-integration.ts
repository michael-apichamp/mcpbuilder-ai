/**
 * Service integration example for the MCPBuilder TypeScript SDK.
 *
 * This example demonstrates how to integrate the SDK into a backend service:
 * - Event-driven architecture
 * - Proper cleanup and error handling
 * - Session management
 *
 * Usage:
 *   1. Set environment variables
 *   2. Run: npx ts-node examples/service-integration.ts
 */

import { MCPChatClient, type ServerEvent } from '../src/index.js';

/**
 * Example service class that wraps MCPChatClient for use in a backend service.
 */
class ChatService {
  private client: MCPChatClient;
  private messageBuffer: string[] = [];
  private isProcessing = false;

  constructor(
    projectToken: string,
    deploymentName: string,
    mcpClientUrl: string,
    cacheHistory: boolean = false
  ) {
    this.client = new MCPChatClient({
      projectToken,
      deploymentName,
      mcpClientUrl,
      autoReconnect: true,
      maxReconnectAttempts: 10,
      reconnectDelayMs: 3000,
      // cacheHistory: Server-side history caching (default: false)
      // - false: Client manages history locally (recommended for most cases)
      // - true: Server maintains conversation history across reconnections
      cacheHistory,
    });

    this.setupCallbacks();
  }

  private setupCallbacks(): void {
    this.client
      .onConnected((sessionId) => {
        console.log(`[ChatService] Connected with session: ${sessionId}`);
      })
      .onToken((text) => {
        // Buffer tokens for later processing
        this.messageBuffer.push(text);
      })
      .onToolStart((name, input) => {
        console.log(`[ChatService] Tool started: ${name}`, input);
      })
      .onToolEnd((name, output, success, error) => {
        if (success) {
          console.log(`[ChatService] Tool completed: ${name}`);
        } else {
          console.error(`[ChatService] Tool failed: ${name}`, error);
        }
      })
      .onFinal((text, toolCalls) => {
        console.log(`[ChatService] Response complete. Full text: ${text.substring(0, 100)}...`);
        if (toolCalls.length > 0) {
          console.log(`[ChatService] Tool calls made: ${toolCalls.map(t => t.name).join(', ')}`);
        }
        this.isProcessing = false;
      })
      .onError((msg) => {
        console.error(`[ChatService] Error: ${msg}`);
        this.isProcessing = false;
      })
      .onDisconnected((reason) => {
        console.log(`[ChatService] Disconnected: ${reason}`);
      });
  }

  /**
   * Initialize the chat service.
   */
  async initialize(timezone?: string): Promise<void> {
    console.log('[ChatService] Initializing...');
    await this.client.connect({ timezone });
    console.log('[ChatService] Ready');
  }

  /**
   * Send a message and wait for the complete response.
   */
  async chat(message: string): Promise<string> {
    if (this.isProcessing) {
      throw new Error('Already processing a message');
    }

    this.isProcessing = true;
    this.messageBuffer = [];

    await this.client.sendMessage(message);

    // Wait for response with timeout
    const startTime = Date.now();
    const timeout = 60000; // 60 seconds

    while (this.isProcessing) {
      if (Date.now() - startTime > timeout) {
        throw new Error('Response timeout');
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    return this.messageBuffer.join('');
  }

  /**
   * Get the current session ID.
   */
  get sessionId(): string | undefined {
    return this.client.sessionId;
  }

  /**
   * Check if the service is connected.
   */
  get isConnected(): boolean {
    return this.client.isConnected;
  }

  /**
   * Shutdown the chat service.
   */
  async shutdown(): Promise<void> {
    console.log('[ChatService] Shutting down...');
    await this.client.disconnect();
    console.log('[ChatService] Shutdown complete');
  }
}

// Example usage
async function main(): Promise<void> {
  const projectToken = process.env.PROJECT_TOKEN!;
  const deploymentName = process.env.DEPLOYMENT_NAME!;
  const mcpClientUrl = process.env.MCP_CLIENT_URL!;

  if (!projectToken || !deploymentName || !mcpClientUrl) {
    console.error('Missing required environment variables');
    process.exit(1);
  }

  // cacheHistory: false (default) - client manages history locally
  // Set to true for server-side history caching
  const service = new ChatService(projectToken, deploymentName, mcpClientUrl);

  try {
    await service.initialize('Europe/Berlin');

    console.log(`\nSession ID: ${service.sessionId}`);
    console.log('---');

    // Send a test message
    const response = await service.chat('What is the capital of France?');
    console.log(`\nResponse: ${response}`);

    // Send another message
    const response2 = await service.chat('And what is its population?');
    console.log(`\nResponse: ${response2}`);
  } catch (err) {
    console.error('Error:', err);
  } finally {
    await service.shutdown();
  }
}

main().catch(console.error);
