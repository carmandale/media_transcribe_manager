"use client"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Play, Pause, Volume2, Maximize, Subtitles } from "lucide-react"
import { Interview } from "@/lib/types"
import { useCallback } from "react"

interface ViewerClientProps {
  interview: Interview
}

export default function ViewerClient({ interview }: ViewerClientProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const transcriptRefs = useRef<(HTMLDivElement | null)[]>([])
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [selectedLanguage, setSelectedLanguage] = useState("en")
  const [activeCueIndex, setActiveCueIndex] = useState(0)
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true)
  const [currentSubtitle, setCurrentSubtitle] = useState<string>("")  // For custom subtitle display
  const [videoError, setVideoError] = useState<string | null>(null)

  // Get available languages
  const availableLanguages = interview.transcripts?.map(t => t.language) || []
  const availableSubtitles = interview.assets?.subtitles || {}

  // Get current transcript
  // TEMPORARY: For English, we'll parse the orig.srt file instead
  const currentTranscript = interview.transcripts?.find(t => t.language === selectedLanguage)

  // Use original video path from assets
  const videoSrc = interview.assets.video

  // Handle video error
  const handleVideoError = () => {
    const filename = interview.assets.video.split('/').pop() || ''
    if (filename.includes('%') || filename.includes('&')) {
      setVideoError('This video has special characters in its filename that prevent it from loading. Please contact support.')
    } else {
      setVideoError('Unable to load video. Please try again later.')
    }
  }

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const updateTime = () => {
      setCurrentTime(video.currentTime)
      
      // Update active cue and current subtitle
      if (currentTranscript?.cues) {
        const activeIndex = currentTranscript.cues.findIndex((cue, index) => {
          const nextCue = currentTranscript.cues[index + 1]
          return video.currentTime >= cue.time && (!nextCue || video.currentTime < nextCue.time)
        })
        if (activeIndex !== -1) {
          if (activeIndex !== activeCueIndex) {
            setActiveCueIndex(activeIndex)
          }
          // Update current subtitle for display
          if (subtitlesEnabled) {
            setCurrentSubtitle(currentTranscript.cues[activeIndex].text)
          }
        } else {
          setCurrentSubtitle("")  // Clear subtitle when no active cue
        }
      }
    }

    const updateDuration = () => setDuration(video.duration)

    video.addEventListener('timeupdate', updateTime)
    video.addEventListener('loadedmetadata', updateDuration)
    video.addEventListener('play', () => setIsPlaying(true))
    video.addEventListener('pause', () => setIsPlaying(false))

    return () => {
      video.removeEventListener('timeupdate', updateTime)
      video.removeEventListener('loadedmetadata', updateDuration)
      video.removeEventListener('play', () => setIsPlaying(true))
      video.removeEventListener('pause', () => setIsPlaying(false))
    }
  }, [currentTranscript, activeCueIndex, subtitlesEnabled])

  // Auto-scroll transcript to keep active cue in view
  useEffect(() => {
    if (transcriptRefs.current[activeCueIndex] && scrollAreaRef.current) {
      const activeElement = transcriptRefs.current[activeCueIndex]
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
      
      if (activeElement && scrollContainer) {
        const elementTop = activeElement.offsetTop
        const elementHeight = activeElement.offsetHeight
        const containerHeight = scrollContainer.clientHeight
        const scrollTop = scrollContainer.scrollTop
        
        // Check if element is out of view
        if (elementTop < scrollTop || elementTop + elementHeight > scrollTop + containerHeight) {
          // Scroll to center the active element
          scrollContainer.scrollTo({
            top: elementTop - containerHeight / 2 + elementHeight / 2,
            behavior: 'smooth'
          })
        }
      }
    }
  }, [activeCueIndex])

  // Clear subtitle when disabled
  useEffect(() => {
    if (!subtitlesEnabled) {
      setCurrentSubtitle("")
    }
  }, [subtitlesEnabled])

  const togglePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause()
      } else {
        videoRef.current.play()
      }
    }
  }

  const handleSeek = (time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time
    }
  }

  const handleVolumeChange = (value: number) => {
    setVolume(value)
    if (videoRef.current) {
      videoRef.current.volume = value
    }
  }

  const toggleFullscreen = () => {
    if (videoRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen()
      } else {
        videoRef.current.requestFullscreen()
      }
    }
  }

  const formatTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = Math.floor(seconds % 60)
    return h > 0 ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}` : `${m}:${s.toString().padStart(2, '0')}`
  }

  if (!interview.assets?.video) {
    return (
      <div className="text-center p-8">
        <p className="text-muted-foreground">No video available for this interview</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Video Player Section */}
      <div className="lg:col-span-2 space-y-4">
        <Card className="overflow-hidden">
          <div className="relative bg-black aspect-video">
            {videoError ? (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-900 text-white">
                <div className="text-center p-8">
                  <p className="text-xl mb-4">⚠️ Video Loading Error</p>
                  <p className="text-sm text-gray-300 max-w-md">{videoError}</p>
                </div>
              </div>
            ) : (
              <>
                <video
                  ref={videoRef}
                  className="w-full h-full"
                  src={videoSrc}
                  crossOrigin="anonymous"
                  onError={handleVideoError}
                />
                
                {/* Custom subtitle overlay */}
                {subtitlesEnabled && currentSubtitle && (
                  <div className="absolute bottom-16 left-0 right-0 flex justify-center px-4 pointer-events-none">
                    <div className="bg-black/80 text-white px-4 py-2 rounded max-w-[80%] text-center">
                      <p className="text-lg leading-relaxed">{currentSubtitle}</p>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Video Controls */}
          <div className="p-4 space-y-3 bg-card">
            {/* Progress Bar */}
            <div className="space-y-1">
              <input
                type="range"
                min={0}
                max={duration || 100}
                value={currentTime}
                onChange={(e) => handleSeek(Number(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{formatTime(currentTime)}</span>
                <span>{formatTime(duration)}</span>
              </div>
            </div>

            {/* Control Buttons */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={togglePlayPause}
                >
                  {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </Button>
                
                <div className="flex items-center gap-2">
                  <Volume2 className="h-4 w-4" />
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.1}
                    value={volume}
                    onChange={(e) => handleVolumeChange(Number(e.target.value))}
                    className="w-20 h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant={subtitlesEnabled ? "default" : "ghost"}
                  onClick={() => setSubtitlesEnabled(!subtitlesEnabled)}
                  title="Toggle subtitles"
                >
                  <Subtitles className="h-4 w-4" />
                </Button>
                
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={toggleFullscreen}
                >
                  <Maximize className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Transcript Section */}
      <div className="space-y-4">
        <Card className="h-[600px] flex flex-col">
          <div className="p-4 border-b">
            <h3 className="font-semibold mb-2">Transcript</h3>
            {availableLanguages.length > 1 && (
              <Tabs value={selectedLanguage} onValueChange={setSelectedLanguage}>
                <TabsList className="grid w-full" style={{ gridTemplateColumns: `repeat(${availableLanguages.length}, 1fr)` }}>
                  {availableLanguages.map((lang) => (
                    <TabsTrigger key={lang} value={lang}>
                      {lang.toUpperCase()}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            )}
          </div>

          <ScrollArea className="flex-1 p-4" ref={scrollAreaRef}>
            {currentTranscript ? (
              <div className="space-y-4">
                {currentTranscript.cues.map((cue, index) => (
                  <div
                    key={index}
                    ref={el => transcriptRefs.current[index] = el}
                    className={`p-2 rounded cursor-pointer transition-colors ${
                      index === activeCueIndex 
                        ? 'bg-primary/20 border-l-4 border-primary' 
                        : 'hover:bg-muted'
                    }`}
                    onClick={() => handleSeek(cue.time)}
                  >
                    <div className="text-xs text-muted-foreground mb-1">
                      {formatTime(cue.time)}
                    </div>
                    <div className="text-sm">{cue.text}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-center">
                No transcript available for this language
              </p>
            )}
          </ScrollArea>
        </Card>
      </div>
    </div>
  )
}