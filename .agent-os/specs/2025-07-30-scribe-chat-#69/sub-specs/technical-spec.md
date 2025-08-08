# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-30-scribe-chat-#69/spec.md

> Created: 2025-07-30
> Version: 1.0.0

## Technical Requirements

### Data Pipeline Requirements
- **SRT Content Extraction:** Parse and clean transcript text from 726 SRT files in `srt_comparison/before/` directory
- **Manifest Population:** Update `manifest.min.json` with extracted transcript content maintaining existing ID structure
- **Content Processing:** Handle multiple languages (English/German) per interview with proper language detection
- **Performance:** Process all 726 interviews within 10 minutes on standard hardware
- **Data Integrity:** Maintain exact ID matching between SRT filenames and manifest entries

### Chat Interface Requirements
- **Response Time:** Sub-2 second response for 95% of queries using existing search infrastructure
- **Multi-turn Context:** Support 10+ turn conversations with context preservation
- **Citation Accuracy:** 98%+ accuracy in linking responses to correct interview sources
- **Language Support:** Handle queries in English, German, Hebrew with responses in query language
- **UI Integration:** Seamless integration with existing Next.js viewer and navigation patterns

### RAG System Requirements
- **Content Retrieval:** Leverage existing Fuse.js search as retrieval engine for semantic content discovery
- **Response Generation:** Use OpenAI GPT-4 for natural language response synthesis
- **Source Attribution:** Every response must include precise citations with interview IDs and timestamps
- **Hallucination Prevention:** Strict grounding to retrieved content only, no external knowledge injection
- **Quality Scoring:** Confidence scoring for generated responses with explicit uncertainty indicators

## Approach Options

**Option A: Comprehensive Vector Database Implementation**
- Pros: State-of-the-art semantic search, scalable for future features, industry standard approach
- Cons: Significant infrastructure overhead, complex deployment, high operational costs, 2-3x development time

**Option B: Enhanced Fuse.js with LLM Integration (Selected)**
- Pros: Leverages existing proven search infrastructure, rapid development, zero infrastructure changes, cost-effective
- Cons: Limited semantic understanding compared to vector embeddings

**Option C: Hybrid Vector + Fuse.js System**
- Pros: Best of both worlds, gradual migration path
- Cons: Complex dual-system architecture, maintenance overhead, longer development timeline

**Rationale:** Option B provides the fastest path to user value while building on proven architecture. The existing Fuse.js system already successfully searches 726 interviews, and this approach only requires populating it with rich transcript content. Vector database can be considered for Phase 2 if semantic search limitations become apparent.

## Implementation Architecture

### Phase 1: Data Pipeline Foundation
```python
# scripts/extract_srt_transcripts.py
class SRTExtractor:
    def extract_clean_text(self, srt_file_path: str) -> Dict[str, str]:
        """Extract clean transcript text from SRT file"""
        
    def process_all_interviews(self) -> Dict[str, InterviewTranscript]:
        """Process all 726 SRT files and return structured data"""

# scripts/populate_manifest.py  
class ManifestPopulator:
    def update_manifest_with_transcripts(self, transcripts: Dict[str, InterviewTranscript]):
        """Update manifest.min.json with extracted transcript content"""
```

### Phase 2: Chat System Architecture
```typescript
// scribe-viewer/app/chat/page.tsx
export default function ChatPage() {
  // Chat interface with existing UI patterns
}

// scribe-viewer/lib/chat-engine.ts
class ChatEngine {
  async processQuery(query: string, context: ChatContext): Promise<ChatResponse> {
    // 1. Use existing search system to find relevant content
    // 2. Generate response using OpenAI GPT-4
    // 3. Format with proper citations
  }
}

// scribe-viewer/app/api/chat/route.ts
export async function POST(request: Request) {
  // Chat API endpoint with rate limiting and error handling
}
```

### Phase 3: Integration Components
```typescript
// scribe-viewer/components/ChatInterface.tsx
interface ChatInterfaceProps {
  onCitationClick: (interviewId: string, timestamp: number) => void;
}

// Integration with existing viewer navigation
// Deep linking from chat responses to synchronized video/transcript moments
```

## External Dependencies

### New Dependencies Required

**Backend/Script Dependencies:**
- **python-dateutil** (v2.8.2) - For parsing SRT timestamps and date handling
  - **Justification:** Essential for accurate timestamp processing in SRT files
- **openai** (v1.0+) - For GPT-4 API integration and response generation
  - **Justification:** Required for natural language response generation in chat system

**Frontend Dependencies:**
- **@radix-ui/react-scroll-area** (latest) - For chat message scrolling with proper UX
  - **Justification:** Provides accessible, smooth scrolling for chat interface
- **react-markdown** (v8.0+) - For rendering formatted responses with proper typography
  - **Justification:** Chat responses may include formatting, lists, and structured content

### API Dependencies
- **OpenAI GPT-4 API** - For natural language response generation
  - **Rate Limits:** 10,000 requests/minute, 150,000 tokens/minute
  - **Cost Estimation:** ~$3-5k/month based on PRD estimates
  - **Fallback:** GPT-3.5-turbo for cost optimization if needed

### Infrastructure Dependencies
- **Existing Fuse.js Search System** - Core content retrieval engine
- **Next.js API Routes** - Chat endpoint hosting
- **Existing Manifest System** - Interview metadata and content storage

## Performance Considerations

### Data Processing Performance
- **SRT Extraction:** Parallel processing of 726 files using ThreadPoolExecutor
- **Manifest Updates:** Atomic updates with backup/restore capability
- **Memory Management:** Streaming processing for large files to avoid memory issues

### Chat System Performance
- **Search Performance:** Existing Fuse.js handles 726 interviews efficiently
- **Response Caching:** Cache similar queries to reduce API costs and improve speed
- **API Optimization:** Batch similar requests and implement request deduplication

### Scalability Considerations
- **Content Loading:** Lazy loading of large manifest file with compression
- **Search Index:** Pre-built search indices for faster query processing
- **Future Migration:** Architecture designed for easy vector database migration in Phase 2