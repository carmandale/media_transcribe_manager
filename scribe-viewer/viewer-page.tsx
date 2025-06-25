"use client"

import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ArrowLeft, Settings, Download, Share } from "lucide-react"

const mockTranscript = {
  EN: [
    { start: 0, end: 4.5, text: "My name is Sarah Cohen, and I was born in Berlin in 1923." },
    { start: 4.5, end: 9.2, text: "I lived there with my family until we had to flee in 1938." },
    { start: 9.2, end: 14.8, text: "Those were very difficult times for Jewish families in Germany." },
    { start: 14.8, end: 20.1, text: "My father owned a small tailoring shop in the Jewish quarter." },
    { start: 20.1, end: 25.6, text: "We had many friends and neighbors who looked out for each other." },
    { start: 25.6, end: 31.2, text: "But as the political situation worsened, we knew we had to leave." },
    { start: 31.2, end: 36.8, text: "The night we left Berlin was the hardest night of my life." },
  ],
  DE: [
    { start: 0, end: 4.5, text: "Mein Name ist Sarah Cohen, und ich wurde 1923 in Berlin geboren." },
    { start: 4.5, end: 9.2, text: "Ich lebte dort mit meiner Familie, bis wir 1938 fliehen mussten." },
    { start: 9.2, end: 14.8, text: "Das waren sehr schwere Zeiten für jüdische Familien in Deutschland." },
    { start: 14.8, end: 20.1, text: "Mein Vater besaß eine kleine Schneiderei im jüdischen Viertel." },
    { start: 20.1, end: 25.6, text: "Wir hatten viele Freunde und Nachbarn, die aufeinander aufpassten." },
    {
      start: 25.6,
      end: 31.2,
      text: "Aber als sich die politische Lage verschlechterte, wussten wir, dass wir gehen mussten.",
    },
    { start: 31.2, end: 36.8, text: "Die Nacht, in der wir Berlin verließen, war die schwerste Nacht meines Lebens." },
  ],
  HE: [
    { start: 0, end: 4.5, text: "שמי שרה כהן, ונולדתי בברלין ב-1923." },
    { start: 4.5, end: 9.2, text: "גרתי שם עם משפחתי עד שנאלצנו לברוח ב-1938." },
    { start: 9.2, end: 14.8, text: "אלה היו זמנים קשים מאוד למשפחות יהודיות בגרמניה." },
    { start: 14.8, end: 20.1, text: "אבי היה בעל חנות תפירה קטנה ברובע היהודי." },
    { start: 20.1, end: 25.6, text: "היו לנו הרבה חברים ושכנים ששמרו זה על זה." },
    { start: 25.6, end: 31.2, text: "אבל כשהמצב הפוליטי החמיר, ידענו שאנחנו חייבים לעזוב." },
    { start: 31.2, end: 36.8, text: "הלילה שעזבנו את ברלין היה הלילה הקשה ביותר בחיי." },
  ],
}

export default function ViewerPage() {
  const [currentTime, setCurrentTime] = useState(12.5) // Simulated current video time
  const [selectedLanguage, setSelectedLanguage] = useState("EN")
  const [subtitleLanguage, setSubtitleLanguage] = useState("EN")
  const videoRef = useRef<HTMLVideoElement>(null)

  const currentTranscript = mockTranscript[selectedLanguage as keyof typeof mockTranscript]
  const activeSegmentIndex = currentTranscript.findIndex(
    (segment) => currentTime >= segment.start && currentTime < segment.end,
  )

  const handleTranscriptClick = (startTime: number) => {
    setCurrentTime(startTime)
    if (videoRef.current) {
      videoRef.current.currentTime = startTime
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Gallery
              </Button>
              <div>
                <h1 className="text-xl font-bold text-foreground">Sarah Cohen</h1>
                <p className="text-sm text-muted-foreground">Interview from April 12, 1995</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm">
                <Share className="h-4 w-4 mr-2" />
                Share
              </Button>
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-2" />
                Download
              </Button>
              <Button variant="outline" size="sm">
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[calc(100vh-200px)]">
          {/* Video Panel */}
          <div className="space-y-4">
            <Card className="overflow-hidden">
              <div className="aspect-video bg-black relative">
                <video
                  ref={videoRef}
                  className="w-full h-full"
                  controls
                  poster="/placeholder.svg?height=400&width=600&text=Video+Player"
                >
                  <source src="/placeholder-video.mp4" type="video/mp4" />
                  Your browser does not support the video tag.
                </video>
              </div>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Subtitles</p>
                    <Select value={subtitleLanguage} onValueChange={setSubtitleLanguage}>
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="off">Off</SelectItem>
                        <SelectItem value="EN">English</SelectItem>
                        <SelectItem value="DE">Deutsch</SelectItem>
                        <SelectItem value="HE">עברית</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="text-sm text-gray-600">Duration: 2h 34m</div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Transcript Panel */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Transcript</h2>
              <Select value={selectedLanguage} onValueChange={setSelectedLanguage}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EN">English</SelectItem>
                  <SelectItem value="DE">Deutsch</SelectItem>
                  <SelectItem value="HE">עברית</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Card className="h-full overflow-hidden">
              <CardContent className="p-0 h-full">
                <div className="h-full overflow-y-auto p-4 space-y-3">
                  {currentTranscript.map((segment, index) => (
                    <div
                      key={index}
                      className={`p-3 rounded-lg cursor-pointer transition-colors ${
                        index === activeSegmentIndex ? "bg-primary/10 border-l-4 border-primary" : "hover:bg-muted/50"
                      }`}
                      onClick={() => handleTranscriptClick(segment.start)}
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-xs text-gray-500 font-mono mt-1 min-w-[60px]">
                          {Math.floor(segment.start / 60)}:{(segment.start % 60).toFixed(1).padStart(4, "0")}
                        </span>
                        <p className={`text-sm leading-relaxed ${index === activeSegmentIndex ? "font-medium" : ""}`}>
                          {segment.text}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
