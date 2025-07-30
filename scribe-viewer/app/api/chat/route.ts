/**
 * Chat API endpoint for Scribe historical interview research assistant
 * Integrates Fuse.js search with OpenAI GPT-4 for intelligent responses
 */

import { NextRequest, NextResponse } from 'next/server';
import { getSearchEngine } from '@/lib/search';
import { Interview, SearchResult } from '@/lib/types';
import OpenAI from 'openai';

// Rate limiting configuration
const RATE_LIMIT_WINDOW = 60 * 1000; // 1 minute
const RATE_LIMIT_MAX_REQUESTS = 60;
const rateLimitMap = new Map<string, { count: number; resetTime: number }>();

// OpenAI configuration
const openai = new OpenAI({
	apiKey: process.env.OPENAI_API_KEY,
});

// Chat request/response interfaces
interface ChatRequest {
	query: string;
	sessionId?: string;
	language?: 'en' | 'de' | 'he';
	maxResults?: number;
}

interface ChatResponse {
	response: string;
	citations: Citation[];
	sources: SourceSummary[];
	sessionId: string;
	responseTime: number;
	tokenUsage?: {
		prompt: number;
		completion: number;
		total: number;
	};
}

interface Citation {
	interviewId: string;
	interviewee: string;
	text: string;
	timestamp: number;
	confidence: number;
}

interface SourceSummary {
	interviewId: string;
	interviewee: string;
	relevantSegments: number;
	totalMatches: number;
}

class ChatEngine {
	private searchEngine: any;
	private interviews: Interview[] = [];

	constructor() {
		this.loadInterviews();
	}

	private async loadInterviews() {
		try {
			const response = await fetch(`${process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000'}/manifest.min.json`);
			this.interviews = await response.json();
			this.searchEngine = getSearchEngine(this.interviews);
		} catch (error) {
			console.error('Failed to load interviews:', error);
			throw new Error('Failed to initialize chat engine');
		}
	}

	async processQuery(
		query: string, 
		options: { language?: string; maxResults?: number } = {}
	): Promise<{
		response: string;
		citations: Citation[];
		sources: SourceSummary[];
		tokenUsage?: any;
	}> {
		const startTime = Date.now();

		// Step 1: Search for relevant content
		const searchResults = this.searchEngine.search({
			query,
			limit: options.maxResults || 10,
			includeTranscripts: true,
		});

		if (searchResults.length === 0) {
			return {
				response: "I couldn't find any interviews that discuss this topic. Try rephrasing your question or using different keywords.",
				citations: [],
				sources: [],
			};
		}

		// Step 2: Prepare context for OpenAI
		const context = this.prepareContext(searchResults, query);
		
		// Step 3: Generate response using OpenAI GPT-4
		const openaiResponse = await this.generateResponse(query, context, options.language);

		// Step 4: Extract citations and format response
		const citations = this.extractCitations(searchResults);
		const sources = this.generateSourceSummary(searchResults);

		return {
			response: openaiResponse.response,
			citations,
			sources,
			tokenUsage: openaiResponse.tokenUsage,
		};
	}

	private prepareContext(searchResults: SearchResult[], query: string): string {
		const contextParts: string[] = [];
		
		contextParts.push("You are a historical research assistant specialized in interviews with Jews who served in the Nazi military during WWII. This is a sensitive historical topic requiring careful, respectful analysis.");
		contextParts.push("");
		contextParts.push("IMPORTANT INSTRUCTIONS:");
		contextParts.push("- Always maintain historical accuracy and scholarly objectivity");
		contextParts.push("- Be respectful when discussing traumatic experiences");
		contextParts.push("- Include specific quotes when relevant, with clear attribution");
		contextParts.push("- Reference interview segments by interviewee name and approximate timestamp");
		contextParts.push("- If you're uncertain about something, say so clearly");
		contextParts.push("");
		contextParts.push("RELEVANT INTERVIEW CONTENT:");
		contextParts.push("");

		searchResults.slice(0, 8).forEach((result, index) => {
			const interview = result.interview;
			const interviewee = interview.metadata.interviewee;
			const snippet = result.snippet;
			const timestamp = result.timestamp || 0;
			
			contextParts.push(`Interview ${index + 1}: ${interviewee}`);
			if (timestamp) {
				const minutes = Math.floor(timestamp / 60);
				const seconds = Math.floor(timestamp % 60);
				contextParts.push(`Timestamp: ${minutes}:${seconds.toString().padStart(2, '0')}`);
			}
			contextParts.push(`Content: "${snippet}"`);
			contextParts.push("");
		});

		contextParts.push("QUERY: " + query);
		contextParts.push("");
		contextParts.push("Please provide a comprehensive response based on the interview content above. Include specific quotes and references to the interviewees.");

		return contextParts.join('\n');
	}

	private async generateResponse(
		query: string, 
		context: string, 
		language?: string
	): Promise<{ response: string; tokenUsage?: any }> {
		try {
			const completion = await openai.chat.completions.create({
				model: 'gpt-4',
				messages: [
					{
						role: 'system',
						content: context
					},
					{
						role: 'user',
						content: query
					}
				],
				max_tokens: 1000,
				temperature: 0.7,
			});

			const response = completion.choices[0]?.message?.content || 
				"I apologize, but I couldn't generate a response. Please try rephrasing your question.";

			return {
				response,
				tokenUsage: completion.usage ? {
					prompt: completion.usage.prompt_tokens,
					completion: completion.usage.completion_tokens,
					total: completion.usage.total_tokens,
				} : undefined,
			};
		} catch (error) {
			console.error('OpenAI API error:', error);
			throw new Error('Failed to generate response');
		}
	}

	private extractCitations(searchResults: SearchResult[]): Citation[] {
		return searchResults.slice(0, 5).map(result => ({
			interviewId: result.interview.id,
			interviewee: result.interview.metadata.interviewee,
			text: result.snippet,
			timestamp: result.timestamp || 0,
			confidence: 1 - (result.score || 0), // Convert Fuse.js score to confidence
		}));
	}

	private generateSourceSummary(searchResults: SearchResult[]): SourceSummary[] {
		const sourceMap = new Map<string, SourceSummary>();

		searchResults.forEach(result => {
			const id = result.interview.id;
			const existing = sourceMap.get(id);

			if (existing) {
				existing.relevantSegments += 1;
				existing.totalMatches += 1;
			} else {
				sourceMap.set(id, {
					interviewId: id,
					interviewee: result.interview.metadata.interviewee,
					relevantSegments: 1,
					totalMatches: 1,
				});
			}
		});

		return Array.from(sourceMap.values()).slice(0, 5);
	}
}

// Rate limiting function
function checkRateLimit(identifier: string): boolean {
	const now = Date.now();
	const userLimit = rateLimitMap.get(identifier);

	if (!userLimit || now > userLimit.resetTime) {
		rateLimitMap.set(identifier, {
			count: 1,
			resetTime: now + RATE_LIMIT_WINDOW,
		});
		return true;
	}

	if (userLimit.count >= RATE_LIMIT_MAX_REQUESTS) {
		return false;
	}

	userLimit.count += 1;
	return true;
}

// Main API handler
export async function POST(request: NextRequest) {
	const startTime = Date.now();

	try {
		// Parse request body
		const body: ChatRequest = await request.json();
		const { query, sessionId, language, maxResults } = body;

		// Validate request
		if (!query || typeof query !== 'string' || query.trim().length === 0) {
			return NextResponse.json(
				{ error: 'Query is required and must be a non-empty string' },
				{ status: 400 }
			);
		}

		if (query.length > 500) {
			return NextResponse.json(
				{ error: 'Query too long. Maximum 500 characters allowed.' },
				{ status: 400 }
			);
		}

		// Rate limiting
		const clientIp = request.ip || request.headers.get('x-forwarded-for') || 'unknown';
		if (!checkRateLimit(clientIp)) {
			return NextResponse.json(
				{ error: 'Rate limit exceeded. Please try again later.' },
				{ status: 429 }
			);
		}

		// Check OpenAI API key
		if (!process.env.OPENAI_API_KEY) {
			console.error('OPENAI_API_KEY not configured');
			return NextResponse.json(
				{ error: 'Chat service temporarily unavailable' },
				{ status: 503 }
			);
		}

		// Initialize chat engine
		const chatEngine = new ChatEngine();
		
		// Process query
		const result = await chatEngine.processQuery(query, {
			language,
			maxResults,
		});

		// Generate session ID if not provided
		const responseSessionId = sessionId || `sess_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

		// Calculate response time
		const responseTime = Date.now() - startTime;

		// Build response
		const response: ChatResponse = {
			response: result.response,
			citations: result.citations,
			sources: result.sources,
			sessionId: responseSessionId,
			responseTime,
			tokenUsage: result.tokenUsage,
		};

		return NextResponse.json(response);

	} catch (error) {
		console.error('Chat API error:', error);
		
		const responseTime = Date.now() - startTime;
		
		return NextResponse.json(
			{
				error: 'Internal server error',
				message: error instanceof Error ? error.message : 'Unknown error',
				responseTime,
			},
			{ status: 500 }
		);
	}
}

// Health check endpoint
export async function GET() {
	return NextResponse.json({
		status: 'healthy',
		timestamp: new Date().toISOString(),
		features: {
			search: true,
			openai: !!process.env.OPENAI_API_KEY,
			rateLimit: true,
		},
	});
}