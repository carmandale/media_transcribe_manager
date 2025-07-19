/**
 * Client-side search component with advanced filtering and real-time search
 */

'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { 
  Search, 
  Filter, 
  X, 
  ChevronDown, 
  ChevronUp, 
  Calendar,
  Users,
  Languages,
  Settings,
  History,
  Bookmark
} from 'lucide-react';
import { Interview, SearchResult, SearchOptions, SearchFilters } from '@/lib/types';
import { getSearchEngine } from '@/lib/search';
import SearchResults from '@/components/SearchResults';

interface SearchPageClientProps {
  interviews: Interview[];
  initialQuery?: string;
  initialLanguages?: string[];
  initialInterviewees?: string[];
}

const RESULTS_PER_PAGE = 20;

export default function SearchPageClient({
  interviews,
  initialQuery = '',
  initialLanguages = [],
  initialInterviewees = [],
}: SearchPageClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // Search state
  const [query, setQuery] = useState(initialQuery);
  const [filters, setFilters] = useState<SearchFilters>({
    languages: initialLanguages,
    interviewees: initialInterviewees,
    dateRange: undefined,
    sortBy: 'relevance',
    sortDirection: 'desc',
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [searchHistory, setSearchHistory] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  
  // UI state
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [showSearchHistory, setShowSearchHistory] = useState(false);

  // Initialize search engine
  const searchEngine = useMemo(() => {
    if (interviews.length === 0) return null;
    return getSearchEngine(interviews);
  }, [interviews]);

  // Get filter options from data
  const filterOptions = useMemo(() => {
    if (!searchEngine) return { languages: [], interviewees: [], dateRange: null };
    return searchEngine.getFilterOptions();
  }, [searchEngine]);

  // Perform search
  const performSearch = useCallback(async (
    searchQuery: string,
    searchFilters: SearchFilters,
    page: number = 1
  ) => {
    if (!searchEngine) return;

    setIsSearching(true);
    
    try {
      const searchOptions: SearchOptions = {
        query: searchQuery,
        languages: searchFilters.languages,
        interviewees: searchFilters.interviewees,
        dateRange: searchFilters.dateRange,
        limit: RESULTS_PER_PAGE * 3, // Get more results for better pagination
        includeTranscripts: true,
      };

      const results = searchEngine.search(searchOptions);
      
      // Apply sorting
      const sortedResults = sortResults(results, searchFilters.sortBy, searchFilters.sortDirection);
      
      // Paginate results
      const startIndex = (page - 1) * RESULTS_PER_PAGE;
      const endIndex = startIndex + RESULTS_PER_PAGE;
      const paginatedResults = sortedResults.slice(startIndex, endIndex);
      
      setSearchResults(paginatedResults);
      setTotalResults(sortedResults.length);
      
      // Update search history
      if (searchQuery.trim() && !searchHistory.includes(searchQuery)) {
        setSearchHistory(prev => [searchQuery, ...prev.slice(0, 9)]); // Keep last 10 searches
      }
      
    } catch (error) {
      console.error('Search error:', error);
      setSearchResults([]);
      setTotalResults(0);
    } finally {
      setIsSearching(false);
    }
  }, [searchEngine, searchHistory]);

  // Sort results
  const sortResults = (results: SearchResult[], sortBy: string, direction: string): SearchResult[] => {
    const sorted = [...results];
    
    sorted.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'relevance':
          comparison = a.score - b.score; // Lower score = more relevant
          break;
        case 'date':
          const dateA = new Date(a.interview.metadata.date || '1900-01-01');
          const dateB = new Date(b.interview.metadata.date || '1900-01-01');
          comparison = dateA.getTime() - dateB.getTime();
          break;
        case 'interviewee':
          comparison = a.interview.metadata.interviewee.localeCompare(b.interview.metadata.interviewee);
          break;
        default:
          comparison = 0;
      }
      
      return direction === 'desc' ? -comparison : comparison;
    });
    
    return sorted;
  };

  // Update URL with search parameters
  const updateURL = useCallback((searchQuery: string, searchFilters: SearchFilters) => {
    const params = new URLSearchParams();
    
    if (searchQuery) params.set('q', searchQuery);
    if (searchFilters.languages.length > 0) params.set('lang', searchFilters.languages.join(','));
    if (searchFilters.interviewees.length > 0) params.set('interviewees', searchFilters.interviewees.join(','));
    if (searchFilters.dateRange) {
      params.set('dateStart', searchFilters.dateRange.start);
      params.set('dateEnd', searchFilters.dateRange.end);
    }
    
    const newURL = params.toString() ? `/search?${params.toString()}` : '/search';
    router.replace(newURL, { scroll: false });
  }, [router]);

  // Handle search input change with debouncing
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (query !== initialQuery || currentPage !== 1) {
        performSearch(query, filters, currentPage);
        updateURL(query, filters);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [query, filters, currentPage, performSearch, updateURL, initialQuery]);

  // Get search suggestions
  useEffect(() => {
    if (query.length >= 2 && searchEngine) {
      const newSuggestions = searchEngine.getSuggestions(query, 5);
      setSuggestions(newSuggestions);
    } else {
      setSuggestions([]);
    }
  }, [query, searchEngine]);

  // Initial search
  useEffect(() => {
    if (initialQuery || initialLanguages.length > 0 || initialInterviewees.length > 0) {
      performSearch(initialQuery, filters, 1);
    }
  }, []);

  // Handle filter changes
  const handleFilterChange = (key: keyof SearchFilters, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setCurrentPage(1);
  };

  // Handle page change
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  // Clear all filters
  const clearFilters = () => {
    setFilters({
      languages: [],
      interviewees: [],
      dateRange: undefined,
      sortBy: 'relevance',
      sortDirection: 'desc',
    });
    setCurrentPage(1);
  };

  // Pagination info
  const paginationInfo = {
    currentPage,
    totalPages: Math.ceil(totalResults / RESULTS_PER_PAGE),
    totalResults,
    resultsPerPage: RESULTS_PER_PAGE,
  };

  return (
    <div className="space-y-8">
      {/* Search Form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            Search Interviews
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Main search input */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-5 w-5" />
            <Input
              type="text"
              placeholder="Search across all interviews and transcripts..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-10 pr-4 py-3 text-lg"
            />
            {query && (
              <Button
                variant="ghost"
                size="sm"
                className="absolute right-2 top-1/2 transform -translate-y-1/2"
                onClick={() => setQuery('')}
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>

          {/* Search suggestions */}
          {suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              <span className="text-sm text-muted-foreground">Suggestions:</span>
              {suggestions.map((suggestion, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  onClick={() => setQuery(suggestion)}
                  className="text-xs"
                >
                  {suggestion}
                </Button>
              ))}
            </div>
          )}

          {/* Quick filters */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Languages filter */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Languages className="h-4 w-4" />
                Languages
              </Label>
              <div className="flex flex-wrap gap-1">
                {filterOptions.languages.map((lang) => (
                  <Badge
                    key={lang}
                    variant={filters.languages.includes(lang) ? "default" : "outline"}
                    className="cursor-pointer text-xs"
                    onClick={() => {
                      const newLanguages = filters.languages.includes(lang)
                        ? filters.languages.filter(l => l !== lang)
                        : [...filters.languages, lang];
                      handleFilterChange('languages', newLanguages);
                    }}
                  >
                    {lang.toUpperCase()}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Sort options */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Settings className="h-4 w-4" />
                Sort by
              </Label>
              <div className="flex gap-2">
                {[
                  { key: 'relevance', label: 'Relevance' },
                  { key: 'date', label: 'Date' },
                  { key: 'interviewee', label: 'Name' },
                ].map((option) => (
                  <Button
                    key={option.key}
                    variant={filters.sortBy === option.key ? "default" : "outline"}
                    size="sm"
                    onClick={() => handleFilterChange('sortBy', option.key)}
                    className="text-xs"
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="space-y-2">
              <Label>Actions</Label>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                >
                  <Filter className="h-4 w-4 mr-1" />
                  Advanced
                  {showAdvancedFilters ? <ChevronUp className="h-4 w-4 ml-1" /> : <ChevronDown className="h-4 w-4 ml-1" />}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={clearFilters}
                  disabled={filters.languages.length === 0 && filters.interviewees.length === 0 && !filters.dateRange}
                >
                  Clear filters
                </Button>
              </div>
            </div>
          </div>

          {/* Advanced filters */}
          <Collapsible open={showAdvancedFilters} onOpenChange={setShowAdvancedFilters}>
            <CollapsibleContent className="space-y-4">
              <Separator />
              
              {/* Date range filter */}
              {filterOptions.dateRange && (
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    Date Range
                  </Label>
                  <div className="grid grid-cols-2 gap-2">
                    <Input
                      type="date"
                      placeholder="Start date"
                      min={filterOptions.dateRange.min}
                      max={filterOptions.dateRange.max}
                      value={filters.dateRange?.start || ''}
                      onChange={(e) => {
                        const newDateRange = {
                          start: e.target.value,
                          end: filters.dateRange?.end || filterOptions.dateRange!.max,
                        };
                        handleFilterChange('dateRange', e.target.value ? newDateRange : undefined);
                      }}
                    />
                    <Input
                      type="date"
                      placeholder="End date"
                      min={filters.dateRange?.start || filterOptions.dateRange.min}
                      max={filterOptions.dateRange.max}
                      value={filters.dateRange?.end || ''}
                      onChange={(e) => {
                        const newDateRange = {
                          start: filters.dateRange?.start || filterOptions.dateRange!.min,
                          end: e.target.value,
                        };
                        handleFilterChange('dateRange', e.target.value ? newDateRange : undefined);
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Interviewees filter */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  Interviewees
                </Label>
                <div className="max-h-32 overflow-y-auto space-y-1">
                  {filterOptions.interviewees.slice(0, 20).map((interviewee) => (
                    <div key={interviewee} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id={`interviewee-${interviewee}`}
                        checked={filters.interviewees.includes(interviewee)}
                        onChange={(e) => {
                          const newInterviewees = e.target.checked
                            ? [...filters.interviewees, interviewee]
                            : filters.interviewees.filter(i => i !== interviewee);
                          handleFilterChange('interviewees', newInterviewees);
                        }}
                        className="rounded"
                      />
                      <Label
                        htmlFor={`interviewee-${interviewee}`}
                        className="text-sm cursor-pointer"
                      >
                        {interviewee}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* Search history */}
          {searchHistory.length > 0 && (
            <Collapsible open={showSearchHistory} onOpenChange={setShowSearchHistory}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm" className="w-full justify-start">
                  <History className="h-4 w-4 mr-2" />
                  Recent Searches
                  {showSearchHistory ? <ChevronUp className="h-4 w-4 ml-auto" /> : <ChevronDown className="h-4 w-4 ml-auto" />}
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="flex flex-wrap gap-2 mt-2">
                  {searchHistory.map((historyQuery, index) => (
                    <Button
                      key={index}
                      variant="outline"
                      size="sm"
                      onClick={() => setQuery(historyQuery)}
                      className="text-xs"
                    >
                      {historyQuery}
                    </Button>
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}
        </CardContent>
      </Card>

      {/* Search Results */}
      <SearchResults
        results={searchResults}
        pagination={paginationInfo}
        isLoading={isSearching}
        onPageChange={handlePageChange}
        detailed={true}
      />
    </div>
  );
}

