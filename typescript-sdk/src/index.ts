/**
 * MCPBuilder TypeScript SDK for agent integration with MCP services.
 *
 * The SDK loads the MCP Client URL from MCP_CLIENT_URL environment variable,
 * or accepts an explicit mcpClientUrl parameter for on-premise deployments.
 *
 * @example
 * ```typescript
 * import { MCPChatClient } from 'mcpbuilder-ai';
 *
 * const client = new MCPChatClient({
 *   projectToken: process.env.PROJECT_TOKEN!,
 *   deploymentName: 'my-deployment',
 * });
 *
 * client.onToken((t) => process.stdout.write(t));
 *
 * await client.connect();
 * await client.sendMessage('Hello!');
 * ```
 *
 * @packageDocumentation
 */

export const VERSION = '0.1.0';

// Primary API
export { MCPChatClient } from './client.js';

// Types
export type {
  // Message history types
  MessageRole,
  HistoryMessage,
  // Server event types
  ServerEvent,
  ServerEventType,
  // Tool call tracking
  ToolCallEntry,
  // Client message types
  ClientMessage,
  ClientMessageType,
  // Configuration types
  MCPChatClientConfig,
  ConnectOptions,
  SendMessageOptions,
  // Callback types
  ConnectedCallback,
  TokenCallback,
  ToolStartCallback,
  ToolEndCallback,
  ToolConsentCallback,
  ConsentTimeoutCallback,
  ConsentPendingCallback,
  FinalCallback,
  ErrorCallback,
  StatusCallback,
  DisconnectedCallback,
} from './types.js';

// Helper functions (optional)
export {
  parseServerEvent,
  createMessage,
  createStopMessage,
  createConsentResponse,
  createConsentSet,
} from './types.js';

// WebSocket client (for advanced usage)
export { WebSocketClient } from './websocket-client.js';
