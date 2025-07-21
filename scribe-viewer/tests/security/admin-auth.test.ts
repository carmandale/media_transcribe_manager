/**
 * Security and Authentication Tests
 * Tests admin authentication, authorization, and security measures
 */

import { NextRequest } from 'next/server';
import { withAdminAuth, getAuthenticatedUser } from '@/lib/auth';

// Mock Next.js request for testing
function createMockRequest(options: {
  headers?: Record<string, string>;
  url?: string;
  method?: string;
}): NextRequest {
  const { headers = {}, url = 'http://localhost:3000/api/admin/test', method = 'GET' } = options;
  
  return new NextRequest(url, {
    method,
    headers: new Headers(headers),
  });
}

// Mock handler for testing
const mockHandler = jest.fn(async (req: NextRequest) => {
  return new Response(JSON.stringify({ success: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
});

describe('Admin Authentication Security Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset environment variables
    delete process.env.ADMIN_API_KEY;
    delete process.env.NODE_ENV;
  });

  describe('API Key Authentication', () => {
    test('should allow access with valid API key in Authorization header', async () => {
      process.env.ADMIN_API_KEY = 'test-secret-key';
      
      const request = createMockRequest({
        headers: {
          'Authorization': 'Bearer test-secret-key',
        },
      });

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(200);
      expect(mockHandler).toHaveBeenCalledWith(request);
    });

    test('should allow access with valid API key in query parameter', async () => {
      process.env.ADMIN_API_KEY = 'test-secret-key';
      
      const request = createMockRequest({
        url: 'http://localhost:3000/api/admin/test?api_key=test-secret-key',
      });

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(200);
      expect(mockHandler).toHaveBeenCalledWith(request);
    });

    test('should reject access with invalid API key', async () => {
      process.env.ADMIN_API_KEY = 'correct-secret-key';
      
      const request = createMockRequest({
        headers: {
          'Authorization': 'Bearer wrong-key',
        },
      });

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(401);
      expect(mockHandler).not.toHaveBeenCalled();
      
      const responseData = await response.json();
      expect(responseData.error).toContain('Unauthorized');
    });

    test('should reject access with missing API key', async () => {
      process.env.ADMIN_API_KEY = 'test-secret-key';
      
      const request = createMockRequest({});

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(401);
      expect(mockHandler).not.toHaveBeenCalled();
    });

    test('should reject access with empty API key', async () => {
      process.env.ADMIN_API_KEY = 'test-secret-key';
      
      const request = createMockRequest({
        headers: {
          'Authorization': 'Bearer ',
        },
      });

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(401);
      expect(mockHandler).not.toHaveBeenCalled();
    });
  });

  describe('Development Mode Bypass', () => {
    test('should allow access in development mode without API key', async () => {
      process.env.NODE_ENV = 'development';
      // No ADMIN_API_KEY set
      
      const request = createMockRequest({});

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(200);
      expect(mockHandler).toHaveBeenCalledWith(request);
    });

    test('should still validate API key in development if provided', async () => {
      process.env.NODE_ENV = 'development';
      process.env.ADMIN_API_KEY = 'dev-key';
      
      const request = createMockRequest({
        headers: {
          'Authorization': 'Bearer wrong-key',
        },
      });

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(401);
      expect(mockHandler).not.toHaveBeenCalled();
    });

    test('should require API key in production mode', async () => {
      process.env.NODE_ENV = 'production';
      // No ADMIN_API_KEY set
      
      const request = createMockRequest({});

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(401);
      expect(mockHandler).not.toHaveBeenCalled();
    });
  });

  describe('User Context Tracking', () => {
    test('should provide authenticated user context', async () => {
      process.env.ADMIN_API_KEY = 'test-key';
      
      const request = createMockRequest({
        headers: {
          'Authorization': 'Bearer test-key',
        },
      });

      const user = getAuthenticatedUser(request);
      
      expect(user).toBeDefined();
      expect(user.id).toBeTruthy();
      expect(user.source).toBe('api_key');
    });

    test('should provide development user in dev mode', async () => {
      process.env.NODE_ENV = 'development';
      
      const request = createMockRequest({});

      const user = getAuthenticatedUser(request);
      
      expect(user).toBeDefined();
      expect(user.id).toBe('dev-user');
      expect(user.source).toBe('development');
    });

    test('should generate consistent user ID for same API key', async () => {
      process.env.ADMIN_API_KEY = 'consistent-key';
      
      const request1 = createMockRequest({
        headers: { 'Authorization': 'Bearer consistent-key' },
      });
      
      const request2 = createMockRequest({
        headers: { 'Authorization': 'Bearer consistent-key' },
      });

      const user1 = getAuthenticatedUser(request1);
      const user2 = getAuthenticatedUser(request2);
      
      expect(user1.id).toBe(user2.id);
    });

    test('should generate different user IDs for different API keys', async () => {
      // Set test environment for this specific test
      process.env.NODE_ENV = 'test';
      
      const request1 = createMockRequest({
        headers: { 'Authorization': 'Bearer key-1' },
      });
      
      const request2 = createMockRequest({
        headers: { 'Authorization': 'Bearer key-2' },
      });

      const user1 = getAuthenticatedUser(request1);
      const user2 = getAuthenticatedUser(request2);
      
      expect(user1.id).not.toBe(user2.id);
    });
  });

  describe('Security Headers and Response', () => {
    test('should not expose sensitive information in error responses', async () => {
      process.env.ADMIN_API_KEY = 'secret-key';
      
      const request = createMockRequest({
        headers: {
          'Authorization': 'Bearer wrong-key',
        },
      });

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      const responseData = await response.json();
      
      // Should not expose the actual API key or internal details
      expect(JSON.stringify(responseData)).not.toContain('secret-key');
      expect(responseData.error).not.toContain('secret-key');
    });

    test('should handle malformed Authorization headers', async () => {
      process.env.ADMIN_API_KEY = 'test-key';
      
      const malformedHeaders = [
        'Bearer', // Missing key
        'Basic test-key', // Wrong auth type
        'Bearer  ', // Empty key with spaces
        'test-key', // Missing Bearer prefix
        'Bearer test-key extra-data', // Extra data
      ];

      for (const authHeader of malformedHeaders) {
        const request = createMockRequest({
          headers: {
            'Authorization': authHeader,
          },
        });

        const protectedHandler = withAdminAuth(mockHandler);
        const response = await protectedHandler(request);
        
        expect(response.status).toBe(401);
        expect(mockHandler).not.toHaveBeenCalled();
        
        mockHandler.mockClear();
      }
    });
  });

  describe('Attack Vector Prevention', () => {
    test('should prevent timing attacks on API key comparison', async () => {
      process.env.ADMIN_API_KEY = 'correct-key-with-specific-length';
      
      const shortWrongKey = 'a';
      const longWrongKey = 'a'.repeat(100);
      const correctLengthWrongKey = 'b'.repeat('correct-key-with-specific-length'.length);
      
      const testKeys = [shortWrongKey, longWrongKey, correctLengthWrongKey];
      const timings: number[] = [];
      
      for (const key of testKeys) {
        const request = createMockRequest({
          headers: {
            'Authorization': `Bearer ${key}`,
          },
        });

        const startTime = performance.now();
        const protectedHandler = withAdminAuth(mockHandler);
        await protectedHandler(request);
        const endTime = performance.now();
        
        timings.push(endTime - startTime);
      }
      
      // Timing differences should be minimal (within reasonable variance)
      const maxTiming = Math.max(...timings);
      const minTiming = Math.min(...timings);
      const timingDifference = maxTiming - minTiming;
      
      // Allow for some variance but prevent obvious timing attacks
      expect(timingDifference).toBeLessThan(50); // 50ms variance threshold
    });

    test('should handle injection attempts in API key', async () => {
      process.env.ADMIN_API_KEY = 'safe-key';
      
      const injectionAttempts = [
        'safe-key; DROP TABLE users;',
        'safe-key<script>alert("xss")</script>',
        'safe-key\\n\\r\\t',
        'safe-key${process.env.SECRET}',
        'safe-key`rm -rf /`',
      ];

      for (const maliciousKey of injectionAttempts) {
        const request = createMockRequest({
          headers: {
            'Authorization': `Bearer ${maliciousKey}`,
          },
        });

        const protectedHandler = withAdminAuth(mockHandler);
        const response = await protectedHandler(request);
        
        expect(response.status).toBe(401);
        expect(mockHandler).not.toHaveBeenCalled();
        
        mockHandler.mockClear();
      }
    });

    test('should handle extremely long API keys', async () => {
      process.env.ADMIN_API_KEY = 'normal-key';
      
      const extremelyLongKey = 'a'.repeat(10000);
      
      const request = createMockRequest({
        headers: {
          'Authorization': `Bearer ${extremelyLongKey}`,
        },
      });

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(401);
      expect(mockHandler).not.toHaveBeenCalled();
    });
  });

  describe('Environment Variable Security', () => {
    test('should handle missing environment variables gracefully', async () => {
      // Ensure no API key is set
      delete process.env.ADMIN_API_KEY;
      process.env.NODE_ENV = 'production';
      
      const request = createMockRequest({
        headers: {
          'Authorization': 'Bearer any-key',
        },
      });

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(401);
      expect(mockHandler).not.toHaveBeenCalled();
    });

    test('should handle empty environment variables', async () => {
      process.env.ADMIN_API_KEY = '';
      process.env.NODE_ENV = 'production';
      
      const request = createMockRequest({
        headers: {
          'Authorization': 'Bearer any-key',
        },
      });

      const protectedHandler = withAdminAuth(mockHandler);
      const response = await protectedHandler(request);
      
      expect(response.status).toBe(401);
      expect(mockHandler).not.toHaveBeenCalled();
    });
  });

  describe('Rate Limiting Considerations', () => {
    test('should handle multiple rapid authentication attempts', async () => {
      process.env.ADMIN_API_KEY = 'test-key';
      
      const rapidRequests = Array.from({ length: 100 }, () => 
        createMockRequest({
          headers: {
            'Authorization': 'Bearer wrong-key',
          },
        })
      );

      const protectedHandler = withAdminAuth(mockHandler);
      
      // All requests should be handled consistently
      const responses = await Promise.all(
        rapidRequests.map(req => protectedHandler(req))
      );
      
      responses.forEach(response => {
        expect(response.status).toBe(401);
      });
      
      expect(mockHandler).not.toHaveBeenCalled();
    });
  });

  describe('CORS and Security Headers', () => {
    test('should handle requests with various origins', async () => {
      process.env.ADMIN_API_KEY = 'test-key';
      
      const origins = [
        'http://localhost:3000',
        'https://malicious-site.com',
        'null',
        undefined,
      ];

      for (const origin of origins) {
        const headers: Record<string, string> = {
          'Authorization': 'Bearer test-key',
        };
        
        if (origin !== undefined) {
          headers['Origin'] = origin;
        }

        const request = createMockRequest({ headers });
        const protectedHandler = withAdminAuth(mockHandler);
        const response = await protectedHandler(request);
        
        // Should authenticate regardless of origin (CORS handled elsewhere)
        expect(response.status).toBe(200);
        
        mockHandler.mockClear();
      }
    });
  });
});
