"use client"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Play, Pause, Volume2, Maximize, Subtitles } from "lucide-react"

interface VideoPlayerProps {
  src: string
  subtitles: { [key: string]: string }
  onTimeUpdate?: (time: number) => void
  selectedLanguage: string
}

export default function VideoPlayer({ src, subtitles, onTimeUpdate, selectedLanguage }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime)
      onTimeUpdate?.(video.currentTime)
    }

    const handleLoadedMetadata = () => {
      setDuration(video.duration)
      
      // Set initial subtitle state
      const tracks = Array.from(video.textTracks)
      tracks.forEach(track => {
        if (track.language === selectedLanguage) {
          track.mode = subtitlesEnabled ? 'showing' : 'hidden'
        } else {
          track.mode = 'hidden'
        }
      })
    }

    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('loadedmetadata', handleLoadedMetadata)
    video.addEventListener('play', () => setIsPlaying(true))
    video.addEventListener('pause', () => setIsPlaying(false))

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('loadedmetadata', handleLoadedMetadata)
      video.removeEventListener('play', () => setIsPlaying(true))
      video.removeEventListener('pause', () => setIsPlaying(false))
    }
  }, [onTimeUpdate, selectedLanguage, subtitlesEnabled])

  // Update subtitles when language or enabled state changes
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const tracks = Array.from(video.textTracks)
    tracks.forEach(track => {
      if (track.language === selectedLanguage) {
        track.mode = subtitlesEnabled ? 'showing' : 'hidden'
      } else {
        track.mode = 'hidden'
      }
    })
  }, [selectedLanguage, subtitlesEnabled])

  const togglePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause()
      } else {
        videoRef.current.play()
      }
    }
  }

  const handleSeek = (value: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = value
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

  return (
    <>
      <style jsx>{`
        video::cue {
          background-color: rgba(0, 0, 0, 0.8);
          color: white;
          font-size: 18px;
          line-height: 1.4;
          padding: 4px 8px;
        }
      `}</style>
      <div className="relative bg-black aspect-video">
        <video
          ref={videoRef}
          className="w-full h-full"
          src={src}
          crossOrigin="anonymous"
        >
          {Object.entries(subtitles).map(([lang, url]) => (
            <track
              key={lang}
              kind="subtitles"
              src={url}
              srcLang={lang}
              label={lang.toUpperCase()}
            />
          ))}
        </video>
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
    </>
  )
}