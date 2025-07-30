# API Specification

This is the API specification for the spec detailed in @.agent-os/specs/2025-07-30-scribe-chat-#69/spec.md

> Created: 2025-07-30
> Version: 1.0.0

## API Overview

The chat system integrates with the existing Next.js API infrastructure, adding new endpoints for conversational interaction while leveraging existing search and data systems.

## Endpoints

### POST /api/chat

**Purpose:** Process chat queries and return AI-generated responses with source citations
**Authentication:** None required (local application)
**Rate Limiting:** 60 requests per minute per session

#### Request Format
```typescript
interface ChatRequest {
  query: string;                    // User's natural language question
  sessionId?: string;              // Optional session ID for context preservation  
  language?: 'en' | 'de' | 'he';   // Preferred response language (default: 'en')
  maxSources?: number;             // Maximum interview sources to reference (default: 5)
  includeContext?: boolean;        // Include conversation context in response (default: true)
}
```

#### Response Format
```typescript
interface ChatResponse {
  id: string;                      // Unique response ID
  sessionId: string;               // Session ID for context tracking
  query: string;                   // Original user query
  response: string;                // AI-generated response text
  sources: CitationSource[];       // Array of interview sources used
  responseTime: number;            // Response time in milliseconds
  tokensUsed?: number;             // API tokens consumed (optional)
  confidence?: number;             // Response confidence score 0-1 (optional)
  error?: string;                  // Error message if request failed
}

interface CitationSource {
  interviewId: string;             // Interview UUID matching manifest
  intervieweeName: string;         // Name for display purposes
  relevantText: string;            // Specific text excerpt used
  timestamp?: number;              // Timestamp in seconds for video linking
  confidence: number;              // Relevance confidence score 0-1
  language: 'en' | 'de' | 'he';    // Language of the source content
}
```

#### Example Request
```json
{
  "query": "What stories do they have about the Eastern Front?",
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "language": "en",
  "maxSources": 5,
  "includeContext": true
}
```

#### Example Response
```json
{
  "id": "resp_123456789",
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "query": "What stories do they have about the Eastern Front?",
  "response": "Several interviewees shared powerful accounts of their experiences on the Eastern Front. Max Goldberg described the harsh winter conditions during the retreat from Moscow, noting how many soldiers struggled with inadequate supplies. Similarly, Hans Mueller recounted the psychological impact of witnessing the massive scale of the conflict.",
  "sources": [
    {
      "interviewId": "225f0880-e414-43cd-b3a5-2bd6e5642f07",
      "intervieweeName": "Max Goldberg",
      "relevantText": "The winter was brutal. We had no proper equipment for the cold, and men were falling out of formation every hour...",
      "timestamp": 1847,
      "confidence": 0.95,
      "language": "en"
    },
    {
      "interviewId": "b8f3d9c2-1a4e-4b7c-9d8e-2f3a1b4c5d6e",
      "intervieweeName": "Hans Mueller", 
      "relevantText": "You couldn't comprehend the scale until you were there. The Eastern Front stretched for thousands of kilometers...",
      "timestamp": 2234,
      "confidence": 0.87,
      "language": "en"
    }
  ],
  "responseTime": 1250,
  "tokensUsed": 892,
  "confidence": 0.91
}
```

#### Error Responses

**400 Bad Request**
```json
{
  "error": "Invalid query: Query must be between 3 and 500 characters",
  "code": "INVALID_QUERY_LENGTH"
}
```

**429 Too Many Requests**
```json
{
  "error": "Rate limit exceeded. Please wait before making another request.",
  "code": "RATE_LIMIT_EXCEEDED",
  "retryAfter": 60
}
```

**500 Internal Server Error**
```json
{
  "error": "Failed to process query due to OpenAI API error",
  "code": "OPENAI_API_ERROR"
}
```

### GET /api/chat/sessions/:sessionId

**Purpose:** Retrieve conversation history for a specific session
**Parameters:** 
- `sessionId` (path): Session UUID to retrieve

#### Response Format
```typescript
interface SessionResponse {
  sessionId: string;
  createdAt: string;               // ISO timestamp
  updatedAt: string;               // ISO timestamp  
  messageCount: number;
  conversations: ChatExchange[];   // Array of query-response pairs
}

interface ChatExchange {
  id: string;
  query: string;
  response: string;
  sources: CitationSource[];
  timestamp: string;               // ISO timestamp
  responseTime: number;
}
```

### DELETE /api/chat/sessions/:sessionId

**Purpose:** Clear conversation history for privacy
**Parameters:**
- `sessionId` (path): Session UUID to clear

#### Response Format
```json
{
  "success": true,
  "message": "Session cleared successfully"
}
```

## API Controllers

### ChatController

```typescript
// scribe-viewer/app/api/chat/route.ts
export class ChatController {
  async processQuery(request: ChatRequest): Promise<ChatResponse> {
    // 1. Validate and sanitize query
    // 2. Search for relevant content using existing Fuse.js system
    // 3. Generate response using OpenAI GPT-4
    // 4. Format response with proper citations
    // 5. Log query metrics for analytics
  }

  private async searchRelevantContent(query: string, maxSources: number): Promise<SearchResult[]> {
    // Leverage existing search infrastructure
  }

  private async generateResponse(query: string, sources: SearchResult[], language: string): Promise<string> {
    // OpenAI GPT-4 integration
  }

  private formatCitations(sources: SearchResult[]): CitationSource[] {
    // Convert search results to citation format
  }
}
```

### SessionController

```typescript
// scribe-viewer/app/api/chat/sessions/[sessionId]/route.ts
export class SessionController {
  async getSession(sessionId: string): Promise<SessionResponse> {
    // Retrieve session data from database
  }

  async clearSession(sessionId: string): Promise<{success: boolean}> {
    // Clear session data for privacy
  }

  async updateSession(sessionId: string, exchange: ChatExchange): Promise<void> {
    // Update session with new conversation
  }
}
```

## Integration Points

### Existing Search System Integration
```typescript
// Integration with existing search infrastructure
import { searchInterviews } from '@/lib/search';

const relevantInterviews = await searchInterviews(query, {
  limit: maxSources,
  threshold: 0.3,  // Minimum relevance score
  includeTranscripts: true
});
```

### Manifest Data Integration
```typescript
// Access to existing interview data
import { getInterview } from '@/lib/data';

const interviewDetails = await getInterview(interviewId);
const citationSource: CitationSource = {
  interviewId: interview.id,
  intervieweeName: interview.intervieweeName,
  relevantText: extractRelevantText(interview.transcripts, query),
  timestamp: findTimestamp(interview.transcripts, relevantText),
  confidence: relevanceScore,
  language: interview.transcripts[0].language
};
```

## Error Handling Strategy

### OpenAI API Errors
- **Retry Logic:** Exponential backoff for transient failures
- **Fallback Responses:** Provide search results without AI generation if OpenAI unavailable
- **Error Logging:** Comprehensive logging without storing sensitive query content

### Search System Errors
- **Graceful Degradation:** Return cached popular content if search fails
- **User Feedback:** Clear error messages explaining what went wrong
- **Monitoring:** Track search performance and failure rates

### Rate Limiting Implementation
```typescript
// Simple in-memory rate limiting for MVP
const rateLimiter = new Map<string, { count: number; resetTime: number }>();

function checkRateLimit(sessionId: string): boolean {
  const now = Date.now();
  const session = rateLimiter.get(sessionId);
  
  if (!session || now > session.resetTime) {
    rateLimiter.set(sessionId, { count: 1, resetTime: now + 60000 });
    return true;
  }
  
  if (session.count >= 60) {
    return false;
  }
  
  session.count++;
  return true;
}
```

## Security Considerations

### Input Validation
- **Query Length:** 3-500 characters
- **Language Validation:** Only accept supported language codes
- **Session ID Validation:** UUID v4 format only
- **XSS Prevention:** Sanitize all user inputs

### Privacy Protection
- **No Query Storage:** Never store actual query content in logs
- **Session Management:** Automatic cleanup after 24 hours  
- **Local Only:** All processing happens locally, no data sent to external services except OpenAI

### API Security
- **CORS Configuration:** Restrict to localhost origins only
- **Request Size Limits:** Maximum 1KB request payload
- **Timeout Protection:** 30-second request timeout