/**
 * Advanced search engine for the Scribe Viewer application
 * Uses Fuse.js for fuzzy search across interview data
 */

import Fuse from 'fuse.js';
import { Interview, SearchResult, SearchOptions } from './types';

// Fuse.js configuration optimized for interview search
const FUSE_OPTIONS: Fuse.IFuseOptions<Interview> = {
  // Fields to search with different weights
  keys: [
    {
      name: 'metadata.interviewee',
      weight: 0.4, // High weight for interviewee names
    },
    {
      name: 'metadata.summary',
      weight: 0.3, // Medium weight for summaries
    },
    {
      name: 'transcripts.text',
      weight: 0.3, // Medium weight for transcript content
    },
  ],
  // Search configuration
  threshold: 0.4, // 0.0 = perfect match, 1.0 = match anything
  distance: 100, // Maximum distance for fuzzy matching
  minMatchCharLength: 2, // Minimum character length for matching
  includeScore: true, // Include relevance scores
  includeMatches: true, // Include match information for highlighting
  ignoreLocation: true, // Don't consider location of match in string
  findAllMatches: true, // Find all matches, not just the first
  useExtendedSearch: true, // Enable extended search syntax
};

// Default search options
const DEFAULT_SEARCH_OPTIONS: Required<SearchOptions> = {
  query: '',
  languages: [],
  dateRange: undefined as any,
  interviewees: [],
  limit: 50,
  includeTranscripts: true,
};

export class SearchEngine {
  private fuse: Fuse<Interview>;
  private interviews: Interview[];

  constructor(interviews: Interview[]) {
    this.interviews = interviews;
    this.fuse = new Fuse(interviews, FUSE_OPTIONS);
  }

  /**
   * Perform a search across all interviews
   */
  search(query: string): SearchResult[];
  search(options: SearchOptions): SearchResult[];
  search(query: string, options: Partial<SearchOptions>): SearchResult[];
  search(queryOrOptions: string | SearchOptions, options?: Partial<SearchOptions>): SearchResult[] {
    let opts: Required<SearchOptions>;
    
    if (typeof queryOrOptions === 'string') {
      // Legacy API: search(query, options)
      opts = { 
        ...DEFAULT_SEARCH_OPTIONS, 
        query: queryOrOptions,
        ...options 
      };
    } else {
      // New API: search(options)
      opts = { ...DEFAULT_SEARCH_OPTIONS, ...queryOrOptions };
    }
    
    if (!opts.query.trim()) {
      return this.getAllInterviews(opts);
    }

    // Perform the search
    const fuseResults = this.fuse.search(opts.query, { limit: opts.limit * 2 }); // Get more results for filtering

    // Convert Fuse results to SearchResult format
    let searchResults = fuseResults.map(result => this.convertFuseResult(result, opts.query));

    // Apply additional filters
    searchResults = this.applyFilters(searchResults, opts);

    // Limit results
    return searchResults.slice(0, opts.limit);
  }

  /**
   * Get all interviews when no search query is provided
   */
  private getAllInterviews(options: Required<SearchOptions>): SearchResult[] {
    let results = this.interviews.map(interview => ({
      interview,
      score: 0,
      snippet: this.generateSnippet(interview.metadata?.summary || 'No summary available', ''),
      context: interview.metadata?.summary || 'No summary available',
      matchedField: 'summary',
    }));

    // Apply filters
    results = this.applyFilters(results, options);

    return results.slice(0, options.limit);
  }

  /**
   * Convert Fuse.js result to SearchResult format
   */
  private convertFuseResult(fuseResult: Fuse.FuseResult<Interview>, query: string): SearchResult {
    const { item: interview, score = 1, matches = [] } = fuseResult;
    
    // Find the best match for snippet generation
    const bestMatch = matches.reduce((best, match) => {
      if (!best || (match.score && best.score && match.score < best.score)) {
        return match;
      }
      return best;
    }, matches[0]);

    // Generate snippet and context
    const { snippet, context, matchedField, timestamp } = this.generateMatchInfo(
      interview,
      bestMatch,
      query
    );

    return {
      interview,
      score,
      snippet,
      context,
      matchedField,
      timestamp,
    };
  }

  /**
   * Generate snippet and context information from match
   */
  private generateMatchInfo(
    interview: Interview,
    match: Fuse.FuseResultMatch | undefined,
    query: string
  ): {
    snippet: string;
    context: string;
    matchedField: string;
    timestamp?: number;
  } {
    if (!match) {
      return {
        snippet: interview.metadata?.summary || 'No summary available',
        context: interview.metadata?.summary || 'No summary available',
        matchedField: 'summary',
      };
    }

    const key = match.key as string;
    const value = match.value || '';
    
    // Handle different field types
    if (key === 'metadata.interviewee') {
      return {
        snippet: this.highlightText(value, query),
        context: `Interview with ${value}`,
        matchedField: 'interviewee',
      };
    }
    
    if (key === 'metadata.summary') {
      return {
        snippet: this.generateSnippet(value, query),
        context: value,
        matchedField: 'summary',
      };
    }
    
    if (key === 'transcripts.text') {
      const snippet = this.generateSnippet(value, query);
      const timestamp = this.findTimestampForText(interview, snippet, query);
      
      return {
        snippet,
        context: `From transcript: ${snippet}`,
        matchedField: 'transcript',
        timestamp,
      };
    }

    return {
      snippet: this.generateSnippet(value, query),
      context: value,
      matchedField: 'unknown',
    };
  }

  /**
   * Generate a contextual snippet around the search term
   */
  private generateSnippet(text: string, query: string, maxLength: number = 200): string {
    if (!query || !text) {
      return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    const queryLower = query.toLowerCase();
    const textLower = text.toLowerCase();
    const queryIndex = textLower.indexOf(queryLower);

    if (queryIndex === -1) {
      // If exact match not found, return beginning of text
      return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    // Calculate snippet boundaries
    const snippetStart = Math.max(0, queryIndex - Math.floor((maxLength - query.length) / 2));
    const snippetEnd = Math.min(text.length, snippetStart + maxLength);

    let snippet = text.substring(snippetStart, snippetEnd);
    
    // Add ellipsis if needed
    if (snippetStart > 0) snippet = '...' + snippet;
    if (snippetEnd < text.length) snippet = snippet + '...';

    return this.highlightText(snippet, query);
  }

  /**
   * Highlight search terms in text
   */
  private highlightText(text: string, query: string): string {
    if (!query) return text;
    
    const regex = new RegExp(`(${this.escapeRegExp(query)})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
  }

  /**
   * Escape special regex characters
   */
  private escapeRegExp(string: string): string {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * Find timestamp for text match in transcript
   */
  private findTimestampForText(interview: Interview, snippet: string, query: string): number | undefined {
    if (!interview.transcripts || interview.transcripts.length === 0) {
      return undefined;
    }

    // Search through all transcripts
    for (const transcript of interview.transcripts) {
      if (!transcript.cues) continue;

      // Find the cue that contains the query
      for (const cue of transcript.cues) {
        if (cue.text.toLowerCase().includes(query.toLowerCase())) {
          return cue.start;
        }
      }
    }

    return undefined;
  }

  /**
   * Apply additional filters to search results
   */
  private applyFilters(results: SearchResult[], options: Required<SearchOptions>): SearchResult[] {
    let filtered = results;

    // Filter by languages
    if (options.languages.length > 0) {
      filtered = filtered.filter(result => {
        const availableLanguages = result.interview.transcripts?.map(t => t.language) || [];
        return options.languages.some(lang => availableLanguages.includes(lang));
      });
    }

    // Filter by date range
    if (options.dateRange) {
      const { start, end } = options.dateRange;
      filtered = filtered.filter(result => {
        const interviewDate = result.interview.metadata?.date;
        if (!interviewDate) return false;
        return interviewDate >= start && interviewDate <= end;
      });
    }

    // Filter by interviewees
    if (options.interviewees.length > 0) {
      filtered = filtered.filter(result => {
        const interviewee = result.interview.metadata?.interviewee?.toLowerCase();
        if (!interviewee) return false;
        return options.interviewees.some(name => 
          interviewee.includes(name.toLowerCase())
        );
      });
    }

    return filtered;
  }

  /**
   * Get search suggestions based on partial query
   */
  getSuggestions(partialQuery: string, limit: number = 5): string[] {
    if (!partialQuery || partialQuery.length < 2) {
      return [];
    }

    const suggestions = new Set<string>();
    
    // Get suggestions from interviewee names
    this.interviews.forEach(interview => {
      const name = interview.metadata.interviewee;
      if (name.toLowerCase().includes(partialQuery.toLowerCase())) {
        suggestions.add(name);
      }
    });

    // Get suggestions from summaries (extract key phrases)
    this.interviews.forEach(interview => {
      const summary = interview.metadata.summary;
      if (summary) {
        const words = summary.split(/\s+/);
        words.forEach(word => {
          if (word.length > 3 && word.toLowerCase().includes(partialQuery.toLowerCase())) {
            suggestions.add(word);
          }
        });
      }
    });

    return Array.from(suggestions).slice(0, limit);
  }

  /**
   * Get available filter options from the dataset
   */
  getFilterOptions(): {
    languages: string[];
    interviewees: string[];
    dateRange: { min: string; max: string } | null;
  } {
    const languages = new Set<string>();
    const interviewees = new Set<string>();
    const dates: string[] = [];

    this.interviews.forEach(interview => {
      // Collect languages
      interview.transcripts?.forEach(transcript => {
        languages.add(transcript.language);
      });

      // Collect interviewees
      interviewees.add(interview.metadata.interviewee);

      // Collect dates
      if (interview.metadata.date) {
        dates.push(interview.metadata.date);
      }
    });

    // Calculate date range
    const sortedDates = dates.sort();
    const dateRange = sortedDates.length > 0 
      ? { min: sortedDates[0], max: sortedDates[sortedDates.length - 1] }
      : null;

    return {
      languages: Array.from(languages).sort(),
      interviewees: Array.from(interviewees).sort(),
      dateRange,
    };
  }

  /**
   * Update the search index with new interviews
   */
  updateIndex(interviews: Interview[]): void {
    this.interviews = interviews;
    this.fuse = new Fuse(interviews, FUSE_OPTIONS);
  }
}

// Singleton instance for the application
let searchEngineInstance: SearchEngine | null = null;

/**
 * Get or create the search engine instance
 */
export function getSearchEngine(interviews?: Interview[]): SearchEngine {
  if (!searchEngineInstance && interviews) {
    searchEngineInstance = new SearchEngine(interviews);
  } else if (interviews && searchEngineInstance) {
    searchEngineInstance.updateIndex(interviews);
  }
  
  if (!searchEngineInstance) {
    throw new Error('Search engine not initialized. Provide interviews data first.');
  }
  
  return searchEngineInstance;
}

/**
 * Utility function to perform a quick search
 */
export function searchInterviews(
  interviews: Interview[],
  query: string,
  options?: Partial<SearchOptions>
): SearchResult[] {
  const engine = getSearchEngine(interviews);
  return engine.search({ query, ...options });
}
