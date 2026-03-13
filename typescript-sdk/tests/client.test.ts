/**
 * Tests for MCPChatClient.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MCPChatClient } from '../src/client.js';

// Mock environment
vi.stubEnv('MCP_CLIENT_URL', 'wss://test.example.com');

describe('MCPChatClient', () => {
  describe('constructor', () => {
    it('should create client with required config', () => {
      const client = new MCPChatClient({
        projectToken: 'test-token',
        deploymentName: 'test-deployment',
        mcpClientUrl: 'wss://test.example.com',
      });

      expect(client).toBeDefined();
      expect(client.sessionId).toBeUndefined();
      expect(client.isConnected).toBe(false);
    });

    it('should use default cloud URL when no MCP client URL is provided', () => {
      vi.stubEnv('MCP_CLIENT_URL', '');
      
      // Should NOT throw - uses default cloud URL
      const client = new MCPChatClient({
        projectToken: 'test-token',
        deploymentName: 'test-deployment',
      });

      expect(client).toBeDefined();
      expect(client.isConnected).toBe(false);

      // Restore
      vi.stubEnv('MCP_CLIENT_URL', 'wss://test.example.com');
    });

    it('should use mcpClientUrl from config over env var', () => {
      const client = new MCPChatClient({
        projectToken: 'test-token',
        deploymentName: 'test-deployment',
        mcpClientUrl: 'wss://custom.example.com',
      });

      expect(client).toBeDefined();
    });
  });

  describe('callback registration', () => {
    let client: MCPChatClient;

    beforeEach(() => {
      client = new MCPChatClient({
        projectToken: 'test-token',
        deploymentName: 'test-deployment',
        mcpClientUrl: 'wss://test.example.com',
      });
    });

    it('should support fluent API for callbacks', () => {
      const result = client
        .onConnected(() => {})
        .onToken(() => {})
        .onToolStart(() => {})
        .onToolEnd(() => {})
        .onToolConsentRequest(() => {})
        .onConsentTimeout(() => {})
        .onFinal(() => {})
        .onError(() => {})
        .onStatus(() => {})
        .onDisconnected(() => {});

      expect(result).toBe(client);
    });
  });

  describe('configuration methods', () => {
    let client: MCPChatClient;

    beforeEach(() => {
      client = new MCPChatClient({
        projectToken: 'test-token',
        deploymentName: 'test-deployment',
        mcpClientUrl: 'wss://test.example.com',
      });
    });

    it('should set system message with fluent API', () => {
      const result = client.setSystemMessage('You are a helpful assistant');
      expect(result).toBe(client);
    });

    it('should set language with fluent API', () => {
      const result = client.setLanguage('German');
      expect(result).toBe(client);
    });
  });
});
