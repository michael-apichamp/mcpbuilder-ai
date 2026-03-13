/**
 * WebSocket client for connecting to MCP client service.
 * 
 * This module is isomorphic - it works in both Node.js and browser environments.
 * - In Node.js: uses the 'ws' package
 * - In browser: uses native WebSocket
 */

import type {
  ServerEvent,
  WebSocketConnectionParams,
  HistoryMessage,
} from './types.js';
import {
  parseServerEvent,
  createMessage,
  createStopMessage,
  createConsentResponse,
  createConsentSet,
} from './types.js';

// Declare global types for browser environment detection
declare const globalThis: {
  WebSocket?: new (url: string) => WebSocket;
} & typeof global;

// Detect if we're in a browser environment
const isBrowser = typeof globalThis.WebSocket !== 'undefined';

// WebSocket type that works in both environments
type WebSocketLike = {
  readyState: number;
  onopen: ((event: unknown) => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onclose: ((event: unknown) => void) | null;
  send(data: string): void;
  close(): void;
};

/**
 * Get the WebSocket constructor for the current environment.
 */
async function getWebSocketConstructor(): Promise<new (url: string) => WebSocketLike> {
  if (isBrowser) {
    return globalThis.WebSocket as unknown as new (url: string) => WebSocketLike;
  } else {
    // Dynamic import for Node.js
    const ws = await import('ws');
    return ws.default as unknown as new (url: string) => WebSocketLike;
  }
}

/**
 * Logger interface for the WebSocket client.
 */
interface Logger {
  debug(message: string): void;
  info(message: string): void;
  warn(message: string): void;
  error(message: string): void;
}

/**
 * Default console logger.
 */
const defaultLogger: Logger = {
  debug: (msg) => console.debug(`[MCPBuilder] ${msg}`),
  info: (msg) => console.info(`[MCPBuilder] ${msg}`),
  warn: (msg) => console.warn(`[MCPBuilder] ${msg}`),
  error: (msg) => console.error(`[MCPBuilder] ${msg}`),
};

/**
 * WebSocket client for MCP chat service communication.
 */
export class WebSocketClient {
  private ws: WebSocketLike | null = null;
  private _isConnected = false;
  private _isConnecting = false;
  private wasEverConnected = false;
  private messageCallbacks: Array<(event: ServerEvent) => void> = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private autoReconnectEnabled = false;
  private reconnectDelayMs = 2000;
  private url = '';
  private connectionParams: Record<string, string> = {};
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private initializedResolve: (() => void) | null = null;
  private logger: Logger;

  constructor(logger?: Logger) {
    this.logger = logger || defaultLogger;
  }

  /**
   * Check if currently connected.
   * Note: WebSocket.OPEN = 1 in both browser and Node.js
   */
  get isConnected(): boolean {
    return this._isConnected && this.ws !== null && this.ws.readyState === 1;
  }

  /**
   * Connect to the MCP WebSocket service.
   */
  async connect(params: WebSocketConnectionParams): Promise<void> {
    const {
      url,
      deploymentName,
      projectToken,
      autoReconnect = true,
      maxReconnectAttempts = 3,
      reconnectDelayMs = 2000,
      timezone,
      systemMessage,
      language,
      securityParams,
      messageHistory,
      cacheHistory,
    } = params;

    if (!deploymentName) {
      throw new Error('deploymentName is required');
    }
    if (!projectToken) {
      throw new Error('projectToken is required');
    }

    this.url = url;
    this.autoReconnectEnabled = autoReconnect;
    this.maxReconnectAttempts = maxReconnectAttempts;
    this.reconnectDelayMs = reconnectDelayMs;
    this.connectionParams = {
      deployment_name: deploymentName,
      project_token: projectToken,
    };

    if (timezone) {
      this.connectionParams.timezone = timezone;
    }
    if (systemMessage) {
      this.connectionParams.system_message = systemMessage;
    }
    if (language) {
      this.connectionParams.language = language;
    }
    if (securityParams && Object.keys(securityParams).length > 0) {
      // JSON-encode security params for URL transport (matching Python SDK)
      // Filter out null, undefined, and empty string values to prevent server-side errors
      const validParams: Record<string, string> = {};
      for (const [key, value] of Object.entries(securityParams)) {
        if (value !== null && value !== undefined && value !== '') {
          validParams[key] = value;
        }
      }
      if (Object.keys(validParams).length > 0) {
        this.connectionParams.security_params = JSON.stringify(validParams);
      }
    }
    if (messageHistory && messageHistory.length > 0) {
      // JSON-encode message history for URL transport
      this.connectionParams.message_history = JSON.stringify(messageHistory);
    }
    if (cacheHistory !== undefined) {
      this.connectionParams.cache_history = String(cacheHistory);
    }

    await this.connectInternal();
  }

  /**
   * Internal connection logic.
   */
  private async connectInternal(): Promise<void> {
    // Guard against concurrent connections
    if (this._isConnecting) {
      this.logger.warn('Connection already in progress, skipping');
      return;
    }
    if (this._isConnected) {
      this.logger.warn('Already connected, skipping');
      return;
    }
    
    this._isConnecting = true;
    
    const queryParams = new URLSearchParams(this.connectionParams);
    const wsUrl = `${this.url}/ws/chat?${queryParams.toString()}`;
    this.logger.info(`Connecting to ${wsUrl}`);

    // Get the appropriate WebSocket constructor for the environment
    const WebSocketImpl = await getWebSocketConstructor();

    return new Promise((resolve, reject) => {
      try {
        // Set up initialization resolver
        this.initializedResolve = null;
        new Promise<void>((res) => {
          this.initializedResolve = res;
        });

        this.ws = new WebSocketImpl(wsUrl);

        this.ws.onopen = () => {
          this._isConnected = true;
          this.wasEverConnected = true;
          this.reconnectAttempts = 0;
          this.logger.info('Connected to MCP service');
        };

        this.ws.onmessage = (event: { data: unknown }) => {
          try {
            // Handle both browser and Node.js message data
            const rawData = typeof event.data === 'string' ? event.data : String(event.data);
            const data = JSON.parse(rawData) as Record<string, unknown>;

            // Handle service-initiated closing
            if (data.type === 'closing') {
              this.logger.info(`Service closing: ${data.reason}`);
              this.broadcastEvent({
                type: 'closing',
                reason: data.reason as string,
              });
              return;
            }

            // Check for "initialized" status to signal connection is ready
            if (data.type === 'status' && data.message === 'initialized') {
              this.logger.info('Received initialized status from server');
              this._isConnecting = false; // Connection complete
              if (this.initializedResolve) {
                this.initializedResolve();
                this.initializedResolve = null; // Clear to prevent timeout from re-resolving
              }
              resolve();
            }

            // Convert to ServerEvent
            const serverEvent = parseServerEvent(data);
            if (serverEvent.type === 'final') {
              this.logger.info(`Received 'final' event from server`);
            }
            this.broadcastEvent(serverEvent);
          } catch (err) {
            this.logger.error(`Failed to parse message: ${err}`);
          }
        };

        this.ws.onerror = (error: unknown) => {
          const errorMessage = error && typeof error === 'object' && 'message' in error
            ? (error as { message?: string }).message || 'Unknown error'
            : 'Unknown error';
          this.logger.error(`WebSocket error: ${errorMessage}`);
          if (!this.wasEverConnected) {
            reject(new Error(`Connection failed: ${errorMessage}`));
          }
        };

        this.ws.onclose = () => {
          this._isConnected = false;
          this.handleDisconnect();
        };

        // Set timeout for initialization
        setTimeout(() => {
          if (!this._isConnected) {
            this._isConnecting = false;
            reject(new Error('Connection timeout'));
          } else if (this.initializedResolve) {
            // Resolve anyway if connected but no init message
            this.logger.warn('Timeout waiting for server initialization, proceeding anyway');
            this._isConnecting = false;
            this.initializedResolve();
            this.initializedResolve = null; // Clear to prevent double-resolve
            resolve();
          }
        }, 30000);
      } catch (err) {
        this.logger.error(`Connection error: ${err}`);
        this._isConnected = false;
        this._isConnecting = false;

        if (this.ws) {
          this.ws.close();
          this.ws = null;
        }

        if (this.wasEverConnected && this.autoReconnectEnabled) {
          this.handleDisconnect();
          resolve();
        } else {
          this.broadcastEvent({
            type: 'error',
            error: `Connection failed: ${err}`,
          });
          reject(err);
        }
      }
    });
  }

  /**
   * Handle disconnection and attempt reconnection.
   */
  private handleDisconnect(): void {
    this.logger.info('Handling disconnect');
    this.broadcastEvent({
      type: 'status',
      status: 'Disconnected from chat service',
    });

    if (
      this.wasEverConnected &&
      this.autoReconnectEnabled &&
      this.reconnectAttempts < this.maxReconnectAttempts
    ) {
      this.reconnectAttempts++;
      const delay = (this.reconnectDelayMs * this.reconnectAttempts);
      this.logger.info(
        `Reconnecting in ${delay}ms (${this.reconnectAttempts}/${this.maxReconnectAttempts})`
      );

      this.reconnectTimer = setTimeout(() => {
        this.connectInternal().catch((err) => {
          this.logger.error(`Reconnection failed: ${err}`);
        });
      }, delay);
    }
  }

  /**
   * Send a chat message to the service.
   */
  async sendMessage(text: string, messageHistory?: HistoryMessage[]): Promise<void> {
    if (!this.isConnected || !this.ws) {
      this.logger.error('WebSocket not connected');
      this.broadcastEvent({
        type: 'error',
        error: 'Not connected to chat service',
      });
      return;
    }

    try {
      const message = createMessage(text, messageHistory);
      this.ws.send(JSON.stringify(message));
      this.logger.debug(`Sent message: ${text.substring(0, 50)}...`);
    } catch (err) {
      this.logger.error(`Failed to send message: ${err}`);
      this.broadcastEvent({
        type: 'error',
        error: `Failed to send message: ${err}`,
      });
    }
  }

  /**
   * Send a stop request to cancel the current operation.
   */
  async sendStop(): Promise<void> {
    if (!this.isConnected || !this.ws) {
      this.logger.error('WebSocket not connected');
      return;
    }

    try {
      const message = createStopMessage();
      this.ws.send(JSON.stringify(message));
      this.logger.info('Sent stop request');
    } catch (err) {
      this.logger.error(`Failed to send stop: ${err}`);
    }
  }

  /**
   * Respond to a tool consent request.
   */
  async sendToolConsent(
    consentId: string,
    allow: boolean,
    allowAll = false
  ): Promise<void> {
    if (!this.isConnected || !this.ws) {
      this.logger.error('WebSocket not connected');
      return;
    }

    try {
      const message = createConsentResponse(
        consentId,
        allow,
        allowAll ? allowAll : undefined
      );
      this.ws.send(JSON.stringify(message));
      this.logger.info(
        `Sent tool consent: ${allow} (allow_all=${allowAll}) for ${consentId}`
      );
    } catch (err) {
      this.logger.error(`Failed to send tool consent: ${err}`);
    }
  }

  /**
   * Set consent preferences.
   */
  async sendConsentSet(options: {
    allowAll?: boolean;
    toolName?: string;
  }): Promise<void> {
    if (!this.isConnected || !this.ws) {
      this.logger.error('WebSocket not connected');
      return;
    }

    try {
      const message = createConsentSet(options);
      this.ws.send(JSON.stringify(message));
      this.logger.info(
        `Sent consent set: allow_all=${options.allowAll}, tool_name=${options.toolName}`
      );
    } catch (err) {
      this.logger.error(`Failed to send consent set: ${err}`);
    }
  }

  /**
   * Register a callback for server events.
   */
  onMessage(callback: (event: ServerEvent) => void): void {
    this.messageCallbacks.push(callback);
  }

  /**
   * Clear all registered callbacks.
   */
  clearCallbacks(): void {
    this.messageCallbacks = [];
  }

  /**
   * Broadcast event to all registered callbacks.
   */
  private broadcastEvent(event: ServerEvent): void {
    if (event.type === 'final') {
      this.logger.info(`Broadcasting final event to ${this.messageCallbacks.length} callbacks`);
    }
    for (const callback of this.messageCallbacks) {
      try {
        callback(event);
      } catch (err) {
        this.logger.error(`Error in callback: ${err}`);
      }
    }
  }

  /**
   * Disconnect from the service.
   */
  async disconnect(): Promise<void> {
    this._isConnected = false;
    this._isConnecting = false;
    this.wasEverConnected = false;
    this.reconnectAttempts = 0;
    this.initializedResolve = null;
    this.clearCallbacks();

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      try {
        this.ws.close();
      } catch (err) {
        this.logger.error(`Error closing WebSocket: ${err}`);
      } finally {
        this.ws = null;
      }
    }

    this.logger.info('WebSocket disconnected');
  }
}
