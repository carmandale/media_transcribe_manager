/**
 * Advanced Search Page for the Scribe Viewer application
 * Provides comprehensive search functionality with filters and advanced options
 */

import { Suspense } from 'react';
import { Metadata } from 'next';
import SearchPageClient from './search-client';
import { Interview } from '@/lib/types';
import { readFile } from 'fs/promises';
import { join } from 'path';

export const metadata: Metadata = {
  title: 'Advanced Search - Scribe Archive',
  description: 'Search across all interviews and transcripts in the Scribe Archive',
};

async function loadManifest(): Promise<Interview[]> {
  try {
    const manifestPath = join(process.cwd(), 'public', 'manifest.json');
    const fileContents = await readFile(manifestPath, 'utf8');
    return JSON.parse(fileContents);
  } catch (error) {
    console.error('Failed to load manifest:', error);
    return [];
  }
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: { [key: string]: string | string[] | undefined };
}) {
  const interviews = await loadManifest();
  
  // Extract search parameters
  const initialQuery = typeof searchParams.q === 'string' ? searchParams.q : '';
  const initialLanguages = typeof searchParams.lang === 'string' 
    ? searchParams.lang.split(',') 
    : Array.isArray(searchParams.lang) 
    ? searchParams.lang 
    : [];
  const initialInterviewees = typeof searchParams.interviewees === 'string'
    ? searchParams.interviewees.split(',')
    : Array.isArray(searchParams.interviewees)
    ? searchParams.interviewees
    : [];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-foreground mb-2">
              Advanced Search
            </h1>
            <p className="text-muted-foreground">
              Search across {interviews.length} interviews and their transcripts
            </p>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Suspense fallback={<SearchPageSkeleton />}>
          <SearchPageClient
            interviews={interviews}
            initialQuery={initialQuery}
            initialLanguages={initialLanguages}
            initialInterviewees={initialInterviewees}
          />
        </Suspense>
      </main>
    </div>
  );
}

function SearchPageSkeleton() {
  return (
    <div className="space-y-8">
      {/* Search form skeleton */}
      <div className="bg-card rounded-lg border border-border p-6">
        <div className="space-y-4">
          <div className="h-12 bg-muted rounded animate-pulse" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="h-10 bg-muted rounded animate-pulse" />
            <div className="h-10 bg-muted rounded animate-pulse" />
            <div className="h-10 bg-muted rounded animate-pulse" />
          </div>
          <div className="flex justify-between">
            <div className="h-10 bg-muted rounded w-24 animate-pulse" />
            <div className="h-10 bg-muted rounded w-32 animate-pulse" />
          </div>
        </div>
      </div>

      {/* Results skeleton */}
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="bg-card rounded-lg border border-border p-6">
            <div className="space-y-4">
              <div className="flex justify-between">
                <div className="h-6 bg-muted rounded w-1/3 animate-pulse" />
                <div className="h-6 bg-muted rounded w-16 animate-pulse" />
              </div>
              <div className="space-y-2">
                <div className="h-4 bg-muted rounded w-full animate-pulse" />
                <div className="h-4 bg-muted rounded w-3/4 animate-pulse" />
              </div>
              <div className="flex justify-between">
                <div className="flex gap-2">
                  <div className="h-6 bg-muted rounded w-12 animate-pulse" />
                  <div className="h-6 bg-muted rounded w-12 animate-pulse" />
                </div>
                <div className="h-8 bg-muted rounded w-24 animate-pulse" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

