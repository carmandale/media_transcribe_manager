import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Calendar } from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { Interview } from "@/lib/types"

interface InterviewCardProps {
  interview: Interview
}

export default function InterviewCard({ interview }: InterviewCardProps) {
  // Extract available languages from transcripts if they exist
  const languages = interview.transcripts?.map(t => t.language.toUpperCase()) || []
  
  // Format date for display
  const formattedDate = interview.metadata.date 
    ? new Date(interview.metadata.date).toLocaleDateString()
    : "Date unknown"

  return (
    <Link href={`/viewer/${interview.id}`} className="block">
      <Card className="hover:shadow-lg transition-shadow cursor-pointer bg-card border-border hover:border-primary/50">
        <div className="aspect-video relative overflow-hidden rounded-t-lg bg-muted">
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <svg className="w-16 h-16 mx-auto text-muted-foreground mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <span className="text-sm text-muted-foreground">Video Interview</span>
            </div>
          </div>
        </div>
      <CardContent className="p-4">
        <div className="space-y-3">
          <div>
            <h3 className="font-semibold text-lg text-foreground">{interview.metadata.interviewee}</h3>
            <div className="flex items-center text-sm text-muted-foreground mt-1">
              <Calendar className="h-4 w-4 mr-1" />
              {formattedDate}
            </div>
          </div>

          <p className="text-sm text-foreground line-clamp-3">
            {interview.metadata.summary || "No summary available"}
          </p>

          <div className="flex items-center justify-between">
            <div className="flex gap-1">
              {languages.map((lang) => (
                <Badge key={lang} variant="secondary" className="text-xs">
                  {lang}
                </Badge>
              ))}
            </div>
            <Button size="sm" variant="ghost" className="pointer-events-none">
              View Interview
            </Button>
          </div>
        </div>
      </CardContent>
      </Card>
    </Link>
  )
}
