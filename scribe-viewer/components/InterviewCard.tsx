import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Calendar, Volume2, Play } from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { Interview } from "@/lib/types"
import { useState, useEffect } from "react"

interface InterviewCardProps {
  interview: Interview
}

interface ThumbnailState {
  thumbnailUrl: string | null;
  isLoading: boolean;
  error: string | null;
  mediaType: 'video' | 'audio' | 'unknown';
}

export default function InterviewCard({ interview }: InterviewCardProps) {
  // Extract available languages from transcripts if they exist
  const languages = interview.transcripts?.map(t => t.language.toUpperCase()) || []
  
  // Format date for display
  const formattedDate = interview.metadata.date 
    ? new Date(interview.metadata.date).toLocaleDateString()
    : "Date unknown"

  // Thumbnail state
  const [thumbnailState, setThumbnailState] = useState<ThumbnailState>({
    thumbnailUrl: interview.assets?.thumbnail || null,
    isLoading: false,
    error: null,
    mediaType: 'unknown'
  });

  // Load thumbnail on component mount
  useEffect(() => {
    const loadThumbnail = async () => {
      // If we already have a thumbnail URL, don't fetch
      if (thumbnailState.thumbnailUrl) {
        setThumbnailState(prev => ({ ...prev, mediaType: 'video' }));
        return;
      }

      setThumbnailState(prev => ({ ...prev, isLoading: true }));

      try {
        const response = await fetch(`/api/thumbnails/${interview.id}`);
        const data = await response.json();

        if (response.ok && data.success) {
          setThumbnailState({
            thumbnailUrl: data.thumbnailPath,
            isLoading: false,
            error: null,
            mediaType: data.mediaType || 'video'
          });
        } else {
          // Handle different error cases
          const mediaType = data.mediaType || 'unknown';
          setThumbnailState({
            thumbnailUrl: null,
            isLoading: false,
            error: data.error || 'Failed to load thumbnail',
            mediaType
          });
        }
      } catch (error) {
        console.error('Error loading thumbnail:', error);
        setThumbnailState({
          thumbnailUrl: null,
          isLoading: false,
          error: 'Network error',
          mediaType: 'unknown'
        });
      }
    };

    loadThumbnail();
  }, [interview.id, thumbnailState.thumbnailUrl]);

  // Render thumbnail content based on state
  const renderThumbnailContent = () => {
    if (thumbnailState.isLoading) {
      return (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-2"></div>
            <span className="text-sm text-muted-foreground">Loading...</span>
          </div>
        </div>
      );
    }

    if (thumbnailState.thumbnailUrl) {
      return (
        <div className="relative w-full h-full">
          <Image
            src={thumbnailState.thumbnailUrl}
            alt={`Thumbnail for ${interview.metadata.interviewee}`}
            fill
            className="object-cover"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            onError={() => {
              setThumbnailState(prev => ({
                ...prev,
                thumbnailUrl: null,
                error: 'Failed to load thumbnail image'
              }));
            }}
          />
          {/* Play button overlay */}
          <div className="absolute inset-0 bg-black/20 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center">
            <div className="bg-white/90 rounded-full p-3">
              <Play className="h-6 w-6 text-black fill-black" />
            </div>
          </div>
        </div>
      );
    }

    // Fallback icons based on media type
    if (thumbnailState.mediaType === 'audio') {
      return (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <Volume2 className="w-16 h-16 mx-auto text-muted-foreground mb-2" />
            <span className="text-sm text-muted-foreground">Audio Interview</span>
          </div>
        </div>
      );
    }

    // Default video icon (fallback)
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <svg className="w-16 h-16 mx-auto text-muted-foreground mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span className="text-sm text-muted-foreground">
            {thumbnailState.mediaType === 'unknown' ? 'Media Interview' : 'Video Interview'}
          </span>
        </div>
      </div>
    );
  };

  return (
    <Link href={`/viewer/${interview.id}`} className="block">
      <Card className="hover:shadow-lg transition-shadow cursor-pointer bg-card border-border hover:border-primary/50" data-testid="interview-card">
        <div className="aspect-video relative overflow-hidden rounded-t-lg bg-muted">
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
