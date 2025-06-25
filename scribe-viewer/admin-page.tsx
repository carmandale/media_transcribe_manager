"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Save, Edit, ArrowLeft, CheckCircle, AlertCircle } from "lucide-react"

const mockInterviews = [
  {
    id: "d6cc9262-5ba2-410c-a707-d981a7459105",
    metadata: {
      interviewee: "Sarah Cohen",
      date: "1995-04-12",
      summary: "Testimony regarding experiences during WWII in Berlin",
      duration: "2h 34m",
      languages: ["EN", "DE", "HE"],
      status: "complete",
    },
  },
  {
    id: "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
    metadata: {
      interviewee: "David Müller",
      date: "1998-09-23",
      summary: "Recollections of life in East Berlin before reunification",
      duration: "1h 47m",
      languages: ["EN", "DE"],
      status: "needs_review",
    },
  },
  {
    id: "f7e8d9c0-b1a2-3456-789a-bcdef0123456",
    metadata: {
      interviewee: "Rachel Goldstein",
      date: "2001-11-15",
      summary: "",
      duration: "3h 12m",
      languages: ["EN", "HE"],
      status: "incomplete",
    },
  },
]

export default function AdminPage() {
  const [selectedInterview, setSelectedInterview] = useState<string | null>(null)
  const [editingData, setEditingData] = useState<any>(null)
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle")

  const handleEdit = (interview: any) => {
    setSelectedInterview(interview.id)
    setEditingData({ ...interview.metadata })
  }

  const handleSave = async () => {
    setSaveStatus("saving")
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000))
    setSaveStatus("saved")
    setTimeout(() => {
      setSaveStatus("idle")
      setSelectedInterview(null)
      setEditingData(null)
    }, 2000)
  }

  const handleCancel = () => {
    setSelectedInterview(null)
    setEditingData(null)
    setSaveStatus("idle")
  }

  if (selectedInterview && editingData) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm border-b">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button variant="ghost" size="sm" onClick={handleCancel}>
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back to List
                </Button>
                <h1 className="text-2xl font-bold text-gray-900">Edit Interview Metadata</h1>
              </div>
              {saveStatus === "saved" && (
                <div className="flex items-center text-green-600">
                  <CheckCircle className="h-5 w-5 mr-2" />
                  Saved successfully
                </div>
              )}
            </div>
          </div>
        </header>

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Card>
            <CardHeader>
              <CardTitle>Interview Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label htmlFor="interviewee">Interviewee Name</Label>
                  <Input
                    id="interviewee"
                    value={editingData.interviewee}
                    onChange={(e) => setEditingData({ ...editingData, interviewee: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="date">Interview Date</Label>
                  <Input
                    id="date"
                    type="date"
                    value={editingData.date}
                    onChange={(e) => setEditingData({ ...editingData, date: e.target.value })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="summary">Summary</Label>
                <Textarea
                  id="summary"
                  rows={4}
                  value={editingData.summary}
                  onChange={(e) => setEditingData({ ...editingData, summary: e.target.value })}
                  placeholder="Brief description of the interview content..."
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label>Duration</Label>
                  <Input value={editingData.duration} disabled className="bg-gray-50" />
                  <p className="text-xs text-gray-500">Duration is automatically calculated from video file</p>
                </div>

                <div className="space-y-2">
                  <Label>Available Languages</Label>
                  <div className="flex gap-2">
                    {editingData.languages.map((lang: string) => (
                      <Badge key={lang} variant="secondary">
                        {lang}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500">Languages are detected from transcript files</p>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-6 border-t">
                <Button variant="outline" onClick={handleCancel}>
                  Cancel
                </Button>
                <Button onClick={handleSave} disabled={saveStatus === "saving"}>
                  {saveStatus === "saving" ? (
                    <>Saving...</>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Changes
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-card shadow-sm border-b border-border">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-foreground">Admin Dashboard</h1>
            <div className="text-sm text-muted-foreground">{mockInterviews.length} interviews in archive</div>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-foreground mb-2">Interview Metadata Management</h2>
          <p className="text-muted-foreground">
            Review and edit interview metadata to improve searchability and accuracy.
          </p>
        </div>

        <div className="space-y-4">
          {mockInterviews.map((interview) => (
            <Card key={interview.id}>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-semibold text-lg">{interview.metadata.interviewee}</h3>
                      <Badge
                        variant={
                          interview.metadata.status === "complete"
                            ? "default"
                            : interview.metadata.status === "needs_review"
                              ? "secondary"
                              : "destructive"
                        }
                      >
                        {interview.metadata.status === "complete" && <CheckCircle className="h-3 w-3 mr-1" />}
                        {interview.metadata.status === "incomplete" && <AlertCircle className="h-3 w-3 mr-1" />}
                        {interview.metadata.status.replace("_", " ")}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-600">
                      <div>
                        <span className="font-medium">Date:</span>{" "}
                        {new Date(interview.metadata.date).toLocaleDateString()}
                      </div>
                      <div>
                        <span className="font-medium">Duration:</span> {interview.metadata.duration}
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="font-medium">Languages:</span>
                        {interview.metadata.languages.map((lang) => (
                          <Badge key={lang} variant="outline" className="text-xs">
                            {lang}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <p className="text-sm text-gray-700 mt-2">
                      {interview.metadata.summary || <em className="text-gray-400">No summary provided</em>}
                    </p>
                  </div>

                  <Button onClick={() => handleEdit(interview)} className="ml-4">
                    <Edit className="h-4 w-4 mr-2" />
                    Edit
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
