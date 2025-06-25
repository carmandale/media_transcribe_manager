"use client"

import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Search, Calendar, Filter } from "lucide-react"
import Image from "next/image"

const mockInterviews = [
  {
    id: "d6cc9262-5ba2-410c-a707-d981a7459105",
    metadata: {
      interviewee: "Sarah Cohen",
      date: "1995-04-12",
      summary: "Testimony regarding experiences during WWII in Berlin",
      duration: "2h 34m",
      languages: ["EN", "DE", "HE"],
    },
    thumbnail: "/placeholder.svg?height=200&width=300&text=Interview+Thumbnail",
  },
  {
    id: "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
    metadata: {
      interviewee: "David Müller",
      date: "1998-09-23",
      summary: "Recollections of life in East Berlin before reunification",
      duration: "1h 47m",
      languages: ["EN", "DE"],
    },
    thumbnail: "/placeholder.svg?height=200&width=300&text=Interview+Thumbnail",
  },
  {
    id: "f7e8d9c0-b1a2-3456-789a-bcdef0123456",
    metadata: {
      interviewee: "Rachel Goldstein",
      date: "2001-11-15",
      summary: "Stories of immigration and community building in New York",
      duration: "3h 12m",
      languages: ["EN", "HE"],
    },
    thumbnail: "/placeholder.svg?height=200&width=300&text=Interview+Thumbnail",
  },
  {
    id: "9876543210-abcd-efgh-ijkl-mnopqrstuvwx",
    metadata: {
      interviewee: "Hans Weber",
      date: "1997-06-08",
      summary: "Experiences as a refugee and resettlement challenges",
      duration: "2h 18m",
      languages: ["EN", "DE", "HE"],
    },
    thumbnail: "/placeholder.svg?height=200&width=300&text=Interview+Thumbnail",
  },
]

export default function GalleryPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [sortBy, setSortBy] = useState("date")

  const filteredInterviews = mockInterviews.filter(
    (interview) =>
      interview.metadata.interviewee.toLowerCase().includes(searchQuery.toLowerCase()) ||
      interview.metadata.summary.toLowerCase().includes(searchQuery.toLowerCase()),
  )

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-foreground">Scribe Archive</h1>
            <div className="text-sm text-muted-foreground">{mockInterviews.length} interviews available</div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search and Filters */}
        <div className="mb-8 space-y-4">
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

          <div className="flex items-center gap-4">
            <Button variant="outline" size="sm">
              <Filter className="h-4 w-4 mr-2" />
              Filter by Date
            </Button>
            <Button variant="outline" size="sm">
              <Filter className="h-4 w-4 mr-2" />
              Filter by Language
            </Button>
            <div className="ml-auto text-sm text-gray-600">
              Showing {filteredInterviews.length} of {mockInterviews.length} interviews
            </div>
          </div>
        </div>

        {/* Interview Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredInterviews.map((interview) => (
            <Card key={interview.id} className="hover:shadow-lg transition-shadow cursor-pointer bg-card border-border">
              <div className="aspect-video relative overflow-hidden rounded-t-lg">
                <Image
                  src={interview.thumbnail || "/placeholder.svg"}
                  alt={`Interview with ${interview.metadata.interviewee}`}
                  fill
                  className="object-cover"
                />
                <div className="absolute bottom-2 right-2 bg-black bg-opacity-75 text-white px-2 py-1 rounded text-sm">
                  {interview.metadata.duration}
                </div>
              </div>
              <CardContent className="p-4">
                <div className="space-y-3">
                  <div>
                    <h3 className="font-semibold text-lg text-foreground">{interview.metadata.interviewee}</h3>
                    <div className="flex items-center text-sm text-muted-foreground mt-1">
                      <Calendar className="h-4 w-4 mr-1" />
                      {new Date(interview.metadata.date).toLocaleDateString()}
                    </div>
                  </div>

                  <p className="text-sm text-foreground line-clamp-3">{interview.metadata.summary}</p>

                  <div className="flex items-center justify-between">
                    <div className="flex gap-1">
                      {interview.metadata.languages.map((lang) => (
                        <Badge key={lang} variant="secondary" className="text-xs">
                          {lang}
                        </Badge>
                      ))}
                    </div>
                    <Button size="sm">View Interview</Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
