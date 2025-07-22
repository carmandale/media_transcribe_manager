"use client"

import { useState, useEffect, useMemo, useCallback } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Search, Filter, ExternalLink, Sparkles, ChevronLeft, ChevronRight } from "lucide-react"
import { Interview, SearchResult } from "@/lib/types"
import { getSearchEngine } from "@/lib/search"
import InterviewCard from "@/components/InterviewCard"

interface GalleryClientProps {
  interviews: Interview[]
}

const ITEMS_PER_PAGE = 24 // Show 24 items per page (divisible by 1, 2, and 3 for responsive grid)

export default function GalleryClient({ interviews }: GalleryClientProps) {
  const router = useRouter()
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>([])
  const [sortBy, setSortBy] = useState("date")
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [searchEngine, setSearchEngine] = useState<ReturnType<typeof getSearchEngine> | null>(null)
  const [currentPage, setCurrentPage] = useState(1)

  // Lazy initialize search engine only when user starts searching
  useEffect(() => {
    if (searchQuery && !searchEngine && interviews.length > 0) {
      setSearchEngine(getSearchEngine(interviews));
    }
  }, [searchQuery, searchEngine, interviews]);

  // Get available languages
  const availableLanguages = useMemo(() => {
    const languages = new Set<string>();
    interviews.forEach(interview => {
      interview.transcripts?.forEach(transcript => {
        languages.add(transcript.language);
      });
    });
    return Array.from(languages).sort();
  }, [interviews]);

  // Perform search with advanced engine
  useEffect(() => {
    if (!searchEngine) return;

    setIsSearching(true);
    
    const timeoutId = setTimeout(() => {
      try {
        const results = searchEngine.search({
          query: searchQuery,
          languages: selectedLanguages,
          limit: 50,
          includeTranscripts: true,
        });
        
        // Sort results
        const sortedResults = [...results].sort((a, b) => {
          switch (sortBy) {
            case 'date':
              const dateA = new Date(a.interview.metadata.date || '1900-01-01');
              const dateB = new Date(b.interview.metadata.date || '1900-01-01');
              return dateB.getTime() - dateA.getTime(); // Newest first
            case 'name':
              return a.interview.metadata.interviewee.localeCompare(b.interview.metadata.interviewee);
            case 'relevance':
            default:
              return a.score - b.score; // Lower score = more relevant
          }
        });
        
        setSearchResults(sortedResults);
      } catch (error) {
        console.error('Search error:', error);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300); // Debounce search

    return () => clearTimeout(timeoutId);
  }, [searchQuery, selectedLanguages, sortBy, searchEngine]);

  // Get interviews to display with pagination
  const allInterviews = searchQuery || selectedLanguages.length > 0 
    ? searchResults.map(result => result.interview)
    : interviews;
  
  const totalPages = Math.ceil(allInterviews.length / ITEMS_PER_PAGE);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = startIndex + ITEMS_PER_PAGE;
  const displayInterviews = allInterviews.slice(startIndex, endIndex);

  // Reset to page 1 when search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, selectedLanguages, sortBy]);

  // Handle language filter toggle
  const toggleLanguage = (language: string) => {
    setSelectedLanguages(prev => 
      prev.includes(language)
        ? prev.filter(l => l !== language)
        : [...prev, language]
    );
  };

  // Clear all filters
  const clearFilters = () => {
    setSearchQuery("");
    setSelectedLanguages([]);
    setSortBy("date");
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-foreground">Scribe Archive</h1>
            <div className="text-sm text-muted-foreground">{interviews.length} interviews available</div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search and Filters */}
        <div className="mb-8 space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-5 w-5" />
            <Input
              type="text"
              placeholder="Search across all interviews and transcripts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-3 text-lg"
            />
            {isSearching && (
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                <div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full"></div>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-4">
            {/* Language filters */}
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Languages:</span>
              {availableLanguages.map((language) => (
                <Badge
                  key={language}
                  variant={selectedLanguages.includes(language) ? "default" : "outline"}
                  className="cursor-pointer text-xs"
                  onClick={() => toggleLanguage(language)}
                >
                  {language.toUpperCase()}
                </Badge>
              ))}
            </div>

            {/* Sort options */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Sort:</span>
              {[
                { key: 'date', label: 'Date' },
                { key: 'name', label: 'Name' },
                { key: 'relevance', label: 'Relevance' },
              ].map((option) => (
                <Button
                  key={option.key}
                  variant={sortBy === option.key ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSortBy(option.key)}
                  className="text-xs"
                >
                  {option.label}
                </Button>
              ))}
            </div>

            {/* Advanced search link */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push(`/search${searchQuery ? `?q=${encodeURIComponent(searchQuery)}` : ''}`)}
              className="ml-auto"
            >
              <Sparkles className="h-4 w-4 mr-1" />
              Advanced Search
              <ExternalLink className="h-4 w-4 ml-1" />
            </Button>
          </div>

          {/* Results info and clear filters */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              {searchQuery || selectedLanguages.length > 0 ? (
                <>
                  Showing {startIndex + 1}-{Math.min(endIndex, allInterviews.length)} of {allInterviews.length} results
                  {searchQuery && (
                    <span className="ml-2">
                      for "<strong>{searchQuery}</strong>"
                    </span>
                  )}
                </>
              ) : (
                `Showing ${startIndex + 1}-${Math.min(endIndex, allInterviews.length)} of ${allInterviews.length} interviews`
              )}
            </div>
            
            {(searchQuery || selectedLanguages.length > 0) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="text-xs"
              >
                Clear filters
              </Button>
            )}
          </div>
        </div>

        {/* Interview Grid */}
        {displayInterviews.length > 0 ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {displayInterviews.map((interview) => (
                <InterviewCard key={interview.id} interview={interview} />
              ))}
            </div>
            
            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                
                <div className="flex items-center gap-1">
                  {/* Show first page */}
                  {currentPage > 3 && (
                    <>
                      <Button
                        variant={currentPage === 1 ? "default" : "outline"}
                        size="sm"
                        onClick={() => setCurrentPage(1)}
                        className="w-10"
                      >
                        1
                      </Button>
                      {currentPage > 4 && <span className="px-1">...</span>}
                    </>
                  )}
                  
                  {/* Show pages around current */}
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    const page = currentPage > 3 ? currentPage - 2 + i : i + 1;
                    if (page < 1 || page > totalPages) return null;
                    if (page === 1 && currentPage > 3) return null;
                    if (page === totalPages && currentPage < totalPages - 2) return null;
                    
                    return (
                      <Button
                        key={page}
                        variant={currentPage === page ? "default" : "outline"}
                        size="sm"
                        onClick={() => setCurrentPage(page)}
                        className="w-10"
                      >
                        {page}
                      </Button>
                    );
                  })}
                  
                  {/* Show last page */}
                  {currentPage < totalPages - 2 && (
                    <>
                      {currentPage < totalPages - 3 && <span className="px-1">...</span>}
                      <Button
                        variant={currentPage === totalPages ? "default" : "outline"}
                        size="sm"
                        onClick={() => setCurrentPage(totalPages)}
                        className="w-10"
                      >
                        {totalPages}
                      </Button>
                    </>
                  )}
                </div>
                
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-12">
            <Search className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No interviews found</h3>
            <p className="text-muted-foreground mb-4">
              {searchQuery || selectedLanguages.length > 0
                ? "Try adjusting your search terms or filters"
                : "No interviews are available in the archive"
              }
            </p>
            {(searchQuery || selectedLanguages.length > 0) && (
              <Button onClick={clearFilters} variant="outline">
                Clear all filters
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
