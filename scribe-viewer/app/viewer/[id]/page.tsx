import { promises as fs } from 'fs'
import path from 'path'
import { Interview } from "@/lib/types"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { ArrowLeft } from "lucide-react"
import ViewerClient from "./viewer-client"

async function loadInterview(id: string): Promise<Interview | null> {
  const manifestPath = path.join(process.cwd(), 'public', 'manifest.json')
  
  try {
    const fileContents = await fs.readFile(manifestPath, 'utf8')
    const interviews: Interview[] = JSON.parse(fileContents)
    return interviews.find(interview => interview.id === id) || null
  } catch (error) {
    console.error('Error loading interview:', error)
    return null
  }
}

export default async function ViewerPage({ 
  params 
}: { 
  params: Promise<{ id: string }> 
}) {
  const { id } = await params
  const interview = await loadInterview(id)

  if (!interview) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-4">Interview Not Found</h1>
        <p className="mb-4">The requested interview could not be found.</p>
        <Link href="/gallery">
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Gallery
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <>
      {/* Header */}
      <header className="bg-card shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/gallery">
                <Button variant="ghost" size="sm">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Gallery
                </Button>
              </Link>
              <div>
                <h1 className="text-xl font-bold text-foreground">{interview.metadata.interviewee}</h1>
                {interview.metadata.date && (
                  <p className="text-sm text-muted-foreground">
                    Interview Date: {new Date(interview.metadata.date).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <ViewerClient interview={interview} />
      </div>
    </>
  )
} 