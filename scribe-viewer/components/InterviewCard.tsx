import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Calendar, Volume2, Play } from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { Interview } from "@/lib/types"
import { useState } from "react"

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

  // State for handling image load errors
  const [imageError, setImageError] = useState(false);

  // Determine if this is an audio-only interview by checking file extension
  const videoPath = interview.assets?.video || '';
  const isAudioOnly = videoPath && 
    (videoPath.toLowerCase().endsWith('.mp3') || 
     videoPath.toLowerCase().endsWith('.wav') ||
     videoPath.toLowerCase().endsWith('.m4a'));


  // Render thumbnail content
  const renderThumbnailContent = () => {
    // Audio-only interviews show the audio icon
    if (isAudioOnly) {
      return (
        <div className="relative w-full h-full">
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100 dark:bg-gray-800">
            <div className="text-center">
              <Volume2 className="w-16 h-16 mx-auto text-gray-400 dark:text-gray-500 mb-2" />
              <span className="text-sm font-medium text-gray-500 dark:text-gray-400">Audio Interview</span>
            </div>
          </div>
        </div>
      );
    }

    // Video interviews show thumbnail or fallback
    if (!imageError && interview.assets?.video) {
      return (
        <div className="relative w-full h-full">
          <Image
            src={`/thumbnails/${interview.id}.jpg`}
            alt={`Thumbnail for ${interview.metadata.interviewee}`}
            width={320}
            height={240}
            className="object-cover w-full h-full"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            loading="lazy"
            onError={() => setImageError(true)}
          />
          {/* Play button overlay */}
          <div className="absolute inset-0 bg-black/0 hover:bg-black/30 transition-colors flex items-center justify-center opacity-0 hover:opacity-100">
            <Play className="w-12 h-12 text-white drop-shadow-lg" />
          </div>
        </div>
      );
    }

    // Fallback for video with no thumbnail
    return (
      <div className="relative w-full h-full">
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 dark:bg-gray-800">
          <div className="text-center">
            <svg className="w-16 h-16 mx-auto text-gray-400 dark:text-gray-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400">Video Interview</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <Link href={`/viewer/${interview.id}`} className="block">
      <Card className="hover:shadow-lg transition-shadow cursor-pointer bg-card border-border hover:border-primary/50" data-testid="interview-card">
        <div className="aspect-[4/3] relative overflow-hidden rounded-t-lg bg-muted">
          {renderThumbnailContent()}
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