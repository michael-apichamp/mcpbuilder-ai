/**
 * Tests for type definitions and helper functions.
 */

import { describe, it, expect } from 'vitest';
import {
  parseServerEvent,
  createMessage,
  createStopMessage,
  createConsentResponse,
  createConsentSet,
} from '../src/types.js';

describe('types', () => {
  describe('parseServerEvent', () => {
    it('should parse a basic status event', () => {
      const data = {
        type: 'status',
        message: 'initialized',
        status: 'session-123',
      };

      const event = parseServerEvent(data);

      expect(event.type).toBe('status');
      expect(event.message).toBe('initialized');
      expect(event.status).toBe('session-123');
    });

    it('should map text to token for token events', () => {
      const data = {
        type: 'token',
        text: 'Hello',
      };

      const event = parseServerEvent(data);

      expect(event.type).toBe('token');
      expect(event.token).toBe('Hello');
      expect(event.text).toBe('Hello');
    });

    it('should map items to tools', () => {
      const data = {
        type: 'tools',
        items: [{ name: 'tool1' }, { name: 'tool2' }],
      };

      const event = parseServerEvent(data);

      expect(event.tools).toEqual([{ name: 'tool1' }, { name: 'tool2' }]);
    });

    it('should handle tool_start event', () => {
      const data = {
        type: 'tool_start',
        name: 'search',
        input: { query: 'test' },
      };

      const event = parseServerEvent(data);

      expect(event.type).toBe('tool_start');
      expect(event.name).toBe('search');
      expect(event.input).toEqual({ query: 'test' });
    });

    it('should handle tool_consent_request event', () => {
      const data = {
        type: 'tool_consent_request',
        consent_id: 'consent-123',
        tool: 'execute_code',
        arguments: { code: 'print("hello")' },
        description: 'Run Python code',
      };

      const event = parseServerEvent(data);

      expect(event.type).toBe('tool_consent_request');
      expect(event.consent_id).toBe('consent-123');
      expect(event.tool).toBe('execute_code');
      expect(event.arguments).toEqual({ code: 'print("hello")' });
      expect(event.description).toBe('Run Python code');
    });

    it('should handle error event', () => {
      const data = {
        type: 'error',
        error: 'Something went wrong',
      };

      const event = parseServerEvent(data);

      expect(event.type).toBe('error');
      expect(event.error).toBe('Something went wrong');
    });
  });

  describe('createMessage', () => {
    it('should create a message object', () => {
      const msg = createMessage('Hello, world!');

      expect(msg).toEqual({
        type: 'message',
        text: 'Hello, world!',
      });
    });
  });

  describe('createStopMessage', () => {
    it('should create a stop message object', () => {
      const msg = createStopMessage();

      expect(msg).toEqual({
        type: 'stop',
      });
    });
  });

  describe('createConsentResponse', () => {
    it('should create a consent response without allowAll', () => {
      const msg = createConsentResponse('consent-123', true);

      expect(msg).toEqual({
        type: 'tool_consent_response',
        consent_id: 'consent-123',
        allow: true,
      });
    });

    it('should create a consent response with allowAll', () => {
      const msg = createConsentResponse('consent-456', true, true);

      expect(msg).toEqual({
        type: 'tool_consent_response',
        consent_id: 'consent-456',
        allow: true,
        allow_all: true,
      });
    });

    it('should create a deny consent response', () => {
      const msg = createConsentResponse('consent-789', false);

      expect(msg).toEqual({
        type: 'tool_consent_response',
        consent_id: 'consent-789',
        allow: false,
      });
    });
  });

  describe('createConsentSet', () => {
    it('should create a consent set with allowAll', () => {
      const msg = createConsentSet({ allowAll: true });

      expect(msg).toEqual({
        type: 'tool_consent_set',
        allow_all: true,
      });
    });

    it('should create a consent set with toolName', () => {
      const msg = createConsentSet({ toolName: 'search' });

      expect(msg).toEqual({
        type: 'tool_consent_set',
        tool_name: 'search',
      });
    });

    it('should create empty consent set', () => {
      const msg = createConsentSet({});

      expect(msg).toEqual({
        type: 'tool_consent_set',
      });
    });
  });
});
