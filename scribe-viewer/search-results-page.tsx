"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Search, ArrowLeft, Play, Clock } from "lucide-react"

const mockSearchResults = [
  {
    interviewId: "d6cc9262-5ba2-410c-a707-d981a7459105",
    interviewee: "Sarah Cohen",
    date: "1995-04-12",
    matches: [
      {
        timestamp: "00:23:45",
        language: "EN",
        context:
          "...we had to leave Berlin in the middle of the night. The situation was becoming too dangerous for Jewish families...",
        highlightedText: "Berlin",
      },
      {
        timestamp: "01:12:30",
        language: "EN",
        context: "...my father worked in a small shop in Berlin before the war. He was a tailor and very skilled...",
        highlightedText: "Berlin",
      },
    ],
  },
  {
    interviewId: "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
    interviewee: "David Müller",
    date: "1998-09-23",
    matches: [
      {
        timestamp: "00:45:12",
        language: "DE",
        context: "...das Leben in Ost-Berlin war sehr anders. Wir konnten nicht frei reisen oder sprechen...",
        highlightedText: "Berlin",
      },
      {
        timestamp: "02:01:45",
        language: "EN",
        context: "...when the wall came down, Berlin changed completely. It was like two cities becoming one again...",
        highlightedText: "Berlin",
      },
    ],
  },
]

export default function SearchResultsPage() {
  const [searchQuery, setSearchQuery] = useState("Berlin")
  const totalMatches = mockSearchResults.reduce((sum, result) => sum + result.matches.length, 0)

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Gallery
            </Button>
            <h1 className="text-2xl font-bold text-foreground">Search Results</h1>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search Bar */}
        <div className="mb-8">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
            <Input
              type="text"
              placeholder="Search across all interviews and transcripts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-3 text-lg"
            />
          </div>

          <div className="mt-4 text-sm text-gray-600">
            Found <span className="font-semibold">{totalMatches} matches</span> for "{searchQuery}" across{" "}
            <span className="font-semibold">{mockSearchResults.length} interviews</span>
          </div>
        </div>

        {/* Search Results */}
        <div className="space-y-6">
          {mockSearchResults.map((result) => (
            <Card key={result.interviewId} className="overflow-hidden bg-card border-border">
              <div className="bg-muted px-6 py-4 border-b border-border">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-lg text-foreground">{result.interviewee}</h3>
                    <p className="text-sm text-muted-foreground">
                      Interview from {new Date(result.date).toLocaleDateString()}
                    </p>
                  </div>
                  <Badge variant="secondary">{result.matches.length} matches</Badge>
                </div>
              </div>

              <CardContent className="p-0">
                {result.matches.map((match, index) => (
                  <div key={index} className="p-6 border-b last:border-b-0 hover:bg-gray-50 cursor-pointer">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="outline" className="text-xs">
                            {match.language}
                          </Badge>
                          <div className="flex items-center text-sm text-gray-600">
                            <Clock className="h-4 w-4 mr-1" />
                            {match.timestamp}
                          </div>
                        </div>
                        <p className="text-gray-700 leading-relaxed">
                          {match.context.split(match.highlightedText).map((part, i, arr) => (
                            <span key={i}>
                              {part}
                              {i < arr.length - 1 && (
                                <mark className="bg-yellow-200 px-1 rounded">{match.highlightedText}</mark>
                              )}
                            </span>
                          ))}
                        </p>
                      </div>
                      <Button size="sm" className="ml-4">
                        <Play className="h-4 w-4 mr-2" />
                        Play from here
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
