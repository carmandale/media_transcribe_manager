/**
 * Chat page for Scribe historical research assistant
 * Connects to /api/chat and displays responses with citations
 */

'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';
import { Loader2, Send } from 'lucide-react';

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

interface ChatResponse {
  response: string;
  citations: Citation[];
  sources: SourceSummary[];
  sessionId: string;
  responseTime: number;
}

export default function ChatPage() {
  const [query, setQuery] = useState('');
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [language, setLanguage] = useState<'en' | 'de' | 'he'>('en');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string>('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [sources, setSources] = useState<SourceSummary[]>([]);

  const ask = async () => {
    setIsLoading(true);
    setError(null);
    setAnswer('');
    setCitations([]);
    setSources([]);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, sessionId, language }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || data.message || 'Request failed');
      }

      const data: ChatResponse = await res.json();
      setAnswer(data.response);
      setCitations(data.citations || []);
      setSources(data.sources || []);
      setSessionId(data.sessionId);
    } catch (e: any) {
      setError(e.message || 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Historical Research Assistant</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Ask about interviews (e.g., Eastern Front, training, identity)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  ask();
                }
              }}
            />
            <select
              className="border rounded px-2"
              value={language}
              onChange={(e) => setLanguage(e.target.value as 'en' | 'de' | 'he')}
              aria-label="Language"
            >
              <option value="en">EN</option>
              <option value="de">DE</option>
              <option value="he">HE</option>
            </select>
            <Button onClick={ask} disabled={isLoading || query.trim().length === 0}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Asking...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  Ask
                </>
              )}
            </Button>
          </div>

          {error && (
            <div className="text-sm text-red-600">{error}</div>
          )}

          {answer && (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Answer</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="prose max-w-none whitespace-pre-wrap">{answer}</div>
                </CardContent>
              </Card>

              {citations.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Citations</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {citations.map((c, idx) => (
                      <div key={idx} className="p-3 border rounded">
                        <div className="flex items-center justify-between">
                          <div className="font-medium">{c.interviewee}</div>
                          <Badge variant="outline">{formatTime(c.timestamp)}</Badge>
                        </div>
                        <div className="text-sm text-muted-foreground mt-1" dangerouslySetInnerHTML={{ __html: c.text }} />
                        <div className="mt-2 text-xs">
                          <Link href={`/viewer/${c.interviewId}`}>Open interview</Link>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {sources.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Sources Summary</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {sources.map((s, idx) => (
                      <div key={idx} className="flex items-center justify-between p-2 border rounded">
                        <div className="font-medium">{s.interviewee}</div>
                        <div className="text-sm text-muted-foreground">
                          {s.relevantSegments} relevant / {s.totalMatches} matches
                        </div>
                        <Link href={`/viewer/${s.interviewId}`} className="text-sm underline">
                          View
                        </Link>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
