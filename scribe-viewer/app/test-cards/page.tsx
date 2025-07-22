import InterviewCard from "@/components/InterviewCard"
import { Interview } from "@/lib/types"

export default function TestCardsPage() {
  // Mock data for testing
  const videoInterview: Interview = {
    id: "test-video",
    metadata: {
      interviewee: "Video Interview Test",
      interviewer: "Test",
      date: "2024-01-01",
      location: "Test Location",
      summary: "This is a test video interview to check card sizing",
      tags: []
    },
    assets: {
      video: "/media/sample_video.mp4"
    },
    transcripts: [{ language: "en" }] as any
  }

  const audioInterview: Interview = {
    id: "test-audio",
    metadata: {
      interviewee: "Audio Interview Test",
      interviewer: "Test",
      date: "2024-01-01",
      location: "Test Location",
      summary: "This is a test audio interview to check card sizing",
      tags: []
    },
    assets: {
      video: "/media/sample_audio.mp3"
    },
    transcripts: [{ language: "en" }] as any
  }

  const noThumbnailVideo: Interview = {
    id: "test-no-thumb",
    metadata: {
      interviewee: "No Thumbnail Video Test",
      interviewer: "Test",
      date: "2024-01-01",
      location: "Test Location",
      summary: "This is a test video with no thumbnail to check fallback",
      tags: []
    },
    assets: {
      video: "/media/missing_video.mp4"
    },
    transcripts: [{ language: "en" }] as any
  }

  return (
    <div className="container mx-auto p-8">
      <h1 className="text-2xl font-bold mb-8">Card Size Test Page</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="border-2 border-red-500 p-1">
          <h2 className="text-red-500 mb-2">Video with Thumbnail</h2>
          <InterviewCard interview={videoInterview} />
        </div>
        
        <div className="border-2 border-blue-500 p-1">
          <h2 className="text-blue-500 mb-2">Audio Interview</h2>
          <InterviewCard interview={audioInterview} />
        </div>
        
        <div className="border-2 border-green-500 p-1">
          <h2 className="text-green-500 mb-2">Video Fallback</h2>
          <InterviewCard interview={noThumbnailVideo} />
        </div>
      </div>
      
      <div className="mt-8 p-4 bg-gray-100 rounded">
        <h2 className="font-bold mb-2">Expected behavior:</h2>
        <ul className="list-disc ml-6">
          <li>All three cards should have identical height and width</li>
          <li>The aspect-[4/3] container should be the same size for all</li>
          <li>Icons and text should be centered within their containers</li>
        </ul>
      </div>
    </div>
  )
}