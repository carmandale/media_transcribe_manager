/**
 * SearchResults component for displaying search results with highlighting and pagination
 */

import React from 'react';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Calendar, Clock, User, FileText, ExternalLink } from 'lucide-react';
import { SearchResult, PaginationInfo } from '@/lib/types';

interface SearchResultsProps {
  /** Array of search results to display */
  results: SearchResult[];
  /** Pagination information */
  pagination?: PaginationInfo;
  /** Loading state */
  isLoading?: boolean;
  /** Error state */
  error?: string;
  /** Callback for pagination */
  onPageChange?: (page: number) => void;
  /** Show detailed view with more metadata */
  detailed?: boolean;
}

export default function SearchResults({
  results,
  pagination,
  isLoading = false,
  error,
  onPageChange,
  detailed = false,
}: SearchResultsProps) {
  if (isLoading) {
    return <SearchResultsSkeleton />;
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <div className="text-red-500 mb-2">Search Error</div>
        <p className="text-muted-foreground">{error}</p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="text-center py-8">
        <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-semibold mb-2">No results found</h3>
        <p className="text-muted-foreground">
          Try adjusting your search terms or filters
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results header */}
      {pagination && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Showing {((pagination.currentPage - 1) * pagination.resultsPerPage) + 1} to{' '}
            {Math.min(pagination.currentPage * pagination.resultsPerPage, pagination.totalResults)} of{' '}
            {pagination.totalResults} results
          </span>
          <span>
            Page {pagination.currentPage} of {pagination.totalPages}
          </span>
        </div>
      )}

      {/* Results list */}
      <div className="space-y-4">
        {results.map((result, index) => (
          <SearchResultCard
            key={`${result.interview.id}-${index}`}
            result={result}
            detailed={detailed}
          />
        ))}
      </div>

      {/* Pagination */}
      {pagination && pagination.totalPages > 1 && (
        <SearchPagination
          pagination={pagination}
          onPageChange={onPageChange}
        />
      )}
    </div>
  );
}

interface SearchResultCardProps {
  result: SearchResult;
  detailed: boolean;
}

function SearchResultCard({ result, detailed }: SearchResultCardProps) {
  const { interview, score, snippet, context, matchedField, timestamp } = result;
  
  // Format the relevance score as a percentage
  const relevancePercentage = Math.round((1 - score) * 100);
  
  // Format date
  const formattedDate = interview.metadata.date
    ? new Date(interview.metadata.date).toLocaleDateString()
    : 'Date unknown';

  // Available languages
  const languages = interview.transcripts?.map(t => t.language.toUpperCase()) || [];

  // Create link with timestamp if available
  const viewerLink = timestamp 
    ? `/viewer/${interview.id}?t=${Math.floor(timestamp)}`
    : `/viewer/${interview.id}`;

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-6">
        <div className="space-y-4">
          {/* Header with title and relevance */}
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <Link 
                href={viewerLink}
                className="group"
              >
                <h3 className="text-lg font-semibold text-foreground group-hover:text-primary transition-colors">
                  {interview.metadata.interviewee}
                  <ExternalLink className="inline h-4 w-4 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                </h3>
              </Link>
              
              <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  {formattedDate}
                </div>
                
                {timestamp && (
                  <div className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {formatTimestamp(timestamp)}
                  </div>
                )}
                
                <div className="flex items-center gap-1">
                  <User className="h-4 w-4" />
                  {getMatchedFieldLabel(matchedField)}
                </div>
              </div>
            </div>
            
            {detailed && (
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-xs">
                  {relevancePercentage}% match
                </Badge>
              </div>
            )}
          </div>

          {/* Snippet with highlighting */}
          <div className="space-y-2">
            <div 
              className="text-foreground leading-relaxed"
              dangerouslySetInnerHTML={{ __html: snippet }}
            />
            
            {detailed && context !== snippet && (
              <div className="text-sm text-muted-foreground italic">
                {context}
              </div>
            )}
          </div>

          {/* Footer with languages and actions */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {languages.map((lang) => (
                <Badge key={lang} variant="secondary" className="text-xs">
                  {lang}
                </Badge>
              ))}
            </div>
            
            <div className="flex items-center gap-2">
              {timestamp && (
                <Button
                  size="sm"
                  variant="outline"
                  asChild
                >
                  <Link href={viewerLink}>
                    <Clock className="h-4 w-4 mr-1" />
                    Jump to moment
                  </Link>
                </Button>
              )}
              
              <Button
                size="sm"
                variant="ghost"
                asChild
              >
                <Link href={`/viewer/${interview.id}`}>
                  View full interview
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface SearchPaginationProps {
  pagination: PaginationInfo;
  onPageChange?: (page: number) => void;
}

function SearchPagination({ pagination, onPageChange }: SearchPaginationProps) {
  const { currentPage, totalPages } = pagination;
  
  // Calculate page range to show
  const getPageRange = () => {
    const delta = 2; // Number of pages to show on each side of current page
    const range = [];
    const rangeWithDots = [];

    for (let i = Math.max(2, currentPage - delta); 
         i <= Math.min(totalPages - 1, currentPage + delta); 
         i++) {
      range.push(i);
    }

    if (currentPage - delta > 2) {
      rangeWithDots.push(1, '...');
    } else {
      rangeWithDots.push(1);
    }

    rangeWithDots.push(...range);

    if (currentPage + delta < totalPages - 1) {
      rangeWithDots.push('...', totalPages);
    } else if (totalPages > 1) {
      rangeWithDots.push(totalPages);
    }

    return rangeWithDots;
  };

  const pageRange = getPageRange();

  return (
    <div className="flex items-center justify-center space-x-2 py-4">
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange?.(currentPage - 1)}
        disabled={currentPage <= 1}
      >
        Previous
      </Button>
      
      {pageRange.map((page, index) => (
        <React.Fragment key={index}>
          {page === '...' ? (
            <span className="px-2 text-muted-foreground">...</span>
          ) : (
            <Button
              variant={page === currentPage ? "default" : "outline"}
              size="sm"
              onClick={() => onPageChange?.(page as number)}
            >
              {page}
            </Button>
          )}
        </React.Fragment>
      ))}
      
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange?.(currentPage + 1)}
        disabled={currentPage >= totalPages}
      >
        Next
      </Button>
    </div>
  );
}

function SearchResultsSkeleton() {
  return (
    <div className="space-y-4">
      {[...Array(5)].map((_, i) => (
        <Card key={i}>
          <CardContent className="p-6">
            <div className="space-y-4">
              <div className="flex items-start justify-between">
                <div className="space-y-2 flex-1">
                  <div className="h-6 bg-muted rounded w-1/3 animate-pulse" />
                  <div className="h-4 bg-muted rounded w-1/2 animate-pulse" />
                </div>
                <div className="h-6 bg-muted rounded w-16 animate-pulse" />
              </div>
              <div className="space-y-2">
                <div className="h-4 bg-muted rounded w-full animate-pulse" />
                <div className="h-4 bg-muted rounded w-3/4 animate-pulse" />
              </div>
              <div className="flex items-center justify-between">
                <div className="flex gap-2">
                  <div className="h-6 bg-muted rounded w-12 animate-pulse" />
                  <div className="h-6 bg-muted rounded w-12 animate-pulse" />
                </div>
                <div className="h-8 bg-muted rounded w-24 animate-pulse" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// Utility functions

function formatTimestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

function getMatchedFieldLabel(field: string): string {
  switch (field) {
    case 'interviewee':
      return 'Name';
    case 'summary':
      return 'Summary';
    case 'transcript':
      return 'Transcript';
    default:
      return 'Content';
  }
}

