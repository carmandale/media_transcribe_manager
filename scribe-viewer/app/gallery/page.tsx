import { promises as fs } from 'fs'
import path from 'path'
import { Interview } from "@/lib/types"
import InterviewCard from "@/components/InterviewCard"
import GalleryClient from "@/app/gallery/gallery-client"

async function loadManifest(): Promise<Interview[]> {
  const manifestPath = path.join(process.cwd(), 'public', 'manifest.min.json')
  
  try {
    const fileContents = await fs.readFile(manifestPath, 'utf8')
    return JSON.parse(fileContents)
  } catch (error) {
    console.error('Error loading manifest.json:', error)
    return []
  }
}

export default async function GalleryPage() {
  const interviews = await loadManifest()
  
  return <GalleryClient interviews={interviews} />
}