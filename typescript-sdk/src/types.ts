/**
 * Type definitions for the MCPBuilder TypeScript SDK.
 */

// =============================================================================
// Message History Types
// =============================================================================

/**
 * Role for a message in the conversation history.
 */
export type MessageRole = 'user' | 'assistant';

/**
 * A message in the conversation history.
 * Used to provide initial context when connecting.
 */
export interface HistoryMessage {
  /** Role of the message sender */
  role: MessageRole;
  /** Content of the message */
  content: string;
}

// =============================================================================
// Server Event Types
// =============================================================================

/**
 * All possible server event types from the MCP chat service.
 */
export type ServerEventType =
  | 'status'
  | 'tools'
  | 'token'
  | 'tool_start'
  | 'tool_end_success'
  | 'tool_end_failure'
  | 'tool_denied'
  | 'tool_error'
  | 'final'
  | 'error'
  | 'connection_closed'
  | 'closing'
  | 'tool_reason'
  | 'credit_limit'
  | 'tool_consent_request'
  | 'consent_timeout'
  | 'consent_pending';

/**
 * Server-sent event from MCP chat service.
 */
export interface ServerEvent {
  /** Event type identifier */
  type: ServerEventType;
  /** Text content (for token/final events) */
  text?: string;
  /** Token content (alternative to text for token events) */
  token?: string;
  /** Tool name */
  name?: string;
  /** Tool input arguments */
  input?: Record<string, unknown>;
  /** Tool output */
  output?: Record<string, unknown> | string;
  /** Alternative tool name field */
  tool_name?: string;
  /** Alternative tool arguments field */
  tool_args?: Record<string, unknown>;
  /** Alternative tool output field */
  tool_output?: Record<string, unknown> | string;
  /** Status or error message */
  message?: string;
  /** Error message */
  error?: string;
  /** Error code for categorization (e.g., "MCP_CONNECTION_FAILED") */
  code?: string;
  /** Additional error details */
  details?: Record<string, unknown>;
  /** Status value */
  status?: string;
  /** Session ID (for status events) */
  session_id?: string;
  /** Available tools list */
  tools?: Array<Record<string, unknown>>;
  /** Items array (alternative to tools) */
  items?: Array<Record<string, unknown>>;
  /** Disconnect/error reason */
  reason?: string;
  /** Consent request ID */
  consent_id?: string;
  /** Tool name for consent request */
  tool?: string;
  /** Tool arguments for consent request */
  arguments?: Record<string, unknown>;
  /** Tool description for consent request */
  description?: string;
  /** Elapsed seconds (for consent_pending) */
  elapsed_seconds?: number;
  /** Timeout seconds (for consent_pending) */
  timeout_seconds?: number;
  /** Status code */
  statuscode?: string;
  /** List of tool calls made during the task */
  tool_calls?: ToolCallEntry[];
}

/**
 * Tool call entry tracking a single tool invocation.
 */
export interface ToolCallEntry {
  /** Tool name */
  name: string;
  /** Input arguments passed to the tool */
  input: Record<string, unknown>;
  /** Tool output (if completed) */
  output?: Record<string, unknown> | string;
  /** Execution status: 'success', 'failure', 'error', 'denied' */
  status: 'success' | 'failure' | 'error' | 'denied';
  /** ISO timestamp when tool started */
  start_time?: string;
  /** ISO timestamp when tool ended */
  end_time?: string;
  /** Error message if status is not 'success' */
  error?: string;
  /** Status code if available */
  statuscode?: string;
  /** Additional message */
  message?: string;
}

/**
 * Parse a raw message object into a ServerEvent.
 */
export function parseServerEvent(data: Record<string, unknown>): ServerEvent {
  // Map text field to token for token events
  if (data.type === 'token' && 'text' in data) {
    data.token = data.text as string;
  }

  // Map items to tools
  if ('items' in data) {
    data.tools = data.items as Array<Record<string, unknown>>;
  }

  return data as unknown as ServerEvent;
}

// =============================================================================
// Client Message Types
// =============================================================================

/**
 * Client message types.
 */
export type ClientMessageType = 'message' | 'stop' | 'tool_consent_response' | 'tool_consent_set';

/**
 * Client message to send to MCP chat service.
 */
export interface ClientMessage {
  type: ClientMessageType;
  text?: string;
  message_history?: HistoryMessage[];
  consent_id?: string;
  allow?: boolean;
  allow_all?: boolean;
  tool_name?: string;
}

/**
 * Create a chat message.
 */
export function createMessage(text: string, messageHistory?: HistoryMessage[]): ClientMessage {
  const msg: ClientMessage = { type: 'message', text };
  if (messageHistory !== undefined) {
    msg.message_history = messageHistory;
  }
  return msg;
}

/**
 * Create a stop message.
 */
export function createStopMessage(): ClientMessage {
  return { type: 'stop' };
}

/**
 * Create a tool consent response.
 */
export function createConsentResponse(
  consentId: string,
  allow: boolean,
  allowAll?: boolean
): ClientMessage {
  const msg: ClientMessage = {
    type: 'tool_consent_response',
    consent_id: consentId,
    allow,
  };
  if (allowAll !== undefined) {
    msg.allow_all = allowAll;
  }
  return msg;
}

/**
 * Create a consent set message.
 */
export function createConsentSet(options: {
  allowAll?: boolean;
  toolName?: string;
}): ClientMessage {
  const msg: ClientMessage = { type: 'tool_consent_set' };
  if (options.allowAll !== undefined) {
    msg.allow_all = options.allowAll;
  }
  if (options.toolName !== undefined) {
    msg.tool_name = options.toolName;
  }
  return msg;
}

// =============================================================================
// Callback Types
// =============================================================================

/** Callback when connection is established */
export type ConnectedCallback = (sessionId: string) => void;

/** Callback for streaming text tokens */
export type TokenCallback = (text: string) => void;

/** Callback when a tool starts execution */
export type ToolStartCallback = (name: string, input: Record<string, unknown>) => void;

/** Callback when a tool completes execution */
export type ToolEndCallback = (
  name: string,
  output: string,
  success: boolean,
  error?: string
) => void;

/** Callback for tool consent requests */
export type ToolConsentCallback = (
  consentId: string,
  tool: string,
  args: Record<string, unknown>,
  description?: string
) => void;

/** Callback for consent timeout */
export type ConsentTimeoutCallback = (consentId: string) => void;

/** Callback for consent pending warning (consent not received in time) */
export type ConsentPendingCallback = (
  consentId: string,
  tool: string,
  message: string,
  elapsedSeconds: number
) => void;

/** Callback for final complete response with tool calls */
export type FinalCallback = (text: string, toolCalls: ToolCallEntry[]) => void;

/**
 * Structured error information from the server.
 */
export interface MCPError {
  /** Human-readable error message */
  message: string;
  /** Error code for categorization (e.g., "MCP_CONNECTION_FAILED") */
  code?: string;
  /** Additional error details */
  details?: Record<string, unknown>;
}

/** Callback for errors (simple message only, for backward compatibility) */
export type ErrorCallback = (message: string) => void;

/** Enhanced callback for errors with full error details */
export type EnhancedErrorCallback = (error: MCPError) => void;

/** Callback for status updates */
export type StatusCallback = (message: string) => void;

/** Callback for disconnection */
export type DisconnectedCallback = (reason?: string) => void;

// =============================================================================
// Configuration Types
// =============================================================================

/**
 * Configuration options for MCPChatClient.
 */
export interface MCPChatClientConfig {
  /** Authentication token for the project */
  projectToken: string;
  /** Deployment identifier for this client */
  deploymentName: string;
  /**
   * MCP Client Service WebSocket URL.
   * Only required for on-premise deployments.
   * If not provided, uses MCP_CLIENT_URL environment variable,
  * falling back to the default cloud service (https://mcp-client.p.apichap.com).
   */
  mcpClientUrl?: string;
  /**
   * Optional security parameters (key-value pairs) that will be merged with
   * security headers loaded from chatbot settings. These take precedence over
   * loaded values, allowing you to override or provide credentials.
   */
  securityParams?: Record<string, string>;
  /** Enable automatic reconnection on disconnect (default: true) */
  autoReconnect?: boolean;
  /** Maximum number of reconnection attempts (default: 5) */
  maxReconnectAttempts?: number;
  /** Base delay between reconnection attempts in ms (default: 2000) */
  reconnectDelayMs?: number;
  /** System message/prompt for the LLM */
  systemMessage?: string;
  /** Language setting for the assistant */
  language?: string;
  /**
   * Optional initial message history to provide context.
   * Messages are inserted after the system message but before new user messages.
   * Useful for continuing conversations or providing example interactions.
   */
  messageHistory?: HistoryMessage[];
  /**
   * Whether to cache conversation history on the server (default: false).
   * If true, messages are automatically appended to history.
   * If false, no history is stored server-side.
   */
  cacheHistory?: boolean;
}

/**
 * Connection options for the connect() method.
 */
export interface ConnectOptions {
  /** Client timezone (e.g., "Europe/Berlin") */
  timezone?: string;
}

/**
 * Options for the sendMessage() method.
 */
export interface SendMessageOptions {
  /**
   * Optional message history override for this message only.
   * If provided, this history overrides configured history for the current request.
   */
  messageHistory?: HistoryMessage[];
}

/**
 * WebSocket connection parameters.
 */
export interface WebSocketConnectionParams {
  url: string;
  deploymentName: string;
  projectToken: string;
  autoReconnect: boolean;
  maxReconnectAttempts: number;
  reconnectDelayMs: number;
  timezone?: string;
  systemMessage?: string;
  language?: string;
  /** Security parameters to merge with loaded credentials */
  securityParams?: Record<string, string>;
  /** Initial message history */
  messageHistory?: HistoryMessage[];
  /** Whether to cache conversation history on the server (default: false) */
  cacheHistory?: boolean;
}
