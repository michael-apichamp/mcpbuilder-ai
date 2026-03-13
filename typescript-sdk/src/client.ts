/**
 * High-level chat client with callback-based event handling.
 *
 * This module provides the MCPChatClient class which wraps the WebSocket connection
 * and provides a clean callback-based API for handling chat events.
 *
 * @example
 * ```typescript
 * import { MCPChatClient } from 'mcpbuilder-ai';
 *
 * // URL is loaded from MCP_CLIENT_URL env var, or pass explicitly for on-premise
 * const client = new MCPChatClient({
 *   projectToken: process.env.PROJECT_TOKEN!,
 *   deploymentName: 'my-deployment',
 *   // Optional: provide security params that override loaded credentials
 *   securityParams: {
 *     'X-API-KEY': process.env.MY_API_KEY!,
 *     'Authorization': `Bearer ${process.env.MY_ACCESS_TOKEN}`,
 *   },
 * });
 *
 * // Register callbacks
 * client
 *   .onToken((text) => process.stdout.write(text))
 *   .onFinal((text, toolCalls) => console.log('\n\nDone!'))
 *   .onError((msg) => console.error(`Error: ${msg}`));
 *
 * // Connect and chat
 * await client.connect();
 * await client.sendMessage("What's the weather in London?");
 *
 * // When done
 * await client.disconnect();
 * ```
 */

import { WebSocketClient } from './websocket-client.js';
import type {
  ServerEvent,
  MCPChatClientConfig,
  ConnectOptions,
  SendMessageOptions,
  ConnectedCallback,
  TokenCallback,
  ToolStartCallback,
  ToolEndCallback,
  ToolConsentCallback,
  ConsentTimeoutCallback,
  ConsentPendingCallback,
  FinalCallback,
  ErrorCallback,
  EnhancedErrorCallback,
  MCPError,
  StatusCallback,
  DisconnectedCallback,
  HistoryMessage,
} from './types.js';

/** Default cloud-hosted MCP Client Service URL */
const DEFAULT_MCP_CLIENT_URL = 'https://mcp-client.p.apichap.com';

/**
 * Get environment variable (works in Node.js and Bun).
 */
function getEnv(key: string): string | undefined {
  if (typeof process !== 'undefined' && process.env) {
    return process.env[key];
  }
  return undefined;
}

/**
 * High-level MCP chat client with callback-based event handling.
 *
 * Provides a fluent API for registering event callbacks and sending messages.
 * All callbacks are optional - only register the ones you need.
 */
export class MCPChatClient {
  private wsClient: WebSocketClient;
  private mcpClientUrl: string;
  private projectToken: string;
  private deploymentName: string;
  private autoReconnect: boolean;
  private maxReconnectAttempts: number;
  private reconnectDelayMs: number;
  private systemMessage?: string;
  private language?: string;
  private securityParams?: Record<string, string>;
  private messageHistory?: HistoryMessage[];
  private cacheHistory: boolean;

  /** The session ID after connecting (undefined before connect) */
  public sessionId?: string;

  // Callback storage
  private onConnectedCallback?: ConnectedCallback;
  private onTokenCallback?: TokenCallback;
  private onToolStartCallback?: ToolStartCallback;
  private onToolEndCallback?: ToolEndCallback;
  private onToolConsentRequestCallback?: ToolConsentCallback;
  private onConsentTimeoutCallback?: ConsentTimeoutCallback;
  private onConsentPendingCallback?: ConsentPendingCallback;
  private onFinalCallback?: FinalCallback;
  private onErrorCallback?: ErrorCallback;
  private onErrorDetailsCallback?: EnhancedErrorCallback;
  private onStatusCallback?: StatusCallback;
  private onDisconnectedCallback?: DisconnectedCallback;

  /**
   * Initialize the chat client.
   *
   * @param config - Configuration options
   */
  constructor(config: MCPChatClientConfig) {
    const {
      projectToken,
      deploymentName,
      mcpClientUrl,
      securityParams,
      autoReconnect = true,
      maxReconnectAttempts = 5,
      reconnectDelayMs = 2000,
      systemMessage,
      language,
      messageHistory,
      cacheHistory = false,
    } = config;

    // Resolve MCP client URL: explicit param > env var > default cloud service
    let resolvedUrl = mcpClientUrl || getEnv('MCP_CLIENT_URL') || DEFAULT_MCP_CLIENT_URL;

    // Convert http/https to ws/wss for WebSocket connection
    resolvedUrl = resolvedUrl.replace(/\/$/, '');
    if (resolvedUrl.startsWith('https://')) {
      resolvedUrl = 'wss://' + resolvedUrl.slice(8);
    } else if (resolvedUrl.startsWith('http://')) {
      resolvedUrl = 'ws://' + resolvedUrl.slice(7);
    }

    this.mcpClientUrl = resolvedUrl;
    this.projectToken = projectToken;
    this.deploymentName = deploymentName;
    this.securityParams = securityParams;
    this.autoReconnect = autoReconnect;
    this.maxReconnectAttempts = maxReconnectAttempts;
    this.reconnectDelayMs = reconnectDelayMs;
    this.systemMessage = systemMessage;
    this.language = language;
    this.messageHistory = messageHistory;
    this.cacheHistory = cacheHistory;

    this.wsClient = new WebSocketClient();
    this.wsClient.onMessage((event) => this.handleEvent(event));
  }

  // ===========================================================================
  // Callback Registration (Fluent API)
  // ===========================================================================

  /**
   * Register callback for connection established event.
   *
   * @param callback - Function called with (sessionId: string)
   * @returns Self for method chaining
   */
  onConnected(callback: ConnectedCallback): this {
    this.onConnectedCallback = callback;
    return this;
  }

  /**
   * Register callback for streaming text tokens.
   *
   * @param callback - Function called with (text: string) for each token
   * @returns Self for method chaining
   */
  onToken(callback: TokenCallback): this {
    this.onTokenCallback = callback;
    return this;
  }

  /**
   * Register callback for tool execution starting.
   *
   * @param callback - Function called with (name: string, input: object)
   * @returns Self for method chaining
   */
  onToolStart(callback: ToolStartCallback): this {
    this.onToolStartCallback = callback;
    return this;
  }

  /**
   * Register callback for tool execution completed.
   *
   * @param callback - Function called with (name: string, output: string, success: boolean, error?: string)
   * @returns Self for method chaining
   */
  onToolEnd(callback: ToolEndCallback): this {
    this.onToolEndCallback = callback;
    return this;
  }

  /**
   * Register callback for tool consent requests.
   *
   * When called, you should call `respondConsent()` to allow/deny the tool.
   *
   * @param callback - Function called with (consentId: string, tool: string, args: object, description?: string)
   * @returns Self for method chaining
   */
  onToolConsentRequest(callback: ToolConsentCallback): this {
    this.onToolConsentRequestCallback = callback;
    return this;
  }

  /**
   * Register callback for consent request timeout.
   *
   * @param callback - Function called with (consentId: string)
   * @returns Self for method chaining
   */
  onConsentTimeout(callback: ConsentTimeoutCallback): this {
    this.onConsentTimeoutCallback = callback;
    return this;
  }

  /**
   * Register callback for consent pending warnings.
   *
   * Called when a consent request hasn't been responded to after ~30s.
   * If not registered, a warning will be logged to the console.
   *
   * @param callback - Function called with (consentId, tool, message, elapsedSeconds)
   * @returns Self for method chaining
   */
  onConsentPending(callback: ConsentPendingCallback): this {
    this.onConsentPendingCallback = callback;
    return this;
  }

  /**
   * Register callback for final complete response.
   *
   * @param callback - Function called with (text: string, toolCalls: ToolCallEntry[]) containing the full response and tool invocations
   * @returns Self for method chaining
   */
  onFinal(callback: FinalCallback): this {
    this.onFinalCallback = callback;
    return this;
  }

  /**
   * Register callback for errors.
   *
   * @param callback - Function called with (message: string)
   * @returns Self for method chaining
   */
  onError(callback: ErrorCallback): this {
    this.onErrorCallback = callback;
    return this;
  }

  /**
   * Register callback for errors with full error details.
   *
   * This is an enhanced version of onError that receives structured error
   * information including error codes and additional details.
   *
   * @param callback - Function called with MCPError object containing:
   *   - message: Human-readable error message
   *   - code: Error code for categorization (e.g., "MCP_CONNECTION_FAILED")
   *   - details: Additional error context
   * @returns Self for method chaining
   */
  onErrorDetails(callback: EnhancedErrorCallback): this {
    this.onErrorDetailsCallback = callback;
    return this;
  }

  /**
   * Register callback for status updates.
   *
   * @param callback - Function called with (message: string)
   * @returns Self for method chaining
   */
  onStatus(callback: StatusCallback): this {
    this.onStatusCallback = callback;
    return this;
  }

  /**
   * Register callback for disconnection events.
   *
   * @param callback - Function called with (reason?: string)
   * @returns Self for method chaining
   */
  onDisconnected(callback: DisconnectedCallback): this {
    this.onDisconnectedCallback = callback;
    return this;
  }

  // ===========================================================================
  // Connection Methods
  // ===========================================================================

  /**
   * Connect to the MCP chat service.
   *
   * All required parameters (projectToken, deploymentName) are configured
   * during client initialization.
   *
  * @param options - Optional connection options (timezone)
   */
  async connect(options: ConnectOptions = {}): Promise<void> {
    await this.wsClient.connect({
      url: this.mcpClientUrl,
      deploymentName: this.deploymentName,
      projectToken: this.projectToken,
      autoReconnect: this.autoReconnect,
      maxReconnectAttempts: this.maxReconnectAttempts,
      reconnectDelayMs: this.reconnectDelayMs,
      timezone: options.timezone,
      systemMessage: this.systemMessage,
      language: this.language,
      securityParams: this.securityParams,
      messageHistory: this.messageHistory,
      cacheHistory: this.cacheHistory,
    });
  }

  /**
   * Disconnect from the service.
   */
  async disconnect(): Promise<void> {
    await this.wsClient.disconnect();
    this.sessionId = undefined;
  }

  /**
   * Check if currently connected.
   */
  get isConnected(): boolean {
    return this.wsClient.isConnected;
  }

  // ===========================================================================
  // Configuration Methods
  // ===========================================================================

  /**
   * Set the system message/prompt for the LLM.
   *
   * @param message - System message text
   * @returns Self for method chaining
   */
  setSystemMessage(message: string): this {
    this.systemMessage = message;
    return this;
  }

  /**
   * Set the language for the assistant.
   *
   * @param language - Language identifier (e.g., "English", "German", "French")
   * @returns Self for method chaining
   */
  setLanguage(language: string): this {
    this.language = language;
    return this;
  }

  // ===========================================================================
  // Message Methods
  // ===========================================================================

  /**
   * Send a chat message.
   *
   * @param text - Message text
    * @param options - Optional per-message options (messageHistory override)
   */
  async sendMessage(text: string, options: SendMessageOptions = {}): Promise<void> {
    await this.wsClient.sendMessage(text, options.messageHistory);
  }

  /**
   * Stop the current agent run.
   */
  async stop(): Promise<void> {
    await this.wsClient.sendStop();
  }

  /**
   * Respond to a tool consent request.
   *
   * @param consentId - The consent request ID from the callback
   * @param allow - Whether to allow this tool execution
   * @param allowAll - If true, auto-allow all future tool calls
   */
  async respondConsent(
    consentId: string,
    allow: boolean,
    allowAll = false
  ): Promise<void> {
    await this.wsClient.sendToolConsent(consentId, allow, allowAll);
  }

  /**
   * Enable/disable auto-consent for all tools.
   *
   * @param enabled - If true, all tool calls will be auto-approved
   */
  async setConsentAll(enabled = true): Promise<void> {
    await this.wsClient.sendConsentSet({ allowAll: enabled });
  }

  /**
   * Auto-allow a specific tool.
   *
   * @param toolName - Name of the tool to auto-allow
   */
  async allowTool(toolName: string): Promise<void> {
    await this.wsClient.sendConsentSet({ toolName });
  }

  // ===========================================================================
  // Event Handling
  // ===========================================================================

  /**
   * Handle incoming server events and dispatch to callbacks.
   */
  private handleEvent(event: ServerEvent): void {
    try {
      const eventType = event.type;

      switch (eventType) {
        case 'status':
          // Check for initialized status with session_id
          if (event.message === 'initialized' && event.session_id) {
            this.sessionId = event.session_id;
            this.onConnectedCallback?.(this.sessionId);
          } else {
            this.onStatusCallback?.(event.message || event.status || '');
          }
          break;

        case 'token':
          this.onTokenCallback?.(event.token || event.text || '');
          break;

        case 'tool_start':
          this.onToolStartCallback?.(
            event.name || event.tool_name || '',
            event.input || event.tool_args || {}
          );
          break;

        case 'tool_end_success': {
          const output = event.output || event.tool_output || {};
          const outputStr = typeof output === 'string' ? output : JSON.stringify(output);
          this.onToolEndCallback?.(
            event.name || event.tool_name || '',
            outputStr,
            true,
            undefined
          );
          break;
        }

        case 'tool_end_failure': {
          const failOutput = event.output || event.tool_output || {};
          const failOutputStr = typeof failOutput === 'string' ? failOutput : JSON.stringify(failOutput);
          this.onToolEndCallback?.(
            event.name || event.tool_name || '',
            failOutputStr,
            false,
            event.message || event.error
          );
          break;
        }

        case 'tool_denied':
          this.onToolEndCallback?.(
            event.name || event.tool_name || '',
            '',
            false,
            event.reason || 'User denied tool execution'
          );
          break;

        case 'tool_error':
          this.onToolEndCallback?.(
            event.name || event.tool_name || '',
            '',
            false,
            event.error || 'Tool execution error'
          );
          break;

        case 'tool_consent_request':
          this.onToolConsentRequestCallback?.(
            event.consent_id || '',
            event.tool || event.name || '',
            event.arguments || event.tool_args || {},
            event.description
          );
          break;

        case 'consent_timeout':
          this.onConsentTimeoutCallback?.(event.consent_id || '');
          break;

        case 'consent_pending': {
          const toolName = event.tool || '';
          const message = event.message || `Consent pending for tool '${toolName}'`;
          const elapsed = event.elapsed_seconds || 0;
          if (this.onConsentPendingCallback) {
            this.onConsentPendingCallback(
              event.consent_id || '',
              toolName,
              message,
              elapsed
            );
          } else {
            // Log warning to console if no callback registered
            console.warn(
              `[MCPChatClient] ${message}\n` +
              `Tip: Register onToolConsentRequest() callback and call respondConsent() to allow/deny tool execution.`
            );
          }
          break;
        }

        case 'final':
          this.onFinalCallback?.(event.text || '', event.tool_calls || []);
          break;

        case 'error': {
          const errorMessage = event.error || event.message || 'Unknown error';
          // Call simple callback for backward compatibility
          this.onErrorCallback?.(errorMessage);
          // Call enhanced callback with full error details
          const errorObj: MCPError = {
            message: errorMessage,
            code: event.code,
            details: event.details,
          };
          this.onErrorDetailsCallback?.(errorObj);
          break;
        }

        case 'closing':
        case 'connection_closed':
          this.onDisconnectedCallback?.(event.reason);
          break;
      }
    } catch (err) {
      const errorMessage = `Event handling error: ${err}`;
      console.error(`Error handling event ${event.type}:`, err);
      this.onErrorCallback?.(errorMessage);
      const errorObj: MCPError = {
        message: errorMessage,
        code: 'INTERNAL_ERROR',
      };
      this.onErrorDetailsCallback?.(errorObj);
    }
  }
}
